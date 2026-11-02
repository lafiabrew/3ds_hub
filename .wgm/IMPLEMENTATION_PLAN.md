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
- **Status:** pending
- **Objective:** Replace personal workstation paths and incidental operator identity with relative workspace descriptions.
- **Spec:** `.wgm/specs/public-paths.md`; `.wgm/specs/CONSTITUTION.md`.
- **Files/areas:** `AGENTS.md` (heading only), `README.md` (heading/introduction), `Makefile` (opening comment), `serve_3ds.py` (module docstring only), `IMPLEMENTATION_PLAN.md` (overview and incidental handle), `specs/CONSTITUTION.md` (heading only), `docs/audit/2026-11-02_3ds-homebrew-suite-audit.md` (scope only); `.wgm/validate_public_hygiene.py`, `.wgm/verify_preservation.py`, and `.wgm/test_public_hygiene_guards.py` for the named validation-signal remediation.
- **Validation:** `python3 .wgm/test_public_hygiene_guards.py && python3 .wgm/validate_public_hygiene.py && python3 .wgm/verify_preservation.py && python3 serve_3ds.py --self-test && python3 -m unittest discover -s pc_companion/tests -v && git diff --check`
- **Acceptance:** No user-home paths/inline personal handles in tracked text across nine repos; no other changes to runtime code or existing tests; links and attribution remain; two fresh non-author reviews and `/rugged review` pass before done.
- **Notes:** An outer coordinator will dispatch the two independent reviews, rugged review, and final holdout validation. If those cannot be independently invoked, leave status blocked, never claim self-review is independent. A headless implementer may complete edits and validation, then leave status in_progress awaiting the outer reviews. Stage only the seven authorized root prose files so the real index is sanitized before running the staged-content gate; do not stage child work. Do not push or commit before the outer review.

### T2 — Demo validation and public-tree handoff
- **Status:** pending
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
