# Spec: Public repository hygiene

Conforms to `.wgm/specs/CONSTITUTION.md` and the governing root constitution.

## JTBD
Publish portable workspace documentation and source comments without exposing the maintainer's workstation layout or incidental personal handle. Apply the operator's wgm consent to the workspace and every nested repository.

## User-visible success criteria
- All nine expected repositories' tracked working-tree text and staged blobs are free of user-home paths and inline personal handles.
- Existing project links, branding, attribution, runtime behavior, and unrelated work remain intact.
- Every repository has `.github/wgm-hive.yml` with consent and automatic reporting enabled.
- Local SD diagnostic exports remain on disk but are excluded from Git additions.

## Magic moment
- **The whoa:** A public checkout describes the repository, not its author's workstation.
- **Demo path:** Run `python3 .wgm/validate_public_hygiene.py`, `python3 serve_3ds.py --self-test`, and `python3 serve_3ds.py --list` from the workspace root.
- **Smallest end-to-end slice:** Clean the seven affected tracked files and validate package discovery without changing runtime code.
- **Functional versus magical:** No blanket deletion, broken links, replacement identities, or new local paths.

## Acceptance criteria → backpressure
| Delta | Criterion (EARS) | Verification |
|---|---|---|
| MODIFIED | The expected nine repositories' tracked text and index blobs shall use repository-relative descriptions instead of user-home paths and inline personal handles. | `python3 .wgm/validate_public_hygiene.py`; disposable index/inventory negative controls in `python3 .wgm/test_public_hygiene_guards.py` |
| MODIFIED | When the installer hub is exercised, its executable behavior shall remain unchanged. | `python3 serve_3ds.py --self-test && python3 serve_3ds.py --list`; compare source AST with the baseline excluding the module docstring |
| ADDED | Where a nested repository exists, its wgm configuration shall enable consent and automatic reporting. | `python3 .wgm/validate_public_hygiene.py` |
| ADDED | When local SD diagnostic exports exist, Git shall ignore them without deleting or modifying their contents, and no diagnostic export shall be in any repository index. | `python3 .wgm/validate_public_hygiene.py`; forced-staging negative control in `python3 .wgm/test_public_hygiene_guards.py`; compare export hashes with the pre-run snapshot |
| UNCHANGED | This cleanup shall retain links, attribution, existing tests, and all root text outside the authorized changed lines. | Root baseline hashes and line-scoped comparison via `python3 .wgm/verify_preservation.py`; out-of-scope edit negative control via `python3 .wgm/test_public_hygiene_guards.py`; `python3 -m unittest discover -s pc_companion/tests -v` |

## Holdout scenarios
A separate tier-1 acceptance journey exists under `.wgm/scenarios/`. Implementers must not open it.

## Ruggedness
- **Actual operator:** The maintainer preparing these existing repositories for public use.
- **Actual environment:** One Git workspace with eight independently tracked app repositories, a working Python host, and unrelated local SD diagnostic exports.
- **Dominant risk:** Operational stress: deleting local evidence, sanitizing valid project attribution, or treating the parent repo's scan as coverage of nested repos.
- **Simplification:** Replace prose only, retaining the server's existing relative runtime discovery; use a single generic tracked-file scan for all nine repositories.
- **Exact field/recovery check:** Run the demo commands from the real workspace, assert no matching tracked text, confirm all nine consent files, compare unchanged executable AST and diagnostic hashes. Any finding blocks completion; fix only the named files and rerun. Never reset/stash/delete unrelated logs.
- **Plan-exit verdict:** Recorded by `/rugged plan` in `.wgm/rugged/2026-11-02-public-paths-plan.md` and the shared plan.

## Assumptions and boundaries
- Incidental personal paths and handles are private; project organization branding and attribution are intentional public metadata.
- `AGENTS.md` approval covers only removing the heading's personal path.
- Prior commits, remote branches, releases, Git author identity, and private machine configuration are out of scope. This is a working-tree cleanup, not historical erasure.
- Existing IP examples and legitimate 3DS/toolchain paths are not personal evidence.
- The seven newly written child consent files are authorized preparation, not unrelated modifications.
- Concurrent independent product work was observed in two child repositories during planning. This cleanup must not modify or stage it; distinguish that work from this run's root preservation checks. The fixed nine-repository privacy/index inventory still applies.
