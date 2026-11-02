# Architecture & Ecosystem Map — `lafiabrew` Nintendo 3DS Suite

This document provides future coding agents and maintainers with the complete architectural model, data-flow diagrams (Mermaid), memory/persistence invariants, and binary layout across all 9 `lafiabrew` Nintendo 3DS repositories.

---

## 1. Multi-Console Workspace & `lafiabrew` Repository Topology

The `/home/lafiamafia/homebrew/` parent directory is organized by target console family (`3ds/`, and future `ps3/`, `ps4/`, `vita/`, `xbox360/`, `wiiu/`). Inside `3ds/`, `3ds_hub` is the root deployment & PC companion repository, while each `3ds_*` subdirectory is an independent, self-contained C11 homebrew repository:

```mermaid
flowchart TB
    subgraph HostPC["Linux x86_64 Host (3ds_hub)"]
        HUB["serve_3ds.py (:8765)<br/>FBI QR & Network Push Hub"]
        SCAN["pc_companion/sd_scanner.py<br/>SD & Crash Log Harvester"]
        PKWEB["pc_companion/pkhex_web.py<br/>PC PKHaX CLI & Surgical Editor"]
        PATCH["pc_companion/romhack_tool.py<br/>IPS / BPS CRC32 Patcher & LayeredFS Stager"]
        WSYNC["pc_companion/wigle_sync.py<br/>WiGLE.net API v2 Multipart Uploader"]
        POD["Rootless Podman<br/>devkitARM + libctru + citro2d + makerom"]
    end

    subgraph Console3DS["Nintendo 3DS Console (Luma3DS CFW — Old 3DS / 2DS / New 3DS XL)"]
        FBI["FBI Title Installer<br/>QR Camera / TCP :5000"]
        DROP["3ds_drop (:8766)<br/>0x0D3E3 · CTR-P-DROP<br/>HTTP/Web UI SD & Log Server"]
        SYSD["3ds_sysdash<br/>0x0D3E2 · CTR-P-SYSD<br/>CFW Telemetry, LayeredFS & Title Cleaner"]
        POKE["3ds_pokedash<br/>0x0D3E1 · CTR-P-PKDS<br/>PKHaX Gen 3-7 & ROM-Hack Save Editor"]
        RNG["3ds_rngtool<br/>0x0D3E5 · CTR-P-PRNG<br/>TSV/G7TID, LCRNG & Luma Cheats"]
        WIGL["3ds_wigle<br/>0x0D3E4 · CTR-P-WIGL<br/>WiGLE-Wifi-1.4 CSV & 2.4GHz Radar"]
        NETP["3ds_netpass<br/>0x0D3E6 · CTR-P-SPAS<br/>300 Play Coins & CECD Vault"]
        PADT["3ds_padtest<br/>0x0D3E7 · CTR-P-PADT<br/>Stick Drift, Button & Pixel Lab"]
        PD3D["3ds_pieceduel<br/>0x0D3E0 · CTR-P-PD3D<br/>3D Strategy Game (UDS/LAN/Web)"]
        SDMC[("FAT32 microSD (sdmc:/)<br/>• 3ds/logs/*.log<br/>• 3ds/Checkpoint/saves/<br/>• luma/titles/ & dumps/<br/>• 3ds/wigle/*.csv")]
    end

    POD -->|".elf / .smdh / .3dsx / .cia"| HUB
    HUB -->|"HTTP Range (:8765/c/0..7)<br/>or TCP Push (:5000)"| FBI
    DROP <-->|"HTTP JSON + Web UI (:8766)<br/>/api/scan · /api/logs · /api/pull · /api/push"| SCAN
    DROP <-->|"Pull CSV / Push wigle_account.json"| WSYNC
    WSYNC <-->|"HTTPS Basic Auth<br/>api.wigle.net/api/v2"| WIGLE_CLOUD(("WiGLE.net<br/>Leaderboard API"))
    POKE & SYSD & DROP & RNG & WIGL & NETP & PADT & PD3D -->|"pk_log_event() + Atomic .tmp->rename()"| SDMC
```

---

## 2. Dual-Target C11 Platform Abstraction (`pk_platform.h`)

Every 3DS app compiles from the **exact same C11 application/domain source files** (`src/*.c`) to two targets:
1. **Linux Host (`src/platform_host.c`)**: Software rasterizer (`fb_top_l[400*240]`, `fb_bot[320*240]`) + input injection harness compiled with `gcc -std=c11 -Wall -Wextra -Werror -O2 -fsanitize=address,undefined` so every frame, button press, touch event, and file operation is verified under ASan/UBSan in `< 0.2s`.
2. **Nintendo 3DS ARM11 (`src/platform_3ds.c`)**: Hardware PICA200 GPU rendering via `citro3d` / `citro2d` (`C2D_DrawRectSolid`, `C2D_DrawText`) with **automatic text width clamping** (`avail_w / ct.width`) so text never clips on either screen (`400×240` top, `320×240` bottom) across Old 3DS, 2DS, and New 3DS XL.

```mermaid
sequenceDiagram
    participant Main as src/main.c (Cooperative Loop)
    participant Plat as platform_3ds.c / platform_host.c
    participant App as App State Machine (app.c)
    participant SD as sdmc:/3ds/logs/<app>.log

    Main->>Plat: pk_platform_init() (gfx, C3D, C2D, soc:U / ptm:u / am:u)
    Main->>App: app_init(&app, sd_root)
    App->>SD: pk_log_event(sd_root, app_name, "INFO", "READY...")
    loop Every Frame (60 FPS while aptMainLoop() == true)
        Main->>Plat: pk_platform_poll_input(&in) (hidScanInput + Touch)
        Main->>App: app_step(&app, &in) (Non-blocking <= 15ms poll slice)
        Main->>App: app_render(&app)
        App->>Plat: pk_render_begin_target(TOP 400x240 / BOTTOM 320x240)
        App->>Plat: pk_draw_text() [Auto-clamps sx so ct.width * sx <= screen_w - x - 6]
        App->>Plat: pk_draw_scrollbar() [8-row sliding viewport thumb]
        Main->>Plat: pk_render_end_frame() (C3D_FrameEnd)
    end
    Main->>Plat: pk_platform_shutdown()
```

---

## 3. Surgical PKHaX Save Editing & Atomic Persistence Flow

To guarantee **zero corruption on custom Pokémon ROM hacks** (Drayano hacks, CFRU/decomp GBA hacks, Luma3DS LayeredFS 3DS hacks), `3ds_pokedash` and `pc_companion/pkhex_web.py` never re-serialize unknown save blocks:

```mermaid
flowchart LR
    A["Original Save File<br/>(Gen 3/4/5/6/7 or ROM Hack)"] --> B["1. Write Exact Backup<br/>&lt;save&gt;.bak"]
    B --> C["2. Mutate Only Target Slot<br/>(0x1400..0x15FF Surgical Block)<br/>Preserve Custom Hack Flags 0x0000..0x13FF"]
    C --> D["3. Recompute Checksums<br/>• Block CRC-16-CCITT<br/>• Gen 6/7 BEEF Footer (sz - 0x1F0)<br/>• Gen 3 Section Sums (0x0FF6 / 0x1FF6)"]
    D --> E["4. Write &lt;save&gt;.tmp<br/>fflush() + fsync()"]
    E --> F["5. Atomic rename()<br/>&lt;save&gt;.tmp -> &lt;save&gt;"]
```

---

## 4. CIA / SMDH / CBMD Packaging & Binary Optimization Pipeline

All 8 apps build inside `localhost/pieceduel-3ds-toolchain:latest` without requiring external `bannertool` shared libraries:
- **Compiler & Linker Flags**: `-Os -flto -fomit-frame-pointer -ffunction-sections -fdata-sections -Wl,--gc-sections` followed by `arm-none-eabi-strip --strip-debug`, shrinking ARM11 `.elf` binaries by **~78%** (`1.5 MB` → `~280–366 KB`).
- **SMDH HOME Menu Patch (`patch_smdh_for_cia`)**: Clears `smdhtool`'s `0xA0` age-rating bytes (`+0x2008..0x2017`) to `0x00`, sets region-free lockout (`0x7FFFFFFF` at `+0x2018`), and sets `0x00000105` flags (`+0x2028`) so the 3DS HOME Menu never renders black-square icons.
- **CBMD 3D Banner (`write_cbmd_bnr`)**: Encodes each app's 256×128 RGBA banner into PICA200 Morton-swizzled RGBA4444 tiles (`0x1580..0x11580`), compresses the 71,040-byte CGFX using a 4 KB hash-chain LZ11 encoder padded to a strict **32-byte (`0x20`) boundary** at `cwav_offset` (`+0x84`), and appends the BCWAV audio chime.
