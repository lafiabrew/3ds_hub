# Current implementation status and safety limits

This page describes **inspected source snapshots**, not every public repository revision. Reviewed 2026-11-03; source references below allow rechecking. A feature requirement or previous audit verdict is not implementation evidence. [README](../README.md) lists build membership; [SOP](SOP.md) provides bounded inspection commands.

## Evidence levels

| Evidence | What it establishes | What it does not establish |
|---|---|---|
| Source inspection | Named branches, constants, paths and algorithms exist. | Correct handling of genuine files, runtime behavior or device compatibility. |
| Host tests / loopback HTTP | The exercised host path and assertions, at the recorded revision. | libctru filesystem semantics, radio behavior, touchscreen feel or physical recovery. |
| ARM build / package verifier | Compilation and the specific package properties checked. | Successful launch, correct icon on a console, safe power loss or readable native text. |
| Model-specific operator test | Only the recorded artifact/model/CFW/input journey. | Other console models or untested workflows. |

## Capabilities that must not be overstated

| Surface | Inspected behavior | Current boundary / safe disposition |
|---|---|---|
| PokeDash / PC save editor | Python requires a private `PKHX` block at `0x1400`; native fallback synthesizes party/trainer values when that block is absent and marks a checksum valid. | **Do not edit real saves using these guides.** This is not demonstrated general Gen 3–7 parsing, ROM-hack compatibility or genuine checksum validation. Backups do not make an unsupported parser safe. |
| 3DS Drop replacement | Existing bytes are copied toward `.bak`, then a temporary file is renamed; backup open/write/flush failures are not all checked. | Do not rely on the UI's atomicity/backup wording for native recovery. Prefer read-only inspection; valuable-file replacement and power-loss safety are **unverified**. |
| Native loggers | Inspected PokeDash/SysDash/Drop adapters open logs in append mode. | Not a uniform atomic journal. The constitution's approved exception is diagnostic-log-only, first scoped to LinkLab; it does not retroactively certify these adapters or saves/configuration. |
| WiGLE | Default coordinates are marked as a fix; configured networks, placeholder identifiers and derived readings can enter CSVs. Host sweeps are synthetic. | **Do not upload these records as measured observations.** CSV header/column validation does not establish genuine BSSID/location data, API acceptance or points. |
| NetPass | Uses `<sd_root>/3ds/netpass/gamecoin.dat`; writes seeded textual `CECD_BOX_V1` summaries. | Not demonstrated system Play Coin modification or actual CECD payload backup/restore. Do not rely on its files to recover StreetPass data. |
| PokeRNG | TSV/G7TID and Method-1 LCRNG routines; writer emits fixed cheat addresses regardless of selected title. | Not validated for a particular game/update/region. **Do not enable generated codes using this guide.** TinyMT and broad generation-specific RNG support are not established here. |
| Pokédex | Small built-in curated list with stat/ability strings and notes. | Not a complete Gen 1–7 dataset; notes are not verified per-ROM-hack documentation. |
| Other games / diagnostics | Source-level models and adapters exist as listed in the README. | No blanket claims of complete gameplay, solvers, 60 FPS, ROM compatibility, physical calibration or hardware acceptance. |

### Sources for these boundaries

- Save contract: [`parse_save_bytes` / `apply_surgical_edit_to_file`](https://github.com/lafiabrew/3ds_hub/blob/d3bae799fbe8f68d803c986981a09e945dd53412/pc_companion/pkhex_web.py), [`pk_load_save_file` / `pk_apply_surgical_edit`](https://github.com/lafiabrew/3ds_pokedash/blob/6d0dc218bf6fcc397c997ecdb373c82dfb45ab0d/src/pkhex.c).
- Transfer: [`/api/push` implementation](https://github.com/lafiabrew/3ds_drop/blob/d3b0dfd3ad7c60d48b815d1264560fd5d007db28/src/drop_server.c). A successful response is not evidence that an earlier backup operation succeeded.
- Logging: native adapters in [PokeDash](https://github.com/lafiabrew/3ds_pokedash/blob/6d0dc218bf6fcc397c997ecdb373c82dfb45ab0d/src/platform_3ds.c), [SysDash](https://github.com/lafiabrew/3ds_sysdash/blob/4c2714eb4175a84a7b030bedeecb86e4f41213df/src/platform_3ds.c), [Drop](https://github.com/lafiabrew/3ds_drop/blob/d3b0dfd3ad7c60d48b815d1264560fd5d007db28/src/platform_3ds.c); [required constitution and narrowly approved exception](../specs/CONSTITUTION.md).
- Wi-Fi CSV provenance: [`wg_init` / `wg_perform_sweep`](https://github.com/lafiabrew/3ds_wigle/blob/0e5e3435f612fb049d03a8d946c606616aa66352/src/wigle.c); [`validate_wigle_csv`](https://github.com/lafiabrew/3ds_hub/blob/d3bae799fbe8f68d803c986981a09e945dd53412/pc_companion/wigle_sync.py) checks shape rather than authenticity.
- Local coin/box files: [`np_init` / `np_set_play_coins` / `np_archive_streetpass_box`](https://github.com/lafiabrew/3ds_netpass/blob/a88247d300c8ec5848c70d44259f7b798ec5001f/src/netpass.c).
- Fixed cheat templates: [`rng_write_luma_cheats`](https://github.com/lafiabrew/3ds_rngtool/blob/7e52b5c072e29f9ce0852dd6be9f209be472a446/src/rng_tool.c); curated data: [`k_dex`](https://github.com/lafiabrew/3ds_pokedex/blob/694a58e1b0e0ec7368800eaa4f949f93ea3353ba/src/pokedex.c).

Sibling source references use public GitHub URLs rather than nonexistent Pages subdirectories. The six primary implementation snapshots above were fetched at their named public commits and matched the previously inspected local sources. This verifies those specific source observations, not live console behavior or every future revision.

## Build and identity boundaries

- Root [Makefile](https://github.com/lafiabrew/3ds_hub/blob/d3bae799fbe8f68d803c986981a09e945dd53412/Makefile) membership is 16 apps. ParkShift is separate. `serve_3ds.py --list` reports **available artifacts**, not supported releases; regenerate rather than hardcoding discovery counts or QR ranges.
- The current `3ds` and `verify-3ds` aggregate loops lack fail-fast status handling: an earlier submake can fail, the next succeeds, and the aggregate returns 0. Failure-injection controls reproduced this. **The code defect remains open**; use explicit per-app chained commands, not aggregate success as certification.
- Current build-metadata allocation: `0x0D3E0` through `0x0D3EF` for the 16 catalog projects, `0x0D400` for ParkShift. The older `0x0D3D*` range is historical, not allocation guidance or permission to delete a title.
- A UniqueId is not a full installed TitleID. Check the actual ticket/TMD/NCCH and product code; version/category also matter. Never change IDs or delete installed titles to disguise an unidentified packaging problem.

## ParkShift: local candidate only

Two original parking modes, six authored boards each, session-only state and no SD diagnostic logs. New 3DS XL is the first operator target; Old 3DS/2DS are compatibility targets, **not verified devices**.

The app has a locally modified `src/app.c` beyond candidate `f89914e`. Prior candidate test/build results must not be treated as acceptance of those changes. Its source, detailed validation record and device checklist remain maintainer-local; this public site does not provide a reviewed downloadable ParkShift build, public repository or release. Local host/package results are not independent implementation-review acceptance. P2/P3/device gates stay open until their own evidence is complete.

## Public profile and protected guidance

The local `../.github` checkout initially contained a seven-line profile at `0c06c5d`; the public main-file snapshot observed on 2026-11-03 contained nine project entries. Those entries must survive reconciliation. HTTP 200 on repository links establishes reachability only. Local code inspection does not certify the currently published app revisions.

Root `AGENTS.md` still contains broad save/system/backup descriptions; ParkShift's existing `AGENTS.md` still permits append logging contrary to its accepted no-write scope. **Both files remain unchanged, awaiting explicit file-specific approval.** Treat these discrepancies as open documentation blockers, not permissions to weaken the constitution or add persistence.

The suite [specification](../specs/01-3ds-homebrew-suite.md) records intended requirements, not completed features. Older [audits](audit/README.md) are dated historical evidence; current warnings supersede their operational assurances. Other sibling READMEs have not all been re-audited in this update.

## Validation and remaining work

The public privacy gate is `python3 tests/pages/check_privacy.py` from hub root. Browser integration checks are in `tests/pages/test_pages.cjs`; see [the Pages audit](audit/2026-11-03-pages-privacy-and-rendering.md) for reproduction. These check named privacy/rendering faults, not automatic semantic truth or device certification.

Unresolved: aggregate failure propagation; unsupported real-save parser behavior; checked backup/native recovery; genuine WiGLE provenance; per-game cheat validation; actual system coin/CECD integration; protected-guide corrections; clean-machine provisioning and physical-console acceptance. A docs-only correction does not repair these implementations or establish a safe release.
