# Releasing {{REPO}}

## Current source and readiness (ledger-derived)

- Repository: {{REPO_URL}}
- Source SHA: `{{SOURCE_SHA}}`
- Current version tag: `{{CURRENT_VERSION}}`
- First new-version recommendation when qualified: `{{RECOMMENDED_INITIAL_VERSION}}`
- Channel: `{{CHANNEL}}`
- Eligibility status: `{{STATUS}}`
- Policy publish_enabled: `{{PUBLISH_ENABLED}}`

### Current tier status

- CI configured: `{{CI_CONFIGURED}}`
- CI executed: `{{CI_EXECUTED}}`
- Reviewed (independent): `{{REVIEWED}}`
- Published existing release: `{{PUBLISHED_EXISTING}}`
- Physically tested (FBI/device): `{{PHYSICAL_TEST}}`

### Blockers

{{BLOCKERS_MD}}

## Required command flow (fail-fast chains)

> All commands are run from a clean clone of this repo on `main` at the approved exact source SHA.

### 1) Build/test/verify (no publish)

```bash
make test && \
make {{NATIVE_TARGET}} && \
make verify-3ds
```

### 2) Review + exact-source approval capture

```bash
# Capture app-coordinator approval record for exact SHA before any publish enable
# Then verify policy remains publish_enabled:false until all gates are cleared.
python3 -m json.tool .github/homebrew-release.json
```

### 3) Version/tag/release path (only after all gates)

```bash
# Stable tag push path (manual, after qualified approval only)
# Never move existing tags. Annotated immutable tags only.
git fetch --tags && \
git tag -a <new_semver_tag> <approved_sha> -m "{{REPO}} <new_semver_tag>" && \
git push origin <new_semver_tag>
```

### 4) Hub refresh and FBI install path verification

```bash
# Trigger hub refresh from 3ds_hub after release workflow completion, then probe:
# https://lafiabrew.github.io/3ds_hub/
# Verify card link == decoded QR == direct CIA asset URL.
```

### 5) Update / rollback / backup

```bash
# Backup before policy/doc/workflow changes
git branch backup/pre-release-$(date -u +%Y%m%dT%H%M%SZ)

# Rollback metadata only (if needed)
git checkout -- .github/workflows/homebrew-release.yml .github/homebrew-release.json docs/RELEASING.md
```

## Canonical references

- Releases: {{RELEASES_URL}}
- Hub source: {{HUB_URL}}
- Hub site: {{HUB_PAGES_URL}}

## Notes

- `stable` channel means existing published stable asset, **not** QA/provenance approval.
- No claim of physical install success is made unless device evidence exists.
- Do not blanket-tag WIP sources.
