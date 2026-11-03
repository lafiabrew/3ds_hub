# Troubleshooting, Crash Dump & Recovery Playbook (`docs/TROUBLESHOOTING.md`)

Symptom-to-solution runbook for diagnosing 3DS CFW issues, decoding Luma3DS exception dumps, restoring `.bak` save backups, and fixing wireless transfers.

---

## 1. HOME Menu Icons, Banners & "Black Squares"

| Symptom | Root Cause | Exact Fix |
|---|---|---|
| **Black square / blank icon on 3DS HOME Menu** | Leftover test installation (`UniqueId 0x0D3D0..0x0D3DF`) or interrupted FBI download in `import.db`. | 1. Open **SysDash** on your 3DS and press **`SELECT`** (purges all `0x0D3D*` titles, tickets, and pending imports).<br/>2. Or switch to SysDash's **`TITLES:R`** tab (where `[OLD]` / `0 KB` entries are sorted to the top) and press **`A`**.<br/>3. If an icon is still cached by the HOME Menu, reboot while holding **`L + R + Down + B`** until the HOME Menu loads. |
| **Reinstalled a `.cia` via QR code, but the old icon/banner still appears** | The 3DS HOME Menu caches SMDH icons inside `IconCache.dat` keyed by `UniqueId` and does not invalidate the cache on same-ID overwrite. | Delete the old title first in **SysDash (`TITLES:R` → `A`)** or **FBI → Titles → Delete Title And Ticket**, then scan the QR code from `http://<pc-ip>:8765/`. |

---

## 2. Decoding Luma3DS Crash Dumps (`luma/dumps/arm11/*.dmp` & `errdisp.txt`)

When a game, ROM hack, or homebrew crashes, Luma3DS writes a binary exception dump to `sdmc:/luma/dumps/arm11/` (or `arm9/`).

### Step 1: Pull the Crash Dump Wirelessly
Open **3DS Drop** on your 3DS and run on your PC:
```bash
python3 pc_companion/sd_scanner.py --url http://192.168.0.170:8766 --dump-logs ./sd_logs
```

### Step 2: Match the Process / Title ID
| Faulting Process / Title ID | Common Cause | Fix |
|---|---|---|
| **`loader`** (`ARM11 prefetch/data abort`) | Corrupted `.3dsx` or broken `code.bin` inside `sdmc:/luma/titles/<TitleID>/` when launching a game. | Open **SysDash** → `L:MODS` tab → press **`A`** on that game's TitleID to disable its LayeredFS mod and test if the vanilla game boots. |
| **`00040000001B5000` (or other Pokémon TitleID)** | Incompatible Luma LayeredFS `romfs` / `code.bin` mismatch with installed game update (e.g. Ultra Sun v1.2 patch vs v1.0 hack). | Ensure your game update version in **FBI → Titles** matches the version required by the ROM hack author, or toggle the mod off in **SysDash**. |
| **`pm` / `menu`** | Bad cheat code address in `sdmc:/luma/titles/<TitleID>/cheats.txt`. | Open Rosalina (`L + Down + Select` → **Cheats**) and uncheck individual cheats, or regenerate clean cheats in **PokeRNG**. |

---

## 3. Restoring `.bak` Save & Play Coin Backups

Every tool in this workspace (`PokeDash`, `3DS Drop`, `NetPass`, `PokeRNG`, `pkhex_web.py`) writes an automatic **`.bak` backup** before modifying any file.

### Restore via `3DS Drop` Web UI (No SD Card Removal):
1. Open **3DS Drop** on your 3DS and visit `http://<3ds-ip>:8766/` on your PC.
2. Find `<save>.bak` (e.g., `3ds/Checkpoint/saves/0x1B50_UltraSun/main.bak` or `3ds/netpass/gamecoin.dat.bak`) in the file table and click **Download**.
3. Select the downloaded `.bak` file in the **Upload** box, set the target path to the original filename (without `.bak`), and click **Upload Atomically to 3DS SD**.
4. For 3DS games, open **Checkpoint**, select the game, and **Restore** the save slot into the cartridge/SD title.

---

## 4. Wireless & Network Troubleshooting (`serve_3ds.py` & `3DS Drop`)

| Symptom | Cause | Fix |
|---|---|---|
| **FBI QR scan fails with `HTTP 404` or connection timeout** | PC firewall blocking port `8765` or 3DS and PC are on isolated Wi-Fi guest/5 GHz VLANs. | Ensure the 3DS is connected to a **2.4 GHz (802.11b/g)** SSID on the same LAN subnet as your PC (`192.168.0.x`), and allow TCP ports `8765` and `8766`. |
| **`Connection reset by peer` on older `3ds_drop` builds** | Older builds called `close(cfd)` before `soc:u` finished draining the 2.4 GHz send buffer. | Update `3DS Drop` to the latest build (`c7477f8+`), which uses 1,024-byte chunked sends + `shutdown(cfd, SHUT_WR)` drain; `sd_scanner.py` also includes automatic retry/salvage logic. |
| **WiGLE upload fails in `pc_companion/wigle_sync.py`** | Missing `WIGLE_API_NAME` (`AID...`) / `WIGLE_API_TOKEN` or CSV has `0` observations. | Press **`A`** in `WiGLE 3DS` to log at least 1 AP sweep first, then pass `--api-name AID... --api-token ...` from [wigle.net/account](https://wigle.net/account). |
