# R5 native diagnostic journal — accepted first slice

## Outcome
Implemented and accepted the approved LinkLab native diagnostic-log storage slice. **Not a whole-app/fleet release or physical SD/power-loss pass.** Save-file and SD-configuration guarantees are unchanged, and no existing AGENTS was edited.

- Runtime/code pin: `748fce8d1e9ec3b8e88dc256c1c1e9304712db69`.
- Final docs pin: `7446e605aeca206733262ab563e7b4a4a43e60f5`; production, tests, Makefile and registries are byte-identical to reviewed runtime source.
- Durable original app ref: `3ds_linklab` → `recovery/native-log-journal`. Main was not merged/moved; no remote push, automatic install or other-app migration occurred.
- Actual source workspace and its Git store are under this run's `workspaces/` and `lanes/` on the project volume. Accepted source is also registered in the original app store. Evidence checkpoints are under `evidence/`, not solely ephemeral temp storage.

## What changed
A fixed-size checked intent, retained active/previous backups, exclusive moves and bounded recognized-state recovery replace the unsafe native overwrite path. Direct FSUSER_RenameFile never deletes a destination to retry. Native archive-close failure retains ownership and prevents opening replacement handles. UI exposes EXPORTED, RECOVERED, RECOVERY PENDING and EXPORT FAILED; root mount is statted rather than mkdir'd.

Unknown/corrupt states, unsafe file types, bad checksums/flags/size and legacy orphan staging are visibly refused while recoverable bytes remain. CRC32 is corruption detection, not authentication. One trusted app writer and fixed diagnostic namespace are explicit limits. Ordinary host behavior and its prior eight test assertions remain unchanged.

## Actual evidence
- Coordinator executed the README seven-stage block **verbatim** on the clean final pin: exit0, **8 existing contracts +10 native-storage tests +1 recovered-log Drop test**, actual ARM11 ELF/SMDH/3DSX/CIA and hygiene. `evidence/final-7446e605/receipt.json` binds the script, full output, source and clean after-state.
- Fail-before uses actual frozen old90c8b113 logger with the pinned SDK delete-before-retry/interrupted retry contract. Successful execution reproduces lost prior committed records; it is not a compile or sanitizer-initialization failure counted as a repro. Independent coordinator proof is retained under `evidence/legacy-proof/`.
- Native tests exercise all eighteen normative stages before/after interruption, repeated recovery, I/O/cleanup failures, partial intents, unknown/corrupt files and native SDK acquire/EEXIST/failed-close/retry/shutdown ownership. Actor mutation probes killed seven deliberately broken guards; these are supporting evidence, not substituted for the coordinator gate.
- Independent scoped **RUGGED**, non-author spec **PASS**, non-author quality **PASS**. Rugged independently added130 adversarial cases and384 repeated malformed-intent recoveries plus real read/close/move EIO wrappers. Spec judged all four model-tier holdout steps met (100/100); physical tier remains unscored.
- Real committed Drop server source `c7477f836f120fe4bd2a72c2573ab57a6555af37`, with a disclosed transport-only loopback bind guard, discovered and returned the recovered app log byte-identically. The guard changes only bind addressing, not HTTP/storage behavior. Stock and guarded binary hashes intentionally differ. `evidence/pinned-748fce8/drop-loopback.json` and the final loopback bind receipt record the actual profile.
- Full final docs audit completed four personas plus a separate writer. A stale historical image ID and traceability lag were corrected; corrective report AMBER/no RED and fresh scoped closure PASS are retained with original dissent, structural exit0 and index. No old RED was silently changed to GREEN.

## Timing — no estimates or speedup claim
- R5 start:2026-11-03T05:38:39Z. Frozen scoped ready-to-test wall: **5737.460 seconds (1h35m37s)**, UTC start to second precision, before final report overhead. This includes recovery/setup, toolchain rebuild, planning, coding, validation, adversarial review and documentation fixes.
- Initial author-lane allocation: **24m09s**, capacity/lifetime bound through author exit; not agent-hours and not the full later review lifetime. The bundled lane reported a roughly five-second gap which includes its capability probe; do not call that productive work or exact parked time.
- Observed active child-agent turns (all completed instrumented planning/implementation/review/audit calls): **2301.504 seconds (38m21.5s), a measured lower bound**, including tool waits. Main-agent turn time is unavailable; one readiness probe was not instrumented.
- Completed instrumented child invocations:23; timed child turns211; missing turns within those records0. Main turn count/durations are unknown, not zero. Summed child invocation lifetime is a different clock, never relabeled active time.
- Peak original implementation lanes:1 for this slice; peak observed completed child-agent invocation concurrency across phases:2. Longest author lane24m09s. A complete orchestration dependency-DAG critical path and full reserved/parked-lane time were not collected; no reconstruction is claimed. Detailed per-phase figures are in METRICS.json; failed plan/audit/ownership outcomes remain separately recorded even when the underlying model call exited normally.
- Original fleet start2026-11-02T21:27:01Z remains a separate incomplete project clock. Missing historical raw/monotonic evidence was not recreated after temp workspaces disappeared. No full-fleet completion wall or causal parallel speedup is asserted.

## Remaining limits / follow-up
Real SD and power-loss behavior, HOME/lid observations, physical two-console networking and installed Drop retrieval remain unverified. No device URL was guessed or contacted. The rest of the twelve-project fleet is not accepted by this module result. Do not copy the backend into other apps until a separate per-app migration preserves its schema/seed/control behavior and passes its own failure/restart/native/API/review gates.

For a walkthrough of the state machine, tests and safe migration points, `/teach-me` can provide the cited tour; `/quiz-me` can check the handoff understanding. This report is evidence and a resumable checkpoint, not a claim that the operator has already learned the implementation.
