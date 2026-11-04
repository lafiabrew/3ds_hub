# Maintainer accuracy and validation playbook

Start with [STATUS](STATUS.md), [SOP](SOP.md) and the [constitution](../specs/CONSTITUTION.md). This guide records how to establish claims, not a catalog of universally proven hardware fixes. Existing root/app `AGENTS.md` files remain protected and contain known drift; do not silently edit or treat their feature descriptions as acceptance evidence.

## Repository ownership

- The hub owns `serve_3ds.py`, PC tools and current hub docs. Apps and `../.github` are independent Git repositories. A local app folder is not proof of a public remote or release.
- Inspect status/HEAD in each repository before edits. Preserve concurrent plans/manifests, dirty source and staged changes. Stage only owned paths; never blanket-stage the workspace.
- Reconcile local profile content with the intended remote baseline before publication. Preserve existing project identities; HTTP reachability is not feature certification. No push/install is implied by a documentation change.
- Other console directories/sites are outside this 3DS review. Do not infer their existence, completion or canonical URLs from this hub.

## Before making a feature claim

1. Find the actual entry point, parser/adapter and native branch. Do not copy a README assertion or requirement into another page as evidence.
2. Record source revision/diff, relevant hashes, exact command origin, output and native exit status. Bind artifact claims to artifact hashes and matching debug symbols.
3. Exercise positive, invalid and degraded paths against the named real artifact. State when only a fixture, host mock or code inspection was possible.
4. Check what the test actually measures. Add omission/failure counterfactuals that run and fail for the intended reason; compilation failures do not count as behavioral mutant kills.
5. Keep source, host test, native package, physical-device and external-service evidence distinct. No blanket “safe,” “fully compatible,” solver, frame-rate or corruption-prevention claims without the corresponding evidence.

The current root native build/verify loops do not reliably propagate early failures. Until repaired and regression-tested, use checked individual app commands; do not call root aggregate success a green fleet gate.

## Console-facing boundaries

- Logical screens are 400×240 top and 320×240 bottom. Layout probes cannot establish native font readability or stylus feel. Measure native text and prefer wrapping/truncation over horizontal squeezing; do not blindly copy one app's font policy.
- Verify exact package sections, hashes, title identity, permissions and CPU/memory flags. A valid magic/header or copied SMDH patch is not proof of HOME Menu behavior. Do not delete unrelated installations to hide a packaging fault.
- Preserve APT responsiveness, acquisition/cleanup ownership and suspend/resume cancellation in the actual native adapter. Host mocks do not certify these boundaries.
- Do not infer native atomic replacement from POSIX host semantics. Inspect the pinned SDK behavior and fault/recovery traces. The approved diagnostic-log journal exception does not cover saves/configuration or unchecked append loggers.
- Synthetic radio/GPS data, fixed cheat templates and app-local system-file stand-ins must be labeled before commands that can publish or mutate data. Reject unsupported real-save workflows; backups cannot validate an incorrect parser.

## Bounded documentation checks

From the hub root:

```sh
python3 tests/pages/check_privacy.py
```

This inventories current public Markdown (including historical docs), rejects identifying address literals, and runs an identifying-host counterfactual plus loopback/documentation-range controls. It does not erase Git history/caches or detect every possible identifier. Browser integration checks are in `tests/pages/test_pages.cjs`; see [the Pages audit](audit/2026-11-03-pages-privacy-and-rendering.md) for reproduction and boundaries. Neither test is a semantic truth oracle or hardware certificate.

Use fresh non-author correctness reviewers and the four-persona docs audit. Retain all findings and dissent; a structurally valid report can still be RED/AMBER. Do not weaken tests or edit historical evidence to make a review appear successful. Actual safety defects, protected-guide corrections and device gates remain open even after prose becomes accurate.
