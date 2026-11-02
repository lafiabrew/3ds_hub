# Docs Audit Report — 2026-11-02 — public-paths privacy delta

- **Scope:** `ed47dbf..7792458` plus the current T2 record: seven authorized public prose surfaces, the diagnostic ignore policy, and named run-specific evidence.
- **Track / trigger:** Standard; T2 demo-validation and handoff audit.
- **Overall verdict:** **GREEN for the privacy delta**, not completion of T2 or approval of unrelated product claims.
- **Independence:** Four supplied persona reports consolidated last; independence is context and lens, not a claim of different models or tooling.
- **Consensus:** Unanimous: no dissent recorded.
- **Delivery:** Stdout only; dispatcher owns filing. No project or child-repository files changed.

## Persona findings

### wgm-docs-junior — clarity & onboarding

| Doc | Observation | Severity | Recommended action |
|---|---|---|---|
| Public prose, `.gitignore`, run spec/plan | Relative descriptions improve portability without an onboarding regression. Diagnostic exclusion, local evidence, preserved history, concurrent child work, and pending T2 gates are bounded. | GREEN | No privacy-delta correction; retain qualifications. |
| Root documentation | Existing title-ID inconsistencies and broad product claims are pre-existing debt. | GREEN | Carry separately; do not block this cleanup. |

### wgm-docs-senior — correctness, completeness, maintainability

| Doc | Observation | Severity | Recommended action |
|---|---|---|---|
| Seven public prose files | Exactly ten line replacements; executable behavior, existing tests, branding, links, and attribution preserved. | GREEN | No correction. |
| `.gitignore`, run spec/plan | Diagnostic ignoring is not deletion or historical erasure; the separate index guard rejects forced additions. Evidence is workspace-specific and child work separately owned. | GREEN | Retain local-only boundaries and pending T2 status. |
| Validation records | Lightweight reruns support privacy, preservation, eight-app discovery, help, and explicit invalid-option errors; suite evidence comes from existing logs. | GREEN | Keep independently rerun evidence distinct from recorded suites. |
| Existing product documentation | Title-ID and broad-claim debt predates this delta. | GREEN | Track separately without expanding cleanup. |

### wgm-docs-principal — architecture, strategic fit, consistency

| Doc | Observation | Severity | Recommended action |
|---|---|---|---|
| Seven public prose files | Ten replacements preserve workspace architecture, branding, and attribution. | GREEN | Accept bounded delta; no product-doc expansion. |
| `.gitignore`, run spec/plan | Exclusion complements preservation; nine-repository checks do not certify concurrent child products unchanged or provide universal privacy/fresh-clone guarantees. | GREEN | Preserve these qualifications. |
| Plan and T1 evidence | Current T1 completion and pending T2 are distinct from historical handoffs; CLI evidence supports eight-app discovery and explicit failure. | GREEN | Keep T2 incomplete until remaining gates pass. |
| Root plan and README | Product-documentation debt and historical/publication boundaries remain separate. | GREEN | Carry debt forward; no historical-erasure claim. |

### wgm-docs-pm — status, risk, traceability

| Doc | Observation | Severity | Recommended action |
|---|---|---|---|
| Run plan | T1 done and T2 in_progress accurately reflect current evidence; earlier pending statements are dated history. | GREEN | Complete T2 only after remaining audit/review gates. |
| Run spec, public prose, `.gitignore` | Ten replacements and diagnostic policy match the delta; preservation/privacy evidence is bounded to checked patterns and surfaces. | GREEN | No correction; retain limitations. |
| Logs and plan | Local snapshot dependence, separately owned child work, and recorded-versus-rerun evidence are explicit. | GREEN | Do not imply publication, hardware validation, fresh-clone reproducibility, or unchanged child products. |
| README and root plan | Existing title-ID and broad product claims are follow-up debt. | GREEN | Carry separately; not a privacy blocker. |

## Consolidated report

### README index check

The root README supplies the scaffold below: **All 8 Nintendo 3DS Homebrew Apps** and **Quick Start Commands**. It has no local Markdown links, so no dangling local linked target was found. All eight named app directories and the companion/hub surfaces exist.

**Unindexed documentation flagged:** Neither `docs/README.md` nor `docs/audit/README.md` exists. The historical audit has no README index entry; the root agent guide, plan, constitution, and run evidence are not indexed from the root README. Run artifacts are instead cross-referenced by `.wgm/IMPLEMENTATION_PLAN.md` and the spec. This records the required index inventory, not a new fifth-persona action or introduced privacy regression. The dispatcher owns this report's filing.

### All 8 Nintendo 3DS Homebrew Apps

All four personas converge: repository-relative prose accurately describes the existing workspace. `git diff --numstat ed47dbf HEAD -- README.md AGENTS.md Makefile serve_3ds.py IMPLEMENTATION_PLAN.md specs/CONSTITUTION.md docs/audit/2026-11-02_3ds-homebrew-suite-audit.md` confirms ten added/ten removed lines across exactly seven authorized files.

The writer reran `PYTHONDONTWRITEBYTECODE=1 python3 .wgm/verify_preservation.py` using normal Python, not optimization. Exit 0 confirms authorized root/index boundaries, unchanged server executable AST/source outside its docstring, diagnostic hashes, discovery, and ancestor history. Child differences are reported separately, not certified unchanged. Diagnostics were accessed only by this hashes-only verifier.

A read-only Python probe using the existing hygiene regexes checked 190 non-holdout tracked files across all nine working trees/indexes, enabled consent, and absence of indexed diagnostics. It excluded holdout entries before reading content. Persona/T2 records report 191 files for their full checker; these are distinct coverage counts, not contradictory results.

### Quick Start Commands

The writer reran `python3 serve_3ds.py --list` and `python3 serve_3ds.py --help`: both exited 0; discovery returned eight apps. `python3 serve_3ds.py --audit-invalid-option` exited 2 with `unrecognized arguments: --audit-invalid-option`. Both `git diff --check` and `git diff --cached --check` exited 0.

Existing `.wgm/t1-validation.log` records ten fixture tests, four integration tests, and successful hub self-test; `.wgm/t2-validation.log` records successful demo checks. These suites were not rerun. No app build, hardware validation, publication, push, history rewrite, or holdout inspection was performed.

The ignore policy excludes root diagnostic export folders; it neither deletes exports nor guarantees exclusion after forced staging without the separate index guard. Helpers and the intentional local hashes-only snapshot are run-specific tooling, not public scanner or fresh-clone promises.

### Agent actions

No corrective privacy-delta findings survive. The following deduplicated dispositions preserve the personas' existing follow-through and debt without authorizing edits during this audit.

| # | Finding / disposition | Raised by | Doc(s) | Action |
|---|---|---|---|---|
| A1 | **Agent action — pending lifecycle gates, not a documentation regression** | All four | `.wgm/IMPLEMENTATION_PLAN.md` | Dispatcher files/checks this audit; coordinator obtains remaining independent final reviews and required T2 acceptance/ruggedness evidence before changing T2 from in_progress. Do not treat this report as those reviews. |
| A2 | **Agent action — pre-existing, nonblocking follow-up debt** | All four | `README.md`, `AGENTS.md`, root plan, historical audit | Carry title-ID inconsistencies and broad product-documentation claims as a separate reconciliation follow-up. Baseline/current title-ID-bearing lines are identical; no product correction is authorized here. |

### Operator actions

**None for this privacy delta.** No persona identified a new human decision, external confirmation, or privileged-access requirement. Historical rewriting, publication, and hardware operations remain outside scope, not implied action items.

### Rejected findings

**None.** All four reports are GREEN; no proposed finding was disproved, downgraded, or silently discarded. Existing debt remains explicitly retained as A2, not rejected as nonexistent.

Checks supporting accepted dispositions were the seven-file numstat command, hashes-only preservation verifier, holdout-excluding privacy/index probe, baseline/current title-ID-line equality probe, actual hub CLI invocations, whitespace checks, and direct inspection of the named plan/spec/logs and T1 reviews.

### Dissent

**Unanimous: no dissent recorded.** All four agree on the GREEN privacy-delta verdict, no corrective documentation requirement, separately retained product debt, bounded local evidence, and incomplete T2 gates. No severity or action disagreement was averaged away.

## Verdict history

Previous artifact: `docs/audit/2026-11-02_3ds-homebrew-suite-audit.md`. Its broader product conclusions are not revalidated or upgraded by this narrowly scoped consolidation. The ten-line privacy cleanup is supported; historical commits retain former text. T1's named spec/quality reviews are PASS and its current ruggedness verdict is RUGGED; T2 remains in_progress.

**Structural validation:** The installed `scripts/audit.sh --check-report` checker validated this report in a temporary session artifact: **exit 0, structure valid**. That artifact was removed; the dispatcher separately checks and files its stdout capture. Structural validity does not complete T2 or replace the qualitative verdict.
