# AGENTS.md — 3DS CFW & ROM-Hack Homebrew Suite (`/home/lafiamafia/homebrew/3ds`)

## Architecture & Operational References
- **System & Ecosystem Architecture (Mermaid Diagrams)**: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- **Human Quick-Start & Standard Operating Procedures (SOP)**: [`docs/SOP.md`](docs/SOP.md)
- **Project Principles & Safety Invariants**: [`specs/CONSTITUTION.md`](specs/CONSTITUTION.md)

## Workspace Structure (`lafiabrew` GitHub Organization)
- `3ds_pieceduel/` — Stereoscopic 3D strategy board game (`CTR-P-PD3D`, UniqueId `0x0D3E0`).
- `3ds_pokedash/` — PKHaX Gen 3–7 & ROM-Hack surgical Pokémon save editor + Type/Nature/Shiny/EV companion (`CTR-P-PKDS`, UniqueId `0x0D3E1`).
- `3ds_sysdash/` — CFW hardware/battery/IP inspector, 1-button Luma3DS LayeredFS mod toggler, 128-title scrollable manager & black-box cleaner (`CTR-P-SYSD`, UniqueId `0x0D3E2`).
- `3ds_drop/` — Wireless LAN HTTP & Web UI SD card scanner, crash log harvester, and atomic save/ROM file drop server (`CTR-P-DROP`, UniqueId `0x0D3E3`, port `:8766`).
- `3ds_wigle/` — `WigleWifi-1.4` CSV wardriver, 2.4 GHz Ch 1–13 spectrum analyzer, 3DS `nwm::UDS` beacon radar & WiGLE account rank viewer (`CTR-P-WIGL`, UniqueId `0x0D3E4`).
- `3ds_rngtool/` — Pokémon RNG shiny frame finder, TSV/G7TID calculator, and Luma3DS Rosalina `cheats.txt` generator (`CTR-P-PRNG`, UniqueId `0x0D3E5`).
- `3ds_netpass/` — 3DS Play Coin maxer (`300/300` with `.bak` backup), pedometer step tracker, and StreetPass `CECD` box vault (`CTR-P-SPAS`, UniqueId `0x0D3E6`).
- `3ds_padtest/` — Circle Pad drift & deadzone analyzer, 10-button matrix tester, dead-pixel screen cycler, and JSON report exporter (`CTR-P-PADT`, UniqueId `0x0D3E7`).
- `pc_companion/` — Host CLI & Web Suite:
  - `sd_scanner.py` — Scans a local SD mount or queries `3ds_drop` (`http://<3ds-ip>:8766`) wirelessly to inventory saves, ROM hacks, LayeredFS mods, and harvest all Luma/app logs (`sdmc:/3ds/logs/*.log`).
  - `pkhex_web.py` — PKHaX CLI & library for Gen 3–7 & ROM-hack saves with surgical block edits, CRC-16/section checksum recalculation, and `.bak` backup.
  - `romhack_tool.py` — Pure-Python `.ips` and `.bps` (CRC32-verified) ROM patcher + Luma3DS LayeredFS TitleID stager.
  - `wigle_sync.py` — Validates 3DS `WigleWifi-1.4` CSVs, uploads them via `multipart/form-data` to `https://api.wigle.net/api/v2/file/upload`, fetches user rank/points, and syncs `wigle_account.json` back to the 3DS.
- `serve_3ds.py` — Universal FBI QR & Network Installer Hub (`:8765`) serving Version-2 (`25×25`) `/c/0..7` QR codes and HTTP Range downloads.

## Build, Optimization & Validation Commands
```bash
# Run all host C11 ASan/UBSan pass/fail tests + ARM11 (-Os -flto + stripped ELF) builds + binary verifiers
make all

# Run PC companion & end-to-end integration tests
python3 -m unittest discover -s pc_companion/tests -v

# Verify FBI QR & HTTP Range hub self-test
python3 serve_3ds.py --self-test
```
