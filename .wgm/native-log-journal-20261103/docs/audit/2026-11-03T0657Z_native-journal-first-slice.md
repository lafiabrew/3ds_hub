# Docs Audit Report — R5 native diagnostic journal @ 748fce8 — r5-native-log-store-1

- **Scope:** README.md, specs/CONSTITUTION.md, specs/log-contract.md, specs/app.md, specs/native-storage-tests.json, include/native_log_store.h and native_log_backend.h, .wgm/IMPLEMENTATION_PLAN.md, .wgm/native-log-journal-spec.md.
- **Track:** Standard (scoped repair, not whole-fleet release)
- **Trigger:** Ship/Handoff
- **Overall verdict:** RED. One RED finding was verified (README image ID). The AMBER status and traceability lag is also verified.

## Persona findings

### wgm-docs-junior — clarity & onboarding
| Doc | Observation | Severity | Recommended action |
|---|---|---|---|
| README.md | The R5 status says RUGGED and reviews are pending, and gives no pointer to the pinned receipt. | AMBER | Update the status and name where the evidence lives. |
| .wgm/IMPLEMENTATION_PLAN.md | The plan is stale: `r5-evidence/`, gate-attempt-1, "DRY RUN ONLY" and a different gate shape. | AMBER | Add a dated status block and mark the old lines historical. |
| README.md validation gate | There is no single ordered seven-stage gate. `$FLEET_RUN` is undefined, DROP_SERVER_BIN cannot be reproduced, and the loopback guard is undisclosed. | AMBER | Give one ordered gate and define `$FLEET_RUN`. Say how to build the Drop host and disclose the guard. |
| README.md | Jargon (intent, sidecar, generation, RUGGED, T1/T2) is undefined, and "the paragraph above" depends on position. | AMBER | Add a glossary and a sidecar table. |
| README.md | Test counts are repeated in several places and are easy to misread. | GREEN | State each count once. |
| log-contract, README, headers | Names, 64 B, 256 KiB and 32 transitions are consistent. | GREEN | None. |
| CONSTITUTION, app.md, headers | Scope is honest, and no personal paths were found. | GREEN | None. |
| native-storage-tests.json | The `owner` field does not say how to obtain the Drop binary. | GREEN | Add a note on where to get the binary. |

### wgm-docs-senior — correctness, completeness, maintainability
| Doc | Observation | Severity | Recommended action |
|---|---|---|---|
| README.md:71 | Image ID `e4fb375a…5635` contradicts plan:23, tests/fixtures/README.md:24 and evidence/toolchain-image-id.txt (all `74542c3d…3938`). | RED | Correct it, or state what `e4fb…` is and where it was recorded. |
| .wgm/IMPLEMENTATION_PLAN.md:3,9 | The status is stale. The gate has 5 stages, no Drop stage and no counts. The base HEAD is outdated and `r5-evidence/` is cited. | AMBER | Update to the pinned 748fce8 seven-stage state and cite the receipt and drop-loopback.json. |
| README, app.md, log-contract | The loopback guard and the stock-hash difference are undisclosed. | AMBER | Add one disclosure sentence. |
| log-contract:28, README:40 | The 2 s exit-pending message is documented only in the plan. | GREEN | Optionally mention it in the README. |
| log-contract vs code | Suffixes, CRC32, offsets, size, limits, statuses and flags match. | GREEN | None. |
| CONSTITUTION, app.md, README | Scope and no-personal-path claims hold. | GREEN | None. |
| native-storage-tests.json | 10 names match 10 test functions. | GREEN | None. |
| native_log_backend.h | The contract matches the source. | GREEN | None. |

### wgm-docs-principal — architecture, strategic fit, consistency
| Doc | Observation | Severity | Recommended action |
|---|---|---|---|
| .wgm/IMPLEMENTATION_PLAN.md | The status is stale: gate-attempt-1 and the dry-run are cited, and the receipt and loopback JSON are not. | AMBER | Update to the pinned state and keep the blockers. |
| README, app.md, log-contract | The loopback transport guard and stock-hash difference are undisclosed. | AMBER | Add a disclosure sentence citing drop-loopback.json. |
| CONSTITUTION | The approval record is referenced without a path or id. | GREEN | Optionally add the approval-record id. |
| README, app.md | There is no explicit "scoped repair ≠ fleet release; native FS/SD/power-loss unverified" line. | GREEN | Add the line near the journal section. |
| Test registries | The additive 10-test registry is consistent. | GREEN | None. |

### wgm-docs-pm — status, risk, traceability
| Doc | Observation | Severity | Recommended action |
|---|---|---|---|
| README R5 status | The status reads older than the actual review state and cites no pin or receipt. | AMBER | State that scoped RUGGED and quality PASS are done at 748fce8, and keep in_progress and the open tiers. |
| IMPLEMENTATION_PLAN | The plan cites gate-attempt-1 and not the pinned receipt, and has no review hashes. | AMBER | Add traceability rows and mark closed waits. |
| IMPLEMENTATION_PLAN:27,34 | The plan says "dry run only" and omits the loopback guard, helper and Drop pin hashes and the flags. | AMBER | Record the guard, hashes and flags. |
| README test_drop_storage.py | The loopback shim is not mentioned. | GREEN | Add one sentence. |
| README "Retained local evidence" | It points to uncommitted `build/repair-evidence/`. | GREEN | Name the external evidence location. |
| README, CONSTITUTION, spec | Incomplete tiers are stated and acceptance is not claimed. | GREEN | None. |
| Public-path check | No personal paths were found, and names, layout and CRC are consistent. | GREEN | None. |

## Consolidated report (wgm-docs-writer)

### README index check
The project has no `docs/README.md` (`ls docs` fails). The root README does not carry an index or Map of the reviewed docs. The reviewed docs (specs/*, .wgm/IMPLEMENTATION_PLAN.md, native-log-journal-spec.md, headers) are referenced inline by path in README/app.md. No dead links were reported by any persona. The README cites `build/repair-evidence/`, which is uncommitted, and the pinned evidence is in the aggregate root and is not referenced.

### Agent actions
> The agent can execute these directly and deterministically.

| # | Finding | Raised by | Doc(s) | Action |
|---|---|---|---|---|
| 1 | RED, verified: README:71 gives image `e4fb375a…5635`. Plan, fixtures README and evidence/toolchain-image-id.txt give `74542c3d…3938`. No evidence file contains `e4fb375a`. | senior | README.md | Replace it with `74542c3d…3938`, the ID in the recorded evidence. If `e4fb…` is a different digest type, label it and its source. |
| 2 | Stale R5 status: README:30 says RUGGED and reviews are "pending". There is no pin, receipt or seven-stage gate citation. | junior, pm | README.md | Update the status to say scoped RUGGED and spec/quality PASS are done at 748fce8 and cite `pinned-748fce8/receipt.json`. Keep in_progress, the unverified native FS/SD/power-loss/two-console tier, and the open T1/T2, device and networking work. Add the "scoped repair ≠ fleet release; inherited blockers retained" line. |
| 3 | Stale plan: it says "Awaiting…" (line 4), cites `r5-evidence/` and gate-attempt-1, has a 5-stage gate (line 9), "DRY RUN ONLY" (line 27) and base HEAD d8b4d0a. It lacks the receipt, drop-loopback.json and review-hash traceability. | junior, senior, principal, pm | .wgm/IMPLEMENTATION_PLAN.md | Add a dated status block for the pinned 748fce8 state. Present the seven-stage gate with the old-8 and new-10 counts. Link the receipt, drop-loopback.json and review report hashes. Mark the dry-run and attempt-1 lines as superseded. |
| 4 | Drop disclosure is missing: the loopback transport-only guard, the intentionally different stock helper hash, the real Drop code with no fake HTTP service, and the helper and Drop pin hashes. | junior, senior, principal, pm | README.md, specs/app.md, specs/log-contract.md, .wgm/IMPLEMENTATION_PLAN.md | Add one disclosure paragraph. Cite drop-loopback.json and state that it is not a stock-helper or device result (`physical_device:false`, `whole_fleet_acceptance:false`). |
| 5 | Validation gate is unclear: there is no single ordered gate, `$FLEET_RUN` is undefined, and the way to build or stage `3ds_drop_host` is not given. | junior | README.md, specs/native-storage-tests.json | Write one ordered gate, say that `$FLEET_RUN` is fleet-only and optional, and note how to obtain DROP_SERVER_BIN. |
| 6 | The README points at uncommitted `build/repair-evidence/` and does not name the pinned external evidence location. | pm | README.md | Name the aggregate evidence location, or state that it is outside the repo. |
| 7 | Jargon is undefined and test counts are repeated. | junior | README.md | Add a first-use glossary and a sidecar table, and state each count once. |
| 8 | Optional low-severity traceability items. | senior, principal | README.md, specs/CONSTITUTION.md | Mention the 2 s exit-pending message, and add the approval-record id to CONSTITUTION if one is available. |

### Operator actions
> These need a human decision, external confirmation, or access the agent doesn't have.

| # | Finding | Raised by | Doc(s) | Why it needs a human |
|---|---|---|---|---|
| 1 | The native FS/SD/power-loss/two-console/whole-app tier remains unverified, and root T1/T2, device and networking remain incomplete. These blockers are retained and not waived by this scoped docs repair. | junior, senior, principal, pm | README.md, specs/app.md | Only device or console observation and coordinator acceptance can close them. |
| 2 | The coordinator-owned Drop and timing integration rows and publication remain pending. The docs must not claim them. | pm, senior | README.md, .wgm/IMPLEMENTATION_PLAN.md | These are coordinator-owned, external to this lane. |
| 3 | If `e4fb375a…` (Agent action 1) is a real, different digest, the author must say what it is. | senior | README.md | Only the author or coordinator knows its provenance. It is not present in the evidence. |

### Rejected findings (verified false or already mitigated)
> Persona observations and severity are hypotheses.

| Finding | Raised by | Verification performed | Evidence / disposition |
|---|---|---|---|
| Personal or workstation paths in public docs | junior, senior, principal, pm | `grep -rn "/home/" README.md specs include .wgm/*.md` | No matches, so no finding. The only hit was the dispatcher-written audit.lock, which is out of scope. |
| Mismatch of sidecar names, CRC, layout, limits, statuses or test counts between docs and code | all (as GREEN checks) | Persona comparison against code, not re-verified by the writer. The README, plan and fixtures README contents were checked by grep only. | No mismatch was found by any persona. Retained as GREEN, no action. |
| Image ID claim as RED: "unsupported" | senior | `grep -rn "e4fb375\|74542c3d"` over README, plan, fixtures README and evidence/toolchain-image-id.txt, and `grep -rl e4fb375a` over the evidence | Confirmed, not rejected. The ID appears only in README:71. It is promoted to Agent action 1 and is not in this table as false. |
| README "pending reviews" severity | junior, pm | `grep -n "pending" README.md` | Confirmed. README:30 reads "pending". The claim of a pass comes from the task brief and was not re-run. The finding is promoted. |

### Dissent
| Finding | Persona A view | Persona B view | Preserved as |
|---|---|---|---|
| Image ID mismatch | Senior: RED, README contradicts the recorded evidence. | Junior, principal and pm did not report it. Their reports do not say they checked that line. | Agent action 1, kept RED. The disagreement is one of coverage, not opposing views. |
| Loopback-guard disclosure severity | Junior, senior, principal, pm AMBER (pm rated its README-only instance GREEN, and the plan instance AMBER). | The pm's README `test_drop_storage.py` row is GREEN. | Agent action 4, kept at AMBER, with the pm's GREEN view noted. |
| Missing "scoped repair ≠ fleet release" line | Principal: GREEN, optional. | Others: not reported. | Agent action 2, optional. |
| Evidence reading | Senior and pm read the receipt or aggregate evidence. | Junior and principal state they did not read the evidence directory. | Findings from the junior and principal are treated as unverified against evidence. |

## Verdict history
- No prior entry was supplied to the writer. This is a first scoped entry. Not recorded / unknown.
- Report checker: `scripts/audit.sh --check-report` was not run by the writer. The dispatcher applies it.
