# Catalogue API fixtures

`api/` holds **actual, unmodified** public GitHub REST API response bodies captured
anonymously (no token) on 2026-11-03T22:52Z:

- `org-repos-page1.json` — `GET /orgs/lafiabrew/repos?type=public&per_page=100&page=1`
  (30 repositories: 28 `3ds_*` homebrew repos, `3ds_hub`, `.github`; no `Link` header, so one page).
- `releases-<repo>.json` — `GET /repos/lafiabrew/<repo>/releases?per_page=100&page=1`
  for each of the 28 homebrew repositories (16 contain one stable `v1.0.0` release
  with `<repo>.cia`, `.3dsx`, `.smdh`; 12 are empty lists).
- `capture-receipt.json` — request path, HTTP status, a header subset and SHA-256 of
  each body. `tests/test_catalog.py` verifies every file still matches its digest.

The tests serve these bytes from a loopback fake GitHub API and run the real
`tools/build_catalog.py` CLI against it. Negative controls (draft, prerelease,
missing/multiple CIA, foreign or HTML URLs, XSS text, pagination, rate limits,
timeouts, truncated JSON, new-contract manifests) are derived **inside the test
code** from these real objects so every mutation is visible next to the assertion
that explains it. No application binary is stored here.

These bytes are a point-in-time observation, not the live inventory. The live
build always queries the API at build time.
