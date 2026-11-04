# Troubleshooting without destructive shortcuts

First read [STATUS](STATUS.md). Stop data-changing operations when identity, backup validity or format support is uncertain. Record the exact command, error, source/artifact hash, model/CFW and launch method before retrying. Do not equate an attractive UI message with verified behavior.

## Build and package symptoms

| Symptom | Check first | Safe disposition |
|---|---|---|
| Root build says success but one app is missing | Root native loops can hide earlier submake failures. Read each app's build output and artifact timestamp/hash. | Run explicit chained per-app checks from the [SOP](SOP.md). The root code defect is still open; do not install a stale package. |
| Native build cannot find an image | Check app prerequisites and local `localhost/pieceduel-3ds-toolchain:latest` identity. | Use the existing reviewed provisioning entry point; ParkShift will not pull an image automatically. Clean-machine setup remains unverified. |
| Hub list/filter prints nothing | Confirm real CIA/3DSX paths exist and the filter matches discovery names. | Empty output can exit 0. No row means no demonstrated discovery, not a release. |
| Icon is blank, stale or banner looks wrong | Match actual package identity and hashes; inspect embedded SMDH/banner and the verifier's output. | Prefer an authorized 3DSX test where practical. Do not delete titles, tickets, databases or reset the HOME Menu simply to force an apparent pass. |

Old guides treated a single packaging constant, cache assumption or purge as a universal fix. Those causes were not established for every device symptom. Preserve an unrelated installed title rather than guessing which ID to remove.

## Network and log collection

- Use the URL actually printed by 3DS Drop; keep PC and console on a mutually reachable trusted LAN. Check isolation/firewall/addresses before changing code or credentials. Do not expose the HTTP services publicly.
- Capture the real HTTP/error output. The scanner can salvage partial JSON and return partial bytes after transport failure; successful report creation does not establish a complete download. Compare lengths/hashes against a separately known source where possible, and record unresolved truncation.
- Log collection retrieves only what exists and the endpoint exposes, not every possible app event. ParkShift intentionally has no SD diagnostic log. Physical Drop transfers were not validated by this docs update.
- For a Luma dump, preserve the original bytes and matching unstripped ELF if available. Do not infer process/PC/LR offsets solely from a filename or extension. Keep console keys, Wi-Fi secrets and private SD data out of public reports.

## Saves, replacement and recovery

There is **no universal successful-backup guarantee** across this workspace. The inspected Drop/NetPass/PokeRNG writers do not all stop on backup failures or check every write/flush. `.tmp` plus native `rename` is not a physical power-loss safety proof.

1. Stop before another edit/overwrite can replace the prior `.bak` generation.
2. Copy the original, candidate and any `.bak`/`.tmp` files to separate PC storage without changing the console originals. Record hashes and provenance; a `.bak` extension alone proves nothing about its contents.
3. For real Pokémon saves, use independently verified format-specific inspection/restore tooling and backups. These docs provide **no real-save editing or live SD restore recipe** until the parser/recovery gaps are resolved.
4. If the file is absent, partial or not known to be a genuine pre-edit save, do not invent a successful recovery claim. Preserve recoverable bytes and obtain qualified, format-specific help.

Checkpoint can be part of an independently validated backup workflow; the mere existence of a decrypted `main` does not make the current PKHX editor compatible with it. NetPass's text box summaries are not real CECD payload backups. The constitution's narrow diagnostic-log journal exception does not change save/configuration requirements.

## WiGLE, cheats and device checks

- A CSV shape check does not validate measured location/BSSID provenance. Do not retry uploads of synthetic/default observations or troubleshoot missing points by submitting more records.
- PokeRNG emits fixed cheat addresses across title selections. Do not enable them or overwrite existing codes to diagnose RNG calculations. Per-game/update/region validation is outstanding.
- Missing physical test evidence means **unverified**, not a proven broken console. ParkShift's local device checklist remains NOT RUN until the operator records actual artifact/model/CFW results. Old 3DS/2DS need their own results; native compilation is not a substitute.
