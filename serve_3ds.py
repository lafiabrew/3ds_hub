#!/usr/bin/env python3
"""
Universal 3DS Homebrew FBI QR & Network Server (serve_3ds.py)

Automatically discovers all .cia, .3dsx, and .smdh artifacts across every project in
the workspace (or a specified directory), parses SMDH title/author metadata,
prints a scannable terminal QR code for FBI (Remote Install -> Scan QR Code), and hosts a
multi-game web dashboard with SVG QR codes and one-click FBI network push (port 5000).
"""

from __future__ import annotations

import argparse
import base64
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
import socket
import struct
import sys
import time
import urllib.parse
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Pure-Python ISO/IEC 18004 QR Code Encoder (Byte Mode, ECC Level L, V1..V8)
# ---------------------------------------------------------------------------

_VERSION_TABLE = {
    1: (26, 7, 1, []),
    2: (44, 10, 1, [6, 18]),
    3: (70, 15, 1, [6, 22]),
    4: (100, 20, 1, [6, 26]),
    5: (134, 26, 1, [6, 30]),
    6: (172, 18, 2, [6, 34]),
    7: (196, 20, 2, [6, 22, 38]),
    8: (242, 24, 2, [6, 24, 42]),
}

_GF_EXP = [0] * 512
_GF_LOG = [0] * 256


def _init_gf() -> None:
    x = 1
    for i in range(255):
        _GF_EXP[i] = x
        _GF_LOG[x] = i
        x <<= 1
        if x & 0x100:
            x ^= 0x11D
    for i in range(255, 512):
        _GF_EXP[i] = _GF_EXP[i - 255]


_init_gf()


def _gf_mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return _GF_EXP[_GF_LOG[a] + _GF_LOG[b]]


def _rs_generator_poly(degree: int) -> List[int]:
    poly = [1]
    for i in range(degree):
        next_poly = [0] * (len(poly) + 1)
        factor = _GF_EXP[i]
        for j, coeff in enumerate(poly):
            next_poly[j] ^= coeff
            next_poly[j + 1] ^= _gf_mul(coeff, factor)
        poly = next_poly
    return poly


def _rs_encode(data: List[int], ec_len: int) -> List[int]:
    gen = _rs_generator_poly(ec_len)
    rem = [0] * ec_len
    for b in data:
        factor = b ^ rem[0]
        rem = rem[1:] + [0]
        if factor != 0:
            for i in range(ec_len):
                rem[i] ^= _gf_mul(gen[i + 1], factor)
    return rem


def _choose_version(payload_len: int) -> int:
    for ver, (total_cw, ec_cw, blocks, _) in _VERSION_TABLE.items():
        data_cw = total_cw - ec_cw * blocks
        if payload_len + 2 <= data_cw:
            return ver
    raise ValueError(f"URL too long for QR V1..V8 ({payload_len} bytes)")


def _encode_data_codewords(payload: bytes, version: int) -> List[int]:
    total_cw, ec_cw, blocks, _ = _VERSION_TABLE[version]
    data_cw = total_cw - ec_cw * blocks

    bits: List[int] = []

    def append_bits(val: int, length: int) -> None:
        for i in range(length - 1, -1, -1):
            bits.append((val >> i) & 1)

    append_bits(0b0100, 4)
    append_bits(len(payload), 8)
    for b in payload:
        append_bits(b, 8)

    rem_bits = data_cw * 8 - len(bits)
    append_bits(0, min(4, max(0, rem_bits)))
    while len(bits) % 8 != 0:
        bits.append(0)

    codewords = []
    for i in range(0, len(bits), 8):
        byte = 0
        for bit in bits[i : i + 8]:
            byte = (byte << 1) | bit
        codewords.append(byte)

    pad_bytes = [0xEC, 0x11]
    idx = 0
    while len(codewords) < data_cw:
        codewords.append(pad_bytes[idx % 2])
        idx += 1

    if blocks == 1:
        return codewords + _rs_encode(codewords, ec_cw)

    block_size = data_cw // blocks
    data_blocks = [
        codewords[i * block_size : (i + 1) * block_size] for i in range(blocks)
    ]
    ec_blocks = [_rs_encode(db, ec_cw) for db in data_blocks]
    interleaved: List[int] = []
    for col in range(block_size):
        for b in range(blocks):
            interleaved.append(data_blocks[b][col])
    for col in range(ec_cw):
        for b in range(blocks):
            interleaved.append(ec_blocks[b][col])
    return interleaved


def _format_bits(mask: int) -> int:
    data = (0b01 << 3) | (mask & 0b111)
    rem = data << 10
    for i in range(14, 9, -1):
        if (rem >> i) & 1:
            rem ^= 0x537 << (i - 10)
    return ((data << 10) | rem) ^ 0x5412


def _version_bits(version: int) -> int:
    rem = version << 12
    for i in range(17, 11, -1):
        if (rem >> i) & 1:
            rem ^= 0x1F25 << (i - 12)
    return (version << 12) | rem


def _mask_bit(mask: int, r: int, c: int) -> bool:
    if mask == 0:
        return (r + c) % 2 == 0
    if mask == 1:
        return r % 2 == 0
    if mask == 2:
        return c % 3 == 0
    if mask == 3:
        return (r + c) % 3 == 0
    if mask == 4:
        return (r // 2 + c // 3) % 2 == 0
    if mask == 5:
        return ((r * c) % 2) + ((r * c) % 3) == 0
    if mask == 6:
        return (((r * c) % 2) + ((r * c) % 3)) % 2 == 0
    if mask == 7:
        return (((r + c) % 2) + ((r * c) % 3)) % 2 == 0
    raise ValueError(f"Invalid QR mask: {mask}")


def _penalty_score(grid: List[List[bool]]) -> int:
    size = len(grid)
    score = 0

    # N1: 5+ consecutive modules of same color in row or col
    for r in range(size):
        run_color = grid[r][0]
        run_len = 1
        for c in range(1, size):
            if grid[r][c] == run_color:
                run_len += 1
            else:
                if run_len >= 5:
                    score += 3 + (run_len - 5)
                run_color = grid[r][c]
                run_len = 1
        if run_len >= 5:
            score += 3 + (run_len - 5)

    for c in range(size):
        run_color = grid[0][c]
        run_len = 1
        for r in range(1, size):
            if grid[r][c] == run_color:
                run_len += 1
            else:
                if run_len >= 5:
                    score += 3 + (run_len - 5)
                run_color = grid[r][c]
                run_len = 1
        if run_len >= 5:
            score += 3 + (run_len - 5)

    # N2: 2x2 blocks of same color
    for r in range(size - 1):
        for c in range(size - 1):
            val = grid[r][c]
            if grid[r][c + 1] == val and grid[r + 1][c] == val and grid[r + 1][c + 1] == val:
                score += 3

    # N3: 1:1:3:1:1 finder-like patterns with 4 light modules on either side
    pat1 = [True, False, True, True, True, False, True, False, False, False, False]
    pat2 = [False, False, False, False, True, False, True, True, True, False, True]
    for r in range(size):
        row = grid[r]
        for c in range(size - 10):
            window = row[c : c + 11]
            if window == pat1 or window == pat2:
                score += 40
    for c in range(size):
        col = [grid[r][c] for r in range(size)]
        for r in range(size - 10):
            window = col[r : r + 11]
            if window == pat1 or window == pat2:
                score += 40

    # N4: dark/light module balance
    dark = sum(1 for r in range(size) for c in range(size) if grid[r][c])
    total = size * size
    k = int(abs(dark * 100.0 / total - 50.0) // 5)
    score += k * 10
    return score


def _write_format_bits(grid: List[List[bool]], size: int, mask: int) -> None:
    fmt = _format_bits(mask)
    for k in range(6):
        grid[k][8] = bool((fmt >> k) & 1)
    grid[7][8] = bool((fmt >> 6) & 1)
    grid[8][8] = bool((fmt >> 7) & 1)
    grid[8][7] = bool((fmt >> 8) & 1)
    for k in range(9, 15):
        grid[8][14 - k] = bool((fmt >> k) & 1)

    # Second copy: bits 0..7 on top-right row 8; bits 8..14 on bottom-left col 8
    for k in range(8):
        grid[8][size - 1 - k] = bool((fmt >> k) & 1)
    for k in range(8, 15):
        grid[size - 15 + k][8] = bool((fmt >> k) & 1)


def encode_qr_matrix(text: str) -> List[List[bool]]:
    payload = text.encode("utf-8")
    ver = _choose_version(len(payload))
    size = 17 + 4 * ver
    codewords = _encode_data_codewords(payload, ver)

    grid: List[List[bool]] = [[False] * size for _ in range(size)]
    is_func: List[List[bool]] = [[False] * size for _ in range(size)]

    def set_func(r: int, c: int, val: bool) -> None:
        if 0 <= r < size and 0 <= c < size:
            grid[r][c] = val
            is_func[r][c] = True

    def place_finder(top: int, left: int) -> None:
        for dr in range(-1, 8):
            for dc in range(-1, 8):
                r, c = top + dr, left + dc
                if 0 <= r < size and 0 <= c < size:
                    in_outer = 0 <= dr <= 6 and 0 <= dc <= 6
                    on_ring = dr in (0, 6) or dc in (0, 6)
                    in_core = 2 <= dr <= 4 and 2 <= dc <= 4
                    set_func(r, c, in_outer and (on_ring or in_core))

    place_finder(0, 0)
    place_finder(0, size - 7)
    place_finder(size - 7, 0)

    for i in range(8, size - 8):
        set_func(6, i, i % 2 == 0)
        set_func(i, 6, i % 2 == 0)

    centers = _VERSION_TABLE[ver][3]
    for r in centers:
        for c in centers:
            if (r == 6 and c == 6) or (r == 6 and c == size - 7) or (r == size - 7 and c == 6):
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    set_func(r + dr, c + dc, max(abs(dr), abs(dc)) in (0, 2))

    if ver >= 7:
        vbits = _version_bits(ver)
        for i in range(18):
            bit = bool((vbits >> i) & 1)
            r, c = i // 3, size - 11 + (i % 3)
            set_func(r, c, bit)
            set_func(c, r, bit)

    for i in range(9):
        if i != 6:
            if not is_func[8][i]:
                set_func(8, i, False)
            if not is_func[i][8]:
                set_func(i, 8, False)
    for i in range(8):
        if not is_func[8][size - 1 - i]:
            set_func(8, size - 1 - i, False)
        if not is_func[size - 1 - i][8]:
            set_func(size - 1 - i, 8, False)
    set_func(size - 8, 8, True)

    bit_stream: List[int] = []
    for cw in codewords:
        for shift in range(7, -1, -1):
            bit_stream.append((cw >> shift) & 1)

    bit_idx = 0
    col = size - 1
    upward = True
    while col > 0:
        if col == 6:
            col -= 1
        rows = range(size - 1, -1, -1) if upward else range(size)
        for r in rows:
            for dc in (0, -1):
                c = col + dc
                if not is_func[r][c]:
                    val = bool(bit_stream[bit_idx]) if bit_idx < len(bit_stream) else False
                    grid[r][c] = val
                    bit_idx += 1
        upward = not upward
        col -= 2

    best_grid: Optional[List[List[bool]]] = None
    best_score: Optional[int] = None
    for mask in range(8):
        cand = [row[:] for row in grid]
        for r in range(size):
            for c in range(size):
                if not is_func[r][c] and _mask_bit(mask, r, c):
                    cand[r][c] = not cand[r][c]
        _write_format_bits(cand, size, mask)
        score = _penalty_score(cand)
        if best_score is None or score < best_score:
            best_score = score
            best_grid = cand

    assert best_grid is not None
    return best_grid


def decode_qr_matrix_for_test(matrix: List[List[bool]]) -> Tuple[int, int, bytes]:
    """Independent QR matrix verifier for --self-test: checks both format copies and decodes payload."""
    size = len(matrix)
    ver = (size - 17) // 4

    # Read Copy 1 format bits (0..14)
    fmt1 = 0
    for k in range(6):
        if matrix[k][8]:
            fmt1 |= 1 << k
    if matrix[7][8]:
        fmt1 |= 1 << 6
    if matrix[8][8]:
        fmt1 |= 1 << 7
    if matrix[8][7]:
        fmt1 |= 1 << 8
    for k in range(9, 15):
        if matrix[8][14 - k]:
            fmt1 |= 1 << k

    # Read Copy 2 format bits (0..14)
    fmt2 = 0
    for k in range(8):
        if matrix[8][size - 1 - k]:
            fmt2 |= 1 << k
    for k in range(8, 15):
        if matrix[size - 15 + k][8]:
            fmt2 |= 1 << k

    assert fmt1 == fmt2, f"Format copy mismatch: fmt1={bin(fmt1)} fmt2={bin(fmt2)}"
    mask = ((fmt1 ^ 0x5412) >> 10) & 0b111

    # Build function-module mask to extract data bits
    is_func = [[False] * size for _ in range(size)]
    for top, left in ((0, 0), (0, size - 7), (size - 7, 0)):
        for dr in range(-1, 8):
            for dc in range(-1, 8):
                r, c = top + dr, left + dc
                if 0 <= r < size and 0 <= c < size:
                    is_func[r][c] = True
    for i in range(8, size - 8):
        is_func[6][i] = True
        is_func[i][6] = True
    for r in _VERSION_TABLE[ver][3]:
        for c in _VERSION_TABLE[ver][3]:
            if (r == 6 and c == 6) or (r == 6 and c == size - 7) or (r == size - 7 and c == 6):
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    is_func[r + dr][c + dc] = True
    if ver >= 7:
        for i in range(18):
            r, c = i // 3, size - 11 + (i % 3)
            is_func[r][c] = True
            is_func[c][r] = True
    for i in range(9):
        is_func[8][i] = True
        is_func[i][8] = True
    for i in range(8):
        is_func[8][size - 1 - i] = True
        is_func[size - 1 - i][8] = True

    bits: List[int] = []
    col = size - 1
    upward = True
    while col > 0:
        if col == 6:
            col -= 1
        rows = range(size - 1, -1, -1) if upward else range(size)
        for r in rows:
            for dc in (0, -1):
                c = col + dc
                if not is_func[r][c]:
                    val = matrix[r][c] ^ _mask_bit(mask, r, c)
                    bits.append(1 if val else 0)
        upward = not upward
        col -= 2

    codewords = [
        int("".join(str(b) for b in bits[i : i + 8]), 2)
        for i in range(0, len(bits) - 7, 8)
    ]
    total_cw, ec_cw, blocks, _ = _VERSION_TABLE[ver]
    data_cw = total_cw - ec_cw * blocks
    if blocks == 1:
        data_bytes = codewords[:data_cw]
        assert codewords[data_cw:total_cw] == _rs_encode(data_bytes, ec_cw)
    else:
        block_size = data_cw // blocks
        data_blocks = [[0] * block_size for _ in range(blocks)]
        idx = 0
        for col_i in range(block_size):
            for b in range(blocks):
                data_blocks[b][col_i] = codewords[idx]
                idx += 1
        for col_i in range(ec_cw):
            for b in range(blocks):
                idx += 1
        data_bytes = [x for db in data_blocks for x in db]

    data_bits = [((cw >> s) & 1) for cw in data_bytes for s in range(7, -1, -1)]
    mode = int("".join(str(b) for b in data_bits[:4]), 2)
    assert mode == 0b0100
    length = int("".join(str(b) for b in data_bits[4:12]), 2)
    out = bytearray()
    for i in range(length):
        bval = int("".join(str(b) for b in data_bits[12 + i * 8 : 20 + i * 8]), 2)
        out.append(bval)
    return fmt1, fmt2, bytes(out)


def render_qr_ascii(matrix: List[List[bool]], border: int = 4, use_ansi: bool = True) -> str:
    n = len(matrix)
    padded_size = n + border * 2

    def is_dark(r: int, c: int) -> bool:
        mr, mc = r - border, c - border
        if 0 <= mr < n and 0 <= mc < n:
            return matrix[mr][mc]
        return False

    lines: List[str] = []
    # Standard polarity: dark modules are foreground glyphs (█/▀/▄) and light quiet-zone/modules
    # are spaces (' '), rendered with explicit ANSI black-on-bright-white (\x1b[30;107m) so both
    # dark and light terminal themes display true black modules on a 4-module white quiet zone.
    prefix = "\x1b[30;107m" if use_ansi else ""
    suffix = "\x1b[0m" if use_ansi else ""
    for r in range(0, padded_size, 2):
        row_chars: List[str] = []
        for c in range(padded_size):
            top = is_dark(r, c)
            bot = is_dark(r + 1, c) if (r + 1) < padded_size else False
            if top and bot:
                row_chars.append("█")
            elif not top and not bot:
                row_chars.append(" ")
            elif top and not bot:
                row_chars.append("▀")
            else:
                row_chars.append("▄")
        lines.append(f"{prefix}{''.join(row_chars)}{suffix}")
    return "\n".join(lines)


def render_qr_svg(matrix: List[List[bool]], border: int = 4, scale: int = 7) -> str:
    n = len(matrix)
    total = (n + border * 2) * scale
    rects: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total} {total}" width="{total}" height="{total}" shape-rendering="crispEdges">',
        f'<rect width="{total}" height="{total}" fill="#ffffff"/>',
    ]
    for r in range(n):
        for c in range(n):
            if matrix[r][c]:
                x = (c + border) * scale
                y = (r + border) * scale
                rects.append(
                    f'<rect x="{x}" y="{y}" width="{scale}" height="{scale}" fill="#000000"/>'
                )
    rects.append("</svg>")
    return "".join(rects)


# ---------------------------------------------------------------------------
# Homebrew Discovery & SMDH Metadata Parser
# ---------------------------------------------------------------------------

class HomebrewPackage:
    def __init__(
        self,
        project: str,
        name: str,
        cia_path: Optional[str],
        threedsx_path: Optional[str],
        smdh_path: Optional[str],
    ) -> None:
        self.project = project
        self.name = name
        self.cia_path = cia_path
        self.threedsx_path = threedsx_path
        self.smdh_path = smdh_path
        self.title = name
        self.description = "Nintendo 3DS Homebrew Application"
        self.author = "Homebrew"
        self._parse_smdh()

    def _parse_smdh(self) -> None:
        if not self.smdh_path or not os.path.isfile(self.smdh_path):
            return
        try:
            with open(self.smdh_path, "rb") as f:
                full = f.read(0x408)
            if len(full) >= 0x208 and full[:4] == b"SMDH":
                # English title struct starts at offset 0x08 + 1 * 0x200 = 0x208, or index 0 at 0x08
                entry = full[0x208:0x408] if len(full) >= 0x408 else full[0x08:0x208]
                short_title = entry[0x00:0x80].decode("utf-16-le", errors="ignore").rstrip("\x00").strip()
                long_desc = entry[0x80:0x180].decode("utf-16-le", errors="ignore").rstrip("\x00").strip()
                publisher = entry[0x180:0x200].decode("utf-16-le", errors="ignore").rstrip("\x00").strip()
                if short_title:
                    self.title = short_title
                if long_desc:
                    self.description = long_desc
                if publisher:
                    self.author = publisher
        except OSError:
            pass

    @property
    def icon_data_uri(self) -> str:
        candidates = []
        if self.smdh_path:
            proj_dir = os.path.dirname(os.path.dirname(os.path.dirname(self.smdh_path)))
            candidates.append(os.path.join(proj_dir, "meta", "icon.png"))
        for c in candidates:
            if os.path.isfile(c):
                try:
                    with open(c, "rb") as fp:
                        b64 = base64.b64encode(fp.read()).decode("ascii")
                    return f"data:image/png;base64,{b64}"
                except OSError:
                    pass
        return ""

    @property
    def primary_path(self) -> Optional[str]:
        return self.cia_path or self.threedsx_path

    @property
    def build_stamp(self) -> str:
        p = self.primary_path
        if not p or not os.path.isfile(p):
            return "v0"
        return f"v{int(os.path.getmtime(p)) % 100000}"

    @property
    def mtime_str(self) -> str:
        p = self.primary_path
        if not p or not os.path.isfile(p):
            return "unknown"
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(p)))

    @property
    def cia_size_kb(self) -> int:
        if self.cia_path and os.path.isfile(self.cia_path):
            return (os.path.getsize(self.cia_path) + 1023) // 1024
        return 0


def discover_homebrew(root_dir: str) -> List[HomebrewPackage]:
    found: Dict[str, Dict[str, str]] = {}
    root_dir = os.path.abspath(root_dir)

    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [
            d for d in dirnames if not d.startswith(".") and d not in ("node_modules", "__pycache__")
        ]
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext not in (".cia", ".3dsx", ".smdh"):
                continue
            full_path = os.path.join(dirpath, fn)
            rel = os.path.relpath(full_path, root_dir)
            parts = rel.split(os.sep)
            project = parts[0] if len(parts) > 1 else os.path.basename(root_dir)
            stem = os.path.splitext(fn)[0]
            key = f"{project}/{stem}"
            slot = found.setdefault(key, {"project": project, "name": stem})
            slot[ext[1:]] = full_path

    packages: List[HomebrewPackage] = []
    for key in sorted(found.keys()):
        info = found[key]
        if "cia" not in info and "3dsx" not in info:
            continue
        packages.append(
            HomebrewPackage(
                project=info["project"],
                name=info["name"],
                cia_path=info.get("cia"),
                threedsx_path=info.get("3dsx"),
                smdh_path=info.get("smdh"),
            )
        )
    return packages


def detect_lan_ip() -> str:
    env_ip = os.environ.get("HOST_IP", "").strip()
    if env_ip:
        return env_ip
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.168.1.1", 80))
            ip = s.getsockname()[0]
            if not ip.startswith("127."):
                return ip
    except OSError:
        pass
    return "127.0.0.1"


def _is_valid_lan_ipv4(ip_str: str) -> bool:
    parts = ip_str.split(".")
    if len(parts) != 4:
        return False
    try:
        octets = [int(p) for p in parts]
    except ValueError:
        return False
    if any(o < 0 or o > 255 for o in octets):
        return False
    a, b, _, _ = octets
    return (
        a == 10
        or a == 127
        or (a == 192 and b == 168)
        or (a == 172 and 16 <= b <= 31)
    )


def push_url_to_fbi(threeds_ip: str, url: str, fbi_port: int = 5000) -> None:
    payload = url.encode("utf-8")
    header = struct.pack(">I", len(payload))
    with socket.create_connection((threeds_ip, fbi_port), timeout=5.0) as sock:
        sock.sendall(header + payload)
        try:
            sock.shutdown(socket.SHUT_WR)
            sock.recv(1)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Multi-Homebrew HTTP Server
# ---------------------------------------------------------------------------

def make_handler(root_dir: str, host_ip: str, port: int):
    class HomebrewHubHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _serve_binary(self, file_path: str, send_body: bool) -> None:
            if not os.path.isfile(file_path):
                self.send_error(404, "Artifact not found")
                return
            file_size = os.path.getsize(file_path)
            range_hdr = self.headers.get("Range")
            start, end = 0, file_size - 1
            status = 200

            if range_hdr:
                if not range_hdr.startswith("bytes=") or "," in range_hdr:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{file_size}")
                    self.send_header("Content-Length", "0")
                    self.send_header("Connection", "close")
                    self.end_headers()
                    return
                spec = range_hdr[6:].strip()
                parts = spec.split("-", 1)
                try:
                    if len(parts) != 2 or (not parts[0] and not parts[1]):
                        raise ValueError("empty range")
                    if not parts[0]:
                        # Suffix byte-range-spec: bytes=-N (last N bytes)
                        suffix_len = int(parts[1])
                        if suffix_len <= 0 or file_size == 0:
                            raise ValueError("invalid suffix")
                        start = max(0, file_size - suffix_len)
                        end = file_size - 1
                    else:
                        start = int(parts[0])
                        end = int(parts[1]) if parts[1] else (file_size - 1)
                        if start < 0 or start >= file_size or end < start:
                            raise ValueError("unsatisfiable range")
                        end = min(file_size - 1, end)
                    status = 206
                except ValueError:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{file_size}")
                    self.send_header("Content-Length", "0")
                    self.send_header("Connection", "close")
                    self.end_headers()
                    return

            length = max(0, end - start + 1)
            self.send_response(status)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header(
                "Content-Disposition",
                f'attachment; filename="{os.path.basename(file_path)}"',
            )
            self.send_header("Accept-Ranges", "bytes")
            if status == 206:
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            self.send_header("Content-Length", str(length))
            self.send_header("Connection", "close")
            self.end_headers()

            if send_body and length > 0:
                try:
                    with open(file_path, "rb") as f:
                        f.seek(start)
                        rem = length
                        while rem > 0:
                            chunk = f.read(min(65536, rem))
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            rem -= len(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        def _resolve_artifact(self, req_path: str) -> Optional[str]:
            clean = urllib.parse.unquote(req_path.split("?", 1)[0]).lstrip("/")
            if clean.startswith("c/"):
                parts = clean.split("/")
                if len(parts) == 2:
                    try:
                        idx = int(parts[1])
                        pkgs = discover_homebrew(root_dir)
                        if 0 <= idx < len(pkgs):
                            return pkgs[idx].primary_path
                    except ValueError:
                        return None
                return None
            if not clean.startswith("dl/"):
                return None
            parts = clean.split("/")
            if len(parts) not in (3, 4):
                return None
            proj = parts[1]
            filename = parts[-1]
            for pkg in discover_homebrew(root_dir):
                if pkg.project == proj:
                    if pkg.cia_path and os.path.basename(pkg.cia_path) == filename:
                        return pkg.cia_path
                    if pkg.threedsx_path and os.path.basename(pkg.threedsx_path) == filename:
                        return pkg.threedsx_path
            return None

        def do_HEAD(self) -> None:
            if self.path.split("?", 1)[0] == "/favicon.ico":
                self.send_error(404)
                return
            target = self._resolve_artifact(self.path)
            if target:
                self._serve_binary(target, send_body=False)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Connection", "close")
            self.end_headers()

        def do_POST(self) -> None:
            if self.path.startswith("/push"):
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    self.send_error(400, "Invalid Content-Length")
                    return
                if length < 0:
                    self.send_error(400, "Negative Content-Length")
                    return
                if length > 4096:
                    self.send_error(413, "Payload Too Large")
                    return
                raw = self.rfile.read(length).decode("utf-8", errors="ignore")
                params = urllib.parse.parse_qs(raw)
                threeds_ip = params.get("ip", [""])[0].strip()
                url = params.get("url", [""])[0].strip()
                if not _is_valid_lan_ipv4(threeds_ip) or not url.startswith("http://"):
                    msg = "Invalid 3DS LAN IPv4 address or URL."
                else:
                    try:
                        push_url_to_fbi(threeds_ip, url)
                        msg = f"Pushed {url} to 3DS ({threeds_ip}:5000)!"
                    except OSError as exc:
                        msg = f"Failed to reach {threeds_ip}:5000 ({exc})"
                self.send_response(303)
                self.send_header("Location", "/?msg=" + urllib.parse.quote(msg))
                self.send_header("Content-Length", "0")
                self.send_header("Connection", "close")
                self.end_headers()
                return
            self.send_error(404)

        def do_GET(self) -> None:
            if self.path.split("?", 1)[0] == "/favicon.ico":
                self.send_error(404)
                return
            target = self._resolve_artifact(self.path)
            if target:
                print(f"[3DS-HUB] Serving {os.path.basename(target)} to {self.client_address[0]}")
                self._serve_binary(target, send_body=True)
                print(f"[3DS-HUB] Finished transfer to {self.client_address[0]}")
                return

            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            flash_msg = qs.get("msg", [""])[0]

            packages = discover_homebrew(root_dir)
            cards: List[str] = []
            for idx, pkg in enumerate(packages):
                cia_url = (
                    f"http://{host_ip}:{port}/dl/{pkg.project}/{pkg.build_stamp}/{os.path.basename(pkg.cia_path)}"
                    if pkg.cia_path
                    else ""
                )
                threedsx_url = (
                    f"http://{host_ip}:{port}/dl/{pkg.project}/{pkg.build_stamp}/{os.path.basename(pkg.threedsx_path)}"
                    if pkg.threedsx_path
                    else ""
                )
                qr_target = f"http://{host_ip}:{port}/c/{idx}" if pkg.primary_path else ""
                svg_qr = render_qr_svg(encode_qr_matrix(qr_target)) if qr_target else ""

                links: List[str] = []
                if cia_url:
                    links.append(f'<a class="btn" href="{html.escape(cia_url)}">Download .cia ({pkg.cia_size_kb} KB)</a>')
                if threedsx_url:
                    links.append(f'<a class="btn secondary" href="{html.escape(threedsx_url)}">Download .3dsx</a>')

                push_form = ""
                if cia_url:
                    push_form = f"""
                    <form method="POST" action="/push" class="push-form">
                      <input type="hidden" name="url" value="{html.escape(cia_url)}"/>
                      <input type="text" name="ip" placeholder="3DS IP (e.g. 192.168.0.150)" required/>
                      <button type="submit">Push to FBI (:5000)</button>
                    </form>"""

                icon_img = (
                    f'<img class="app-icon" src="{pkg.icon_data_uri}" width="48" height="48" alt="{html.escape(pkg.title)} icon"/>'
                    if pkg.icon_data_uri
                    else ""
                )

                cards.append(f"""
                <div class="card">
                  <div class="card-top">{icon_img}<div class="badge">{html.escape(pkg.project)}</div></div>
                  <h2>{html.escape(pkg.title)}</h2>
                  <p class="desc">{html.escape(pkg.description)}</p>
                  <p class="meta">Author: <b>{html.escape(pkg.author)}</b> · Built: {html.escape(pkg.mtime_str)}</p>
                  <div class="qr">{svg_qr}</div>
                  <code>{html.escape(qr_target)}</code>
                  <div class="actions">{''.join(links)}</div>
                  {push_form}
                </div>""")

            empty_html = (
                "<p>No <code>.cia</code> or <code>.3dsx</code> files found yet. Run <code>make 3ds</code> in a project directory first.</p>"
                if not cards
                else ""
            )
            flash_html = (
                f'<div class="flash">{html.escape(flash_msg)}</div>' if flash_msg else ""
            )

            page = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>3DS Homebrew QR & FBI Hub</title>
  <style>
    body {{ background:#0f1524; color:#f2f5fc; font-family:system-ui,-apple-system,sans-serif; margin:0; padding:2rem; }}
    header {{ max-width:1080px; margin:0 auto 2rem auto; text-align:center; }}
    h1 {{ margin:0 0 0.5rem 0; color:#f5d069; }}
    .sub {{ color:#9fb0cf; margin:0; }}
    .flash {{ max-width:640px; margin:1rem auto; padding:0.8rem 1rem; background:#1e3a2f; border:1px solid #48c78e; border-radius:8px; text-align:center; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:1.5rem; max-width:1080px; margin:0 auto; }}
    .card {{ background:#182238; border:2px solid #2d3d63; border-radius:16px; padding:1.5rem; text-align:center; }}
    .card-top {{ display:flex; align-items:center; justify-content:center; gap:0.6rem; margin-bottom:0.5rem; }}
    .app-icon {{ border-radius:10px; image-rendering:pixelated; box-shadow:0 2px 8px rgba(0,0,0,0.4); }}
    .badge {{ display:inline-block; background:#263759; color:#8ec5ff; font-size:0.8rem; padding:0.2rem 0.6rem; border-radius:999px; }}
    h2 {{ margin:0.25rem 0; color:#ffffff; }}
    .desc {{ color:#b7c5e0; font-size:0.9rem; margin:0.4rem 0; }}
    .meta {{ color:#7f92b5; font-size:0.8rem; margin:0.4rem 0 1rem 0; }}
    .qr svg {{ border-radius:8px; box-shadow:0 4px 16px rgba(0,0,0,0.35); }}
    code {{ display:block; background:#0b101c; color:#f5d069; padding:0.45rem; border-radius:6px; font-size:0.8rem; margin:0.85rem 0; word-break:break-all; }}
    .actions {{ display:flex; gap:0.5rem; justify-content:center; flex-wrap:wrap; margin-bottom:0.85rem; }}
    .btn {{ background:#f5d069; color:#111625; text-decoration:none; font-weight:700; padding:0.5rem 0.9rem; border-radius:8px; font-size:0.85rem; }}
    .btn.secondary {{ background:#2b3d63; color:#e6eefc; }}
    .push-form {{ display:flex; gap:0.4rem; justify-content:center; margin-top:0.5rem; }}
    .push-form input {{ background:#0b101c; border:1px solid #354973; color:#fff; padding:0.45rem 0.6rem; border-radius:6px; font-size:0.85rem; width:175px; }}
    .push-form button {{ background:#48c78e; color:#0b1510; border:none; font-weight:700; padding:0.45rem 0.75rem; border-radius:6px; cursor:pointer; font-size:0.85rem; }}
  </style>
</head>
<body>
  <header>
    <h1>3DS Homebrew QR &amp; FBI Installer Hub</h1>
    <p class="sub">On your 3DS: Open <b>FBI → Remote Install → Scan QR Code</b> (or use Receive URLs over the network)</p>
    {flash_html}
  </header>
  <main class="grid">
    {''.join(cards)}
    {empty_html}
  </main>
</body>
</html>""".encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(page)

    return HomebrewHubHandler


def main() -> None:
    default_root = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(
        description="Universal 3DS Homebrew QR & FBI Network Installer Hub"
    )
    parser.add_argument(
        "filter",
        nargs="?",
        default="",
        help="Optional project name filter (e.g. 3ds_pieceduel)",
    )
    parser.add_argument("--root", default=default_root, help="Root homebrew directory to scan")
    parser.add_argument("--host", default=detect_lan_ip(), help="LAN IP to encode in QR URLs")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("CIA_PORT", "8765")),
        help="HTTP port (default: 8765)",
    )
    parser.add_argument(
        "--push",
        default=os.environ.get("IP", ""),
        help="Optional 3DS IP to immediately push the CIA URL to FBI port 5000",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all discovered 3DS homebrew packages (.cia, .3dsx, .smdh) and exit",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Verify discovery, SMDH parsing, and QR generation then exit",
    )
    args = parser.parse_args()

    all_packages = discover_homebrew(args.root)
    packages = all_packages
    if args.filter:
        packages = [
            p for p in all_packages if args.filter.lower() in p.project.lower() or args.filter.lower() in p.name.lower()
        ]

    def canonical_index(pkg: HomebrewPackage) -> int:
        for i, cand in enumerate(all_packages):
            if cand.project == pkg.project and cand.name == pkg.name:
                return i
        return 0

    if args.list:
        for pkg in packages:
            print(f"{pkg.project}: {pkg.title} — {pkg.description} (cia={bool(pkg.cia_path)}, 3dsx={bool(pkg.threedsx_path)})")
        return

    if args.self_test:
        import threading
        import urllib.request

        assert len(packages) >= 1, f"Expected at least 1 homebrew package under {args.root}"
        pkg = packages[0]
        c_idx = canonical_index(pkg)
        short_url = f"http://{args.host}:{args.port}/c/{c_idx}"
        mat = encode_qr_matrix(short_url)
        assert len(mat) == 25, f"Expected Version 2 (25x25) QR matrix for {short_url}, got {len(mat)}x{len(mat)}"
        fmt1, fmt2, decoded_bytes = decode_qr_matrix_for_test(mat)
        assert fmt1 == fmt2 and decoded_bytes.decode("utf-8") == short_url
        svg = render_qr_svg(mat)
        ascii_qr = render_qr_ascii(mat)
        assert "<svg" in svg and len(ascii_qr.splitlines()) >= 10

        handler_cls = make_handler(args.root, args.host, 0)
        srv = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
        actual_port = srv.server_address[1]
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{actual_port}/") as resp:
                body = resp.read().decode("utf-8")
                assert resp.status == 200 and pkg.title in body and "<svg" in body
            c_url = f"http://127.0.0.1:{actual_port}/c/{c_idx}"
            with urllib.request.urlopen(c_url) as resp:
                c0_data = resp.read()
                assert resp.status == 200 and len(c0_data) == os.path.getsize(pkg.primary_path)
            dl_url = f"http://127.0.0.1:{actual_port}/dl/{pkg.project}/{os.path.basename(pkg.primary_path)}"
            with urllib.request.urlopen(dl_url) as resp:
                data = resp.read()
                assert resp.status == 200 and data == c0_data
            # Test Range: bytes=0-63 and suffix Range: bytes=-32
            req_range = urllib.request.Request(dl_url, headers={"Range": "bytes=0-63"})
            with urllib.request.urlopen(req_range) as resp:
                chunk = resp.read()
                assert resp.status == 206 and chunk == data[:64]
            req_suffix = urllib.request.Request(dl_url, headers={"Range": "bytes=-32"})
            with urllib.request.urlopen(req_suffix) as resp:
                chunk = resp.read()
                assert resp.status == 206 and chunk == data[-32:]
        finally:
            srv.shutdown()
            srv.server_close()

        print(
            f"PASS: Discovered {len(packages)} package(s); primary='{pkg.title}' ({pkg.project}) -> {short_url} (QR {len(mat)}x{len(mat)})"
        )
        print(ascii_qr)
        return

    print("=" * 68)
    print("  3DS Homebrew QR & FBI Installer Hub")
    print("=" * 68)
    print(f"  Root Dir : {os.path.abspath(args.root)}")
    print(f"  Web Hub  : http://{args.host}:{args.port}/")
    print(f"  Projects : {len(packages)} discovered")
    print("-" * 68)

    for pkg in packages:
        idx = canonical_index(pkg)
        if pkg.cia_path:
            cia_url = f"http://{args.host}:{args.port}/c/{idx}"
            print(f"  [{pkg.project}] {pkg.title} ({pkg.cia_size_kb} KB)")
            print(f"  FBI QR URL: {cia_url}")
            print("  On 3DS    : Open FBI -> Remote Install -> Scan QR Code\n")
            print(render_qr_ascii(encode_qr_matrix(cia_url)))
            print("-" * 68)
            if args.push:
                try:
                    push_url_to_fbi(args.push, cia_url)
                    print(f"  [FBI] Pushed {cia_url} to 3DS at {args.push}:5000!")
                except OSError as exc:
                    print(f"  [FBI] Could not push to {args.push}:5000 ({exc}); scan QR instead.")

    handler_cls = make_handler(args.root, args.host, args.port)
    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer(("0.0.0.0", args.port), handler_cls)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down 3DS Homebrew Hub.")
        server.server_close()


if __name__ == "__main__":
    main()
