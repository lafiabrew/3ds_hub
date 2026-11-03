# Next-wave twelve-project execution plan

## Authorization, scope and clocks
- User selected ALL twelve proposed apps. Full track; parallel Pi author contexts in distinct jj workspaces, separate public lafiabrew repos, at most2 native compiler jobs and3 review contexts. No more preference interview; explicit defaults below.
- Run clock:2026-11-03T17:16:08Z. Measured phases preserve setup/retries/reviews/audits; ready-to-test only freezes after its real deterministic gate. No causal speedup without serial baseline. Record wall, allocation, observed active turns, missing/main timings, parked/critical-path limits separately.
- Source/evidence/workspaces/Git stores and SDK OCI archive stay on the project volume under this wave/runtime areas. Raw transcripts are private/ignored, outside each actual guarded candidate/snapshot Git root. No temp-only checkpoint or publication of raw sessions.
- Each repo already has an honest public WIP source/runtime baseline, not a released game. Publication result/remote SHA in manifest and runtime/publication-results.json is verified. Public WIP is not app acceptance. Ports import no engine/assets before actual license/provenance checks; original runtime/scaffold is MIT and upstream terms remain separate.
- Preserve old apps, all original AGENTS and prior wave source/history. New source identity range0x0D3F4..0x0D3FF and product codes are unique in manifest. No save/config edits; replay/media are new exclusive immutable files. Approved native journal applies diagnostic logs only.

## Authoritative execution defaults and review fixes
`EXECUTION_DEFAULTS.md` resolves all engineering-default choices inside user authorization: exact wrapper subprocess regressions (already passed3), explicit metrics fixture command/arithmetic/negative oracles, source-pin invalidation/dissent handling, externally sourced engine applicability (PocketTracker+3ports; original PCM Rhythm exempt), privacy allowlists and quantitative first-slice bounds. It also names durable evidence, actual journal pin/manifest, candidate upstreams and coordinator-owned integration. These are engineering decisions, not a new operator interview. Initial rugged UNKNOWN is retained as history; obtain the scoped matrix rerun before author release. Baseline four-persona-plus-writer completed AMBER/no RED; preserve its clarity notes without mislabeling it GREEN.

## Shared contracts and genuine slices
Each repo's specs/app.md + plan/AGENTS is normative for its selected slice. Common gate: `make test && python3 -m unittest discover -s tests -p test_contract.py -v && make 3ds && make verify-3ds && git diff --check`. Externally sourced engine lanes (PocketTracker, Neverball, TuxPuck, Supaplex only) additionally `python3 tests/verify_engine.py` (actual upstream source/compiler/map/reachable defined symbols, SAME-ARM launcher negative control). Passing existing `make journal-check` is only runtime support, not app proof.

| Repo | Required named feature case in test_contract.py | Exact observation / error + recovery oracle |
|---|---|---|
| 3ds_pinball | test_ball_flippers_score_restart | Fixed-step seeded real physics: wall/flipper collision, score/drain/restart, differing input affects state; native controls drive it and actual stereo table/ball render; no static-only screen. |
| 3ds_rhythm | test_pcm_chart_timing_score | Real PCM generation/player, chart timing/input scoring/retry; native NDSP buffers/lifecycle unavailable/cleanup/retry. Original tune, no unmeasured latency claim. |
| 3ds_gridblast | test_arena_and_real_peer_recovery | Real arena mechanics and two real loopback peers exchange validated bounded packets; malformed/late/dropped peer/reconnect and closed sockets; native controls/session wired. |
| 3ds_foldquest | test_suspend_resume_solve_reset | Solve/reset and synthetic lifecycle transition exercise same core; actual APT hook wired; no activity while asleep and no power-loss saved-campaign claim. |
| 3ds_voxeltoy | test_edit_mesh_bounds_and_reset | 16^3 capacity, surface/mesh indices, palette/edit/reset/orbit; actual stereo/native mesh path; bounds/stress reject overflow, truthful measured workloads. |
| 3ds_orrery | test_orbits_camera_reset | Deterministic bounded body/orbit/camera/reset, finite state, real native per-eye geometry; approximations/units explicit. |
| 3ds_capturekit | test_capture_clock_bounds_privacy | Explicit record/stop and bounded real native accel/gyro acquisition; unavailable/failure/retry/shutdown; raw units/read clocks labeled, no default media capture/upload or fake values. |
| 3ds_cartdash | test_readonly_card_service_failures | Actual read-only card/title API and visible unavailable/not-inserted state; no write/ROM dump/private unique IDs; model never physical evidence. |
| 3ds_pockettracker | test_decoder_pcm_lifecycle | Genuine declared decoder/original tune, actual PCM/decode/bounds/error path and native NDSP use; unsafe/truncated file fails; close/retry. |
| 3ds_neverball | test_engine_level_and_asset_errors | Real pinned engine/graphics dependency compatibility, source/data notices; native engine calls actual controls/level. No imitation/launcher; missing data visible, valid data only if lawful. |
| 3ds_tuxpuck | test_engine_match_and_asset_errors | Real pinned TuxPuck engine, source/assets terms, actual native match/input/restart; malformed/unavailable data and clean shutdown. |
| 3ds_supaplex | test_engine_puzzle_and_asset_errors | Real pinned OpenSupaplex engine, deterministic core/controls/map; licence/data rules, corrupted/missing asset rejection, no toy substitution. |

Every app also has `test_log_schema_and_recovery` and `test_required_names`: real own-app exported `build/test_sd/3ds/logs/<repo>.log`, first ASCII JSON record<=199B, active<=256KiB, eight fields schema/app/build/event/elapsed_us/seed/settings/capabilities, unavailable null. Correct seeded/null policy and clock units; no copied LinkLab app name/metadata. Per-app wrapper production code is tested against corruption/torn tail/exact bound/unwritable/cleanup/retry with retained data, not only generic core smoke.

Native journal source is vendored EXACTLY from reviewed7446e605 with file hashes; reuse APIs rather than handrolling another unsafe native replace. Keep old function prefix internal if useful. If runtime is modified, version/prove it separately; don't silently inherit old verdict on changed code.

## Tasks
### N0 — Current durable infrastructure signal
- Status: signals passed: 12 real journal smokes; current recovered-runtime8host+10native contracts/SDK ARM/artifact chain; actual new-wrapper3subprocess regressions, semantic/framing/root self-test; one shared SDK image plus checked durable533MiB OCI archive. Exact remaining source/model checks are dispatch prerequisites, not app acceptance. Records in runtime/bootstrap-signals.json, runtime/infrastructure/native-baseline.log, runtime/wrapper-regressions.log and aggregate .wgm/toolchains/.
- Objective: verified journal smoke in all12 source repos, actual Pi/branch/jj execution and actual current SDK build before app claims.
- Areas: wave agent.py (reuses reviewed EventStream/OwnedProcess), shared image and durable OCI archive, read-only current template, no old source edits.
- Validation: `python3 agent.py self-test`; each repo `make journal-check` (12 real signals already exited0); actual current shared-image probe using a committed existing app `make test && make 3ds && make verify-3ds`; actual selected model READY probes; real installed jj fixture harness if needed. Record exact image/package versions.
- Acceptance: terminal error/length/unsettled with process0 fail; output loss fail, not tail-shaped PASS; logs outside actual guarded repo; retained cleanup ownership. Cached OCI archive checksum+load works next run; image build once, never per lane. No app accepted here.

### N1 — Twelve first-slice candidates, one task per author iteration
- Status: pending.
- Objective: every lane implements its SPEC slice and required real behavioral/native/log tests.
- Areas: that new repo only; source links/dependencies/LICENCES where declared. Parents clean and immutable until writer exits. Code source references are read-only committed snapshots, not another agent's live work.
- Validation: exact common app chain above plus engine proof where applicable; queued native compiler `build_slot.py -- make 3ds`; full on-disk source+command+exit evidence and required verbose selections.
- Acceptance: actual usable interactive first session, SDK calls/metadata/native identity/artifacts, truthful model labels, user-visible failures/retry/cleanup and correct actual app log. No previous test weakening, fake bytes/runtime, silent Root mutation, bogus image/time/latency/physical success. Candidate in_progress until external reviews.

### N2 — Exact-pin independent reviews and scoped repairs
- Status: pending.
- Objective: inspect actual artifacts, not author/smoke assertions.
- Areas: paused candidate/ref, declared source patch and exact evidence, max3 fresh reviewers.
- Validation: repeat common gate on final pin, current scoped `/rugged review` RUGGED first, then independent non-author spec and quality PASS carrying full source SHA and rugged hash. Judge held-out tier1 scenario only in Validate/Review; atomic mean>=95 PLUS every deterministic/review gate.
- Acceptance: real native main reaches feature (not merely links unused symbols), source/asset/SDK/io boundary correct, no fake port or physical evidence. At stall wonder/reflect/escalate <=3cycles then precise blocked result. Do not repair stacked parent/child lanes concurrently or move a running branch. Preserve old failed sources in durable refs.

### N3 — Real Drop demo, integration freshness and source publication
- Status: pending.
- Objective: all useful reviewed candidates produce data retrievable through existing actual server routes and safely update their WIP repos.
- Areas: candidate emitted logs/source/artifacts; isolated committed Drop daemon, ordinary/crowded diagnostic fixtures; no duplicate server.
- Validation: `python3 integration/check_logs.py --manifest manifest.json` (first create actual signal, no fake server), actual `/api/logs` discovery and `/api/pull` byte parity and schema/source/log freshness; host daemon loopback-only transport and terminate/wait. Update repo only after exact reviewed pin; verify actual pushed SHA via git ls-remote.
- Acceptance: no acceptance from process exit/public WIP creation. Current exact source and tests after integration refresh; only source/known artifacts published, licences/unknown assets/private paths checked. Device URL absent -> hardware tier unverified, no guessed network/install. If 32-entry scanner hides logs, explicit tested selection/pagination requirement or block; exact known-path pull alone is not discovery.

### N4 — Consolidated demo/docs/metrics handoff
- Status: pending.
- Objective: exact scope outcomes and measured timing, no overclaim.
- Areas: accepted/blocked repo docs, run report, records and immutable audit snapshot.
- Validation: all accepted common gates, real log integration, exact evidence-consistency checks, final four personas+writer docs dispatcher + installed audit.sh --check-report before indexing; metric arithmetic fixture tests and actual ledger/intervals.
- Acceptance: each repo state WIP/build-verified/reviewed/device-tested separately, remaining blockers explicit, CI/deploy only green if actually run. Capture wall freeze at real scoped ready-to-test, allocated lifetime vs observed active lower bound/parked/missing counts/peak/critical-path definition, setup/review/audit tax. No serial-speedup claim. All source/checkpoints/evidence persist on project volume.

## Explicit non-goals and operator boundary
No emulator ROM redistribution, cartridge writing/dumping, default private media/network-ID collection, secret uploads, automatic hardware installs or strict native powerloss guarantee. Old3DS/2D baseline for originals; advanced port/model limits must be tested/documented, never silently waived. Explicit immutable new media/replay files avoid the separate unchanged save/config replacement contract. No additional human product preference is needed to begin these twelve selected bounded slices.
