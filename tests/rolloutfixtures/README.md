# Rollout fixtures and scratch ownership

`public28/` is a sanitized **actual public** observation, not synthetic repos:
28 nonarchived public `lafiabrew/3ds_*` repositories excluding `3ds_hub`.
Audit observation: 2026-11-03T21:48:43Z; corrected Make profiles:
22:08:34Z; public version/release observation: 22:28:05Z. Sixteen repositories
had existing v1.0.0 releases; twelve were untagged. None of these facts grants
qualification for a new release. Prior CI configured/executed, reviewed and device
statuses are observation-time states, not permanent installed-CI labels.

- `audit.json`: public slugs, public-main commit pins, branch and prior workflows.
- `profiles.json`: matching immutable public source pins and actual Make targets;
  corrects the historical audit parser's missed multitarget WIP stubs. Presence
  is not passing build proof (17 `3ds-native`, 11 `3ds` profiles).
- `readiness.json`: allowlisted public tag/peeled-commit and published release
  asset metadata, observation-time status, and a generic qualification reminder.
  No local-only/private-candidate entries or private approval history is copied.
- `provenance.json`: SHA256 of each fixture file; public GitHub owner/source URLs;
  immutable per-repo source pin, Makefile URL, Git blob ID and SHA256. These
  Makefile bytes were checked against the public source tree's blob ID when
  freezing the fixture. Tags and assets are historical observations, not promises
  of current remote availability; GitHub release assets themselves can change.

Source ownership here means the observed public GitHub namespace `lafiabrew`,
not a claim that public accessibility clears authorship/license/history/assets.
No personal paths, raw sessions, tokens or private-repository payloads are present.
The portable test ALWAYS consumes this snapshot with or without `PAGES_RUN` and
checks fixture hashes, matching pins, counts, generated policies and caller/docs.
It is not a replacement for the coordinator's fresh explicit runtime plan and
reviewed-public-kit reachability gate.

## Disposable real Git tests

Scratch clones and bare remotes are created with `tempfile` under caller `TMPDIR`
(project volume for coordinator runs), or standard temp space for public CI.
Never under source. Teardown verifies the created directory identity, removes
only that owned directory and checks removal. A pre-existing historical empty
`_work/` is ignored, not deleted. Full Git source status/content is compared
before/after the suite. Run Python with `PYTHONDONTWRITEBYTECODE=1` / `-B` to avoid
interpreter cache changes in source during clean-tree evidence runs.

`transport.py` is copied into each scratch PATH as `gh`/`git`. Git source, index,
origin, branch, diff and commits use real `/usr/bin/git`. Only `ls-remote` is
redirected to actual scratch bare remotes, with controlled real ref races and
local output existence/symlink races. GH accepts only read-only API calls,
requires `type=all`, and models both owner-visible private totals and hidden or
archived PRs (synthetic transport names only). It rejects write-method flags.
Production has no JSON PR-counter override or fixture-mode bypass. Optional
`ROLLOUT_PROCESS_LOG` captures every test process's full stdout/stderr/exit/argv
outside committed source. No network write or physical install is involved.
