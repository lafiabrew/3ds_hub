# Implementation plan — public repository hygiene

## Scope and approvals
- Standard track; fresh headless build via the installed wgm loop runner. Artifacts stay under `.wgm/`; never overwrite the existing root plan.
- Operator requested personal paths and incidental personal details removed for public repositories.
- Operator explicitly approved removing the personal path from the existing `AGENTS.md` heading, and enabled wgm consent for all repositories/subrepositories here.
- Preserve project branding, copyright/license attribution, links, tests, runtime behavior, local SD diagnostics, and existing Git history. Do not push.
- Root pre-run HEAD: `ed47dbf`; eight child repositories initially clean. The only pre-existing root residue is the untracked local `sd_logs_170/` export, which must remain untouched.
- Preparation: write missing consent files in seven app repositories, retain two existing enabled configs, snapshot diagnostic hashes, and commit a shared planning baseline including an ignore rule for SD export folders. No private diagnostic data enters Git.

## Convergence
- Satisfaction threshold: 95; one tier-1 holdout journey under `.wgm/scenarios/`.
- Holdout files may be read only in Validate/Review, never by the implementer.
- Deterministic signal already exists: a tracked-file regex scan currently fails on seven files. New local validator formalizes it without echoing private matches.

## Ruggedness gate
| When | Scope | Verdict | Date | Producer | Follow-up |
|---|---|---|---|---|---|
| Plan-exit | Plan and public-paths spec | RUGGED | 2026-11-02 | `/rugged plan` rerun; `.wgm/rugged/2026-11-02-public-paths-plan.md` | T1 includes the index/inventory/diagnostic/edit-boundary checks |
| Review T1 | Seven-file prose delta and guards | RUGGED | 2026-11-02 | Fresh `/rugged review`; `.wgm/rugged/2026-11-02-public-paths-review-t1.md` | None |
| Review T2 | Demo and documentation handoff | RUGGED | 2026-11-02 | `/rugged review` companion protocol, coordinator; `.wgm/rugged/2026-11-02-public-paths-review-t2.md` | None |

Preflight readiness: 96/100 (goal 20/20, observable success 20/20, demo coverage 19/20, backpressure 19/20, scope edges 18/20). Specs, checklist, tasks, constitution and tier-1 journey are consistent; all requirements have commands and task coverage.

### Exact remediation check design (T1)
- Extend `.wgm/validate_public_hygiene.py` to assert the known inventory (root plus the eight app names in the root Makefile), scan both working-tree bytes and `git show :<path>` staged blobs, and reject any tracked/indexed path under `sd_logs*/` even after `git add -f`.
- Extend `.wgm/verify_preservation.py` to compare root baseline lines outside the authorized changed lines (AGENTS/Makefile/constitution line 1; audit scope line 4; README lines 1 and 3; old plan lines 4 and 15) and compare executable server AST excluding only its module docstring. This is intentionally a narrow prose edit, not a document rewrite.
- Add `.wgm/test_public_hygiene_guards.py`; run `python3 .wgm/test_public_hygiene_guards.py` from the real workspace. In disposable Git fixtures, clean inventory/content must pass; a missing expected repo, personal path staged then cleaned only in the working tree, forcibly staged diagnostic, and edit outside an authorized line must each fail with nonzero/check rejection. Synthetic private examples must use constructed strings so no literal personal path is committed.
- Expected real workspace result after sanitization: `python3 .wgm/validate_public_hygiene.py` exits 0 for all nine repo indexes and working trees, followed by preservation and hub CLI checks. Any negative-control survivor blocks completion; fix only task-owned files and rerun. Never reset/stash/delete unrelated files.
- Review history: first plan verdict was UNKNOWN because the original working-tree-only signal missed staged data, inventory omissions, forced diagnostic staging, and narrow edit guards. The revised contract above is the validation-signal task required by that verdict; a fresh plan readiness review must approve it before implementation.

### Concurrent-work boundary
- During planning, independent edits/commits appeared in `3ds_sysdash/` and `3ds_wigle/`; their authors also captured the authorized consent configs. Do not edit, stage, revert, or commit any of their product files.
- Child file changes after the initial snapshot are not owned by this cleanup. Validate all child public indexes for privacy and consent, but distinguish concurrent product changes from preservation of this run's root edits. No claim is made that the whole child workspace is unchanged.
- Five child consent-only commits were made directly by this run; the other two new configs were included by concurrent work. The root and PieceDuel configs were already enabled.

## Tasks
### T1 — Sanitize public workspace text without altering behavior
- **Status:** done
- **Objective:** Replace personal workstation paths and incidental operator identity with relative workspace descriptions.
- **Spec:** `.wgm/specs/public-paths.md`; `.wgm/specs/CONSTITUTION.md`.
- **Files/areas:** `AGENTS.md` (heading only), `README.md` (heading/introduction), `Makefile` (opening comment), `serve_3ds.py` (module docstring only), `IMPLEMENTATION_PLAN.md` (overview and incidental handle), `specs/CONSTITUTION.md` (heading only), `docs/audit/2026-11-02_3ds-homebrew-suite-audit.md` (scope only); `.wgm/validate_public_hygiene.py`, `.wgm/verify_preservation.py`, and `.wgm/test_public_hygiene_guards.py` for the named validation-signal remediation.
- **Validation:** `python3 .wgm/test_public_hygiene_guards.py && python3 .wgm/validate_public_hygiene.py && python3 .wgm/verify_preservation.py && python3 serve_3ds.py --self-test && python3 -m unittest discover -s pc_companion/tests -v && git diff --check`
- **Acceptance:** No user-home paths/inline personal handles in tracked text across nine repos; no other changes to runtime code or existing tests; links and attribution remain; two fresh non-author reviews and `/rugged review` pass before done.
- **Notes:** An outer coordinator will dispatch the two independent reviews, rugged review, and final holdout validation. If those cannot be independently invoked, leave status blocked, never claim self-review is independent. A headless implementer may complete edits and validation, then leave status in_progress awaiting the outer reviews. Stage only the seven authorized root prose files so the real index is sanitized before running the staged-content gate; do not stage child work. Do not push or commit before the outer review.

### T2 — Demo validation and public-tree handoff
- **Status:** done
- **Objective:** Prove portability cleanup, retained diagnostics, and unchanged package discovery on the actual workspace.
- **Spec:** `.wgm/specs/public-paths.md`.
- **Files/areas:** `.wgm/IMPLEMENTATION_PLAN.md`, `.wgm/rugged/`, `.wgm/docs/audit/`; actual `serve_3ds.py` CLI and all nine repository indexes.
- **Validation:** `python3 .wgm/validate_public_hygiene.py && python3 serve_3ds.py --self-test && python3 serve_3ds.py --list && python3 .wgm/verify_preservation.py && git diff --check`
- **Acceptance:** All commands exit zero; all eight apps discovered; exported diagnostics byte-identical and ignored; server executable AST unchanged; no cleanup-owned changes to child product files or existing tests/attribution (concurrent work reported separately); holdout score >=95; independent reviews and one RUGGED review verdict; mandatory five-role docs audit recorded and structurally checked.
- **Notes:** Docs audit is scoped only to this privacy delta; preserve and list unrelated pre-existing documentation debt rather than expanding into product changes.

## Validation and resume record
- Baseline: generic scan failed on exactly seven tracked files; no matches found in child tracked files.
- Enabled consent was verified in all nine repositories.
- Headless capability probe exited 0 with READY. No plugin metadata was discovered. Use Copilot CLI for fresh context; record unavailable capabilities honestly.
- All run-specific logs, snapshots, and review raw outputs are local ignored scratch; the durable plan/spec and consolidated audit may be explicitly added despite the existing `.wgm/` ignore rule.

### T1 implementer handoff — 2026-11-02
- **State:** T1 remains `in_progress`; T2 remains `pending`. Stop after this one implementation iteration. No commit, push, child edit/staging, or STOP sentinel was performed.
- **Root review HEAD:** `732ffba`; original prose baseline remains `ed47dbf` in Git only. The hashes-only snapshot remains `.wgm/privacy-baseline.json`; no copy of private baseline prose was written.
- **Implemented:** Sanitized exactly the seven authorized root prose files (10 replaced lines). `AGENTS.md` changed only its heading. Server source outside its module docstring, executable AST, unrelated root files, links, attribution, and existing tests are preserved.
- **Guards:** `.wgm/validate_public_hygiene.py` requires the fixed root-plus-eight inventory and matching Makefile app list, scans tracked working-tree bytes and staged blobs, checks both consent surfaces, and rejects indexed diagnostic exports, including forced additions. Findings print categories, not private matched text. `.wgm/verify_preservation.py` checks root working-tree/index lines against Git, preserves source outside the server docstring, verifies diagnostic hashes and discovery/history, and reports child changes without requiring old child file hashes.
- **Fixture signal:** `.wgm/test_public_hygiene_guards.py` contains 10 passing tests. Constructed synthetic paths/handles exercise working-tree and staged-only leaks, all nine indexes, missing inventory, forced diagnostic staging, staged consent, every authorized line boundary, unauthorized index/disk edits, server source/AST preservation, and concurrent child development. Fixture repositories are disposable and cleaned automatically.
- **Backpressure:** The exact T1 Validation command above exited **0** after final guard edits: 10 fixture tests; 187 tracked files across all nine repositories; preservation checks; hub self-test discovering eight packages; four PC integration tests; `git diff --check`. `git diff --cached --check` also exited 0. An in-memory scan of the seven original Git blobs reproduced seven privacy failures without printing or persisting their content.
- **Local diff review:** PASS for the authorized root lines and the three task-owned helper/test files; no existing test was edited. This is author review only, not an independent correctness or ruggedness verdict.
- **Index:** Exactly the seven authorized root prose files are staged. The task plan and two existing helpers remain unstaged; the new fixture test is an ignored, on-disk `.wgm/` file deliberately left unstaged. The coordinator must retain that file for review and later authorized staging.
- **Validation environment:** Commands ran on the actual Python/Git host, including existing self-test/integration service checks. No OCI/Podman or holdout-service validation was run or claimed. No diagnostic content or holdout scenario was opened during Analyze/Implement; diagnostics were accessed only by the hash-preservation check during Validate.
- **Outstanding gates:** Coordinator must run fresh spec-compliance and quality reviews, `/rugged review`, and independent holdout judging (target >=95). No satisfaction score or diff ruggedness verdict is claimed by this implementer. Do not mark T1 done until those gates pass; do not begin T2 in this iteration.

#### Child work — reported separately, not owned by T1
All eight child worktrees were clean at handoff inspection. Differences from the older snapshot are committed preparation/concurrent work, not edits made by this implementer:
- `3ds_drop`, `3ds_netpass`, `3ds_padtest`, `3ds_pokedash`, `3ds_rngtool`: consent configuration and `src/platform_3ds.c` (two paths each).
- `3ds_pieceduel`: `src/platform/platform_3ds.c` (one path).
- `3ds_sysdash`: `include/sd_app.h`, `include/sd_sysdash.h`, `meta/app.rsf`, `src/app.c`, `src/platform_3ds.c`, `src/sysdash.c` (six paths).
- `3ds_wigle`: `src/platform_3ds.c` (one path).

**Implementer handoff gate (historical):** Independent reviews and holdout scoring were still pending when the implementer stopped; it correctly left T1 in_progress at that time.

### T1 coordinator completion — 2026-11-02
- The coordinator reran the exact T1 validation command; exit **0**, recorded in local `.wgm/t1-validation.log`: 10 guard fixtures, four PC integration tests, nine-repository index/working-tree scan, preservation checks, hub self-test, and whitespace gate.
- Fresh non-author spec reviewer **PASS** (`.wgm/spec-review-t1.md`); fresh non-author code-quality reviewer **PASS** (`.wgm/quality-review-t1.md`). Both had the RUGGED verdict in hand. They inspected real artifacts and independently reran lightweight checks. Independence is fresh context and role, not different model/tooling.
- `/rugged review` **RUGGED**, dated 2026-11-02; evidence rung 4; `.wgm/rugged/2026-11-02-public-paths-review-t1.md`.
- Independent tier-1 acceptance scoring: 100, 100, 98, 100, 100; mean **99.6/100**. Weakest step is hub behavior: reviewer reran discovery but relied on the coordinator's real self-test log. No regression. Nonblocking reservation: run the preservation helper with normal Python, not `-O`; these helpers are a scoped run-specific signal, not universal PII detection.
- **Iteration-exit gate:** PASS — implementation done; exact validation exited 0; result recorded; scope/acceptance reviewed by two non-authors; one current RUGGED diff verdict recorded; plan updated; exactly T1 advanced to done. T2 remains pending.
- No new product public API, CLI flag, or runtime behavior; seven edited public files include documentation. Validation helpers are run-specific `.wgm/` tooling. No push performed.
- T1 committed as `7792458` (`docs: remove private workstation details from public files`).

### T2 demo evidence — 2026-11-02
- The exact T2 demo-validation command exited **0** on the real host, captured in local `.wgm/t2-validation.log`. It confirmed all nine repository indexes/working trees, eight real app packages, unchanged root source outside authorized lines and executable AST, byte-identical diagnostic exports, and ancestor-history preservation.
- No separate product deploy pipeline or remote publication is part of this cleanup; no push is authorized or claimed. Native hardware testing and universal PII detection are not claims of this prose-only change.
- The plan/spec and private hashes-only snapshot describe this run's local evidence; the preservation checker deliberately requires that local `.wgm/privacy-baseline.json`, not a fresh clone. Existing `.wgm/` ignore policy remains; only selected durable artifacts are explicitly staged.
- At demo capture time, T2 still awaited the five-role audit and final reviews. Those gates are completed below.

### T2 coordinator completion — 2026-11-02
- Five-role audit completed through the installed portable dispatcher: four fresh persona contexts and a separate writer; GREEN for this privacy delta. `.wgm/docs/audit/2026-11-02T2110Z_public-repository-hygiene.md` passed the actual `scripts/audit.sh --check-report` structural checker (exit 0) before indexing in `.wgm/docs/audit/README.md`.
- First audit attempt correctly aborted when its own redirected live log changed inside the guarded target. Exact delta showed only that log; no files were reverted. Complete rerun passed with dispatcher output outside the target tree and bytecode generation disabled. Local failure and successful external logs are retained; the lesson is in `.wgm/memories.md`.
- Fresh non-author final spec reviewer **PASS** (`.wgm/spec-review-t2.md`); fresh non-author final quality reviewer **PASS** (`.wgm/quality-review-t2.md`). Both had the T2 RUGGED verdict in hand. Their timing reservations were resolved by waiting for both reports and explicitly filing the durable evidence.
- Final tier-1 acceptance: 100, 100, 98, 98, 98; mean **98.8/100**, above 95. No scenario crossed below the convergence threshold. Reservations retained: some suite/hash observations came from real recorded logs rather than every reviewer repeating them; concurrent child commits are outside cleanup ownership.
- `/rugged review` **RUGGED**, dated 2026-11-02; evidence rung 4; `.wgm/rugged/2026-11-02-public-paths-review-t2.md`.
- Product docs required no further correction. The installed skill's `check-docs.sh` is hard-wired to its own tool source tree; an attempted help probe ran that tool self-audit and reported unrelated existing placeholder debt, not a check of this workspace. The actual project audit report's structure passed the supported `audit.sh --check-report` path; no outside-tool failure is relabeled as product success.
- History audit: cleanup-owned commits use Conventional Commits; no root trailer requirement exists. Original root/child baselines remain ancestors. No history rewrite, push, release, deploy, or native-hardware validation was performed or claimed.
- Anonymized single-lesson harvest was previewed, inspected, then reported upstream automatically under the enabled consent. The courier performed its own de-duplication, residual-identifier checks, and publication; exit 0. No project names, data, paths, or private identifiers were included in that report.
- **Iteration-exit gate:** PASS — demo work done; exact validation exited 0; result recorded; two independent final reviews PASS; one current RUGGED T2 verdict; plan updated; exactly T2 advanced. All must-have tasks are done.

## Nonblocking follow-up (outside this cleanup)
- **D1 — Reconcile pre-existing product documentation.** Areas: `README.md`, `AGENTS.md`, root plan/specs/historical audit, child `meta/app.rsf`. Signal: `git grep -nE '0x0D3[D-E][0-7]|UniqueId' -- README.md AGENTS.md IMPLEMENTATION_PLAN.md specs docs` followed by each child's `make verify-3ds` and an accuracy review of broad feature claims. Acceptance: current identifiers match verified metadata; historical claims are clearly labeled rather than silently rewritten. Optional separate work, not a privacy blocker; any additional `AGENTS.md` changes need new explicit approval.

## Telemetry (no estimates)
- Total wall time to ready-to-test: **not captured**; no reliable start marker for the full interactive run.
- Allocated lane time, parked lane time, lane counts, peak lane concurrency, and critical-path duration: **not collected**; no worktree/swarm lanes were used.
- Active agent time and timed-versus-missing turn counts: **unavailable**; the host does not expose a summed per-turn clock here.
- `.wgm/metrics.tsv` measured **one build invocation, 209 seconds**, from 21:01:45Z to 21:05:14Z. This is process duration, not active agent time, billing, or a speedup claim. Fresh reviewer/doc-persona calls were not instrumented as lanes or turns.

## Handoff
- Public product cleanup is seven files and ten prose-line replacements, plus the diagnostic ignore policy. All nine repositories have enabled wgm consent; five consent-only commits were authored by this cleanup, two new configs were captured in concurrent child commits, and two configs already existed.
- Validate locally with the T1/T2 commands above; `.wgm/privacy-baseline.json` intentionally remains local/ignored for diagnostic hashes. The executable server and existing tests are unchanged by this cleanup.
- The root tree will be committed and left clean; unrelated child work is preserved and separately reported. Historical commits still contain former text. Offer `/teach-me` or `/quiz-me` only if the maintainer wants an evidence/tooling walkthrough; no new application behavior was built.
