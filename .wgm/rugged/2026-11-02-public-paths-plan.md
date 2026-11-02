## Context
PLAN review of `.wgm/specs/public-paths.md` and `.wgm/IMPLEMENTATION_PLAN.md`: the operator is the publishing maintainer; the environment is nine independent Git repositories, a Python host, retained SD exports, and concurrent child-repository work. The revised boundary explicitly protects that work without exempting child indexes from privacy checks.

## Decomposition
**Intrinsic:** working-tree cleanliness cannot prove index cleanliness. **User capacity:** manually reconciling nine repositories and permitted edits invites omissions. **Operational stress—dominant:** rushed staging, forced additions, and concurrent changes can leak exports or damage unrelated work.

## Simplification
Keep prose-only edits and existing runtime discovery; use one fixed-inventory publication gate. Narrow line allowances replace whole-file exemptions. Accept less editing freedom and no historical-erasure guarantee in exchange for explicit, recoverable boundaries.

## Field/recovery check design
The previous review’s gaps are addressed in `.wgm/IMPLEMENTATION_PLAN.md:21-30`.

| Claim | Exact planned check and expected observation |
|---|---|
| Complete inventory; clean working trees/indexes; consent; diagnostic exclusion | `python3 .wgm/validate_public_hygiene.py` from the workspace root: zero exit across all nine repositories. |
| Guards reject unsafe states | `python3 .wgm/test_public_hygiene_guards.py`: disposable clean fixture passes; missing repository, staged-only private content, forced diagnostic staging, and unauthorized-line edit each produce rejection. |
| Preservation and unchanged behavior | `python3 .wgm/verify_preservation.py`: baseline hashes, diagnostic hashes, permitted-line boundaries, and executable AST match. |
| Actual hub behavior and regression coverage | `python3 serve_3ds.py --self-test && python3 serve_3ds.py --list && python3 -m unittest discover -s pc_companion/tests -v && git diff --check`: zero exits; eight apps discovered. |

Recovery is explicit: any finding or surviving negative control blocks completion; correct only task-owned files and rerun, without resetting, stashing, deleting, or staging unrelated work.

**Certainty: rung 2—cited validation design inspected.** Validator extensions and fixtures are planned T1 work; execution evidence is owed at T1 Review, not before implementation.

## Verdict
**RUGGED** — the revised plan names actual operators and conditions, removes manual-reconciliation and quiet-workspace assumptions, and supplies concrete positive, negative, and recovery checks.

**Next action:** Execute T1, including its guard extensions and fixtures, and present their results at T1 Review.
