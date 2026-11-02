# Constitution — 3DS CFW & ROM-Hack Homebrew Suite

## Core Principles

1. **Save & SD Data Integrity First (PKHaX Surgical Safety)**:
   - Never overwrite a Pokémon save (`main` or `.sav`) or SD configuration file in-place.
   - Every save or file modification MUST:
     1. Create a timestamped or `.bak` backup copy first (`<path>.bak`).
     2. Only mutate the specific target block/offset (surgical block editing so custom ROM-hack event flags, scripts, and expanded dex data are never destroyed).
     3. Recalculate the exact block and footer checksums (CRC-16-CCITT / Gen 3–7 block checksums) before writing.
     4. Write to `<path>.tmp`, flush, and atomically `rename()` over `<path>`.
2. **Cooperative 3DS Main-Loop Safety**:
   - Because `libctru`'s `aptMainLoop()` must run every frame on the single main thread to service HOME Menu suspension, lid sleep, and power interrupts, all socket operations (`accept()`, `connect()`, `recv()`, `send()`) in `3ds_pokedash`, `3ds_sysdash`, and `3ds_drop` must use non-blocking `O_NONBLOCK` sockets and bounded `poll()` waits ($\le 250\text{ ms}$ per frame slice, $\le 1500\text{ ms}$ per request).
3. **Path Traversal & SD Boundary Protection**:
   - All remote path queries served by `3ds_drop` (`/api/scan`, `/api/logs`, `/api/pull`, `/api/push`) must reject `..` path traversal segments and restrict access strictly to the configured SD root (`sdmc:/` on 3DS or the configured `--sd-root` sandbox directory on host).
4. **Zero-Privilege Reproducible Builds**:
   - Every 3DS app (`3ds_pokedash`, `3ds_sysdash`, `3ds_drop`, `3ds_pieceduel`) must compile cleanly on the Linux host (`gcc -std=c11 -Wall -Wextra -Werror -fsanitize=address,undefined`) AND cross-compile to ARM11 `.elf`, `.smdh`, `.3dsx`, and `.cia` via rootless Podman (`localhost/pieceduel-3ds-toolchain:latest`) with zero warnings and zero host `bannertool` glibc dependencies.
5. **Dual-Input Accessibility**:
   - Every 3DS utility screen must be operable via both D-Pad/Circle Pad + hardware buttons (`A`, `B`, `X`, `Y`, `L`, `R`, `START`, `SELECT`) and bottom-screen (`320×240`) stylus touch.
