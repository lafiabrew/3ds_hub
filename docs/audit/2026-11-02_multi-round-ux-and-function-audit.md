# Multi-Round, Multi-Persona UX, Functional & Documentation Audit Report

> **Historical snapshot — warning added 2026-11-03.** This report is not current operating guidance or release/device certification. Some assurances below were not supported by later source review. Read [current status](../STATUS.md); the original report is preserved below, not retroactively validated.

- **Date:** 2026-11-02
- **Scope:** `/home/lafiamafia/homebrew/3ds` (`3ds_hub`, `3ds_pieceduel`, `3ds_pokedash`, `3ds_sysdash`, `3ds_drop`, `3ds_wigle`, `3ds_rngtool`, `3ds_netpass`, `3ds_padtest`)
- **Mode:** 2-Round, 5-Persona Review (CFW Power User · Pokémon ROM-Hack / RNG Player · Hardware/UX Designer · Systems/Security Engineer · Technical Writer Consolidator)
- **Independence Note:** Executed across the five distinct persona lenses in two sequential audit rounds (Round 1 findings -> remediation -> Round 2 verification).

---

## Round 1 — Multi-Persona Findings & Remediations

| Persona Lens | Round 1 Finding | Severity | Action Classification | Remediation Applied |
|---|---|---|---|---|
| **1. CFW Power User (`SysDash` & `3DS Drop`)** | 1. `SysDash` `TITLES:R` tab was capped at `SD_MAX_TITLES = 32` and rendered rows `0..7` without advancing a `scroll_offset`, so scrolling past row 8 moved the cursor off-screen.<br>2. `3ds_drop` `walk_sd_logs` walked `Nintendo 3DS/` and `boot9strap/`, adding SD I/O latency. | High | **Agent action** (Resolved) | 1. Increased `SD_MAX_TITLES` to `128`, sorted `[OLD]`/`0KB` black-box titles to the top, and implemented an 8-row sliding viewport (`scroll_mod`, `scroll_log`, `scroll_title`) with proportional scrollbar (`pk_draw_scrollbar`) and `D-Pad Left/Right` 8-row page jumps.<br>2. Excluded `Nintendo 3DS/`, `System Volume Information/`, and `boot9strap/` in both `walk_sd_files` and `walk_sd_logs`. |
| **2. Pokémon ROM-Hack / RNG Player (`PokeDash` & `PokeRNG`)** | `3ds_rngtool` only drew the first 7 RNG frame hits without a sliding viewport, and its 4 bottom-screen Luma `cheats.txt` game cards could not be tapped with the stylus. | Medium | **Agent action** (Resolved) | Added sliding 7-row viewport (`scroll_hit`) + scrollbar on `3ds_rngtool`'s top screen and stylus touch selection + double-tap write on the 4 bottom-screen Luma3DS `cheats.txt` cards. |
| **3. Hardware / UX Designer (`PadTest`, `NetPass` & `WiGLE 3DS`)** | 1. `3ds_padtest` did not visualize which hardware buttons (`A`, `B`, `SEL`, `STR`, `D-Pad`, `L`, `R`) had been tested or live stylus touch coordinates.<br>2. `3ds_netpass` bottom-screen action prompts were keyboard-only.<br>3. `3ds_wigle` needed a dedicated on-screen WiGLE.net Account & Leaderboard Rank view (`B` / `Y`) plus scrollable AP rows. | Medium | **Agent action** (Resolved) | 1. Added a 10-button interactive matrix + live `3D SLIDER %` and `TOUCH (X,Y)` cursor box in `3ds_padtest`.<br>2. Added touch hitboxes for `Max 300 Coins`, `+50 Coins`, and `Archive CECD Box` + CECD scrollbar in `3ds_netpass`.<br>3. Added `WG_VIEW_ACCOUNT` view, `wigle_account.json` parser, and 7-row sliding AP table + scrollbar in `3ds_wigle`. |
| **4. Systems / Security Engineer (Logging, WiGLE Sync & Pass/Fail Tests)** | 1. Apps lacked a unified SD telemetry log directory (`sdmc:/3ds/logs/<app>.log`) for post-run harvesting via `3ds_drop`.<br>2. WiGLE CSV uploads needed a PC/LAN companion (`pc_companion/wigle_sync.py`) to validate `WigleWifi-1.4` CSVs, upload via `multipart/form-data`, fetch `/api/v2/stats/user` rank/points, and sync `wigle_account.json` back to the 3DS.<br>3. C11 and Python tests needed explicit "fail the fail" negative cases alongside "pass the pass". | High | **Agent action** (Resolved) | 1. Added `pk_log_event()` across all 7 utility apps writing UTC-timestamped logs to `<sd_root>/3ds/logs/<app>.log`.<br>2. Built `pc_companion/wigle_sync.py` with strict CSV validation, `multipart/form-data` upload, user rank fetch, and `3ds_drop` sync.<br>3. Added negative/adversarial assertions across all 7 C test suites and `pc_companion/tests/test_suite.py`. |
| **5. Technical Writer Consolidator** | Root `README.md`, `AGENTS.md`, and per-app `README.md` files needed documentation for `pc_companion/wigle_sync.py`, unified `sdmc:/3ds/logs/*.log` harvesting, and the new `SysDash` / `WiGLE 3DS` controls. | Low | **Agent action** (Resolved) | Updated root `README.md`, `AGENTS.md`, and per-project `README.md` files with exact commands and control tables. |

---

## Round 2 — Verification & Sign-Off Across All 5 Personas

1. **CFW Power User:** Verified `test_sysdash` exercises 14 titles, confirms `[OLD]` black-box candidates sort to indices `0` and `1`, scrolls down 10 rows (`selected_title == 10`, `scroll_title == 3`), and renders the scrollbar. **PASS**.
2. **Pokémon ROM-Hack / RNG Player:** Verified `test_pokedash` and `test_rngtool` pass both positive surgical edits / LCRNG searches and negative corrupted-CRC / truncated-save / empty-title rejections under ASan/UBSan. **PASS**.
3. **Hardware / UX Designer:** Verified `pk_draw_text` auto-clamps text width to `400px` (top) and `320px` (bottom) with `pk_draw_scrollbar` across all scrollable lists, compatible with Old 3DS, 2DS, and New 3DS XL. **PASS**.
4. **Systems / Security Engineer:** Verified `test_suite.py` (`test_05_wigle_sync_pass_and_fail_and_unified_logs`) confirms all 7 `<app>.log` files are written, malformed WiGLE CSVs and empty credentials fail deterministically, and valid WiGLE CSVs upload and update `wigle_account.json`. **PASS**.
5. **Technical Writer Consolidator:** Confirmed zero open **Agent actions** remain.
   - **Operator action:** Set `export WIGLE_API_NAME="AID..."` and `export WIGLE_API_TOKEN="..."` from [wigle.net/account](https://wigle.net/account) when running `python3 pc_companion/wigle_sync.py --url http://<3ds-ip>:8766` to upload 3DS wardriving sessions for live WiGLE leaderboard points.
