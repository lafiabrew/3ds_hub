# AGENTS.md — 3DS CFW & ROM-Hack Homebrew Suite (`/home/lafiamafia/homebrew/3ds`)

## Workspace Structure
- `3ds_pieceduel/` — Strategy board game homebrew (`CTR-P-PD3D`, UniqueId `0x0D3D0`).
- `3ds_pokedash/` — PKHaX-style Pokémon Gen 3–7 & ROM-Hack Save Inspector/Editor + Dual-Screen Type/Nature/Shiny/EV Companion (`CTR-P-PKDS`, UniqueId `0x0D3D1`).
- `3ds_sysdash/` — CFW Hardware/Battery/SD Inspector, Luma3DS LayeredFS ROM-Hack Mod Toggler & Diagnostic Log Exporter (`CTR-P-SYSD`, UniqueId `0x0D3D2`).
- `3ds_drop/` — Wireless LAN HTTP/TCP SD Card Scanner, Log Harvester & Save/ROM/LayeredFS File Drop Server (`CTR-P-DROP`, UniqueId `0x0D3D3`, port `:8766`).
- `pc_companion/` — PC-side CLI & Web Suite:
  - `sd_scanner.py` — Scans a mounted 3DS SD card or queries `3ds_drop` (`http://<3ds-ip>:8766`) wirelessly to inventory saves, ROM hacks, LayeredFS mods, and pull all Luma/homebrew logs into a structured diagnostic bundle.
  - `pkhex_web.py` — PKHaX CLI & Browser Editor for Gen 3–7 & ROM-hack saves with surgical block edits, CRC-16/block checksum recalculation, `.bak` backup, and wireless pull/push to `3ds_drop`.
  - `romhack_tool.py` — Pure-Python `.ips` and `.bps` ROM patcher/creator + Luma3DS LayeredFS TitleID packager.
- `serve_3ds.py` — Universal FBI QR & Network Installer Hub (`:8765`) that auto-discovers all `.cia`, `.3dsx`, and `.smdh` packages across the workspace.

## Build & Validation Commands
```bash
# Build & test a single 3DS app (host ASan/UBSan tests + ARM11 .elf/.smdh/.3dsx/.cia)
make -C 3ds_pokedash test && make -C 3ds_pokedash 3ds && make -C 3ds_pokedash verify-3ds
make -C 3ds_sysdash test  && make -C 3ds_sysdash 3ds  && make -C 3ds_sysdash verify-3ds
make -C 3ds_drop test     && make -C 3ds_drop 3ds     && make -C 3ds_drop verify-3ds

# Run PC companion & end-to-end integration tests
python3 -m unittest discover -s pc_companion/tests -v

# Serve FBI QR codes for all built 3DS homebrew apps
python3 serve_3ds.py
```
