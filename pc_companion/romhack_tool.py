#!/usr/bin/env python3
"""
3DS & GBA/NDS ROM Hack Patcher & Luma3DS LayeredFS Stager (pc_companion/romhack_tool.py)

Supports:
  1. Applying and creating `.ips` patches (standard "PATCH" .. "EOF" format)
  2. Applying and creating `.bps` patches ("BPS1" format with source/target/patch IEEE CRC32 verification)
  3. Staging a 3DS LayeredFS ROM hack into `luma/titles/<TitleID>/` (with automatic TitleID lookup for
     Pokemon X/Y, Omega Ruby/Alpha Sapphire, Sun/Moon, Ultra Sun/Ultra Moon).
"""

from __future__ import annotations

import argparse
import os
import shutil
import struct
import zlib
from typing import Dict, List, Optional, Tuple

POKEMON_3DS_TITLE_IDS: Dict[str, str] = {
    "x": "0004000000055D00",
    "eternal_x": "0004000000055D00",
    "y": "0004000000055E00",
    "wilting_y": "0004000000055E00",
    "omega_ruby": "000400000011C400",
    "rutile_ruby": "000400000011C400",
    "alpha_sapphire": "000400000011C500",
    "star_sapphire": "000400000011C500",
    "sun": "0004000000164800",
    "nova_sun": "0004000000164800",
    "moon": "0004000000175E00",
    "umbra_moon": "0004000000175E00",
    "ultra_sun": "00040000001B5000",
    "photonic_sun": "00040000001B5000",
    "ultra_moon": "00040000001B5100",
    "prismatic_moon": "00040000001B5100",
}


# ---------------------------------------------------------------------------
# IPS Patcher ("PATCH" ... "EOF")
# ---------------------------------------------------------------------------

def create_ips_patch(source: bytes, target: bytes) -> bytes:
    out = bytearray(b"PATCH")
    i = 0
    n = len(target)
    while i < n:
        if i < len(source) and source[i] == target[i]:
            i += 1
            continue
        start = i
        while i < n and (i - start) < 0xFFFF and (i >= len(source) or source[i] != target[i]):
            i += 1
        chunk = target[start:i]
        # Avoid 0x454F46 ("EOF") offset collision
        if start == 0x454F46 and start > 0:
            start -= 1
            chunk = target[start:i]
        out.extend(
            [
                (start >> 16) & 0xFF,
                (start >> 8) & 0xFF,
                start & 0xFF,
                (len(chunk) >> 8) & 0xFF,
                len(chunk) & 0xFF,
            ]
        )
        out.extend(chunk)
    out.extend(b"EOF")
    return bytes(out)


def apply_ips_patch(source: bytes, patch: bytes) -> bytes:
    if not patch.startswith(b"PATCH") or len(patch) < 8:
        raise ValueError("Invalid IPS header (expected 'PATCH')")
    out = bytearray(source)
    idx = 5
    while idx + 3 <= len(patch):
        if patch[idx : idx + 3] == b"EOF":
            break
        offset = (patch[idx] << 16) | (patch[idx + 1] << 8) | patch[idx + 2]
        idx += 3
        size = (patch[idx] << 8) | patch[idx + 1]
        idx += 2
        if size == 0:
            # RLE record
            rle_len = (patch[idx] << 8) | patch[idx + 1]
            val = patch[idx + 2]
            idx += 3
            if offset + rle_len > len(out):
                out.extend(b"\x00" * (offset + rle_len - len(out)))
            out[offset : offset + rle_len] = bytes([val]) * rle_len
        else:
            chunk = patch[idx : idx + size]
            idx += size
            if offset + size > len(out):
                out.extend(b"\x00" * (offset + size - len(out)))
            out[offset : offset + size] = chunk
    return bytes(out)


# ---------------------------------------------------------------------------
# BPS Patcher ("BPS1" + VLI numbers + CRC32 footers)
# ---------------------------------------------------------------------------

def _bps_encode_num(val: int) -> bytes:
    out = bytearray()
    while True:
        x = val & 0x7F
        val >>= 7
        if val == 0:
            out.append(0x80 | x)
            break
        out.append(x)
        val -= 1
    return bytes(out)


def _bps_decode_num(data: bytes, idx: int) -> Tuple[int, int]:
    val = 0
    shift = 1
    while True:
        b = data[idx]
        idx += 1
        val += (b & 0x7F) * shift
        if b & 0x80:
            break
        shift <<= 7
        val += shift
    return val, idx


def create_bps_patch(source: bytes, target: bytes, metadata: str = "") -> bytes:
    body = bytearray(b"BPS1")
    body.extend(_bps_encode_num(len(source)))
    body.extend(_bps_encode_num(len(target)))
    meta_bytes = metadata.encode("utf-8")
    body.extend(_bps_encode_num(len(meta_bytes)))
    body.extend(meta_bytes)

    # Action 0 = SourceRead (where target matches source at same offset), Action 1 = TargetRead
    i = 0
    n = len(target)
    while i < n:
        if i < len(source) and source[i] == target[i]:
            start = i
            while i < n and i < len(source) and source[i] == target[i]:
                i += 1
            length = i - start
            body.extend(_bps_encode_num(((length - 1) << 2) | 0))
        else:
            start = i
            while i < n and not (i < len(source) and source[i] == target[i]):
                i += 1
            chunk = target[start:i]
            body.extend(_bps_encode_num(((len(chunk) - 1) << 2) | 1))
            body.extend(chunk)

    src_crc = zlib.crc32(source) & 0xFFFFFFFF
    tgt_crc = zlib.crc32(target) & 0xFFFFFFFF
    body.extend(struct.pack("<II", src_crc, tgt_crc))
    patch_crc = zlib.crc32(bytes(body)) & 0xFFFFFFFF
    body.extend(struct.pack("<I", patch_crc))
    return bytes(body)


def apply_bps_patch(source: bytes, patch: bytes) -> bytes:
    if not patch.startswith(b"BPS1") or len(patch) < 16:
        raise ValueError("Invalid BPS header (expected 'BPS1')")
    expected_patch_crc = struct.unpack_from("<I", patch, len(patch) - 4)[0]
    actual_patch_crc = zlib.crc32(patch[:-4]) & 0xFFFFFFFF
    if expected_patch_crc != actual_patch_crc:
        raise ValueError("BPS patch CRC32 mismatch")

    src_crc, tgt_crc = struct.unpack_from("<II", patch, len(patch) - 12)
    if (zlib.crc32(source) & 0xFFFFFFFF) != src_crc:
        raise ValueError("BPS source ROM CRC32 mismatch")

    idx = 4
    src_size, idx = _bps_decode_num(patch, idx)
    if len(source) != src_size:
        raise ValueError("BPS source ROM size mismatch")
    tgt_size, idx = _bps_decode_num(patch, idx)
    meta_size, idx = _bps_decode_num(patch, idx)
    idx += meta_size

    out = bytearray(tgt_size)
    out_offset = 0
    src_rel_offset = 0
    tgt_rel_offset = 0
    end_actions = len(patch) - 12

    while idx < end_actions:
        cmd, idx = _bps_decode_num(patch, idx)
        action = cmd & 3
        length = (cmd >> 2) + 1
        if action == 0:  # SourceRead
            out[out_offset : out_offset + length] = source[out_offset : out_offset + length]
            out_offset += length
        elif action == 1:  # TargetRead
            out[out_offset : out_offset + length] = patch[idx : idx + length]
            idx += length
            out_offset += length
        elif action == 2:  # SourceCopy
            off_raw, idx = _bps_decode_num(patch, idx)
            src_rel_offset += (-1 if (off_raw & 1) else 1) * (off_raw >> 1)
            for _ in range(length):
                out[out_offset] = source[src_rel_offset]
                out_offset += 1
                src_rel_offset += 1
        else:  # TargetCopy
            off_raw, idx = _bps_decode_num(patch, idx)
            tgt_rel_offset += (-1 if (off_raw & 1) else 1) * (off_raw >> 1)
            for _ in range(length):
                out[out_offset] = out[tgt_rel_offset]
                out_offset += 1
                tgt_rel_offset += 1

    if (zlib.crc32(bytes(out)) & 0xFFFFFFFF) != tgt_crc:
        raise ValueError("BPS patched target CRC32 mismatch")
    return bytes(out)


def stage_layeredfs_mod(
    sd_root: str,
    title_or_alias: str,
    romfs_dir: Optional[str] = None,
    code_bin: Optional[str] = None,
) -> str:
    key = title_or_alias.strip().lower().replace(" ", "_")
    tid = POKEMON_3DS_TITLE_IDS.get(key, title_or_alias.strip().upper())
    dest_dir = os.path.join(sd_root, "luma", "titles", tid)
    os.makedirs(os.path.join(dest_dir, "romfs"), exist_ok=True)
    if romfs_dir and os.path.isdir(romfs_dir):
        shutil.copytree(romfs_dir, os.path.join(dest_dir, "romfs"), dirs_exist_ok=True)
    if code_bin and os.path.isfile(code_bin):
        shutil.copyfile(code_bin, os.path.join(dest_dir, "code.bin"))
    return dest_dir


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Apply/create IPS & BPS ROM hack patches or stage Luma3DS LayeredFS folders.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_apply = sub.add_parser("apply", help="Apply .ips or .bps patch to a clean ROM")
    p_apply.add_argument("source_rom")
    p_apply.add_argument("patch_file")
    p_apply.add_argument("output_rom")

    p_stage = sub.add_parser("stage-layeredfs", help="Stage a Luma3DS LayeredFS ROM hack folder")
    p_stage.add_argument("--sd-root", required=True)
    p_stage.add_argument("--title", required=True, help="Title alias (e.g. photonic_sun, rutile_ruby) or 16-hex TitleID")
    p_stage.add_argument("--romfs", help="Optional source romfs directory")
    p_stage.add_argument("--code-bin", help="Optional code.bin path")

    args = parser.parse_args(argv)
    if args.cmd == "apply":
        with open(args.source_rom, "rb") as fp:
            src = fp.read()
        with open(args.patch_file, "rb") as fp:
            patch = fp.read()
        if patch.startswith(b"BPS1"):
            out = apply_bps_patch(src, patch)
        else:
            out = apply_ips_patch(src, patch)
        tmp = f"{args.output_rom}.tmp"
        with open(tmp, "wb") as fp:
            fp.write(out)
        os.replace(tmp, args.output_rom)
        print(f"Patched ROM written to {args.output_rom} ({len(out)} bytes)")
    elif args.cmd == "stage-layeredfs":
        dest = stage_layeredfs_mod(args.sd_root, args.title, args.romfs, args.code_bin)
        print(f"Staged Luma3DS LayeredFS mod at {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
