# Release rollout planner (P3)

This lane owns a **declarative rollout planner** for metadata-only release onboarding across audited public `3ds_*` repositories.

## Scope and ownership

Owned files in this lane:

- `tools/rollout_release.py`
- `templates/homebrew-release.yml.in`
- `templates/homebrew-release.json`
- `templates/RELEASING.md`
- `tests/test_release_rollout.py`
- `tests/rolloutfixtures/*`
- `docs/RELEASE_ROLLOUT.md`

Planner output is for exactly three per-repo paths:

- `.github/workflows/homebrew-release.yml`
- `.github/homebrew-release.json`
- `docs/RELEASING.md`

No tag/release/API writes are performed by this author iteration.

## CLI contract

### Plan (read-only default)

```bash
python3 tools/rollout_release.py plan \
  --audit "$PAGES_RUN/reports/REPO_AUDIT.json" \
  --profiles "$PAGES_RUN/reports/BUILD_PROFILES.json" \
  --readiness "$PAGES_RUN/reports/RELEASE_READINESS.json" \
  --kit-ref "<40hex kit sha>" \
  --output "$PAGES_RUN/runtime/rollout-plan.json"
```

Required invariants before any output is written:

1. The repository sets in audit/profiles/readiness match exactly.
2. `profiles.rows[*].source_sha == audit.rows[*].head_sha` for every repo.
3. `readiness.rows[*].source_sha == audit.rows[*].head_sha` for every repo.
4. `--kit-ref` is an explicit full 40-hex SHA (no `@main`, no placeholders).
5. Each profile provides `native_target` and includes `verify-3ds` target.

If any invariant fails, command exits nonzero and does not emit a plan.

### Apply (explicit, local-safe)

```bash
python3 tools/rollout_release.py apply \
  --plan "$PAGES_RUN/runtime/rollout-plan.json" \
  --kit-ref "<same 40hex kit sha>" \
  --repos-root /path/to/local/public/repos \
  --expected-heads /path/to/expected-heads.json \
  --open-prs-json /path/to/open-prs.json \
  --max-open-prs 5 \
  --expected-branch main \
  --dry-run \
  --output "$PAGES_RUN/runtime/rollout-apply.json"
```

Apply safety gates:

- Clean working tree required for each target repo.
- Checked-out branch must match expected (`main` by default).
- Optional expected-head pins are checked before application.
- Existing conflicting files cause a hard fail (no clobber).
- Existing identical files are idempotent (`unchanged`).
- Re-probes `HEAD` immediately before hypothetical remote operations.
- Global open rollout PR cap enforced (`<=5`).
- Refuses symlink overwrites.

## Policy/document semantics generated per repo

- `publish_enabled` defaults to `false` for all repos.
- `channel` is `stable` only if a stable release exists in readiness ledger; otherwise `wip`.
- `reason` is non-empty while disabled.
- `native_target` is profile-driven (`3ds-native` or `3ds`).
- Commands are argv arrays, not shell strings.
- WIP repos remain blocked and visible as blocked.
- Existing versions are taken from actual readiness tags; untagged repos remain untagged with initial recommendation `v0.1.0`.

## Testing

Run:

```bash
python3 -m unittest discover -s tests -p test_release_rollout.py -v
```

The suite uses real `git` repositories in fixtures under project volume and validates:

- required CLI flags and `--help`
- bogus flag rejection
- stale/mismatched input rejection
- profile target/schema failures
- 28-repo readonly plan generation
- conflict/idempotent apply behavior
- dirty repo, branch mismatch, head-race safety
- cross-check that only the three owned target paths are handled
- max-5 open PR cap
