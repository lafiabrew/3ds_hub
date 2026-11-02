# Standard Operating Procedures (SOP) & Human Quick-Start Guide

This guide covers step-by-step procedures for installing, using, syncing, and troubleshooting your Nintendo 3DS homebrew suite.

---

## SOP 1: Installing or Updating Any App on Your 3DS (`serve_3ds.py`)

1. **Start the Installer Hub on your PC:**
   ```bash
   cd /home/lafiamafia/homebrew/3ds
   python3 serve_3ds.py
   ```
2. **Open the Web Dashboard:**
   - Open **`http://192.168.0.104:8765/`** (or your PC's LAN IP shown in the terminal) in your browser.
   - You will see all **8 homebrew apps** with their custom 48×48 pixel icons and ultra-crisp 25×25 QR codes (`/c/0` .. `/c/7`).
3. **Install via FBI on your 3DS:**
   - **Method A (Camera QR Scan):** Open **FBI → Remote Install → Scan QR Code** and point the 3DS camera at the QR code on your monitor.
   - **Method B (No-Camera Network Push):** Open **FBI → Remote Install → Receive URLs over the network**, type your 3DS IP (e.g. `192.168.0.170`) into the **Push to FBI (:5000)** box on the web page, and click **Push**.

---

## SOP 2: Clearing Old "Black Square" Test Icons (`SysDash`)

If you have leftover black-square icons on your 3DS HOME Menu from earlier test builds:
1. Launch **SysDash** on your 3DS.
2. **One-Button Auto-Purge:** Press **`SELECT`**. SysDash will scan the SD title database (`am:u`) and delete all legacy `0x0D3D*` test titles and tickets at once.
3. **Manual Per-Title Delete:**
   - Press **`R`** (or tap **`TITLES:R`** on the bottom touch screen) to open the scrollable Title Manager.
   - Any broken/legacy/0KB titles are automatically sorted to the top and labeled **`01.[OLD]`** in red.
   - Use **`D-Pad Up/Down`** (1 row) or **`D-Pad Left/Right`** (page jump 8 rows) to highlight any unwanted title and press **`A`** to delete its title + ticket.

---

## SOP 3: Wireless SD Card Scanning, Web File Drop & Log Harvesting (`3DS Drop`)

Never unscrew your New 3DS XL backplate just to move a save file or check a crash log:
1. Open **3DS Drop** on your 3DS.
2. Look at the top or bottom screen of your 3DS — it displays your live URL, e.g.:
   ```text
   3DS URL: http://192.168.0.170:8766
   ```
3. **Use the Browser Web UI (Drag & Drop):**
   - Open **`http://192.168.0.170:8766/`** in your PC browser.
   - Click **Download** next to any save file, screenshot, or log.
   - To upload a modified `.sav` / `main` file or ROM hack, choose the file, verify the target SD path, and click **Upload Atomically to 3DS SD** (it automatically saves a `.bak` backup of the old file first!).
4. **Harvest All Logs & Crash Dumps to Your PC (For Debugging with an Agent):**
   ```bash
   python3 pc_companion/sd_scanner.py --url http://192.168.0.170:8766 --dump-logs ./sd_logs
   ```
   This downloads `sd_diagnostic_report.json`, all Luma `errdisp.txt` / ARM11 `.dmp` crash dumps, and every app's operational log (`3ds/logs/pokedash.log`, `sysdash.log`, `wigle.log`, etc.) into `./sd_logs/`.

---

## SOP 4: Editing Pokémon & ROM-Hack Saves Safely (`PokeDash` & `pkhex_web.py`)

### On Your 3DS (`PokeDash`):
1. First back up your Pokémon save in **Checkpoint** (so a decrypted save exists under `sdmc:/3ds/Checkpoint/saves/`). *(NDS `.sav` files in `sdmc:/roms/nds/saves/` and GBA `.sav` files in `sdmc:/roms/gba/` are detected automatically without Checkpoint!)*
2. Open **PokeDash** on your 3DS:
   - **`SELECT`**: Cycle between discovered save files.
   - **`D-Pad Left / Right`**: Select Party Slot (`1..6`).
   - **`D-Pad Up / Down`** (or Touch on Bottom Screen): Pick a surgical PKHaX edit (`MAX IVS 6X31`, `TRICK ROOM 0 SPE`, `TOGGLE SHINY PID`, `CYCLE NATURE`, `LEVEL 100`, `EV 252/252`, `MAX MONEY + 999 ITEMS`).
   - **`A`**: Apply edit. PokeDash writes `<save>.bak`, updates only the target slot bytes (leaving custom ROM-hack scripts/abilities untouched), recalculates the CRC-16/section checksum, and saves atomically.

### On Your PC (`pc_companion/pkhex_web.py`):
```bash
# Inspect party, IVs, EVs, Nature, Shiny status, and checksum validity
python3 pc_companion/pkhex_web.py /path/to/main

# Surgically max IVs, turn Shiny ON, and max Money/Candies/Master Balls (creates main.bak)
python3 pc_companion/pkhex_web.py /path/to/main --slot 0 --max-ivs --shiny on --max-money
```

---

## SOP 5: Wardriving & Uploading to WiGLE.net for Leaderboard Points (`WiGLE 3DS`)

1. Open **WiGLE 3DS** on your 3DS:
   - Press **`A`** (or tap **`A: SWEEP NOW`**) for a single scan, or press **`X`** (or tap **`X: AUTO [ON]`**) to continuously sweep every 2 seconds while walking/driving.
   - Press **`Y`** (or **`L`/`R`**) to cycle between:
     1. **2.4 GHz Ch 01–13 Spectrum Analyzer**
     2. **2D Polar Radar Scope**
     3. **WiGLE Account & Global/Monthly Leaderboard Rank Card**
2. **Sync & Upload Your Wardriving Session to WiGLE.net:**
   - Grab your **API Name (`AID...`)** and **API Token** from [https://wigle.net/account](https://wigle.net/account).
   - Open **3DS Drop** on your 3DS (or insert your microSD card into your PC) and run:
     ```bash
     export WIGLE_API_NAME="AID_your_api_name"
     export WIGLE_API_TOKEN="your_api_token"
     python3 pc_companion/wigle_sync.py --url http://192.168.0.170:8766
     ```
   - `wigle_sync.py` pulls `3ds/wigle/wigle_3ds_session.csv` from your 3DS, validates the `WigleWifi-1.4` format, uploads it to `api.wigle.net` for points, fetches your updated **Global Rank, Monthly Rank & Discovered Wi-Fi total**, and pushes `wigle_account.json` back to your 3DS!

---

## SOP 6: Pokémon RNG Abuse, Luma Cheats, Play Coins & Stick Drift Testing

- **`PokeRNG` (`3ds_rngtool`)**:
  - Use **`D-Pad Up/Down`** to scroll through Shiny (`SH*` / `SQ*`) and high-IV RNG frames, **`Y`** to filter Shiny-only frames, and **`L`/`R` + `A`** (or tap the game card on the bottom screen) to write ready-to-use Luma3DS Rosalina `cheats.txt` files (`sdmc:/luma/titles/<TitleID>/cheats.txt`). Enable them in-game via **`L + Down + Select` → Cheats**.
- **`NetPass` (`3ds_netpass`)**:
  - Press **`A`** (or tap **`A: MAX PLAY COINS`**) to immediately set your 3DS Play Coins to **`300/300`** (with automatic `gamecoin.dat.bak` backup), or press **`Y`** to archive StreetPass `CECD` boxes.
- **`PadTest` (`3ds_padtest`)**:
  - Rotate your Circle Pad to measure min/max excursion, let go to check your resting **Drift %** and **Recommended Deadzone**, press each hardware button to light up the 10-button test matrix, press **`Y`** to cycle full-screen dead-pixel colors (`Red`, `Green`, `Blue`, `White`, `Black`), and press **`X`** to save `sdmc:/3ds/padtest/hardware_report.json`.
