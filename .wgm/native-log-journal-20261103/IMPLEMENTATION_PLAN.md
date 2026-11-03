# R5 — Native diagnostic-log journal

## Scope and approvals
- Track: Full, resumed from the approved fleet; one LinkLab storage slice first. User explicitly approved native diagnostic journaling twice. Save/config guarantees unchanged; no existing AGENTS edits.
- Root constitution now records the narrowly scoped decision. SPEC.md is the behavior contract. No automatic migration to other apps or physical-test claim.
- Source base: reviewed LinkLab `90c8b113c77dfa9240c0a1ccb9bce15e32f0724b`, recovered from persistent local ref. Root/live apps remain untouched while a persistent separate Git/jj workspace builds the candidate.
- Runtime workspaces/evidence are persistent outside the guarded root, not ephemeral temp storage. Historical raw evidence no longer present is explicitly unavailable. Preserve original fleet start 2026-11-02T21:27:01Z; R5 start 2026-11-03T05:38:39Z, no invented clock continuity.
- Goal/defaults/limits are explicit in SPEC.md. No further product interview is needed. Native physical SD/power-loss testing is separately unverified.

## Tasks
### J0 — Re-establish current source/toolchain signal
- Status: done as the current source/toolchain validation signal; recorded before J1 feature implementation. Recovered code ran all eight host contracts plus actual ARM artifact/hygiene gate with exit0. Current image `74542c3d894b2a06a3148a635fb771f7156ffeb52aae67c9037b3f6351b03938`, devkitARM16.1.0, libctru2.7.0-1, 3ds-sdl1.2.15-19. Complete fresh outputs are copied to the durable evidence directory. This is not new storage or full app acceptance.
- Objective: validate recovered source and actual current toolchain before feature claims.
- Areas: persistent source clone, shared rootless image, local evidence only.
- Validation: on the untouched recovered clone, `make test && python3 -m unittest discover -s tests -p test_contract.py -v && make 3ds && make verify-3ds` (native via reviewed max-two helper); record source pin, actual image ID, compiler/libctru versions, full logs/exit and absent workers.
- Acceptance: existing eight tests and real artifacts pass, or exact setup blocker is retained. Old missing logs are not credited as fresh execution evidence. Shared image builds once, not per lane.

### J1 — Implement complete recoverable native log export
- Status: done for the approved first storage slice. Runtime/code pin `748fce8d1e9ec3b8e88dc256c1c1e9304712db69`; final documentation pin `7446e605aeca206733262ab563e7b4a4a43e60f5` has identical production/test/Makefile/registry bytes. Scoped acceptance is in ACCEPTANCE.json; whole app/fleet/device is NOT accepted.
- Objective: add checked journal/backup/exclusive-move storage and wire actual native LinkLab export/retry/shutdown.
- Areas: `src/native_log_store.c`, `include/native_log_store.h`, optional separate native platform adapter, `src/linklab_log.c`, `include/linklab_log.h`, `src/main.c`, `Makefile`, `tests/native_storage_driver.c`, `tests/test_native_storage.py`, bounded SDK fixtures, README/specs/plan. Do not edit networking behavior or existing AGENTS.
- Validation: `make test && python3 -m unittest discover -s tests -p test_contract.py -v && python3 -m unittest discover -s tests -p test_native_storage.py -v && make 3ds && make verify-3ds && git diff --check`; native via reviewed queue.
- Acceptance: all SPEC.md invariants, actual old-logger delete-before-retry fail-first proof, production store/app model covers every boundary and repeated recovery, old tests not weakened, no false success/lost bytes/resource handles, actual native SDK backend compiles with real identity. Candidate stays in_progress until exact-pin rugged/spec/quality reviews pass. Host models identify themselves, never claim physical evidence.

### J2 — Adversarial review and repair
- Status: done. Independent RUGGED, non-author spec PASS and non-author quality PASS on runtime pin748fce8 plus exact rugged hash. Rugged independently ran130 additional cases and384 malformed-intent repeated recoveries, real EIO wrappers and byte snapshots. All four model-tier holdout steps met (100/100); physical tier explicitly unscored. No production changes were made after these reviews.
- Objective: review a pinned immutable J1 candidate, one scoped correction per iteration if required.
- Areas: exact candidate, its actual test/command outputs and three fresh non-author review contexts; source writers paused.
- Validation: `make test && python3 -m unittest discover -s tests -p test_contract.py -v && python3 -m unittest discover -s tests -p test_native_storage.py -v && make 3ds && make verify-3ds && git diff --check` on every changed pin; current scoped `/rugged review` must be RUGGED; independent spec and quality reviewers PASS with source/report hashes. Run extra tail/CRC/state/type/read/close/retry/move fault probes rather than repeating happy paths.
- Acceptance: no acceptance from author prose/process exit alone; preserve dissent and exact limits. After repeated non-improvement use wonder/reflect/escalate, at most three recovery cycles then explicit blocker.

### J3 — Drop demo, docs audit and durable handoff
- Status: done for this slice. README seven-stage block executed VERBATIM on clean final pin7446e605, exit0 (8 existing +10 native tests +1 real recovered-log Drop test), real ARM artifacts, no skips. Final five-role docs audit: original RED image/status traceability fixed, corrective report AMBER/no RED, fresh scoped senior-doc closure PASS on all five named actions; dissent/history retained. Installed report structural check/index and durable source/evidence references recorded at handoff. No physical SD/powerloss or whole-app/fleet approval.
- Objective: prove actual emitted/recovered active log is discoverable/pullable and leave permanent source/evidence references.
- Areas: isolated committed Drop host snapshot, disposable SD fixture, app docs, root approval record, source refs, sanitized report.
- Validation: `DROP_SERVER_BIN="$PWD/build/host/3ds_drop_host" python3 -m unittest discover -s tests -p test_drop_storage.py -v` for actual `/api/logs` and `/api/pull` byte parity, bounded terminate/wait; the full explicit J1 command chain on final source; full five-role docs audit on immutable source/docs snapshot and installed `audit.sh --check-report` on the actual report; `git diff --check`.
- Acceptance: real host/API/native compilation evidence stays distinct from physical SD/power-loss; save/config policy unchanged; accepted/blocked source refs also registered in durable original app Git store. No unpublished work left solely in temp directories. New public surface documented. Report wall/allocated/observed active clocks with missing data explicit, no causal speedup claim.

## Exact acceptance design
SPEC.md now contains the normative fixed64-byte intent layout, exact sidecar names, eighteen named checkpoint selectors, first/append/rotation starting bytes, per-case exact test names, byte-preservation/success/refusal oracles, recovery limits (32 transitions/call, five-second child test bound), old-production fail-before method, SDK ownership fixture, and actual Drop integration invocation. This is the single case-to-command-to-oracle matrix required by the first review.

## Gate history
- First R5 plan review: UNKNOWN on missing enumerated fixture/oracle design, not missing implementation. Remediation specified the matrix above; a fresh plan rerun was RUGGED before J1. The initial UNKNOWN remains history, not a second current verdict.
- Full-track baseline audit completed four real personas plus writer: AMBER, no RED. Exact layout/state/selector/approval/precedence/sidecar/name gaps have been addressed in the spec and governing parent plan; local app constitution/log-contract/test registration remains an explicit J1 acceptance requirement, not a claim already migrated. Minor onboarding/reporting reservations are retained for final audit.
- Approval is coordinator-attested from the two explicit user yes messages, not missing operator input. Implementation-format defaults and test-registration mechanics are normal coordinator decisions within that approved scope; no new human question is required.

## Readiness and ruggedness
- Resume/Grill: goal, user-visible recovery, constraints, exact scope/limits, explicit approval and immaterial-default boundary are known.
- Plan readiness: scoped rerun verdict **RUGGED**, no remaining design gap; actual baseline four-persona-plus-writer review completed AMBER/no RED and its load-bearing specification gaps corrected by the executable matrix. Current plan verdict is in evidence/rugged-plan-r5-rerun.md; initial UNKNOWN retained as history.
- Readiness score:94/100 (goal20, observable success19, scenario coverage18, backpressure19, scope18). Constitution/spec/plan/scenario agree; no physical success implied. No additional operator decisions are required inside this approved first slice.
- Preflight: separate candidate parent is committed/clean at dispatch; existing root changes are the explicitly approved doctrine/spec record, not stashed user work. Root is not reset or stashed to manufacture a baseline. No code iteration marked done before its exact exit0 and required reviews.
