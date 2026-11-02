#!/usr/bin/env python3
"""
WiGLE.net Wardriving Account Sync & Multipart CSV Uploader (`pc_companion/wigle_sync.py`)

Connects your Nintendo 3DS (`3ds_wigle` + `3ds_drop`) to https://wigle.net so you earn
WiGLE points and global/monthly leaderboard rank for every 3DS wardriving session:
  1. Pulls `3ds/wigle/wigle_3ds_session.csv` (and `3ds/wigle/wigle_account.json`) from either:
     - Your live 3DS running `3ds_drop` (`--url http://<3ds-ip>:8766`), OR
     - A local/mounted SD card directory (`--sd-root /path/to/sd`)
  2. Validates the `WigleWifi-1.4` 2-line header and observation rows (rejecting empty or
     malformed CSVs before upload).
  3. Uploads the CSV via `multipart/form-data` (`POST /api/v2/file/upload`) with HTTP Basic Auth
     (`WIGLE_API_NAME` / `WIGLE_API_TOKEN` from https://wigle.net/account or `--api-name` / `--api-token`).
  4. Queries `/api/v2/stats/user` for your latest WiGLE username, global rank, monthly rank, and
     discovered Wi-Fi count, writes `3ds/wigle/wigle_account.json`, and pushes it back to the 3DS!
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

import sd_scanner

DEFAULT_WIGLE_API_BASE = "https://api.wigle.net"


def validate_wigle_csv(csv_bytes: bytes) -> Tuple[bool, str, int]:
    """Validate WigleWifi-1.4 2-line header and count data rows.
    Returns (is_valid, reason, data_row_count).
    """
    if not csv_bytes:
        return False, "empty_csv", 0
    try:
        text = csv_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return False, "invalid_utf8", 0

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return False, "missing_wigle_two_line_header", 0
    if not lines[0].startswith("WigleWifi-1.4,"):
        return False, "invalid_preheader_magic", 0
    expected_cols = (
        "MAC,SSID,AuthMode,FirstSeen,Channel,RSSI,"
        "CurrentLatitude,CurrentLongitude,AltitudeMeters,AccuracyMeters,Type"
    )
    if lines[1] != expected_cols:
        return False, "invalid_column_header", 0

    data_rows = 0
    for row in lines[2:]:
        parts = row.split(",")
        if len(parts) != 11 or ":" not in parts[0]:
            return False, f"malformed_observation_row:{row[:32]}", 0
        data_rows += 1

    if data_rows == 0:
        return False, "zero_observations", 0
    return True, "ok", data_rows


def _basic_auth_header(api_name: str, api_token: str) -> str:
    if not api_name or not api_token or ":" in api_name:
        raise ValueError("Invalid WiGLE API credentials (expected AID... and token)")
    raw = f"{api_name}:{api_token}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def upload_csv_to_wigle(
    csv_bytes: bytes,
    filename: str,
    api_name: str,
    api_token: str,
    api_base: str = DEFAULT_WIGLE_API_BASE,
    donate: bool = True,
) -> Dict[str, Any]:
    ok, reason, row_count = validate_wigle_csv(csv_bytes)
    if not ok:
        raise ValueError(f"Refusing to upload invalid WiGLE CSV ({reason})")

    auth_hdr = _basic_auth_header(api_name, api_token)
    boundary = f"----LafiaBrewWiGLEBoundary{int(time.time() * 1000)}"
    body_parts: List[bytes] = []

    # donate field
    body_parts.append(f"--{boundary}\r\n".encode("ascii"))
    body_parts.append(b'Content-Disposition: form-data; name="donate"\r\n\r\n')
    body_parts.append((b"on" if donate else b"off") + b"\r\n")

    # file field
    body_parts.append(f"--{boundary}\r\n".encode("ascii"))
    body_parts.append(
        f'Content-Disposition: form-data; name="file"; filename="{os.path.basename(filename)}"\r\n'
        f"Content-Type: text/csv\r\n\r\n".encode("utf-8")
    )
    body_parts.append(csv_bytes)
    if not csv_bytes.endswith(b"\n"):
        body_parts.append(b"\r\n")
    else:
        body_parts.append(b"\r\n")
    body_parts.append(f"--{boundary}--\r\n".encode("ascii"))
    payload = b"".join(body_parts)

    url = f"{api_base.rstrip('/')}/api/v2/file/upload"
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Authorization": auth_hdr,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
            "User-Agent": "lafiabrew-3ds-wigle/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=10.0) as resp:
        res_data = json.loads(resp.read().decode("utf-8", errors="replace"))
    res_data["validated_rows"] = row_count
    return res_data


def fetch_wigle_user_stats(
    api_name: str,
    api_token: str,
    api_base: str = DEFAULT_WIGLE_API_BASE,
) -> Dict[str, Any]:
    auth_hdr = _basic_auth_header(api_name, api_token)
    url = f"{api_base.rstrip('/')}/api/v2/stats/user"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": auth_hdr,
            "Accept": "application/json",
            "User-Agent": "lafiabrew-3ds-wigle/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=10.0) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="replace"))

    stats = data.get("statistics", data)
    return {
        "username": str(data.get("user") or stats.get("userName") or "WIGLE_USER").upper()[:31],
        "api_name": api_name[:35],
        "rank": int(stats.get("rank", 0)),
        "month_rank": int(stats.get("monthRank", 0)),
        "discovered_wifi": int(stats.get("discoveredWiFi", 0)),
    }


def sync_3ds_wigle(
    sd_root: Optional[str] = None,
    drop_url: Optional[str] = None,
    api_name: str = "",
    api_token: str = "",
    api_base: str = DEFAULT_WIGLE_API_BASE,
) -> Dict[str, Any]:
    rel_csv = "3ds/wigle/wigle_3ds_session.csv"
    rel_acct = "3ds/wigle/wigle_account.json"

    if drop_url:
        base = drop_url.rstrip("/")
        csv_bytes = sd_scanner._http_get_bytes(f"{base}/api/pull?path={urllib.parse.quote(rel_csv)}")
        try:
            acct_raw = sd_scanner._http_get_bytes(f"{base}/api/pull?path={urllib.parse.quote(rel_acct)}")
            prev_acct = json.loads(acct_raw.decode("utf-8", errors="replace"))
        except Exception:
            prev_acct = {}
    elif sd_root:
        csv_path = os.path.join(sd_root, rel_csv)
        with open(csv_path, "rb") as fp:
            csv_bytes = fp.read()
        acct_path = os.path.join(sd_root, rel_acct)
        if os.path.isfile(acct_path):
            with open(acct_path, "r", encoding="utf-8") as fp:
                prev_acct = json.load(fp)
        else:
            prev_acct = {}
    else:
        raise ValueError("Specify either --sd-root or --url")

    upload_res = upload_csv_to_wigle(
        csv_bytes, "wigle_3ds_session.csv", api_name, api_token, api_base=api_base
    )
    user_stats = fetch_wigle_user_stats(api_name, api_token, api_base=api_base)

    now_utc = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    new_acct = {
        "username": user_stats["username"],
        "api_name": api_name,
        "rank": user_stats["rank"],
        "month_rank": user_stats["month_rank"],
        "discovered_wifi": user_stats["discovered_wifi"],
        "total_uploads": int(prev_acct.get("total_uploads", 0)) + 1,
        "last_sync_utc": now_utc,
        "last_uploaded_rows": upload_res.get("validated_rows", 0),
    }

    if drop_url:
        tmp_acct = "/tmp/wigle_account_sync.json"
        with open(tmp_acct, "w", encoding="utf-8") as fp:
            json.dump(new_acct, fp, indent=2)
        sd_scanner.push_file_to_remote(drop_url, tmp_acct, rel_acct)
    elif sd_root:
        acct_path = os.path.join(sd_root, rel_acct)
        os.makedirs(os.path.dirname(acct_path), exist_ok=True)
        tmp_path = f"{acct_path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as fp:
            json.dump(new_acct, fp, indent=2)
        os.replace(tmp_path, acct_path)

    return {"status": "ok", "upload": upload_res, "account": new_acct}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Upload 3DS WiGLE v1.4 CSV logs to wigle.net and sync user rank/points back to 3DS.")
    parser.add_argument("--sd-root", help="Local or mounted 3DS SD card root")
    parser.add_argument("--url", help="Live 3ds_drop URL (e.g. http://192.168.0.170:8766)")
    parser.add_argument("--api-name", default=os.environ.get("WIGLE_API_NAME", ""), help="WiGLE API Name (AID... from wigle.net/account)")
    parser.add_argument("--api-token", default=os.environ.get("WIGLE_API_TOKEN", ""), help="WiGLE API Token")
    parser.add_argument("--api-base", default=DEFAULT_WIGLE_API_BASE, help="WiGLE API base URL (default: https://api.wigle.net)")
    args = parser.parse_args(argv)

    res = sync_3ds_wigle(
        sd_root=args.sd_root,
        drop_url=args.url,
        api_name=args.api_name,
        api_token=args.api_token,
        api_base=args.api_base,
    )
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
