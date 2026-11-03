#!/usr/bin/env python3
"""
Deterministic Dual-Screen 3DS Screenshot Generator (`pc_companion/render_screenshots.py`)

Runs every 3DS homebrew application's host simulator binary with `PK_DUMP_FRAMEBUFFER` set,
captures both the 400x240 Top Screen and 320x240 Bottom Touch Screen framebuffers, and
stitches them into a framed 424x516 Nintendo 3DS Dual-Screen PNG (`docs/screenshot.png`)
for each repository and the root documentation gallery.
"""

from __future__ import annotations

import os
import struct
import subprocess
import tempfile
import zlib
from typing import List, Tuple

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOP_W, TOP_H = 400, 240
BOT_W, BOT_H = 320, 240
CANVAS_W, CANVAS_H = 424, 516


def write_png(path: str, width: int, height: int, rgba_bytes: bytes) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    raw_rows = bytearray()
    stride = width * 4
    for y in range(height):
        raw_rows.append(0)
        raw_rows.extend(rgba_bytes[y * stride : (y + 1) * stride])

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    compressed = zlib.compress(bytes(raw_rows), 9)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", ihdr))
        f.write(chunk(b"IDAT", compressed))
        f.write(chunk(b"IEND", b""))


def compose_dual_screen_png(fb_raw: bytes, out_png: str) -> None:
    expected = (TOP_W * TOP_H + BOT_W * BOT_H) * 4
    if len(fb_raw) != expected:
        raise ValueError(f"Expected {expected} bytes, got {len(fb_raw)}")

    top_bytes = fb_raw[: TOP_W * TOP_H * 4]
    bot_bytes = fb_raw[TOP_W * TOP_H * 4 :]

    canvas = bytearray(CANVAS_W * CANVAS_H * 4)
    # Dark metallic New 3DS XL shell bezel background
    for y in range(CANVAS_H):
        for x in range(CANVAS_W):
            idx = (y * CANVAS_W + x) * 4
            if x < 2 or x >= CANVAS_W - 2 or y < 2 or y >= CANVAS_H - 2:
                canvas[idx : idx + 4] = bytes((58, 72, 104, 255))
            elif 256 <= y <= 262:
                # 3DS hinge line
                canvas[idx : idx + 4] = bytes((10, 12, 18, 255))
            else:
                canvas[idx : idx + 4] = bytes((20, 24, 34, 255))

    # Blit 400x240 Top Screen at (12, 10)
    top_x0, top_y0 = 12, 10
    for y in range(TOP_H):
        src_off = y * TOP_W * 4
        dst_off = ((top_y0 + y) * CANVAS_W + top_x0) * 4
        canvas[dst_off : dst_off + TOP_W * 4] = top_bytes[src_off : src_off + TOP_W * 4]

    # Blit 320x240 Bottom Touch Screen centered at (52, 266)
    bot_x0, bot_y0 = 52, 266
    for y in range(BOT_H):
        src_off = y * BOT_W * 4
        dst_off = ((bot_y0 + y) * CANVAS_W + bot_x0) * 4
        canvas[dst_off : dst_off + BOT_W * 4] = bot_bytes[src_off : src_off + BOT_W * 4]

    write_png(out_png, CANVAS_W, CANVAS_H, bytes(canvas))


def generate_all_screenshots() -> List[str]:
    apps: List[Tuple[str, List[str]]] = [
        ("3ds_pokedash", ["build/host/3ds_pokedash_host", "--sd-root", "build/test_sd", "--once"]),
        ("3ds_sysdash", ["build/host/3ds_sysdash_host", "--sd-root", "build/test_sd", "--once"]),
        ("3ds_drop", ["build/host/3ds_drop_host", "--sd-root", "build/test_sd", "--port", "0", "--once"]),
        ("3ds_wigle", ["build/host/3ds_wigle_host", "--sd-root", "build/test_sd", "--once"]),
        ("3ds_rngtool", ["build/host/3ds_rngtool_host", "--sd-root", "build/test_sd", "--once"]),
        ("3ds_netpass", ["build/host/3ds_netpass_host", "--sd-root", "build/test_sd", "--once"]),
        ("3ds_padtest", ["build/host/3ds_padtest_host", "--sd-root", "build/test_sd", "--once"]),
        ("3ds_pieceduel", ["build/host/3ds_pieceduel_host", "--once"]),
        ("3ds_picross", ["build/host/3ds_picross_host", "--sd-root", "build/test_sd", "--once"]),
        ("3ds_sandlab", ["build/host/3ds_sandlab_host", "--sd-root", "build/test_sd", "--once"]),
        ("3ds_chip8", ["build/host/3ds_chip8_host", "--sd-root", "build/test_sd", "--once"]),
        ("3ds_solitaire", ["build/host/3ds_solitaire_host", "--sd-root", "build/test_sd", "--once"]),
        ("3ds_pokedex", ["build/host/3ds_pokedex_host", "--sd-root", "build/test_sd", "--once"]),
        ("3ds_sokoban", ["build/host/3ds_sokoban_host", "--sd-root", "build/test_sd", "--once"]),
        ("3ds_roulette", ["build/host/3ds_roulette_host", "--sd-root", "build/test_sd", "--once"]),
        ("3ds_mahjong", ["build/host/3ds_mahjong_host", "--sd-root", "build/test_sd", "--once"]),
    ]

    generated: List[str] = []
    for proj, cmd in apps:
        proj_dir = os.path.join(WORKSPACE_ROOT, proj)
        subprocess.run(["make", "-C", proj_dir, "host"], check=True, capture_output=True)
        with tempfile.NamedTemporaryFile(suffix=".fb", delete=False) as tf:
            fb_path = tf.name
        try:
            env = dict(os.environ)
            env["PK_DUMP_FRAMEBUFFER"] = fb_path
            subprocess.run(cmd, cwd=proj_dir, env=env, check=True, capture_output=True)
            with open(fb_path, "rb") as fp:
                fb_raw = fp.read()
            out_png = os.path.join(proj_dir, "docs", "screenshot.png")
            os.makedirs(os.path.dirname(out_png), exist_ok=True)
            compose_dual_screen_png(fb_raw, out_png)
            generated.append(out_png)
            print(f"Generated {out_png} ({os.path.getsize(out_png)} bytes)")
        finally:
            if os.path.exists(fb_path):
                os.remove(fb_path)
    return generated


if __name__ == "__main__":
    generate_all_screenshots()
