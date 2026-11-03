# Metadata release rollout: plan, local preparation, coordinator publication

This tool onboards audited public `lafiabrew/3ds_*` repositories, excluding the
hub, without app runtime edits. Its only generated repository outputs are:

1. `.github/workflows/homebrew-release.yml`
2. `.github/homebrew-release.json`
3. `docs/RELEASING.md`

**Neither `apply` nor `verify-publish` pushes, creates a PR, merges, tags, releases
or uploads.** An apply receipt means local preparation, not remote installation,
CI execution, review, publication or physical FBI testing. Author iterations never
run remote publication commands. Coordinator publication remains independently
gated on the reviewed immutable source and current app-coordinator notification.

## Read-only plan

From the reviewed hub checkout, with `PAGES_RUN` pointing to the private evidence
run and `KIT_SHA` the full reviewed **public** executable hub commit:

```sh
python3 tools/rollout_release.py plan \
  --audit "$PAGES_RUN/reports/REPO_AUDIT.json" \
  --profiles "$PAGES_RUN/reports/BUILD_PROFILES.json" \
  --readiness "$PAGES_RUN/reports/RELEASE_READINESS.json" \
  --kit-ref "$KIT_SHA" \
  --output "$PAGES_RUN/runtime/rollout-plan.json"
```

All example output names must be unused; select a new attempt-specific name and
use that same plan path in later commands. Reusing an example name fails closed.
Plan performs no network writes (indeed no network calls). It reads three explicit
inputs and exclusively creates the requested NEW private plan, including full rendered
contents, paths, byte counts, SHA256, source pins, status, blockers and commands.
Review/hash this artifact before use; it contains private input locations and is
not a public release asset. Repository sets must match and be nonempty; all pins
must be full lowercase hex and agree. Admitted names cannot contain slashes,
traversal, whitespace or foreign owners. Explicit archived/private/foreign rows
are rejected. Audited branch must be main. Current public audit has 28 repos;
profiles correct the old multitarget parser: 17 `3ds-native`, 11 `3ds` profiles.
Every native, host-test and verify target must actually be present in the profile.
WIP target stubs deliberately fail; target presence is **not** a passing build.
Current-public `extra_engine_check:true` applies **only to FoldQuest**, requiring
regular nonempty `tests/test_contract.py` and actual nonzero collection with no
failures/skips in the kit. Its generated build flow explicitly runs
`python3 -m unittest discover -s tests -p test_contract.py -v` between make test and
native build. Other public profiles are false: the original four private-engine
candidate list is stale and does not establish public coverage. PieceDuel's own
make test already includes its engine/node checks. Re-audit engine obligations
when private candidates are promoted; never inherit a public stub's false flag.

Only installed trusted templates are supported. All initial policies are schema 1,
`publish_enabled:false`; existing stable releases do not grant approval. Caller
workflow and `kit_ref` use the identical full immutable SHA, never `main` or a tag.
Apply independently regenerates **all** rows from embedded admitted inputs and
its installed templates, comparing exact schema/types/paths/content/hashes/policy/
caller pin. Editing contents and recomputing hashes cannot authorize new output.
The plan is an operator-reviewed source-pin authorization, not a signed approval
for app publication. A real public kit pin is a coordinator prerequisite; syntactic
full-SHA acceptance in a read-only author demonstration is not proof the kit is
public/reviewed. Apply additionally probes public hub identity, compares kit SHA
against actual central main (base and merge-base must both be that SHA, status
ahead/identical), and requires a regular nonempty reusable workflow at that exact
ref. Unreachable/foreign-object/missing-workflow pins block. Independent review is
still an external coordinator gate, not inferred from object existence. Live app
repository admission is also independently checked on apply.

## Explicit local preparation

Use standalone isolated clean clones, each checked out on actual default `main`,
under `REPOS_ROOT`. Exact public origin must be either canonical HTTPS `.git` or
canonical GitHub SSH `.git`, with no alternate push URL. No linked worktrees,
nested Git roots, staged/unstaged tracked changes, unrelated untracked files,
symlink roots/ancestors/outputs, dangling links or special-file outputs. Existing
identical untracked generated files are allowed for idempotent retry; conflicts
are never overwritten. Ignored build products are not app-source changes.

Select at most five repos (repeat `--repo`) from the full plan. Example one-repo
batch, after coordinator notification and exclusive coordinator rollout admission:

```sh
python3 tools/rollout_release.py apply \
  --plan "$PAGES_RUN/runtime/rollout-plan.json" --kit-ref "$KIT_SHA" \
  --repos-root "$REPOS_ROOT" --repo 3ds_padtest \
  --dry-run --output "$PAGES_RUN/runtime/rollout-preflight-padtest.json"
```

Remove `--dry-run` only for authorized **local preparation**, choosing a NEW
receipt name for that attempt. Plans/receipts are immutable: existing regular
files (even identical), symlinks/dangling links and symlink ancestors are refused
before API apply preflight or repository output writes. All output paths must be
outside this tool's guarded source; receipts must also be outside `REPOS_ROOT`. Optional `--expected-heads` is an additional assertion,
never a way to override plan source pins. Only main is admitted by apply.

Before the first file/receipt write, **two complete global preflights** check all
selected clones, every output path/content, local branch/source/index, live public
GitHub repo identity/default branch, and `git ls-remote --symref origin HEAD
refs/heads/main`. Local HEAD/origin-main cache is not remote freshness. Both live
remote checks must equal the plan source pin. Missing/changed identity or remote
SHA aborts without output/index/source/remote mutation. Conflict in repo 2/path 3
cannot leave repo 1/path 1 behind. Dry-run also rejects symlinks.

Both passes query current organization rollout PRs via supported read-only
`gh api --paginate --slurp` endpoints: organization repositories with `type=all`,
then every organization repository's open pulls, including private, archived, hub and
non-`3ds_*` repositories (counting scope only).
These are counting-only reads, not extra caller admission, PR creation or app
source scope; selected callers remain only the admitted public repositories.
GitHub may silently hide inaccessible private repos. Therefore both passes also
require owner-visible `orgs/lafiabrew.total_private_repos` and reconcile that total
against the complete private inventory. Missing total, incomplete visibility or
failed private pulls block with a precise global-cap-unproven/probe error; a
public-only token cannot establish a global cap. Some non-owner tokens with
repository read access still lack this total and intentionally fail closed. No
private names/payloads go into receipts or public docs. No optional JSON counter, default-zero fallback or
token output. Canonical rollout heads use reserved prefix
`rollout/homebrew-release`; coordinator must use that namespace for every rollout
PR. Current count **plus the entire pending batch** must be <=5 (`--max-open-prs`
may lower, never raise, the cap). At five open, even one new preparation is blocked.
Incomplete/API/auth/rate/transport failures block rather than assume zero.

### Honest concurrency and I/O limits

Preflight rejection is nonmutating. This is **not** an all-or-nothing I/O
transaction: disk-full, process termination or post-preflight filesystem changes
may leave newly created files/directories. Creation is exclusive/no-clobber (`O_CREAT|O_EXCL|O_NOFOLLOW`) and
walks ancestor directory descriptors with `O_NOFOLLOW`. After both preflights,
the NEW receipt name is atomically reserved **before** any repository file is
created, so a late competing output cannot cause repository writes. Reservation
is not atomic content completion: interrupted/failed local I/O can leave an empty
or partial receipt and partial repository files. Preserve prior bytes and inspect
those new files; no force/reset/stash/delete or rollback is attempted. Inspect and preserve partial work, resolve the cause and
retry identical repository outputs with a NEW receipt name. A remote can change after the last read; local preparation
never claims a remote lock. Coordinator must serialize batches globally and rerun
checks at actual remote boundaries, below. External concurrent PR creation cannot
be atomically locked by a read-only API probe; do not run multiple publishers.

## Separate coordinator remote publication (not author execution)

After exact-source independent review of the public kit and plan, notify the app
coordinator **before** changing metadata heads. For each selected repo, inspect
local changes then create one normal commit on the reserved topic branch. Example
for `REPO=3ds_padtest`, after successful apply, from its standalone clone:

```sh
git switch -c rollout/homebrew-release &&
git add -- .github/workflows/homebrew-release.yml .github/homebrew-release.json docs/RELEASING.md &&
git commit -m "Configure pinned homebrew release workflow"
```

Back in the reviewed hub checkout, run the real boundary check. It requires a
clean topic branch with exactly one commit whose parent is the approved source,
exactly the three changed paths and byte-identical rendered files. It repeats
actual remote-main/identity/cap checks; output is read-only except the receipt.

```sh
python3 tools/rollout_release.py verify-publish \
  --plan "$PAGES_RUN/runtime/rollout-plan.json" --kit-ref "$KIT_SHA" \
  --repos-root "$REPOS_ROOT" --repo "$REPO" \
  --output "$PAGES_RUN/runtime/before-push.json" &&
git -C "$REPOS_ROOT/$REPO" push origin rollout/homebrew-release &&
python3 tools/rollout_release.py verify-publish \
  --plan "$PAGES_RUN/runtime/rollout-plan.json" --kit-ref "$KIT_SHA" \
  --repos-root "$REPOS_ROOT" --repo "$REPO" \
  --output "$PAGES_RUN/runtime/before-pr.json" &&
gh pr create --repo "lafiabrew/$REPO" --base main --head rollout/homebrew-release \
  --title "Configure pinned homebrew release workflow" \
  --body "Metadata only; publishing disabled; app QA/provenance remains blocked."
```

These are actual separate Git/gh operations, **not fictional apply push flags**.
No automatic merge. Normal topic-branch push never modifies main; on a remote race,
stop and preserve both source histories/topic branch. Do not retry by force or
repin stale approval. Protected branch/permissions/scopes failures remain blockers.
Before a separately authorized merge, refresh main, PR head/checks and review
source; confirm the main pin still matches, request fresh review if any source
changed, and use the exact PR-head match guard supported by `gh pr merge
--match-head-commit`. Do not bypass protections. Record old/new public main heads,
three-path diff, PR/run IDs and actual checks; notify app coordinator afterward.
Refresh audit/profiles/readiness at new source before any subsequent rollout.
Count existing rollout PRs before the next batch; pause/consolidate at five.

## Caller and exact-source approval contract

P2/P3 additive contract explicitly acknowledged: reusable inputs are `kit_ref`,
`release_tag` (empty default), `dry_run` (true default), `approval_id` and
`approval_ref` (both empty default). Caller exposes and forwards these exact keys.
Default token permissions read-only; only the reusable caller job grants required
contents/id-token permissions, while P2 isolates the writer from app build code.
Tag pushes are safe dry-runs by default. Empty approval inputs cannot publish.

Future qualified publication uses A0 app source with enabled stable policy after
all tests/reviews/provenance gates; executable caller+kit stay immutable K0.
Separately reviewed, public-central-main-reachable R1 carries approval **data**
binding exact A0/K0/policy/tag/native identity/assets and evidence. Dispatch at A0's
existing annotated tag supplies R1 and SHA256 record ID without mutating A0 or
repinning K0. No approval data code executes. This avoids the central-kit/caller
source cycle; P2 enforces the trusted data-plane verification. No approval is
created by this planner, and no initial policy is enabled.

Generated docs distinguish audited prior CI state from configured-after-install;
CI execution/review/published legacy/device tiers remain separate. They include
actual version/blockers, qualified initial v0.1.0, fail-fast build/test/native,
manual dry-run, independent approvals, annotated no-move tags, immutable assets,
hub refresh, FBI/update/save-backup and conservative rollback. Metadata is escaped;
private paths/session-shaped data are omitted from public generated prose.
Canonical hub: https://lafiabrew.github.io/3ds_hub/ .

## Tests and evidence

```sh
python3 -m unittest discover -s tests -p test_release_rollout.py -v
```

All 34 original tests remain; additional output/visibility race controls are
required too. `test_plan_works_on_real_28_repo_inputs` ALWAYS reads the committed
`tests/rolloutfixtures/public28/` snapshot, independent of `PAGES_RUN`. Its public
pins/version states were observed on 2026-11-03, with per-file hashes, public
source URLs and Makefile blob/SHA256 provenance; see the fixture README. It is not
a fabricated repository set, a live audit, or current-source coordinator approval.
The separate explicit live-runtime 28-repo plan above remains a coordinator gate,
bound to matching source SHAs and a reviewed public kit before apply.

Test clones/remotes use `tempfile` under caller-provided `TMPDIR` (project volume
for coordinator evidence), or the standard temporary directory in public CI.
Checked teardown removes only each test's created directory after verifying its
identity; no source scratch writes or unknown-path cleanup. The historical empty
`tests/rolloutfixtures/_work/` may remain untouched. Tests compare full Git source
status and tracked/untracked content before/after. To suppress Python cache writes
when proving a pristine source tree:

```sh
env -u PAGES_RUN PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -p test_release_rollout.py -v
```

The explicit offline process seam replaces only GH transport and redirects `ls-remote` to real
bare repos; all source/index/origin/branch operations use actual Git. No production
fixture flags or JSON PR-count bypass exist. Tests retain earlier scenarios and
add tampered-plan/hash/policy/pin/extra-output, full input admission, correct apply
and retry, dirty staged/unstaged, wrong origin/default/remote races, full-batch
nonmutation, symlinks/dangling links, cap including pending, failed current probe
and prepared-commit boundary controls. Process logs can be captured with
`ROLLOUT_PROCESS_LOG` (private evidence only). Actionlint must run on actual
rendered callers, not the unexpanded template. Passing local tests is not
independent approval, remote installation or a real workflow/device run.

### Existing server self-test prerequisite (not a source repair)

The historical no-argument `python3 serve_3ds.py --self-test` failure in a clean
public clone is retained in earlier evidence: that clone has no SDK-built CIA.
Independent integration RUGGED accepted pointing the **unchanged** server at the
actual previously built public PadTest checkout as legitimate prerequisite
recovery, not a weakened test:

```sh
python3 serve_3ds.py --root "$PAGES_RUN/runtime/sdk-padtest" --self-test
```

Require its original exit zero; do not fabricate artifacts or repair app source.
This local SDK/host check establishes neither a deployed workflow nor physical FBI
installation. Publication, per-app exact-source qualification, live refresh and
device gates remain distinct and pending until separately evidenced.
