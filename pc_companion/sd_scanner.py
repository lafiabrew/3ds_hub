#!/usr/bin/env python3
"""
3DS SD Card & Diagnostic Log Scanner (pc_companion/sd_scanner.py)

Scans either:
  1. A local/mounted 3DS microSD card directory (--sd-root /path/to/sd)
     or auto-detected Linux mount points (/media/$USER/*, /run/media/$USER/*, /mnt/*), OR
  2. A live 3DS running `3ds_drop` over Wi-Fi (--url http://<3ds-ip>:8766)

Produces a complete inventory of:
  - Pokémon & game saves (Checkpoint, TWiLightMenu++, GBA/open_agb_firm)
  - Luma3DS LayeredFS ROM hack folders (luma/titles/<TitleID> and luma/titles_disabled/<TitleID>)
  - Luma3DS ARM9/ARM11 exception dumps (.dmp), errdisp.txt, and homebrew .log files
and can pull/bundle all logs + saves into a local diagnostic directory (--dump-logs <dir>)
so you or a coding agent can immediately inspect crash logs or SD layout.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import socket
import struct
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

KNOWN_TITLES = {
    "0004000000055D00": "Pokemon X (Eternal X / Wilting Y)",
    "0004000000055E00": "Pokemon Y (Wilting Y)",
    "000400000011C400": "Pokemon Omega Ruby (Rutile Ruby)",
    "000400000011C500": "Pokemon Alpha Sapphire (Star Sapphire)",
    "0004000000164800": "Pokemon Sun (Nova Sun)",
    "0004000000175E00": "Pokemon Moon (Umbra Moon)",
    "00040000001B5000": "Pokemon Ultra Sun (Photonic Sun)",
    "00040000001B5100": "Pokemon Ultra Moon (Prismatic Moon)",
    "0004000000030800": "Mario Kart 7 (CTGP-7)",
}


def parse_luma_dmp_bytes(raw: bytes) -> str:
    if len(raw) >= 24:
        magic, _ver, proc, exc, pc, lr = struct.unpack("<IIIIII", raw[:24])
        exc_map = {0: "FIQ", 1: "UNDEF", 2: "PREFETCH_ABORT", 3: "DATA_ABORT"}
        return (
            f"LUMA_DMP HDR:0x{magic:08X} ARM{proc if proc in (9, 11) else 11} "
            f"{exc_map.get(exc, f'EXC_{exc}')} PC:0x{pc:08X} LR:0x{lr:08X}"
        )
    return "LUMA_DMP (short)"


def auto_detect_sd_mount() -> Optional[str]:
    user = getpass.getuser()
    candidates = [
        f"/run/media/{user}",
        f"/media/{user}",
        "/media",
        "/mnt",
    ]
    for base in candidates:
        if not os.path.isdir(base):
            continue
        try:
            for entry in os.listdir(base):
                full = os.path.join(base, entry)
                if os.path.isdir(full) and (
                    os.path.isdir(os.path.join(full, "Nintendo 3DS"))
                    or os.path.isdir(os.path.join(full, "luma"))
                    or os.path.isdir(os.path.join(full, "3ds"))
                ):
                    return full
        except OSError:
            continue
    return None


def scan_local_sd(sd_root: str) -> Dict[str, Any]:
    sd_root = os.path.abspath(sd_root)
    files: List[Dict[str, Any]] = []
    logs: List[Dict[str, Any]] = []
    layeredfs_mods: List[Dict[str, Any]] = []

    for subdir, enabled in (("luma/titles", True), ("luma/titles_disabled", False)):
        tdir = os.path.join(sd_root, subdir)
        if os.path.isdir(tdir):
            for tid in sorted(os.listdir(tdir)):
                full_tid = os.path.join(tdir, tid)
                if os.path.isdir(full_tid) and not tid.startswith("."):
                    layeredfs_mods.append(
                        {
                            "title_id": tid.upper(),
                            "title_name": KNOWN_TITLES.get(tid.upper(), "Custom LayeredFS Title"),
                            "enabled": enabled,
                            "has_romfs": os.path.isdir(os.path.join(full_tid, "romfs")),
                            "has_code_bin": os.path.isfile(os.path.join(full_tid, "code.bin")),
                        }
                    )

    for root, dirs, filenames in os.walk(sd_root):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fn in sorted(filenames):
            if fn.startswith("."):
                continue
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, sd_root).replace("\\", "/")
            try:
                sz = os.path.getsize(full)
            except OSError:
                continue

            cat = "other"
            if (
                "Checkpoint/saves" in rel
                or fn in ("main", "sav.dat")
                or fn.endswith((".sav", ".dsv", ".srm"))
            ):
                cat = "save"
            elif "luma/titles" in rel:
                cat = "layeredfs_mod"
            elif (
                fn.endswith((".dmp", ".log"))
                or fn in ("errdisp.txt", "crash.txt", "diagnostic_snapshot.json")
            ):
                cat = "log"
            elif "screenshots" in rel:
                cat = "screenshot"

            files.append({"path": rel, "size": sz, "category": cat})

            if cat == "log":
                try:
                    with open(full, "rb") as fp:
                        raw = fp.read(512)
                    if fn.endswith(".dmp"):
                        excerpt = parse_luma_dmp_bytes(raw)
                    else:
                        excerpt = raw.decode("utf-8", errors="replace").strip().replace("\n", " | ")[:200]
                except OSError:
                    excerpt = "unreadable"
                logs.append(
                    {
                        "path": rel,
                        "size": sz,
                        "type": "crash_dump" if fn.endswith(".dmp") else "log",
                        "excerpt": excerpt,
                    }
                )

    return {
        "source": "local",
        "sd_root": sd_root,
        "total_files": len(files),
        "files": files,
        "layeredfs_mods": layeredfs_mods,
        "logs": logs,
    }


def _http_get_bytes(url: str, timeout: float = 4.0) -> bytes:
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 80
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"

    chunks: List[bytes] = []
    for _attempt in range(3):
        chunks.clear()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            s.connect((host, port))
            req = f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
            s.sendall(req.encode("utf-8"))
            while True:
                try:
                    data = s.recv(4096)
                    if not data:
                        break
                    chunks.append(data)
                except ConnectionResetError:
                    break
                except socket.timeout:
                    break
        finally:
            s.close()
        raw = b"".join(chunks)
        if b"\r\n\r\n" in raw:
            hdr_bytes, body = raw.split(b"\r\n\r\n", 1)
            hdr_text = hdr_bytes.decode("utf-8", errors="replace")
            first_line = hdr_text.splitlines()[0] if hdr_text else ""
            if " 400 " in first_line:
                raise urllib.error.HTTPError(url, 400, "Bad Request", {}, None)
            if " 404 " in first_line:
                raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
            if len(body) > 0:
                return body
    return b""


def _http_get_json(url: str, timeout: float = 4.0) -> Dict[str, Any]:
    raw_body = _http_get_bytes(url, timeout=timeout)
    text = raw_body.decode("utf-8", errors="replace").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Salvage truncated JSON array if legacy 3ds_drop closed socket mid-transfer
        if '"files":[' in text and not text.endswith("}"):
            last_obj = text.rfind("}")
            if last_obj > 0:
                salvaged = text[: last_obj + 1] + '],"total_files":-1,"truncated":true}'
                try:
                    return json.loads(salvaged)
                except json.JSONDecodeError:
                    pass
        if '"logs":[' in text and not text.endswith("}"):
            last_obj = text.rfind("}")
            if last_obj > 0:
                salvaged = text[: last_obj + 1] + '],"log_count":-1,"truncated":true}'
                try:
                    return json.loads(salvaged)
                except json.JSONDecodeError:
                    pass
        return {"raw_partial": text}


def scan_remote_3ds(base_url: str) -> Dict[str, Any]:
    base_url = base_url.rstrip("/")
    scan_data = _http_get_json(f"{base_url}/api/scan")
    logs_data = _http_get_json(f"{base_url}/api/logs")
    return {
        "source": "remote_3ds_drop",
        "url": base_url,
        "sd_root": scan_data.get("sd_root", "sdmc:"),
        "total_files": scan_data.get("total_files", 0),
        "files": scan_data.get("files", []),
        "logs": logs_data.get("logs", []),
    }


def harvest_logs_to_dir(report: Dict[str, Any], out_dir: str) -> List[str]:
    os.makedirs(out_dir, exist_ok=True)
    saved: List[str] = []

    report_path = os.path.join(out_dir, "sd_diagnostic_report.json")
    with open(report_path, "w", encoding="utf-8") as fp:
        json.dump(report, fp, indent=2)
    saved.append(report_path)

    for log_entry in report.get("logs", []):
        rel = log_entry.get("path", "")
        if not rel or ".." in rel or rel.startswith("/"):
            continue
        dest = os.path.join(out_dir, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if report.get("source") == "remote_3ds_drop":
            base_url = report["url"]
            encoded = urllib.parse.quote(rel)
            raw = _http_get_bytes(f"{base_url}/api/pull?path={encoded}")
            with open(dest, "wb") as fp:
                fp.write(raw)
            saved.append(dest)
        elif report.get("source") == "local":
            src = os.path.join(report["sd_root"], rel)
            if os.path.isfile(src):
                with open(src, "rb") as sfp, open(dest, "wb") as dfp:
                    dfp.write(sfp.read())
                saved.append(dest)

    return saved


def push_file_to_remote(base_url: str, local_path: str, remote_rel_path: str) -> Dict[str, Any]:
    base_url = base_url.rstrip("/")
    with open(local_path, "rb") as fp:
        payload = fp.read()
    encoded = urllib.parse.quote(remote_rel_path)
    req = urllib.request.Request(
        f"{base_url}/api/push?path={encoded}",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/octet-stream", "Content-Length": str(len(payload))},
    )
    with urllib.request.urlopen(req, timeout=3.0) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Scan a 3DS SD card (local mount or live 3ds_drop server) and harvest logs.")
    parser.add_argument("--sd-root", help="Path to local or mounted 3DS SD card root")
    parser.add_argument("--url", help="URL of live 3ds_drop server (e.g. http://192.168.1.50:8766)")
    parser.add_argument("--dump-logs", help="Directory to save harvested crash dumps, logs, and sd_diagnostic_report.json")
    parser.add_argument("--json", action="store_true", help="Print full JSON report to stdout")
    args = parser.parse_args(argv)

    if args.url:
        report = scan_remote_3ds(args.url)
    else:
        sd_root = args.sd_root or auto_detect_sd_mount()
        if not sd_root or not os.path.isdir(sd_root):
            print("ERROR: No --sd-root or --url specified and no mounted 3DS SD card auto-detected.", file=sys.stderr)
            return 1
        report = scan_local_sd(sd_root)

    if args.dump_logs:
        saved = harvest_logs_to_dir(report, args.dump_logs)
        report["harvested_files"] = saved

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"=== 3DS SD Scanner ({report['source']}) ===")
        print(f"Root: {report.get('sd_root')} | Total files: {report.get('total_files')}")
        saves = [f for f in report.get("files", []) if f.get("category") == "save"]
        print(f"Saves found ({len(saves)}):")
        for s in saves:
            print(f"  - {s['path']} ({s['size']} B)")
        logs = report.get("logs", [])
        print(f"Diagnostic / Crash Logs ({len(logs)}):")
        for l in logs:
            print(f"  - {l['path']} [{l.get('type')}]: {l.get('excerpt')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
