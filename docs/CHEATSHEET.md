# 3DS Field Cheat Sheet (`docs/CHEATSHEET.md`)

A phone-friendly, one-page reference for all **8 `lafiabrew` 3DS apps**, Luma3DS/GodMode9 hardware shortcuts, and Pokémon 3DS Title IDs.

---

## 1. On-Console App Controls At a Glance

| App | `A` | `B` | `X` | `Y` | `L` / `R` | `SELECT` | `D-Pad` |
|---|---|---|---|---|---|---|---|
| **PokeDash** (`0x0D3E1`) | Apply Surgical Edit (`.bak`+CRC) | — | Rescan SD Saves | Toggle Shiny Charm (Tab 3) | Switch Tab (`PKHaX` / `Type` / `Shiny`) | Cycle Save File | `L/R`: Party Slot `1..6`<br/>`U/D`: Select Edit |
| **SysDash** (`0x0D3E2`) | Toggle Mod / Delete Title | — | Export Snapshot JSON | Rescan SD & Titles | Switch Tab (`MODS` / `LOGS` / `TITLES`) | **Purge All `[OLD]` Black Boxes** | `U/D`: Scroll 1 Row<br/>`L/R`: Page Jump (8 Rows) |
| **3DS Drop** (`0x0D3E3`) | — | — | — | — | — | — | Shows Live `http://<3ds-ip>:8766` (`START` to exit) |
| **WiGLE 3DS** (`0x0D3E4`) | Sweep 2.4 GHz + UDS Now | **Show WiGLE Account Rank** | Toggle Auto-Sweep (Every 2s) | Cycle View (`Bars` / `Radar` / `Account`) | Cycle View (`Bars` / `Radar` / `Account`) | Start Fresh WiGLE CSV | `U/D`: Scroll APs<br/>`L/R`: Nudge GPS Lon |
| **PokeRNG** (`0x0D3E5`) | Write Luma `cheats.txt` | — | Write Luma `cheats.txt` | Toggle `Shiny Only` Filter | Select Target Pokémon Title | — | `U/D`: Scroll RNG Frames<br/>`L/R`: Adjust Seed |
| **NetPass** (`0x0D3E6`) | **Max Play Coins (`300/300`)** | — | Add `+50` Play Coins | Archive Selected CECD Box | — | — | `U/D`: Scroll CECD Boxes |
| **PadTest** (`0x0D3E7`) | Test Button Matrix | Test Button Matrix | Export `hardware_report.json` | **Cycle Dead-Pixel Screen (`R/G/B/W/K`)** | Test `L`/`R` Triggers | Test `SELECT` | Rotate Circle Pad for Drift % |
| **PieceDuel** (`0x0D3E0`) | Place / Give Piece | Back / Cancel | Toggle Threat Hints | Toggle Colorblind Palette | Switch Variant / Tab | — | Move Board / Tray Cursor |

> **Universal Exit:** Press **`START`** in any utility app to cleanly flush sockets/files and return to the 3DS HOME Menu or Homebrew Launcher.

---

## 2. Essential CFW 3DS Boot & In-Game Combos

| Combo | When to Hold / Press | What It Opens |
|---|---|---|
| **`L + Down + Select`** | Anytime in-game or on HOME Menu | **Luma3DS Rosalina Menu** (Enable `cheats.txt`, take screenshots, NTP time sync, system info) |
| **`Hold START`** | While powering on 3DS | **GodMode9** (NAND backup, `.cia` building, SD file management) |
| **`Hold SELECT`** | While powering on 3DS | **Luma3DS Configuration** (Ensure *"Enable game patching"* is checked for LayeredFS ROM hacks!) |
| **`Hold L + R + Down + B`** | While powering on 3DS (until HOME Menu loads) | **Rebuild HOME Menu Icon Cache (`IconCache.dat`)** (Clears ghost/stale HOME Menu icons) |
| **`Hold L + R + A + Up`** | While powering on 3DS | **3DS Safe Mode / System Update Recovery** |

---

## 3. Pokémon 3DS Title ID Reference (LayeredFS & `cheats.txt`)

Luma3DS LayeredFS ROM hacks and Rosalina cheats live at:
- **Active Mod / Cheats:** `sdmc:/luma/titles/<TitleID>/` (`romfs/`, `code.bin`, `exefs/`, `cheats.txt`)
- **Disabled Mod (via `SysDash`):** `sdmc:/luma/titles_disabled/<TitleID>/`

| 3DS TitleID | Vanilla Game | Popular LayeredFS ROM Hacks | Decrypted Save Size |
|---|---|---|---|
| `0004000000055D00` | **Pokémon X** | *Eternal X*, *Wilting Y* | `0x65600` (415,232 B) |
| `0004000000055E00` | **Pokémon Y** | *Wilting Y*, *Eternal X* | `0x65600` (415,232 B) |
| `000400000011C400` | **Pokémon Omega Ruby** | *Rutile Ruby*, *Rising Ruby* | `0x76000` (483,328 B) |
| `000400000011C500` | **Pokémon Alpha Sapphire** | *Star Sapphire*, *Sinking Sapphire* | `0x76000` (483,328 B) |
| `0004000000164800` | **Pokémon Sun** | *Nova Sun*, *Supernova Sun* | `0x6BE00` (441,856 B) |
| `0004000000175E00` | **Pokémon Moon** | *Umbra Moon*, *Penumbra Moon* | `0x6BE00` (441,856 B) |
| `00040000001B5000` | **Pokémon Ultra Sun** | *Photonic Sun*, *Supernova Sun* | `0x6CC00` (445,440 B) |
| `00040000001B5100` | **Pokémon Ultra Moon** | *Prismatic Moon*, *Penumbra Moon* | `0x6CC00` (445,440 B) |

---

## 4. One-Liner PC Commands (`3ds_hub`)

```bash
# 1. Serve all 8 .cia QR codes on http://<pc-ip>:8765/
python3 serve_3ds.py

# 2. Scan 3DS SD card & pull all logs/crash dumps over Wi-Fi (while 3DS Drop is open)
python3 pc_companion/sd_scanner.py --url http://192.168.0.170:8766 --dump-logs ./sd_logs

# 3. Upload 3DS WiGLE wardriving CSVs to wigle.net & sync your rank back to the 3DS
WIGLE_API_NAME="AID..." WIGLE_API_TOKEN="..." python3 pc_companion/wigle_sync.py --url http://192.168.0.170:8766

# 4. Surgically max IVs + Shiny + Money on a save file (creates .bak backup first)
python3 pc_companion/pkhex_web.py /path/to/main --slot 0 --max-ivs --shiny on --max-money
```
