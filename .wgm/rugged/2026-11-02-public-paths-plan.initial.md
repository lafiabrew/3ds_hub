## Context
**PLAN mode:** readiness of `.wgm/specs/CONSTITUTION.md`, `.wgm/specs/public-paths.md`, and `.wgm/IMPLEMENTATION_PLAN.md` for a maintainer publishing the root and eight independent nested repositories, with existing local SD exports. Scope is working-tree cleanup, not historical erasure.

Inspected both validators; did not execute them, read diagnostics or holdouts, edit files, or commit.

## Bottleneck decomposition
- **Intrinsic design:** working-tree scanning does not necessarily validate staged publication content.
- **User capacity:** manually reconciling nine repositories and distinguishing private identity from legitimate attribution invites omissions.
- **Operational stress — dominant:** partial cleanup or rushed staging can expose diagnostics or alter unrelated material despite a passing narrow check.

## Simplify
Keep the seven-file prose-only change and existing runtime discovery. Use one explicit nine-repository publication gate rather than manual reconciliation. Accept narrowly scoped diff review for permitted prose changes; retain automated preservation checks elsewhere. No runtime refactor or history rewrite is justified.

## Exact field/recovery check design
From the real workspace root, the planned positive checks are concrete:

```sh
python3 .wgm/validate_public_hygiene.py &&
python3 serve_3ds.py --self-test &&
python3 serve_3ds.py --list &&
python3 .wgm/verify_preservation.py &&
python3 -m unittest discover -s pc_companion/tests -v &&
git diff --check
```

Expected: zero exits, nine repositories checked, eight apps discovered, enabled consent, unchanged executable AST and baseline hashes.

Three publication-safety checks remain underspecified:
- `.wgm/validate_public_hygiene.py:17-29` discovers repositories dynamically and reads working-tree bytes; it does not assert the expected inventory or inspect staged blobs.
- Directory ignore checks at lines 44-46 do not prove diagnostic files are absent from every index, including forced additions.
- `.wgm/verify_preservation.py:22-36` exempts entire allowed files; it cannot enforce heading/comment-only edits or preservation of all attribution within them.

Add exact negative-control probes for those cases in a disposable fixture, requiring nonzero exits. Recovery must block publication, reverse only task-owned changes, preserve unrelated work and exports, then rerun the gate.

**Certainty:** rung 2—cited validation design inspected; no implementation success claimed or required yet.

## Verdict
**UNKNOWN** — concrete positive checks exist, but publication-boundary and permitted-edit checks remain incomplete.

**Highest-leverage next action:** complete the single publication-gate contract with exact inventory, staged-content, diagnostic-exclusion, and allowed-edit negative controls before building.
