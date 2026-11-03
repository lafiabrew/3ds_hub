# Docs Audit Report — final R5 docs correction at 281a415

- **Scope:** README.md, specs/app.md, specs/log-contract.md, .wgm/IMPLEMENTATION_PLAN.md, .wgm/history/r5-author-handoff-at-748fce8.md (diff 748fce8..HEAD).
- **Track:** Full
- **Trigger:** Ship/Handoff
- **Overall verdict:** AMBER (no RED; open items are standalone-reader clarity and traceability. Structural validity is not GREEN.)

## Persona findings

### wgm-docs-junior — clarity & onboarding
| Doc | Observation | Severity | Recommended action |
|---|---|---|---|
| Scope | Diff touches only 5 docs; imageID is current. | GREEN | None |
| README gate | Ordered gate and FLEET_RUN fallback clear (not executed). | GREEN | None |
| README "Base checks retained" | Duplicates the gate; the `$FLEET_RUN` block has no standalone fallback. | AMBER | Label or fold duplicates |
| README Drop companion | Loopback-guard helper not named or linked; `DROP_SERVER_BIN` export wording vague. | AMBER | Name the helper or mark it coordinator-only |
| README test counts | Bare counts, no registry pointer. | GREEN | Reference the registry |

### wgm-docs-senior — correctness, completeness, maintainability
| Doc | Observation | Severity | Recommended action |
|---|---|---|---|
| README image | 74542c3d matches `evidence/toolchain-image-id.txt`, which lies outside `pinned-748fce8/`. | GREEN | Name the file |
| README gate | Targets, counts, hashes and pins match the evidence. | GREEN | None |
| README Base checks | Commands exist in two places. | GREEN | Collapse or label historical |
| README Drop companion | Guard build and invocation not documented; the profile is aggregate-only. | AMBER | State aggregate-only or give build steps |
| specs/app.md, log-contract.md | Review claims supported by evidence reports. | GREEN | Optional note that code is unchanged since 748fce8 |
| README status | Does not overclaim. | GREEN | None |

### wgm-docs-principal — architecture, strategic fit, consistency
| Doc | Observation | Severity | Recommended action |
|---|---|---|---|
| README "eight contracts" | 8 tests; `required-tests.json` has "11 entries" (structure not inspected). | AMBER | Confirm reconciliation |
| README "ten tests" | Accurate. | GREEN | None |
| Scope/code unchanged | Holds. | GREEN | None |
| Image ID | Stale e4fb375a gone; prior RED resolved. | GREEN | None |
| Status/provenance | Consistent across README and specs. | GREEN | None |
| Evidence pointers | `pinned-748fce8/` not resolvable from the standalone repo; existence unconfirmed. | AMBER | Verify the path; note the pointer is aggregate-relative |
| Gate | Coherent and fail-fast. | GREEN | None |

### wgm-docs-pm — status, risk, traceability
| Doc | Observation | Severity | Recommended action |
|---|---|---|---|
| Scope | Docs-only diff. | GREEN | None |
| README:107 image | 74542c3d is not in `pinned-748fce8/receipt.json`; it is only in `evidence/toolchain-image-id.txt`. | AMBER | Cite the correct source |
| README:84-92 | The unguarded `$FLEET_RUN` snippet is copyable standalone and fails. | AMBER | Label "fleet only" or add the fallback |
| README:30 | Status scoping clear. | GREEN | None |
| Evidence | Files match the 7-stage claim; the receipt is pinned at 748. | GREEN | None |

## Consolidated report (wgm-docs-writer)

### README index check
README is the entry point. specs/app.md, specs/log-contract.md, specs/required-tests.json, specs/native-storage-tests.json and .wgm/IMPLEMENTATION_PLAN.md exist. .wgm/history/r5-author-handoff-at-748fce8.md exists; I did not confirm that the README links to it (plan history). Evidence directory pointers resolve only in the aggregate checkout (`.wgm/native-log-journal-20261103/evidence/` verified to exist there, including `pinned-748fce8/`). No broken index entry found inside the standalone repo.

## Agent actions
> Deterministic doc edits.

| # | Finding | Raised by | Doc(s) | Action |
|---|---|---|---|---|
| 1 | "Base checks retained" block duplicates the gate, and its `$FLEET_RUN` snippet (README line 91) has no fallback. Verified: README lines 82-91. | junior, senior, pm | README.md | Label the block "fleet-only/historical" and point to the canonical gate, or reuse the line-70 conditional |
| 2 | Image ID source is not cited. Verified: `grep -c 74542c3d` gives 0 in `pinned-748fce8/receipt.json` and 1 in `evidence/toolchain-image-id.txt`. | pm, senior | README.md | Cite `evidence/toolchain-image-id.txt` as the source and say the receipt omits it |
| 3 | The Drop loopback-guard helper is unnamed and its build is undocumented (guard source is `evidence/drop_loopback_bind.c`). `DROP_SERVER_BIN` wording is vague. | junior, senior | README.md | Name the helper, mark it aggregate/coordinator-only, and state that `DROP_SERVER_BIN` must be exported in the shell running the last stage |
| 4 | Evidence pointers are aggregate-relative. | principal | README.md | State that the pointer is relative to the aggregate checkout |
| 5 | Test counts have no source pointer (low). | junior | README.md | Reference `specs/required-tests.json` and `specs/native-storage-tests.json` |

## Operator actions
> None required for this docs revision. The following remain inherited, undocumented-as-closed blockers (per README status).

| # | Finding | Raised by | Doc(s) | Why it needs a human |
|---|---|---|---|---|
| 1 | Real SD, power-loss, console and two-peer evidence, plus whole-app/fleet acceptance, remain unverified. | pm, senior, principal | README.md | Needs physical hardware and a coordinator decision |
| 2 | The final coordinator gate must refresh the pin; the 748fce8 receipt is not execution of this doc revision. | pm | README.md, evidence | The coordinator runs the gate; I did not execute anything (read-only) |

## Rejected findings (verified false or already mitigated)
| Finding | Raised by | Verification performed | Evidence / disposition |
|---|---|---|---|
| "11 entries in required-tests.json may conflict with the 8 contract tests" | principal | `python3 -c "import json;print(list(json.load(open('specs/required-tests.json'))))"` | The 11 are top-level schema keys (schema, repo, kind, ..., tests, matrix_sha256), not 11 tests, so there is no conflict. Rejected. |
| `pinned-748fce8/` existence unconfirmed | principal | `ls .wgm/native-log-journal-20261103/evidence` | Directory exists with `receipt.json`. Existence is resolved. The aggregate-relative note stays in Agent action 4. |
| Image ID stale (prior RED) | prior audit | `grep -n 74542c3d README.md` | README line 107 now has the current ID. Resolved. |
| Scope not docs-only | all | `git diff --stat 748fce8..HEAD` | Only 5 doc files changed. Claim holds. |

## Dissent
| Finding | Persona A view | Persona B view | Preserved as |
|---|---|---|---|
| Image ID not in pinned receipt | pm: AMBER | senior: GREEN (file is named elsewhere and matches) | Dissent preserved. Verified fact: absent from the receipt. Kept as an Agent action (low). |
| Base-checks duplication | junior, pm: AMBER (copyable-failure risk) | senior: GREEN (drift only) | Preserved. Promoted because the unguarded snippet is verified. |
| Loopback-guard helper undocumented | junior, senior: AMBER | principal: GREEN (gate coherent) | Preserved. Kept as AMBER. |
| required-tests count | principal: AMBER | others: not raised | Preserved. Rejected on verification. |
