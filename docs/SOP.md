# Setup and safe inspection procedures

Start with [STATUS](STATUS.md). These procedures deliberately exclude real-save editing, valuable-file overwrite, title deletion, generated-cheat activation and live WiGLE upload until the named safety gaps are resolved. No command below installs an app automatically.

## 1. Workspace prerequisites

Run hub commands in the directory containing `serve_3ds.py`. App directories are **separate repositories**, not files guaranteed to arrive when cloning the hub. The organization repository list identifies public projects; ParkShift currently exists as a local candidate only. Do not invent a public ParkShift clone URL.

Prerequisites for inspection: Python 3 and existing app checkouts/artifacts for discovery. Host app tests require Make/GCC and sanitizer libraries. Native builds require the appropriate rootless toolchain image and app-specific dependencies. PieceDuel additionally documents Node-based compatibility tests.

For a standalone hub checkout, start at the [public PieceDuel prerequisites](https://github.com/lafiabrew/3ds_pieceduel#prerequisites--building-containerfile3ds-or-native-devkitarm) or [public repository](https://github.com/lafiabrew/3ds_pieceduel). Its separate checkout must be named `3ds_pieceduel/` directly under this hub directory; a hub clone does not obtain it automatically. Once present, the existing local provisioning entry point is [PieceDuel's public build documentation](https://github.com/lafiabrew/3ds_pieceduel#prerequisites--building-containerfile3ds-or-native-devkitarm) and [Makefile](https://github.com/lafiabrew/3ds_pieceduel/blob/main/Makefile). With that separate checkout available, its `make 3ds` can build the container if needed. Inspect its `Containerfile.3ds` before allowing network downloads. **Clean-machine provisioning was not tested by this docs update**; an existing image is not a reproducibility guarantee.

ParkShift consumes `localhost/pieceduel-3ds-toolchain:latest` with `--pull=never --network=none`. It will not obtain a missing image. Inspect it without downloading or retagging:

<!-- {% raw %} -->
```sh
podman image inspect localhost/pieceduel-3ds-toolchain:latest --format '{{.Id}}'
```
<!-- {% endraw %} -->

The accepted slice records image ID `d4e9a0e114502d3b535b1ab33dd40c542e4453027dfc76030490f8fb969bd306`, also observed by this update; this is a maintainer-local test image identity, not a published image download or an independent provenance certificate. Stop if it is missing or different. Matching the ID identifies bytes, not independent provenance approval or clean-machine reproducibility; do not silently substitute/retag an unknown image. A missing sibling checkout/toolchain is a missing prerequisite, not proof of an app defect.

## 2. Inspect the installer hub

From the hub root:

<!-- check: local-smoke -->
```sh
python3 serve_3ds.py --self-test &&
python3 serve_3ds.py --list
```

Expected: self-test exits 0; list prints the packages actually present. Package presence does not prove those files match current source. Printed names/descriptions come from package metadata or fallback labels and may retain overstated feature titles such as “Auto-Solver”; they are not validation results. Use STATUS for inspected limits. QR routes change with discovery; do not bookmark an index as an app identity.

To inspect only ParkShift's existing packages from the same directory:

```sh
python3 serve_3ds.py 3ds_parkshift --list
```

An unmatched filter currently exits 0 with empty output. Confirm the named row is present; exit status alone is insufficient.

## 3. Build one app, not an unsound aggregate

From the hub root, with the [public PadTest repository](https://github.com/lafiabrew/3ds_padtest) checked out as `3ds_padtest/` and its reviewed image available:

```sh
make -C 3ds_padtest test &&
make -C 3ds_padtest 3ds &&
make -C 3ds_padtest verify-3ds
```

This runs host tests, native packaging and the app's package verifier. Inspect each command's result and retain matching source/artifact hashes and debug ELF. Physical acceptance and independent code review remain separate. Root `make all` is **not** reliable fleet acceptance while its native build/verify loops can conceal earlier failures; [STATUS](STATUS.md) records that unresolved code defect.

## 4. Optional local installer dashboard

From hub root, explicitly disable automatic startup push:

```sh
python3 serve_3ds.py --push ''
```

The empty argument overrides the `IP` environment variable, which otherwise supplies an automatic FBI push target. Do not rely on omitting `--push` for inspection-only startup. `--list` and `--self-test` return before startup push handling. Use the LAN URL printed by the server, not a hardcoded personal IP. Keep the service on a trusted network; it is not an authenticated public deployment service. Dashboard push controls still require operator authorization.

FBI camera scanning or its network receiver is an **operator-authorized installation step**. Match the app name, CIA hash, product/TitleID and matching debug ELF against an independently reviewed build record first. Stop on a missing record or mismatch. Rebuilding can change CIA bytes; a new record and review are required, not simply accepting fresh hashes. No reviewed public ParkShift artifact or hash record is provided by this page. Do not use the CLI `--push` option casually: it initiates a remote installation request. For ParkShift, follow its local `docs/DEVICE_CHECKLIST.md`; hardware tests are still owed per console model.

## 5. Optional read-oriented SD/log collection

Open an independently reviewed 3DS Drop build on the console. On the PC, substitute the complete URL **inside the quotes** with the address shown on that console:

```sh
python3 pc_companion/sd_scanner.py --url 'http://REPLACE_WITH_3DS_IP:8766' --dump-logs ./sd_logs
```

This performs remote scan/log requests and writes a local report/downloads under `./sd_logs`; a pristine remote SD is not promised because the running server can itself log activity. Review collected filenames and errors. The current client may return partial JSON/bytes after transport errors, so a report file alone is not proof of complete transfer. Keep private dumps and backups out of public issues.

This live-console journey was **not run by the documentation update**. No fixture or host loopback is a substitute. ParkShift has no SD app log to harvest in this slice.

## 6. Workflows intentionally withheld

- Do not feed real saves to PokeDash or the PC editor on the strength of old general-format claims. Use an independently verified format-specific tool and offline backups instead.
- Do not use Drop's upload/replacement control as a guaranteed safe restore mechanism. Its UI wording does not establish checked backups or native power-loss recovery.
- Do not upload current synthetic/default WiGLE observations as genuine measurements; no API credential or points workflow is recommended here.
- Do not enable PokeRNG's fixed generated cheat templates without independently validated game/update/region-specific codes.
- Do not treat NetPass's local files as a real CECD vault or system coin backup. Do not purge titles to fix an unexplained icon.

For symptom handling and the information to preserve, see [troubleshooting](TROUBLESHOOTING.md).
