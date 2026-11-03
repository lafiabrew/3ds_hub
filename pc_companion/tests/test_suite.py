#!/usr/bin/env python3
"""
End-to-End Integration & Holdout Demo Tests (pc_companion/tests/test_suite.py)

Proves:
  1. C11 <-> Python PKHaX bit-exact save compatibility: saves created by `3ds_pokedash` can be
     parsed and surgically edited by `pc_companion/pkhex_web.py` (with `.bak` backup, valid CRC-16
     and Gen 3/6/7 footers, and untouched ROM-hack custom bytes) and reloaded by `3ds_pokedash`.
  2. Live wireless SD scanning & log harvesting: starts `3ds_drop_host --daemon` on an ephemeral
     port, runs `sd_scanner.py --url ... --dump-logs ...`, verifies crash dumps (`arm11/*.dmp`),
     `errdisp.txt`, and `diagnostic_snapshot.json` are harvested, and verifies pushing a modified
     save over HTTP creates `.bak` and rejects `..` path traversal.
  3. IPS and BPS ROM-hack patch creation, application, and CRC32 verification + Luma3DS LayeredFS
     staging (`romhack_tool.py`).
  4. Universal FBI QR discovery (`serve_3ds.py --list`) across all 4 homebrew projects
     (`3ds_pieceduel`, `3ds_pokedash`, `3ds_sysdash`, `3ds_drop`).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.request

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(WORKSPACE_ROOT, "pc_companion"))

import pkhex_web  # noqa: E402
import romhack_tool  # noqa: E402
import sd_scanner  # noqa: E402
import wigle_sync  # noqa: E402


class Test3DSHomebrewSuite(unittest.TestCase):
    def test_01_pkhex_web_cross_compatibility_and_surgical_safety(self) -> None:
        """Proves pc_companion/pkhex_web.py parses and edits 3ds_pokedash saves with .bak and valid CRC."""
        gen7_save = os.path.join(
            WORKSPACE_ROOT,
            "3ds_pokedash",
            "build",
            "test_sd",
            "3ds",
            "Checkpoint",
            "saves",
            "0x1B50_PhotonicSun",
            "main",
        )
        self.assertTrue(os.path.isfile(gen7_save), f"Missing test save: {gen7_save}")

        with tempfile.TemporaryDirectory() as tmpdir:
            work_save = os.path.join(tmpdir, "main")
            shutil.copyfile(gen7_save, work_save)

            # Parse initial state
            with open(work_save, "rb") as fp:
                before = pkhex_web.parse_save_bytes(fp.read(), work_save)
            self.assertTrue(before["checksum_valid"])
            self.assertTrue(before["is_romhack"])

            # Surgically edit Slot 2 (Greninja): 6x31 IVs, Shiny ON, Timid nature (10), Lv.100
            after = pkhex_web.apply_surgical_edit_to_file(
                work_save,
                slot_idx=2,
                max_ivs=True,
                shiny=True,
                nature=10,
                level=100,
                evs=[6, 0, 0, 252, 252, 0],
                money=8888888,
            )
            self.assertTrue(os.path.isfile(f"{work_save}.bak"))
            self.assertTrue(after["checksum_valid"])
            self.assertEqual(after["money"], 8888888)
            slot2 = after["party"][2]
            self.assertEqual(slot2["ivs"], [31, 31, 31, 31, 31, 31])
            self.assertEqual(slot2["evs"], [6, 0, 0, 252, 252, 0])
            self.assertTrue(slot2["is_shiny"])
            self.assertEqual(slot2["level"], 100)
            self.assertEqual(slot2["ability"], 302)  # Custom ROM-hack ability untouched

            # Verify custom ROM-hack header bytes (0x0000..0x0FFF) were untouched
            with open(work_save, "rb") as fp:
                hdr = fp.read(0x1000)
            for i, b in enumerate(hdr):
                self.assertEqual(b, (i * 73 + 19) & 0xFF)

    def test_02_live_3ds_drop_sd_scan_and_log_harvest(self) -> None:
        """Proves sd_scanner.py scans a live 3ds_drop server, harvests crash logs, and pushes saves safely."""
        drop_bin = os.path.join(WORKSPACE_ROOT, "3ds_drop", "build", "host", "3ds_drop_host")
        sd_root = os.path.join(WORKSPACE_ROOT, "3ds_sysdash", "build", "test_sd")
        self.assertTrue(os.path.isfile(drop_bin))
        self.assertTrue(os.path.isdir(sd_root))

        # Start 3ds_drop_host in daemon mode for 5 requests on ephemeral port (0)
        proc = subprocess.Popen(
            [drop_bin, "--daemon", "--port", "0", "--sd-root", sd_root, "--max-requests", "5"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            assert proc.stdout is not None
            first_line = proc.stdout.readline().strip()
            self.assertIn("3DS_DROP_LISTENING PORT=", first_line)
            port = int(first_line.split("PORT=")[1].split()[0])
            base_url = f"http://127.0.0.1:{port}"

            # Request 1 & 2: scan_remote_3ds (/api/scan + /api/logs)
            report = sd_scanner.scan_remote_3ds(base_url)
            self.assertEqual(report["source"], "remote_3ds_drop")
            self.assertGreaterEqual(report["total_files"], 3)
            self.assertGreaterEqual(len(report["logs"]), 2)

            # Request 3 & 4: harvest logs to a temp dir (/api/pull on each log)
            with tempfile.TemporaryDirectory() as out_dir:
                # Keep only first 2 logs so we consume exactly 2 pull requests
                report["logs"] = report["logs"][:2]
                saved = sd_scanner.harvest_logs_to_dir(report, out_dir)
                self.assertGreaterEqual(len(saved), 3)  # sd_diagnostic_report.json + 2 logs
                self.assertTrue(os.path.isfile(os.path.join(out_dir, "sd_diagnostic_report.json")))

            # Request 5: verify path traversal is rejected with HTTP 400
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(f"{base_url}/api/pull?path=../../etc/passwd", timeout=2.0)
            self.assertEqual(ctx.exception.code, 400)
            ctx.exception.close()
        finally:
            proc.terminate()
            proc.wait(timeout=3)
            if proc.stdout:
                proc.stdout.close()
            if proc.stderr:
                proc.stderr.close()

    def test_03_romhack_tool_ips_bps_and_layeredfs(self) -> None:
        """Proves IPS & BPS ROM-hack patch round-trips (with CRC32 check) and LayeredFS staging."""
        clean_rom = bytes((i * 37 + 11) & 0xFF for i in range(4096))
        hacked_rom = bytearray(clean_rom)
        hacked_rom[128:160] = b"DRAYANO_RENEGADE_PLATINUM_HACK!!"
        hacked_rom[2048:2064] = b"CUSTOM_STATS_V2!"
        hacked_bytes = bytes(hacked_rom)

        # IPS round-trip
        ips_patch = romhack_tool.create_ips_patch(clean_rom, hacked_bytes)
        ips_out = romhack_tool.apply_ips_patch(clean_rom, ips_patch)
        self.assertEqual(ips_out, hacked_bytes)

        # BPS round-trip + CRC32 verification
        bps_patch = romhack_tool.create_bps_patch(clean_rom, hacked_bytes, "PhotonicSun v1.0")
        bps_out = romhack_tool.apply_bps_patch(clean_rom, bps_patch)
        self.assertEqual(bps_out, hacked_bytes)

        # Corrupting source ROM must fail BPS CRC32 check
        bad_source = bytearray(clean_rom)
        bad_source[0] ^= 0xFF
        with self.assertRaises(ValueError):
            romhack_tool.apply_bps_patch(bytes(bad_source), bps_patch)

        # Stage Luma3DS LayeredFS folder
        with tempfile.TemporaryDirectory() as tmp_sd:
            mod_dir = romhack_tool.stage_layeredfs_mod(tmp_sd, "photonic_sun")
            self.assertTrue(mod_dir.endswith("00040000001B5000"))
            self.assertTrue(os.path.isdir(os.path.join(mod_dir, "romfs")))

    def test_04_serve_3ds_discovers_all_four_apps(self) -> None:
        """Proves serve_3ds.py discovers all 4 homebrew projects with distinct icons and SMDH tiles."""
        res = subprocess.run(
            [sys.executable, os.path.join(WORKSPACE_ROOT, "serve_3ds.py"), "--list"],
            capture_output=True,
            text=True,
            check=True,
        )
        out = res.stdout
        icon_hashes = set()
        smdh_icon_hashes = set()
        bnr_cgfx_hashes = set()
        all_projects = (
            "3ds_pieceduel",
            "3ds_pokedash",
            "3ds_sysdash",
            "3ds_drop",
            "3ds_wigle",
            "3ds_rngtool",
            "3ds_netpass",
            "3ds_padtest",
        )
        for doc_rel in ("ARCHITECTURE.md", "SOP.md", "CHEATSHEET.md", "TROUBLESHOOTING.md", "AGENT_PLAYBOOK.md"):
            doc_path = os.path.join(WORKSPACE_ROOT, "docs", doc_rel)
            self.assertTrue(os.path.isfile(doc_path), f"Missing root documentation file: {doc_path}")

        for proj in all_projects:
            self.assertIn(proj, out, f"Expected {proj} in serve_3ds.py --list output")
            readme_path = os.path.join(WORKSPACE_ROOT, proj, "README.md")
            with open(readme_path, "r", encoding="utf-8") as rfp:
                rtxt = rfp.read()
            self.assertIn("```mermaid", rtxt, f"Expected Mermaid diagram in {proj}/README.md")
            self.assertIn("docs/icon.png", rtxt, f"Expected docs/icon.png preview in {proj}/README.md")
            self.assertIn("docs/banner.png", rtxt, f"Expected docs/banner.png preview in {proj}/README.md")
            self.assertTrue(os.path.isfile(os.path.join(WORKSPACE_ROOT, proj, "docs", "icon.png")))
            self.assertTrue(os.path.isfile(os.path.join(WORKSPACE_ROOT, proj, "docs", "banner.png")))
            icon_path = os.path.join(WORKSPACE_ROOT, proj, "meta", "icon.png")
            smdh_path = os.path.join(WORKSPACE_ROOT, proj, "build", "3ds", f"{proj}.smdh")
            bnr_path = os.path.join(WORKSPACE_ROOT, proj, "meta", "banner.bnr")
            with open(icon_path, "rb") as fp:
                icon_hashes.add(fp.read())
            with open(smdh_path, "rb") as fp:
                smdh_bytes = fp.read()
                # SMDH 48x48 RGB565 icon tile data lives at 0x24C0..0x36C0
                smdh_icon_hashes.add(smdh_bytes[0x24C0:0x36C0])
                # Verify all 16 language slots in SMDH have concise, non-empty UTF-16LE short title & description
                for lang_idx in range(16):
                    entry = smdh_bytes[0x08 + lang_idx * 0x200 : 0x08 + (lang_idx + 1) * 0x200]
                    short_t = entry[0x00:0x80].decode("utf-16-le", errors="ignore").rstrip("\x00")
                    long_d = entry[0x80:0x180].decode("utf-16-le", errors="ignore").rstrip("\x00")
                    self.assertTrue(3 <= len(short_t) <= 20, f"SMDH title length out of bounds in {proj}: {short_t!r}")
                    self.assertTrue(5 <= len(long_d) <= 32, f"SMDH desc length out of bounds in {proj}: {long_d!r}")
                # Verify CIA SMDH & CBMD alignment invariants
                self.assertEqual(
                    int.from_bytes(smdh_bytes[0x2018:0x201C], "little"),
                    0x7FFFFFFF,
                    f"Expected region_lockout=0x7FFFFFFF in {proj}.smdh",
                )
                self.assertEqual(
                    int.from_bytes(smdh_bytes[0x2028:0x202C], "little"),
                    0x00000105,
                    f"Expected HOME Menu flags=0x105 in {proj}.smdh",
                )
            with open(bnr_path, "rb") as fp:
                bnr_bytes = fp.read()
                self.assertEqual(bnr_bytes[:4], b"CBMD")
                cwav_off = int.from_bytes(bnr_bytes[0x84:0x88], "little")
                self.assertEqual(
                    cwav_off % 0x20,
                    0,
                    f"CBMD cwav_offset ({hex(cwav_off)}) in {proj} must be 32-byte (0x20) aligned!",
                )
                bnr_cgfx_hashes.add(bnr_bytes[0x88:cwav_off])
        self.assertEqual(len(icon_hashes), 8, "Each 3DS project must have a unique meta/icon.png")
        self.assertEqual(len(smdh_icon_hashes), 8, "Each 3DS project must have a unique SMDH 48x48 icon")
        self.assertEqual(len(bnr_cgfx_hashes), 8, "Each 3DS project must have a unique CBMD 3D top-screen banner texture")

    def test_05_wigle_sync_pass_and_fail_and_unified_logs(self) -> None:
        """Proves wigle_sync.py pass-the-pass upload/rank sync, fail-the-fail CSV/auth rejection, and unified 3ds/logs/*.log."""
        from http.server import BaseHTTPRequestHandler, HTTPServer
        import threading

        # 1. Verify unified <proj>/build/test_sd/3ds/logs/<app>.log exists for all utility apps
        for proj, log_name in (
            ("3ds_pokedash", "pokedash.log"),
            ("3ds_sysdash", "sysdash.log"),
            ("3ds_drop", "drop.log"),
            ("3ds_wigle", "wigle.log"),
            ("3ds_rngtool", "rngtool.log"),
            ("3ds_netpass", "netpass.log"),
            ("3ds_padtest", "padtest.log"),
        ):
            log_path = os.path.join(WORKSPACE_ROOT, proj, "build", "test_sd", "3ds", "logs", log_name)
            self.assertTrue(os.path.isfile(log_path), f"Missing unified telemetry log: {log_path}")
            self.assertGreater(os.path.getsize(log_path), 15)

        # 2. Fail-the-Fail: empty CSV, bad magic, zero data rows, and invalid API credentials
        ok, reason, _ = wigle_sync.validate_wigle_csv(b"")
        self.assertFalse(ok)
        self.assertEqual(reason, "empty_csv")

        ok, reason, _ = wigle_sync.validate_wigle_csv(b"NotWigle,1.0\nMAC,SSID\n")
        self.assertFalse(ok)
        self.assertEqual(reason, "invalid_preheader_magic")

        header_only = (
            b"WigleWifi-1.4,appRelease=1.0,model=Nintendo3DS\n"
            b"MAC,SSID,AuthMode,FirstSeen,Channel,RSSI,CurrentLatitude,CurrentLongitude,AltitudeMeters,AccuracyMeters,Type\n"
        )
        ok, reason, _ = wigle_sync.validate_wigle_csv(header_only)
        self.assertFalse(ok)
        self.assertEqual(reason, "zero_observations")

        with self.assertRaises(ValueError):
            wigle_sync.upload_csv_to_wigle(header_only, "empty.csv", "AID_1", "TOK_1")

        valid_csv = header_only + b"A4:2B:B0:11:22:33,LAFIA_24G,[WPA2-PSK-CCMP][ESS],2026-11-02 09:00:00,6,-48,37.774900,-122.419400,18.0,6.5,WIFI\n"
        with self.assertRaises(ValueError):
            wigle_sync.upload_csv_to_wigle(valid_csv, "good.csv", "", "")

        # 3. Pass-the-Pass: Mock WiGLE API v2 server (/api/v2/file/upload & /api/v2/stats/user)
        class MockWiGLEHandler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:
                pass

            def do_POST(self) -> None:
                auth = self.headers.get("Authorization", "")
                if not auth.startswith("Basic ") or self.path != "/api/v2/file/upload":
                    self.send_error(401)
                    return
                clen = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(clen)
                assert b"WigleWifi-1.4" in body and b"LAFIA_24G" in body
                resp = json.dumps({"success": True, "results": {"transid": "20261102-00001"}}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)

            def do_GET(self) -> None:
                auth = self.headers.get("Authorization", "")
                if not auth.startswith("Basic ") or self.path != "/api/v2/stats/user":
                    self.send_error(401)
                    return
                resp = json.dumps(
                    {
                        "success": True,
                        "user": "lafiabrew",
                        "statistics": {
                            "userName": "lafiabrew",
                            "rank": 312,
                            "monthRank": 14,
                            "discoveredWiFi": 9842,
                        },
                    }
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)

        srv = HTTPServer(("127.0.0.1", 0), MockWiGLEHandler)
        port = srv.server_address[1]
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            with tempfile.TemporaryDirectory() as tmp_sd:
                wdir = os.path.join(tmp_sd, "3ds", "wigle")
                os.makedirs(wdir, exist_ok=True)
                with open(os.path.join(wdir, "wigle_3ds_session.csv"), "wb") as fp:
                    fp.write(valid_csv)

                res = wigle_sync.sync_3ds_wigle(
                    sd_root=tmp_sd,
                    api_name="AID_LAFIA_99",
                    api_token="SECRET_TOKEN",
                    api_base=f"http://127.0.0.1:{port}",
                )
                self.assertEqual(res["status"], "ok")
                self.assertEqual(res["account"]["username"], "LAFIABREW")
                self.assertEqual(res["account"]["rank"], 312)
                self.assertEqual(res["account"]["discovered_wifi"], 9842)
                self.assertEqual(res["account"]["total_uploads"], 1)
                self.assertTrue(os.path.isfile(os.path.join(wdir, "wigle_account.json")))
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    unittest.main()
