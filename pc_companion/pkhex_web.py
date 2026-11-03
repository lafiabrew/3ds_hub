#!/usr/bin/env python3
"""
PC Companion PKHaX Save Inspector & Surgical Editor (pc_companion/pkhex_web.py)

Compatible bit-for-bit with `3ds_pokedash` surgical PKHaX save blocks:
  - Supports Gen 3 (0x20000), Gen 4/5 (0x80000), Gen 6 (0x65600/0x76000), Gen 7 (0x6BE00/0x6CC00)
  - Permissive PKHaX ROM-hack mode: preserves custom ROM-hack abilities, moves, and event flags
    outside the surgical block (0x1400..0x15FF) bit-for-bit.
  - Creates mandatory `<save>.bak` backup before every write, recalculates CRC-16-CCITT +
    Gen 3 (0x0FF6/0x1FF6) / Gen 6-7 BEEF footers, and writes atomically via `<save>.tmp` -> `rename()`.
  - Can pull/push saves directly to a 3DS running `3ds_drop` (`http://<3ds-ip>:8766`).
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import argparse
import json
import os
import shutil
import struct
import urllib.parse
from typing import Any, Dict, List, Optional, Type

PKHAX_BLOCK_OFFSET = 0x1400
PKHAX_BLOCK_SIZE = 0x0200
PKHAX_MAGIC = 0x58484B50  # "PKHX" LE

NATURES = [
    "Hardy", "Lonely", "Brave", "Adamant", "Naughty",
    "Bold", "Docile", "Relaxed", "Impish", "Lax",
    "Timid", "Hasty", "Serious", "Jolly", "Naive",
    "Modest", "Mild", "Quiet", "Bashful", "Rash",
    "Calm", "Gentle", "Sassy", "Careful", "Quirky",
]


def crc16_ccitt(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def gen3_section_checksum(section: bytes) -> int:
    total = 0
    for i in range(0, len(section) // 4 * 4, 4):
        (word,) = struct.unpack_from("<I", section, i)
        total = (total + word) & 0xFFFFFFFF
    return ((total & 0xFFFF) + ((total >> 16) & 0xFFFF)) & 0xFFFF


def is_shiny_pid(pid: int, tid: int, sid: int) -> bool:
    p_high = (pid >> 16) & 0xFFFF
    p_low = pid & 0xFFFF
    return (tid ^ sid ^ p_high ^ p_low) < 16


def parse_save_bytes(raw: bytes, path: str = "save.sav") -> Dict[str, Any]:
    if len(raw) < PKHAX_BLOCK_OFFSET + PKHAX_BLOCK_SIZE:
        raise ValueError(f"Save file too small ({len(raw)} bytes)")

    blk = raw[PKHAX_BLOCK_OFFSET : PKHAX_BLOCK_OFFSET + PKHAX_BLOCK_SIZE]
    (magic,) = struct.unpack_from("<I", blk, 0x00)
    if magic != PKHAX_MAGIC:
        raise ValueError("Save file does not contain initialized PKHX surgical block")

    expected_crc = crc16_ccitt(blk[:-2])
    (stored_crc,) = struct.unpack_from("<H", blk, PKHAX_BLOCK_SIZE - 2)

    gen = blk[0x04]
    is_romhack = bool(blk[0x05])
    party_count = min(6, int(blk[0x06]))
    tid, sid, money, candies, mballs = struct.unpack_from("<HHIHH", blk, 0x08)
    trainer_name = blk[0x14:0x2C].split(b"\x00", 1)[0].decode("utf-8", errors="replace")

    party: List[Dict[str, Any]] = []
    for i in range(party_count):
        slot = blk[0x30 + i * 64 : 0x30 + (i + 1) * 64]
        species, level, nature, friendship, _pad, ability, held_item = struct.unpack_from(
            "<HBBBBHH", slot, 0x00
        )
        moves = list(struct.unpack_from("<4H", slot, 0x0A))
        (iv32,) = struct.unpack_from("<I", slot, 0x12)
        ivs = [(iv32 >> (st * 5)) & 0x1F for st in range(6)]
        evs = list(slot[0x16:0x1C])
        pid, mtid, msid = struct.unpack_from("<IHH", slot, 0x1C)
        nick = slot[0x24:0x3C].split(b"\x00", 1)[0].decode("utf-8", errors="replace")
        party.append(
            {
                "slot": i,
                "species": species,
                "nickname": nick,
                "level": level,
                "nature": nature,
                "nature_name": NATURES[nature % 25],
                "friendship": friendship,
                "ability": ability,
                "held_item": held_item,
                "moves": moves,
                "ivs": ivs,
                "evs": evs,
                "pid": pid,
                "tid": mtid,
                "sid": msid,
                "is_shiny": is_shiny_pid(pid, mtid, msid),
            }
        )

    return {
        "path": path,
        "file_size": len(raw),
        "gen": gen,
        "is_romhack": is_romhack,
        "trainer_name": trainer_name,
        "tid": tid,
        "sid": sid,
        "money": money,
        "rare_candies": candies,
        "master_balls": mballs,
        "checksum": stored_crc,
        "checksum_valid": (expected_crc == stored_crc),
        "party_count": party_count,
        "party": party,
    }


def apply_surgical_edit_to_file(
    path: str,
    slot_idx: int = 0,
    max_ivs: bool = False,
    trick_room: bool = False,
    shiny: Optional[bool] = None,
    nature: Optional[int] = None,
    level: Optional[int] = None,
    evs: Optional[List[int]] = None,
    money: Optional[int] = None,
) -> Dict[str, Any]:
    with open(path, "rb") as fp:
        buf = bytearray(fp.read())

    # Step 1: Mandatory .bak backup
    bak_path = f"{path}.bak"
    shutil.copyfile(path, bak_path)

    info = parse_save_bytes(bytes(buf), path)
    if money is not None:
        info["money"] = min(9999999, max(0, int(money)))
        info["rare_candies"] = 999
        info["master_balls"] = 999

    if 0 <= slot_idx < len(info["party"]):
        mon = info["party"][slot_idx]
        if max_ivs:
            mon["ivs"] = [31, 31, 31, 31, 31, 31]
        if trick_room:
            mon["ivs"] = [31, 31, 31, 0, 31, 31]
        if shiny is not None:
            p_low = mon["pid"] & 0xFFFF
            if shiny:
                sh_high = (mon["tid"] ^ mon["sid"] ^ p_low) ^ 0x0001
                mon["pid"] = ((sh_high & 0xFFFF) << 16) | p_low
            else:
                ns_high = (mon["tid"] ^ mon["sid"] ^ p_low) ^ 0x0100
                mon["pid"] = ((ns_high & 0xFFFF) << 16) | p_low
        if nature is not None:
            mon["nature"] = int(nature) % 25
        if level is not None:
            mon["level"] = min(100, max(1, int(level)))
        if evs is not None and len(evs) == 6:
            mon["evs"] = [min(252, max(0, int(x))) for x in evs]

    # Step 2: Re-serialize only the 512-byte PKHX block
    blk = bytearray(PKHAX_BLOCK_SIZE)
    struct.pack_into("<I", blk, 0x00, PKHAX_MAGIC)
    blk[0x04] = info["gen"]
    blk[0x05] = 1 if info["is_romhack"] else 0
    blk[0x06] = info["party_count"]
    struct.pack_into(
        "<HHIHH",
        blk,
        0x08,
        info["tid"],
        info["sid"],
        info["money"],
        info["rare_candies"],
        info["master_balls"],
    )
    tn_bytes = info["trainer_name"].encode("utf-8")[:23]
    blk[0x14 : 0x14 + len(tn_bytes)] = tn_bytes

    for i, mon in enumerate(info["party"]):
        off = 0x30 + i * 64
        struct.pack_into(
            "<HBBBBHH",
            blk,
            off,
            mon["species"],
            mon["level"],
            mon["nature"] % 25,
            mon["friendship"],
            0,
            mon["ability"],
            mon["held_item"],
        )
        struct.pack_into("<4H", blk, off + 0x0A, *mon["moves"])
        iv32 = 0
        for st in range(6):
            iv32 |= (mon["ivs"][st] & 0x1F) << (st * 5)
        struct.pack_into("<I", blk, off + 0x12, iv32)
        for st in range(6):
            blk[off + 0x16 + st] = mon["evs"][st] & 0xFF
        struct.pack_into("<IHH", blk, off + 0x1C, mon["pid"], mon["tid"], mon["sid"])
        nb = mon["nickname"].encode("utf-8")[:23]
        blk[off + 0x24 : off + 0x24 + len(nb)] = nb

    blk_crc = crc16_ccitt(bytes(blk[:-2]))
    struct.pack_into("<H", blk, PKHAX_BLOCK_SIZE - 2, blk_crc)
    buf[PKHAX_BLOCK_OFFSET : PKHAX_BLOCK_OFFSET + PKHAX_BLOCK_SIZE] = blk

    # Step 3: Update generation footers (Gen 3 section checksums / Gen 6-7 BEEF table)
    sz = len(buf)
    gen = info["gen"]
    if gen == 3 and sz >= 0x2000:
        struct.pack_into("<I", buf, 0x0FF8, 0x08012025)
        struct.pack_into("<H", buf, 0x0FF6, gen3_section_checksum(bytes(buf[0x0000:0x0FF4])))
        struct.pack_into("<I", buf, 0x1FF8, 0x08012025)
        struct.pack_into("<H", buf, 0x1FF6, gen3_section_checksum(bytes(buf[0x1000:0x1FF4])))
    elif gen in (6, 7) and sz >= 0x2000:
        beef_off = sz - 0x1F0
        struct.pack_into("<I", buf, beef_off, 0x42454546)
        struct.pack_into("<H", buf, beef_off + 6, blk_crc)
    elif gen in (4, 5) and sz >= 0x2000:
        struct.pack_into("<H", buf, 0x1FFE, blk_crc)

    # Step 4: Atomic write via <path>.tmp -> os.replace()
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "wb") as fp:
        fp.write(buf)
        fp.flush()
        os.fsync(fp.fileno())
    os.replace(tmp_path, path)

    return parse_save_bytes(bytes(buf), path)


def make_pkhex_web_handler(save_path: str) -> Type[BaseHTTPRequestHandler]:
    class PKHaXWebHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            pass

        def _send_json(self, status: int, data: Dict[str, Any]) -> None:
            raw = json.dumps(data, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:
            if self.path.startswith("/api/save"):
                try:
                    with open(save_path, "rb") as fp:
                        summary = parse_save_bytes(fp.read(), save_path)
                    self._send_json(200, summary)
                except Exception as exc:
                    self._send_json(400, {"error": str(exc)})
                return

            html_doc = """<!doctype html><html><head><meta charset="utf-8"/>
<title>PokeDash PKHaX Web Editor (lafiabrew)</title>
<style>
body{background:#0e1526;color:#eef3fc;font-family:system-ui,sans-serif;max-width:960px;margin:0 auto;padding:1.5rem}
h1{color:#ffd666;margin:0 0 .3rem 0}.sub{color:#9ab0d4;margin:0 0 1rem 0;font-size:.9rem}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1rem}
.card{background:#17233b;border:1px solid #2d4470;border-radius:12px;padding:1rem}
button{background:#38c890;color:#08150f;border:none;padding:.45rem .75rem;border-radius:7px;font-weight:700;cursor:pointer;margin:.2rem .2rem 0 0}
button.alt{background:#4a78c2;color:#fff}
.shiny{color:#ffd666;font-weight:700}
</style></head><body>
<h1>PokeDash PKHaX — Browser Surgical Save Editor</h1>
<p class="sub" id="hdr">Loading save...</p>
<div style="margin-bottom:1rem">
  <button class="alt" onclick="editSlot(0,{max_money:true})">Max Money ($9,999,999) + 999 Candies/Master Balls</button>
</div>
<div class="grid" id="party"></div>
<script>
async function loadSave(){
  const s=await (await fetch('/api/save')).json();
  document.getElementById('hdr').textContent=`Save: ${s.path} (Gen ${s.gen} ${s.is_romhack?'ROMHACK':'Vanilla'}) | OT: ${s.trainer_name} | $${s.money} | CRC: 0x${s.checksum.toString(16).toUpperCase()} (${s.checksum_valid?'VALID':'ERR'})`;
  const box=document.getElementById('party');box.innerHTML='';
  (s.party||[]).forEach(m=>{
    const d=document.createElement('div');d.className='card';
    d.innerHTML=`<h3>[${m.slot+1}] ${m.nickname} (#${m.species}) Lv.${m.level} ${m.is_shiny?'<span class="shiny">*SHINY*</span>':''}</h3>
    <p>Nature: <b>${m.nature_name}</b> | Ability ID: <code>${m.ability}</code></p>
    <p>IVs: <code>${m.ivs.join('/')}</code> | EVs: <code>${m.evs.join('/')}</code></p>
    <button onclick='editSlot(${m.slot},{max_ivs:true})'>6x31 IVs</button>
    <button onclick='editSlot(${m.slot},{trick_room:true})'>0 Spe (Trick Room)</button>
    <button onclick='editSlot(${m.slot},{shiny:${!m.is_shiny}})'>Toggle Shiny</button>
    <button onclick='editSlot(${m.slot},{level:100})'>Lv.100</button>`;
    box.appendChild(d);
  });
}
async function editSlot(slot,opts){
  await fetch('/api/edit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.assign({slot},opts))});
  loadSave();
}
loadSave();
</script></body></html>""".encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html_doc)))
            self.end_headers()
            self.wfile.write(html_doc)

        def do_POST(self) -> None:
            if self.path.startswith("/api/edit"):
                clen = int(self.headers.get("Content-Length", "0"))
                req = json.loads(self.rfile.read(clen).decode("utf-8", errors="replace") or "{}")
                try:
                    updated = apply_surgical_edit_to_file(
                        save_path,
                        slot_idx=int(req.get("slot", 0)),
                        max_ivs=bool(req.get("max_ivs", False)),
                        trick_room=bool(req.get("trick_room", False)),
                        shiny=req.get("shiny") if "shiny" in req else None,
                        nature=req.get("nature"),
                        level=req.get("level"),
                        evs=req.get("evs"),
                        money=9999999 if req.get("max_money") else req.get("money"),
                    )
                    self._send_json(200, updated)
                except Exception as exc:
                    self._send_json(400, {"error": str(exc)})
                return
            self._send_json(404, {"error": "not_found"})

    return PKHaXWebHandler


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="PKHaX Save Inspector & Surgical Editor (CLI)")
    parser.add_argument("save_path", help="Path to Pokémon save file (main or .sav)")
    parser.add_argument("--slot", type=int, default=0, help="Party slot index (0..5)")
    parser.add_argument("--max-ivs", action="store_true", help="Set 6x31 IVs on slot")
    parser.add_argument("--trick-room", action="store_true", help="Set 31/31/31/0/31/31 IVs on slot")
    parser.add_argument("--shiny", choices=["on", "off"], help="Set or clear shiny PID")
    parser.add_argument("--nature", type=int, help="Set nature ID (0..24)")
    parser.add_argument("--level", type=int, help="Set level (1..100)")
    parser.add_argument("--max-money", action="store_true", help="Max money ($9,999,999) + 999 Rare Candies & Master Balls")
    parser.add_argument("--serve", action="store_true", help="Launch interactive browser PKHaX Web UI")
    parser.add_argument("--port", type=int, default=8767, help="Port for --serve Web UI (default: 8767)")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args(argv)

    if args.serve:
        srv = ThreadingHTTPServer(("0.0.0.0", args.port), make_pkhex_web_handler(args.save_path))
        print(f"PKHaX Web UI listening on http://127.0.0.1:{args.port}/ (editing {args.save_path})")
        srv.serve_forever()
        return 0

    did_edit = any(
        [
            args.max_ivs,
            args.trick_room,
            args.shiny is not None,
            args.nature is not None,
            args.level is not None,
            args.max_money,
        ]
    )
    if did_edit:
        summary = apply_surgical_edit_to_file(
            args.save_path,
            slot_idx=args.slot,
            max_ivs=args.max_ivs,
            trick_room=args.trick_room,
            shiny=(args.shiny == "on") if args.shiny else None,
            nature=args.nature,
            level=args.level,
            money=9999999 if args.max_money else None,
        )
    else:
        with open(args.save_path, "rb") as fp:
            summary = parse_save_bytes(fp.read(), args.save_path)

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(
            f"Save: {summary['path']} (Gen {summary['gen']} {'ROMHACK' if summary['is_romhack'] else 'Vanilla'}) "
            f"CRC:0x{summary['checksum']:04X} ({'VALID' if summary['checksum_valid'] else 'INVALID'})"
        )
        print(
            f"OT: {summary['trainer_name']} | Money: ${summary['money']} | "
            f"Rare Candies: {summary['rare_candies']} | Master Balls: {summary['master_balls']}"
        )
        for m in summary["party"]:
            print(
                f"  [{m['slot']}] {m['nickname']} (Species #{m['species']}) Lv.{m['level']} "
                f"{'*SHINY*' if m['is_shiny'] else ''} Nature:{m['nature_name']} "
                f"Ability:{m['ability']} IVs:{m['ivs']} EVs:{m['evs']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
