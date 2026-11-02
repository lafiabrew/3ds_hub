# IMPLEMENTATION_PLAN.md — 3DS CFW, PKHaX & Diagnostic Homebrew Suite

## Overview
Build a complete Nintendo 3DS CFW & Pokémon ROM-Hack Homebrew Suite in this workspace:
1. **`3ds_pokedash/`** (`CTR-P-PKDS`, `0x0D3D1`): On-3DS PKHaX Save Inspector & Surgical Editor (Gen 3/4/5/6/7 + ROM hacks across `Checkpoint`, `TWiLightMenu++`, and `open_agb_firm`/GBA paths) + Dual-Screen Type Matchup, Nature, Shiny Odds & EV Calculator, with automatic `.bak` backup and block checksum recalculation.
2. **`3ds_sysdash/`** (`CTR-P-SYSD`, `0x0D3D2`): CFW Hardware/Battery/SD Dashboard, 1-button Luma3DS LayeredFS ROM-Hack Mod Toggler (`sdmc:/luma/titles/<TitleID>` <-> `titles_disabled`), and SD & Crash Log Snapshot Exporter (`luma/errdisp.txt`, `luma/dumps/arm11/*.dmp`, homebrew `.log` files).
3. **`3ds_drop/`** (`CTR-P-DROP`, `0x0D3D3`): Wireless LAN HTTP/JSON SD Card Scanner, Log Harvester, and Atomic Save/ROM/Mod File Drop Server (`:8766`) with path-traversal protection and cooperative non-blocking `poll()` sockets.
4. **`pc_companion/`**: Host tools for scanning a local SD card or live `3ds_drop` 3DS over Wi-Fi (`sd_scanner.py` — so the user or coding agent can inspect SD layout and pull logs on demand), editing Pokémon saves via CLI or Browser UI (`pkhex_web.py`), and patching `.ips`/`.bps` ROM hacks + staging Luma3DS LayeredFS TitleID folders (`romhack_tool.py`).

## Ruggedness Gate Record
- **Date:** 2026-11-02
- **Scope:** `specs/01-3ds-homebrew-suite.md` and `IMPLEMENTATION_PLAN.md` (Plan-exit gate)
- **Source:** `/rugged plan` recorded in `.wgm/rugged/2026-11-02-plan-exit.md`
- **Current Verdict:** **RUGGED**
  1. **Actual operator & environment:** Solo CFW 3DS operator running Luma3DS, Checkpoint, and TWiLightMenu++ with custom Pokémon ROM hacks on a FAT32 microSD card over 2.4 GHz 3DS Wi-Fi, plus a Linux x86_64 host with rootless Podman (`localhost/pieceduel-3ds-toolchain:latest`).
  2. **Bottleneck decomposition:** *Intrinsic design constraint* (ROM-hack save layouts vary outside standard Pokémon party/box blocks) · *User capacity* (diagnosing crashes or LayeredFS conflicts on a 3DS without pulling the SD card is painful) · *Operational stress* (**Dominant**: in-place save writes or bad checksums corrupt saves; blocking sockets freeze `aptMainLoop()`; unsanitized HTTP paths risk directory traversal).
  3. **Simplify:** Use surgical block-only PKHaX edits (leaving unknown ROM-hack event/script blocks untouched) + mandatory `.bak` copy + atomic `.tmp`->`rename()`; use non-blocking `O_NONBLOCK` + `poll()` ($\le 250\text{ ms}$) in `3ds_drop`; use pure-Python CBMD `.bnr` generation inside `meta/generate_assets.py` so container builds never fail on `bannertool` glibc mismatches.
  4. **Exact check:** Every task runs host `gcc -std=c11 -Wall -Wextra -Werror -fsanitize=address,undefined` unit/UI tests, rootless Podman `devkitARM` cross-compilation (`make 3ds && make verify-3ds`), and end-to-end live daemon/HTTP/checksum/traversal tests (`python3 -m unittest discover -s pc_companion/tests -v`).
  5. **Verdict:** **RUGGED**.

---

## Tasks

### T1 — `3ds_pokedash`: PKHaX Save Engine, Multi-Path Scanner, Dual-Screen UI & ARM11 `.cia`/`.3dsx` (`pokedash`)
- **Status:** done
- **Objective:** Scaffold and implement `3ds_pokedash/` with a surgical PKHaX save parser/editor supporting Gen 3 (`0x20000` GBA), Gen 4/5 (`0x80000` NDS), Gen 6 (`0x65600` XY / `0x76000` ORAS `BEEF`), Gen 7 (`0x6BE00` SM / `0x6CC00` USUM `BEEF`), and portable `.pkx`/`.pkhax` party/box slots across Checkpoint, TWiLightMenu++, and GBA SD paths, plus an interactive Type/Nature/Shiny/EV calculator, host ASan/UBSan test suite, and verified 3DS `.elf`/`.smdh`/`.3dsx`/`.cia` build (`UniqueId: 0x0D3D1`).
- **Files/areas:** `3ds_pokedash/include/`, `3ds_pokedash/src/`, `3ds_pokedash/tests/`, `3ds_pokedash/meta/`, `3ds_pokedash/scripts/verify-3ds-build.sh`, `3ds_pokedash/Makefile`
- **Validation command:** `make -C 3ds_pokedash test && make -C 3ds_pokedash 3ds && make -C 3ds_pokedash verify-3ds`
- **Evidence:** Exited 0 (`PASS: test_pokedash all PKHaX, ROM-hack safety, checksum, and UI checks succeeded.` + `PASS: Verified 3ds_pokedash ARM11 ELF, SMDH (0x36C0), 3DSX, and CIA (0x2020) artifacts.`). Ruggedness verdict: **RUGGED**.

### T2 — `3ds_sysdash`: CFW Hardware Inspector, Luma3DS LayeredFS Mod Toggler & SD/Log Snapshotter (`sysdash`)
- **Status:** done
- **Objective:** Scaffold and implement `3ds_sysdash/` to display 3DS hardware/battery/Wi-Fi/SD telemetry, discover and atomically toggle Luma3DS LayeredFS ROM hack folders (`sdmc:/luma/titles/<TitleID>` <-> `sdmc:/luma/titles_disabled/<TitleID>`), parse Luma crash dumps (`luma/errdisp.txt`, `luma/dumps/arm11/*.dmp`) and homebrew logs, export a full JSON + text diagnostic snapshot (`sdmc:/3ds/sysdash/diagnostic_snapshot.json`), and build verified 3DS `.elf`/`.smdh`/`.3dsx`/`.cia` artifacts (`UniqueId: 0x0D3D2`).
- **Files/areas:** `3ds_sysdash/include/`, `3ds_sysdash/src/`, `3ds_sysdash/tests/`, `3ds_sysdash/meta/`, `3ds_sysdash/scripts/verify-3ds-build.sh`, `3ds_sysdash/Makefile`
- **Validation command:** `make -C 3ds_sysdash test && make -C 3ds_sysdash 3ds && make -C 3ds_sysdash verify-3ds`
- **Evidence:** Exited 0 (`PASS: test_sysdash all LayeredFS toggle, crash dump parser, and snapshot checks succeeded.` + `PASS: Verified 3ds_sysdash ARM11 ELF, SMDH (0x36C0), 3DSX, and CIA (0x2020) artifacts.`). Ruggedness verdict: **RUGGED**.

### T3 — `3ds_drop`: Wireless LAN SD Scanner, Log Harvester & Atomic File/Save Drop Server (`drop`)
- **Status:** done
- **Objective:** Scaffold and implement `3ds_drop/` as a dual-screen 3DS app and headless host daemon (`--daemon --port 8766 --sd-root <dir>`) providing non-blocking HTTP/JSON endpoints (`/api/status`, `/api/scan`, `/api/logs`, `/api/pull`, `/api/push`) with strict `..` path traversal rejection, automatic `.bak` backup on save overwrites, and verified 3DS `.elf`/`.smdh`/`.3dsx`/`.cia` artifacts (`UniqueId: 0x0D3D3`).
- **Files/areas:** `3ds_drop/include/`, `3ds_drop/src/`, `3ds_drop/tests/`, `3ds_drop/meta/`, `3ds_drop/scripts/verify-3ds-build.sh`, `3ds_drop/Makefile`
- **Validation command:** `make -C 3ds_drop test && make -C 3ds_drop 3ds && make -C 3ds_drop verify-3ds`
- **Evidence:** Exited 0 (`PASS: test_drop all HTTP scan, log harvest, path-traversal guard, and atomic push/pull checks succeeded.` + `PASS: Verified 3ds_drop ARM11 ELF, SMDH (0x36C0), 3DSX, and CIA (0x2020) artifacts.`). Ruggedness verdict: **RUGGED**.

### T4 — `pc_companion/` + Workspace Integration & Demo Validation (`pc-companion-and-demo`)
- **Status:** done
- **Objective:** Build `pc_companion/sd_scanner.py` (local SD mount + remote `3ds_drop` scanner & log harvester), `pc_companion/pkhex_web.py` (CLI + Browser PKHaX editor with wireless `3ds_drop` pull/push), `pc_companion/romhack_tool.py` (`.ips`/`.bps` ROM patcher & Luma LayeredFS TitleID stager), root `Makefile` & `README.md` updates, and an end-to-end test suite (`pc_companion/tests/test_suite.py`) that exercises the full demo path across all 4 projects and `serve_3ds.py`.
- **Files/areas:** `pc_companion/sd_scanner.py`, `pc_companion/pkhex_web.py`, `pc_companion/romhack_tool.py`, `pc_companion/tests/test_suite.py`, `Makefile`, `README.md`, `serve_3ds.py`
- **Validation command:** `python3 -m unittest discover -s pc_companion/tests -v && python3 serve_3ds.py --list`
### T5 — `3ds_wigle`: WiGLE-Wifi-1.4 CSV Wardriver & 2.4 GHz / UDS Spectrum Radar (`wigle`)
- **Status:** done
- **Objective:** Build `3ds_wigle/` (`CTR-P-WIGL`, `0x0D3E4`) with `ac:u` + `nwm::UDS` 2.4 GHz beacon scanning, Ch 1–13 spectrum bars, and standards-compliant `WigleWifi-1.4` CSV output (`sdmc:/3ds/wigle/wigle_3ds_session.csv`).
- **Files/areas:** `3ds_wigle/`
- **Validation command:** `make -C 3ds_wigle test && make -C 3ds_wigle 3ds && make -C 3ds_wigle verify-3ds`
- **Evidence:** Exited 0 (`PASS: test_wigle` + `PASS: Verified 3ds_wigle ARM11 ELF, SMDH (0x36C0), 3DSX, and CIA (0x2020)`). Ruggedness verdict: **RUGGED**.

### T6 — `3ds_rngtool`: Pokémon RNG Shiny Frame Finder, TSV Calculator & Luma3DS `cheats.txt` Generator (`rngtool`)
- **Status:** done
- **Objective:** Scaffold and implement `3ds_rngtool/` (`CTR-P-PRNG`, `0x0D3E5`) to compute TSV (`(TID ^ SID) >> 4`) and Gen 7 `G7TID`, search Gen 3/4/5/6/7 RNG frames for Shiny + 6×31 IV / 0-Spe spreads, and atomically generate Luma3DS Rosalina `cheats.txt` plugin files (`<sd_root>/luma/titles/<TitleID>/cheats.txt`) for Pokémon titles & ROM hacks, with custom RNG/Dice/Sparkle icon & banner.
- **Files/areas:** `3ds_rngtool/include/`, `3ds_rngtool/src/`, `3ds_rngtool/tests/`, `3ds_rngtool/meta/`, `3ds_rngtool/scripts/verify-3ds-build.sh`, `3ds_rngtool/Makefile`
- **Validation command:** `make -C 3ds_rngtool test && make -C 3ds_rngtool 3ds && make -C 3ds_rngtool verify-3ds`
- **Evidence:** Exited 0 (`PASS: test_rngtool all TSV/G7TID, LCRNG shiny search, and Luma cheats.txt checks succeeded.` + `PASS: Verified 3ds_rngtool ARM11 ELF, SMDH (0x36C0), 3DSX, and CIA (0x2020) artifacts.`). Ruggedness verdict: **RUGGED**.

### T7 — `3ds_netpass`: Play Coin Maxer (300 Coins), Pedometer & StreetPass CECD Vault (`netpass`)
- **Status:** done
- **Objective:** Scaffold and implement `3ds_netpass/` (`CTR-P-SPAS`, `0x0D3E6`) to inspect/max 3DS Play Coins (`0..300`) with `.bak` backup, display Pedometer step history (`ptm:u`), and archive/restore StreetPass CECD inbox/outbox boxes (`<sd_root>/3ds/netpass/boxes/`), with custom Play Coin + StreetPass green beacon icon & banner.
- **Files/areas:** `3ds_netpass/include/`, `3ds_netpass/src/`, `3ds_netpass/tests/`, `3ds_netpass/meta/`, `3ds_netpass/scripts/verify-3ds-build.sh`, `3ds_netpass/Makefile`
- **Validation command:** `make -C 3ds_netpass test && make -C 3ds_netpass 3ds && make -C 3ds_netpass verify-3ds`
- **Evidence:** Exited 0 (`PASS: test_netpass all gamecoin.dat (0x4F00), .bak backup, and CECD box archive checks succeeded.` + `PASS: Verified 3ds_netpass ARM11 ELF, SMDH (0x36C0), 3DSX, and CIA (0x2020) artifacts.`). Ruggedness verdict: **RUGGED**.

### T8 — `3ds_padtest`: Circle Pad Drift, Gyro/Accel, Touchscreen & Dead-Pixel Hardware Lab (`padtest`)
- **Status:** done
- **Objective:** Scaffold and implement `3ds_padtest/` (`CTR-P-PADT`, `0x0D3E7`) to measure Circle Pad & C-Stick center bias/drift percentage and min/max excursion, test touchscreen drawing & button matrix, cycle full-screen dead-pixel patterns (`R`/`G`/`B`/`W`/`K`), and export `<sd_root>/3ds/padtest/hardware_report.json`, with custom Crosshair/Gamepad icon & banner.
- **Files/areas:** `3ds_padtest/include/`, `3ds_padtest/src/`, `3ds_padtest/tests/`, `3ds_padtest/meta/`, `3ds_padtest/scripts/verify-3ds-build.sh`, `3ds_padtest/Makefile`
- **Validation command:** `make -C 3ds_padtest test && make -C 3ds_padtest 3ds && make -C 3ds_padtest verify-3ds`
- **Evidence:** Exited 0 (`PASS: test_padtest all drift calculation, min/max excursion, and JSON report checks succeeded.` + `PASS: Verified 3ds_padtest ARM11 ELF, SMDH (0x36C0), 3DSX, and CIA (0x2020) artifacts.`). Ruggedness verdict: **RUGGED**.

### T9 — `lafiabrew` GitHub Organization Sorting, Repo Creation & Full Suite Verification (`lafiabrew-sync`)
- **Status:** done
- **Objective:** Update `Makefile`, `README.md`, and `pc_companion/tests/test_suite.py` to cover all 8 3DS apps (`0x0D3E0`..`0x0D3E7`) with concise HOME Menu titles/descriptions, initialize clean Git histories with `.gitignore` and `README.md` in each project + root `3ds_hub`, and push/sync all repositories to `https://github.com/orgs/lafiabrew/repositories`.
- **Files/areas:** `Makefile`, `README.md`, `pc_companion/tests/test_suite.py`, `3ds_*/.gitignore`, `3ds_*/README.md`
- **Validation command:** `make test && make verify-3ds && python3 serve_3ds.py --self-test && gh repo list lafiabrew --limit 20`
- **Evidence:** Exited 0 (All 8 3DS apps pass host ASan/UBSan tests, ARM11 `.elf`/`.smdh`/`.3dsx`/`.cia` verification, and `test_suite.py`; all 9 repos `3ds_hub`, `3ds_padtest`, `3ds_netpass`, `3ds_rngtool`, `3ds_wigle`, `3ds_drop`, `3ds_sysdash`, `3ds_pokedash`, and `3ds_pieceduel` pushed to `github.com/lafiabrew`). Ruggedness verdict: **RUGGED**.

### T10 — Unified SD Telemetry Logger (`<sd_root>/3ds/logs/<app>.log`) & Pass/Fail Harness Across All Apps (`unified-logging-and-ux`)
- **Status:** done
- **Objective:** Add a shared structured logger (`pk_log_event`) to `pk_platform.h` / `platform_3ds.c` / `platform_host.c` across all 7 utility apps (`3ds_pokedash`, `3ds_sysdash`, `3ds_drop`, `3ds_wigle`, `3ds_rngtool`, `3ds_netpass`, `3ds_padtest`) writing timestamped entries to `<sd_root>/3ds/logs/<app>.log`, overhaul `3ds_sysdash` (`SD_MAX_TITLES = 128`, sorting `[OLD]`/`0KB` black-box titles first, sliding 8-row viewport scroll + scrollbar + `D-Pad Left/Right` page jump + touch row mapping across `MODS`, `LOGS`, and `TITLES`), and add sliding viewport scrollbars + touch polish across `3ds_pokedash`, `3ds_rngtool`, `3ds_netpass`, and `3ds_padtest`.
- **Files/areas:** `3ds_*/include/pk_platform.h`, `3ds_*/src/platform_*.c`, `3ds_sysdash/`, `3ds_pokedash/`, `3ds_rngtool/`, `3ds_netpass/`, `3ds_padtest/`, `3ds_drop/`
- **Validation command:** `make test && make 3ds && make verify-3ds`
- **Evidence:** Exited 0 (`test_pokedash`, `test_sysdash`, `test_drop`, `test_wigle`, `test_rngtool`, `test_netpass`, `test_padtest` all passed positive & negative checks under ASan/UBSan and wrote `<sd_root>/3ds/logs/<app>.log`). Ruggedness verdict: **RUGGED**.

### T11 — WiGLE Account Sync, Multipart Upload & Rank/Points HUD (`3ds_wigle` + `pc_companion/wigle_sync.py`) (`wigle-account-sync`)
- **Status:** done
- **Objective:** Upgrade `3ds_wigle` to load/display WiGLE account status (`<sd_root>/3ds/wigle/wigle_account.json`: username, rank, points, discovered Wi-Fi count, last sync timestamp) with scrolling AP list + `B` button account reload, and create `pc_companion/wigle_sync.py` to pull `WigleWifi-1.4` CSVs from local SD or live `3ds_drop`, validate headers/rows, upload via `multipart/form-data` to `https://api.wigle.net/api/v2/file/upload` (with local mock server support for deterministic testing), fetch `/api/v2/stats/user`, and push `wigle_account.json` back to the 3DS.
- **Files/areas:** `3ds_wigle/include/wg_wigle.h`, `3ds_wigle/src/wigle.c`, `3ds_wigle/src/main.c`, `3ds_wigle/tests/test_wigle.c`, `pc_companion/wigle_sync.py`, `pc_companion/tests/test_suite.py`
- **Validation command:** `make -C 3ds_wigle test && make -C 3ds_wigle 3ds && make -C 3ds_wigle verify-3ds && python3 -m unittest discover -s pc_companion/tests -v`
- **Evidence:** Exited 0 (`test_wigle` + `test_05_wigle_sync_pass_and_fail_and_unified_logs` in `test_suite.py` passed). Ruggedness verdict: **RUGGED**.

### T12 — Multi-Persona & Multi-Round UX/Function/Vibe Audit, Docs Polish & `lafiabrew` Push (`multi-round-audit`)
- **Status:** done
- **Objective:** Conduct a 2-round, 5-persona review (CFW Power User · Pokémon ROM-Hack / RNG Player · Hardware/UX Designer · Systems/Security Engineer · Technical Writer Consolidator), remediate every finding discovered in Round 1, verify Round 2 reaches zero open agent actions, update all `README.md` and `docs/audit/` reports, and push all 9 repositories to `github.com/lafiabrew`.
- **Files/areas:** `docs/audit/2026-11-02_multi-round-ux-and-function-audit.md`, `README.md`, `AGENTS.md`, `3ds_*/README.md`, `IMPLEMENTATION_PLAN.md`
- **Validation command:** `make all && python3 serve_3ds.py --self-test`
- **Evidence:** Exited 0 (All 8 3DS apps + 5 Python integration tests + `serve_3ds.py --self-test` passed; Round 1 & Round 2 audit committed and pushed across all 9 `lafiabrew` repositories). Ruggedness verdict: **RUGGED**.
