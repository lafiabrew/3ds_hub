# Docs Audit Report — native-log-journal plan-exit baseline

- **Scope:** `.wgm/IMPLEMENTATION_PLAN.md`, `.wgm/native-log-journal-spec.md` (root README/specs historical, not claimed migrated; future module/tests are requirements)
- **Track:** Full
- **Trigger:** Plan-exit baseline
- **Overall verdict:** AMBER (no RED; structural validity is not GREEN)

## Persona findings

### wgm-docs-junior — clarity & onboarding
Ten findings (8 AMBER, 2 GREEN, no RED): undefined jargon (R1/R5, T1/T2, RUGGED, fleet clock, ownership manifest, "reviewed queue"); typos in plan (`approval2026-11-03`, `reviewed90c8b113…`, `existing8`); Behavior/Acceptance as dense fragments; validation chain unexplained and new test not marked expected-to-fail; spec terms used before defined, no layout table or transaction state diagram; 64-byte "recommended" ambiguous; no worked sidecar example or recovery-state/UI-message table; vague cross-references with no paths; GREEN: files-to-create not marked, Evidence-durability section unexplained, plan/spec acceptance overlap.

### wgm-docs-senior — correctness, completeness, maintainability
Eleven findings (9 AMBER, 2 GREEN, no RED): same typos and history file not cited by path; Acceptance asserts legacy loss as established rather than as a fail-before requirement; SDK/header pin behind the delete-before-retry model not named; sidecar names incomplete (previous-backup suffix unnamed, so Drop `.log` exclusion unassertable); intent record layout/CRC unspecified; no state-by-placement recovery matrix; no precedence over `specs/log-contract.md`; constitution invariant 1 (atomic `rename()`) vs spec, exception wording unspecified; intent publication/flush ordering and partial-intent handling unspecified; user-visible states/retry bound/shutdown outcome undefined; GREEN: replacement for `mkdir` on device mount unstated; plan/test-count/ancestor consistency verified.

### wgm-docs-principal — architecture, strategic fit, consistency
Five findings (3 AMBER, 2 GREEN, no RED): local constitution says "Deviations … none" while plan requires native-log exception, and plan does not gate acceptance on recording it; spec does not state it amends `specs/log-contract.md` rotation text, no named target specs or sidecar suffix list; `tests/test_native_storage.py` not reconciled with `specs/required-tests.json` / AGENTS gate / matrix precedence; GREEN: typos and 64-byte normativity; "guarded root"/"original fleet clock" undefined. No conflict found on Drop route reuse or save/config boundary.

### wgm-docs-pm — status, risk, traceability
Nine findings (6 AMBER, 3 GREEN, no RED): two plans (root T1 vs `.wgm` R5) with no governing statement; baseline `90c8b113` vs HEAD relationship unstated; typos and approval recorded only by date; new test additive to matrix gate unstated and required test names for slice unlisted; residual risks only in spec, not in plan; previous-backup name ambiguous; constitution exception not yet present and no owner/timing; GREEN: spec traceability good; review chain stated clearly.

## Consolidated report (wgm-docs-writer)

Overall AMBER: all four personas found specification gaps, none RED. Findings were verified against the working tree (checks listed under Rejected findings and below). Verified true: plan line 5/6/10 typos (`approval2026-11-03`, `reviewed90c8b113…`, `existing8`); `specs/CONSTITUTION.md` says "Deviations from the root constitution: none" and has zero matches for "journal"/"native"; `specs/required-tests.json` has zero matches for `test_native`; `.wgm/history/r1-plan-at-90c8b113.md` exists but plan says only "under history".

### README index check
- Root `README.md` exists; there is no `docs/` directory, so no `docs/README.md` index.
- Root README read order lists `AGENTS.md`, `IMPLEMENTATION_PLAN.md`, `specs/app.md`, `specs/log-contract.md` only. `.wgm/IMPLEMENTATION_PLAN.md`, `.wgm/native-log-journal-spec.md` and `.wgm/history/r1-plan-at-90c8b113.md` are indexed nowhere (grep of README for "wgm" found nothing). Per scope the README is historical and the first slice excludes broad rollout, so this is flagged, not treated as a new defect in unrelated docs.
- No index entry points at a missing file. Reported commit `90c8b113` exists.

### Agent actions
> The agent can execute these directly and deterministically.

| # | Finding | Raised by | Doc(s) | Action |
|---|---|---|---|---|
| 1 | Missing-space typos (`approval 2026-11-03`, `reviewed 90c8b113…`, `existing 8`) and "under history" lacks path | junior, senior, principal, pm | `.wgm/IMPLEMENTATION_PLAN.md` | Fix spacing; cite `.wgm/history/r1-plan-at-90c8b113.md`; use "eight" consistently |
| 2 | Exact sidecar names incomplete: previous-backup suffix unnamed; no rule table that none end in `.log` | senior, principal, pm, junior | `.wgm/native-log-journal-spec.md` | Add table of exact suffixes/roles (`.tmp`, `.txn`, `.bak`, `.previous`, previous backup) plus a worked example |
| 3 | Spec has no precedence/supersession statement vs `specs/log-contract.md` rotation text; target spec files for the Documentation item unnamed | senior, principal | spec, plan | State native-only supersession and name `specs/log-contract.md` / `specs/app.md` deltas |
| 4 | Terms undefined / used before definition (R1/R5, T1/T2, RUGGED, ownership manifest, intent record, generation, fleet clock, guarded root, "reviewed queue") and vague cross-references | junior, principal, pm | plan, spec | Add glossary and relative links |
| 5 | Plan/spec acceptance and behavior text are dense fragments; duplicated lists; validation chain is one line; new tests not marked expected-to-fail | junior | plan, spec | Rewrite as numbered/bulleted testable checklist; state spec acceptance governs |
| 6 | Acceptance asserts legacy loss as established fact | senior | plan | Reword as fail-before requirement under the delete-before-retry model |
| 7 | Plan does not state which plan governs (root T1 vs `.wgm` R5) and root plan/README/specs remain historical | pm | plan | Add one-line governing-plan/precedence statement |
| 8 | New `tests/test_native_storage.py` not reconciled with `specs/required-tests.json`, AGENTS gate and matrix precedence; required names unlisted | principal, pm | plan, spec | State the gate is additive to the matrix gate and list required test names (or name the registration deliverable) |
| 9 | Plan has no known-limits/risks section (single writer, CRC not authentication, no hardware/power-loss evidence, physical tier unverified) | pm | plan | Add "Known limits and risks" and what "done" does not prove |
| 10 | Intent record layout (offsets, magic, CRC coverage), 64-byte normative vs recommended, intent publication/flush order, partial-intent handling | junior, senior, principal | spec | Specify v1 layout and write protocol, or make layout an explicit header+spec deliverable |
| 11 | No state-by-placement recovery matrix; user-visible states, retry bound and shutdown outcome undefined; no recovery-state message table | senior, junior | spec | Add recovery matrix (roll-forward/no-op/refuse) and canonical state vocabulary with retry limits |
| 12 | Constitution exception must be an explicit acceptance gate landing with the candidate; exception wording not specified | principal, pm, senior | plan, spec | Add acceptance item to record the native-log-only exception in the local constitution deviations, citing approval; wording drafted in the spec |
| 13 | Pinned SDK version/fixture behind the delete-before-retry model not named | senior | spec | Name pinned SDK version/commit and fixture path |
| 14 | `mkdir` replacement on device mount unstated; files-to-create not marked | senior, junior | spec, plan | Add one sentence for replacement; mark new vs modified files |
| 15 | Evidence-durability section: undefined "guarded root", "original fleet clock" | junior, principal | spec | Define or link; move to an operator-process heading |
| 16 | Plan/spec docs not indexed by root README (flagged in index check) | writer index check | `README.md` | Add pointer only if/when the migration slice is accepted; otherwise leave as noted |

### Operator actions
> These need a human decision, external confirmation, or access the agent doesn't have.

| # | Finding | Raised by | Doc(s) | Why it needs a human |
|---|---|---|---|---|
| 1 | Where the approval ("two explicit yes responses", `2026-11-03`) is recorded, or whether it is operator-attested | pm | plan, spec | Only the operator can supply or attest the approval record |
| 2 | Decide whether 64-byte record is normative and whether new tests join `specs/required-tests.json` vs run as extra gate; confirm fleet matrix permits it | junior, principal, pm | plan, spec | Matrix is coordinator-supplied and precedence is a policy call |
| 3 | Owner/timing for the constitution exception and for the persistent evidence storage location | pm, junior | plan, spec | Ownership and external process decisions |

### Rejected findings (verified false or already mitigated)

| Finding | Raised by | Verification performed | Evidence / disposition |
|---|---|---|---|
| AMBER: baseline `90c8b113` vs HEAD relationship is unclear (source may differ) | pm | `git diff --stat 90c8b113 HEAD`; `git diff --stat 90c8b113 HEAD -- src include tests Makefile` | Only `.wgm/IMPLEMENTATION_PLAN.md`, `.wgm/history/r1-plan-at-90c8b113.md`, `.wgm/native-log-journal-spec.md` differ; source/tests/Makefile identical. Already mitigated by scope statement; downgraded to the optional one-line note folded into Agent action 7, not a standalone AMBER |
| Reviewed commit may not exist | pm (checked) | `git cat-file -t 90c8b113` | Returns `commit`; no defect |
| New module/test absent is a defect | pm, senior | Scope text; `ls tests` per personas | Explicitly out of scope as future requirements; not promoted |
| Conflict on Drop route reuse / save-config boundary | principal (none found) | Personas' cross-checks | No contradiction found; nothing to promote |

### Dissent
Severity differences only, none contradictory on action:

| Finding | Persona A view | Persona B view | Preserved as |
|---|---|---|---|
| Typos (`approval2026-11-03` etc.) | junior, senior: AMBER | principal, pm: GREEN | Agent action 1 (severity split preserved; not averaged) |
| 64-byte intent record not pinned | senior: AMBER (untestable without layout) | junior: AMBER (ambiguity); principal: GREEN | Agent action 10 and Operator action 2 |
| Baseline vs HEAD | pm: AMBER | senior: GREEN (reviewed commit is ancestor of HEAD, verified) | Rejected as standalone AMBER; dissent noted |
| Evidence-durability undefined terms | junior, principal: GREEN | not raised by senior/pm | Agent action 15 |
| Constitution exception | principal, pm: AMBER (acceptance gate) | senior: AMBER (wording) | Agent action 12; converge on AMBER |

## Verdict history
- No prior entry in a `docs/audit/README.md` (no `docs/` directory exists); first recorded baseline for this slice. Report checker: run by dispatcher via `scripts/audit.sh --check-report`.
