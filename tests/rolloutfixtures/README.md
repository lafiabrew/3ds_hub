Fixture workspace for test_release_rollout.py.

Runtime-created standalone clones and bare remotes are created under
`tests/rolloutfixtures/_work/` to keep tests on project volume. Source/remote/index
snapshots include file bytes and Git refs; teardown removes only each test's own
fixture directory, never source/evidence.

`transport.py` is copied into each fixture PATH as `gh`/`git`. Git source, index,
origin, branch, diff and commits use real `/usr/bin/git`. Only `ls-remote` is
redirected to the actual fixture bare remote, with explicit real remote/local-ref
race controls. GH accepts only read-only API calls and returns organization,
repository and open-pull evidence; it rejects write-method flags. Production CLI
has no JSON PR-counter override or fixture-mode bypass. Optional
`ROLLOUT_PROCESS_LOG` captures every test process's full stdout/stderr/exit/argv
outside committed source. No network write or physical install is involved.
