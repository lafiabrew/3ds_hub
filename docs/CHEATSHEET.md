# Field reference: inspect first

Read [STATUS](STATUS.md) before any data-changing operation. This is a bounded reference, not a complete control map for every app or firmware. [SOP](SOP.md) has prerequisites and command origins.

## PC commands (hub directory)

| Task | Command | Evidence limit |
|---|---|---|
| Hub local self-test | `python3 serve_3ds.py --self-test` | Host path only; no physical FBI install. |
| Current package inventory | `python3 serve_3ds.py --list` | Available artifacts, not builds/releases. |
| ParkShift discovery | `python3 serve_3ds.py 3ds_parkshift --list` | Require an actual ParkShift row; unmatched filters can exit 0 silently. |
| Local dashboard | `python3 serve_3ds.py --push ''` | Empty target overrides inherited `IP`; dashboard installation actions still require approval. |
| Scanner options | `python3 pc_companion/sd_scanner.py --help` | Help output is not live transfer acceptance. |

**Do not use aggregate build exit 0 as acceptance.** Root native build/verify loops can conceal earlier failures. Chain each app's own `test`, `3ds` and `verify-3ds` commands as shown in the SOP.

## ParkShift controls (local candidate)

| Input | Action |
|---|---|
| Slide stylus | Press a car, drag along its lane, lift inside the board to commit. |
| Jam stylus | Tap a car to attempt one departure; holding does not repeat. |
| D-pad Left/Right | Select car. |
| Slide Up/Down; A | One cell backward/forward; A moves forward. |
| Jam A | Depart selected car if its path is clear. |
| B / X / Y | Undo / restart / help. Y, B or the Help control closes help. |
| L/R / Select / Start | Previous/next puzzle / mode / exit. |

Boundary puzzle navigation stays at puzzle 1/6 without resetting the board in the current modified source. No SD saves/logs or persistent resume. Check current source/build identity before testing; this reference is not native touch/font/HOME/lid acceptance.

## Other inspected control boundaries

- PadTest: Y cycles screen-test state; X requests a JSON export. Export is a write, not a physical calibration certificate.
- PokeRNG: A/X can generate fixed cheat files. Do not activate those templates based on a title label.
- SysDash: Select can invoke a multi-title purge; title activation can delete a title/ticket. **Do not use either as routine icon troubleshooting.**
- PokeDash: applying an edit can write synthesized PKHX data into an unsupported save. The displayed values/checksum are not proof of correct native decoding.
- WiGLE and NetPass controls can create files; no genuine-observation upload, system coin effect or CECD recovery guarantee is implied.

## Identity and firmware shortcuts

Use each actual package's full TitleID and product code; a UniqueId range is not deletion authority. `0x0D3D*` examples in older materials are historical. The current build-metadata catalog is in the [repository README](https://github.com/lafiabrew/3ds_hub/blob/main/README.md).

Firmware/boot shortcuts depend on the installed CFW and payload configuration. Consult that version's official instructions before maintenance. This guide deliberately does not prescribe cache-reset/database-reset combinations, system updates or deletion to fix unknown symptoms.
