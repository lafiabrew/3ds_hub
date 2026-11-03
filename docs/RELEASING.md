# Qualified, immutable homebrew releases

This hub supplies `.github/workflows/homebrew-release.yml` and the stdlib CLI
`tools/release_hub/kit.py`. It does not approve application behavior, license,
history, banners, or physical hardware. The initial approval registry is empty;
all rollout policies are **false**, including the next builds of legacy apps.
The author iteration performs no external tag, release, upload, or push.
Conditional publication is permitted later, after independent qualification —
this is not a permanent ban or a green-build shortcut.

## Observed versions, profiles and evidence tiers

The 2026-11-03 public audit found 28 repositories. Sixteen already have actual
`v1.0.0` tags/releases: chip8, drop, mahjong, netpass, padtest, picross, pieceduel,
pokedash, pokedex, rngtool, roulette, sandlab, sokoban, solitaire, sysdash, wigle
(all prefixed `3ds_`). Preserve those lightweight tags and existing assets;
never convert, move, replace or certify them retroactively. Determine the next
version from **fresh actual remote SemVer tags and reviewed changes**, not this
historical list. A legacy public CIA is not approval of its next build.

The other twelve have no tag in that observation; initial recommendation is
`v0.1.0`, **only once qualified**. Eleven public Makefiles deliberately fail
`make test`, `make 3ds`, and `make verify-3ds`: capturekit, cartdash, gridblast,
neverball, orrery, pinball, pockettracker, rhythm, supaplex, tuxpuck, voxeltoy.
Their journal smoke is not application acceptance. FoldQuest has a real native
profile but no approved release; history/assets remain blockers, not permission
to rewrite ancestry. Lawful Supaplex data cannot be invented. Local-only projects
are not admitted to this public rollout. Refresh the coordinator's private
`RELEASE_READINESS.json` and source-bound evidence before acting.

Keep these separate in release notes and per-repository release docs:

| Tier | What it establishes |
|---|---|
| Source/WIP | Public source exists; functionality may be unfinished |
| CI configured | Pinned workflow/policy installed, not executed |
| CI executed | Exact run ID/source/time and actual command exits |
| Reviewed | Exact-source QA, provenance and independent review records |
| Published | Versioned public assets exist; not necessarily reviewed legacy assets |
| Physically tested | Observed FBI install/app/device result with limits; never inferred from HTTP/QR/build |

Canonical installation flow: [Install from the hub](INSTALL_FROM_HUB.md).
Metadata rollout is separate: [Release rollout](RELEASE_ROLLOUT.md). Those are
coordinator-owned companion documents; deploying Pages is not part of this kit.

## Unchanged schema-1 repository policy

Path: `.github/homebrew-release.json`. Unknown/duplicate keys and wrong JSON types
fail. A `false` policy needs a nonempty reason. `stable` describes an existing
stable channel, not approval. All generated policies start false.

```json
{
  "schema": 1,
  "repo": "lafiabrew/3ds_padtest",
  "publish_enabled": false,
  "channel": "stable",
  "reason": "Exact-source QA and license/history/banner clearance are pending",
  "native_target": "3ds-native",
  "artifact_dir": "build/3ds",
  "cia_asset": "3ds_padtest.cia",
  "host_commands": [["make", "test"]],
  "native_commands": [["make", "3ds-native"], ["make", "verify-3ds"]],
  "extra_engine_check": false
}
```

`repo` must be the exact `lafiabrew/3ds_<name>` slug (hub excluded).
`cia_asset` is exactly `<name>.cia` including the `3ds_` prefix. Commands are argv,
never shell snippets. The current bounded profiles admit exactly `make test`,
then `make <native_target>` and `make verify-3ds`; native target is `3ds-native`
for 17 audited repos and `3ds` for the eleven public stubs. Future different
profiles require a reviewed kit extension, not arbitrary commands/assignments.
Missing targets/failing stubs block, never substitute `echo passed`.

Despite its legacy name, `extra_engine_check:true` currently means **FoldQuest's
actual public `tests/test_contract.py` gate**, after `make test`. The file must
be nonempty, regular, discover at least one test, pass with no skips. Other
current public profiles are false. This is explicitly coordinated with P3;
it does not waive later engine-specific obligations for promoted app sources.
PieceDuel's real `make test` already runs its C and Node differential/network
suites. Its external TypeScript engine reference is **not included or guessed**
by this kit; absence fails visibly and blocks that profile until separately
pinned, licensed inputs are reviewed. Node itself is pinned in the SDK recipe.

## Immutable caller and actual workflow identity

Caller must use:

```yaml
uses: lafiabrew/3ds_hub/.github/workflows/homebrew-release.yml@<40hexKIT_SHA>
with:
  kit_ref: <same40hexKIT_SHA>
  release_tag: ${{ inputs.release_tag || '' }}
  dry_run: ${{ github.event_name != 'workflow_dispatch' || inputs.dry_run }}
  approval_ref: ${{ inputs.approval_ref || '' }}
  approval_id: ${{ inputs.approval_id || '' }}
permissions:
  contents: write
  id-token: write
```

This is a schematic **calling-job** fragment: replace both placeholders with
the same reviewed, **public** full lowercase commit; never `main`, a version tag,
or a short SHA. Keep the caller workflow top-level contents-read. The calling
job must delegate contents-write even for a dry run, because reusable workflows
cannot elevate their caller's declared permissions (a skipped nested publisher
is not a permission exception). Actual reusable **build** and identity jobs
explicitly reduce contents to read; only the isolated publisher has write and
it is skipped for dry runs. This job-level delegation is not app approval or a
publishing-policy override. Do not grant global write or reviewer autoapproval.

Inputs are `kit_ref` (required full SHA), `release_tag` (default empty), `dry_run`
(boolean default true), `approval_ref` and `approval_id` (default empty strings).
Tag events use the actual `refs/tags/...`; a branch dry run uses `release_tag`
or candidate `v0.1.0`. Publication additionally requires an **already existing
annotated stable tag** whose peeled commit equals the run's source and current
app main. `v01.0.0`, prereleases, ranges and implicit tag creation are rejected.
Legacy lightweight releases stay intact and are not republished through here.

Before any checkout, a code-free identity job fetches the OIDC token directly
from GitHub's runner-supplied HTTPS endpoint (restricted to
`*.actions.githubusercontent.com`), requesting audience `homebrew-release-kit`.
It checks issuer, audience, expiration, repository/source and both
`job_workflow_ref` and `job_workflow_sha`. These identify the **executed reusable
workflow**, not caller-controlled `workflow_ref` inputs. Both must match the
input's full kit SHA. The response is trusted only because it is obtained
directly from that authenticated TLS endpoint; no caller-supplied/unsigned JWT
is accepted. GitHub's OIDC reference documents these claim names and
`ACTIONS_ID_TOKEN_REQUEST_URL`/`ACTIONS_ID_TOKEN_REQUEST_TOKEN`.
See https://docs.github.com/en/actions/reference/security/oidc . No live Actions
OIDC/run has yet been executed by this author; local tests replace transport,
execute the exact inline bootstrap in a child process and reject bad claims.

## Cycle-free independent approval (additive interface agreed with P3)

A boolean or a hash typed into a dispatch form is not approval. The trust root
is independently reviewed **approval data on public hub main**, not app code,
app policy, artifact metadata, or unreviewed shared GitHub objects.

1. Review and publish executable kit/workflow K0. App caller pins both to K0.
2. Clear the app's QA/provenance prerequisites before enabling its policy.
   Freeze the final app commit A0 including policy/caller metadata. Re-run
   exact-source tests and reviews on A0: metadata changes also change source;
   previous approvals cannot be inherited. App coordinator approves A0's tests,
   scoped RUGGED then fresh nonauthor spec/quality (every atom >=95), history,
   licenses/assets, current Drop producer freshness or evidenced N/A. Verify K0
   itself has its independent reviews. No author self-approval.
3. Obtain and preserve native candidate hashes/identity from A0. The independent
   app-coordinator record below binds A0, K0, policy bytes, intended version and
   **exact approved binary hashes**, not just a product code from the app.
4. Review/integrate that JSON data in the central hub as commit R1, reachable
   from actual public hub main. Its filename is SHA256 of exact record bytes.
   R1 need not equal K0 and contains no executable authority. The app remains
   A0, still pins K0; no caller repin/source cycle. R1 is read via contents API,
   **never checked out or executed**. No approval records exist initially.
5. Recheck all gates/current remote source, policy and tag absence before the
   authorized coordinator creates a normal annotated immutable version tag at
   A0. Then dispatch **at that existing tag**, `dry_run:false`, `approval_ref:R1`,
   `approval_id:<record SHA256>`. The kit never creates/pushes a tag.

The record schema is exact; unknown keys fail. Example structure (placeholders
are not usable approval):

```json
{
  "schema": 1,
  "repo": "lafiabrew/3ds_padtest",
  "tag": "v1.0.1",
  "source_sha": "<A0 full40>",
  "policy_sha256": "<SHA256 exact .github/homebrew-release.json bytes at A0>",
  "kit_sha": "<K0 full40>",
  "decision": "approved",
  "approver_role": "app-coordinator",
  "evidence": {
    "tests": "<64hex evidence digest>",
    "rugged": "<64hex report digest>",
    "spec": "<64hex report digest>",
    "quality": "<64hex report digest>",
    "license_history_assets": "<64hex clearance digest>",
    "drop_integration": "<64hex producer-freshness or explicit N/A rationale digest>"
  },
  "assets": [{
    "name": "3ds_padtest.cia",
    "size": 123456,
    "sha256": "<64hex independently approved binary digest>",
    "native_identity": {"title_id": "0004000000d3e703", "product_code": "CTR-P-PADT"}
  }]
}
```

Private detailed evidence includes source/report bindings, commands, actual
exits/log hashes, all review atoms, provenance decisions and device limits.
Central reviewers verify the evidence behind the public opaque hashes; the
CLI cannot decide whether a human review was competent. Do not publish private
paths, sessions, retail data or secrets. Optional approved `.3dsx`/`.smdh` entries
use only name/size/sha256. Entries are sorted by name, unique, one CIA mandatory.
No build success fabricates this record.

`approval_ref` must be a full lowercase hub commit. The compare API must report
R1 as both base and merge-base of `R1...main`, with status ahead/identical;
foreign/unreachable/mutable refs fail. Exact fetched bytes must hash to
`approval_id`. App source must still equal current remote main and existing
annotated tag, and policy must remain enabled/stable with identical bytes.
Source/policy/K0/tag/binary changes invalidate approval. A changed binary needs
investigation and new independent qualification, not an automatic new digest.

## Jobs, inputs and trust boundaries

- Default token is contents-read. All checkouts disable credential persistence.
  The identity job alone requests id-token-write.
- Build checks clean exact source and absent `build/3ds`; freezes policy outside
  the app mount. Publication admission checks remote policy/approval and release
  absence **before** any binary transfer. Disabled policy fails here even if a
  caller requests publication with otherwise valid approval fields.
- The kit builds only its own pinned Containerfile. Host tests and native gates
  execute inside networkless, nonroot containers with read-only root and kit,
  app-only writable mount, scratch `/tmp`, dropped capabilities, no Docker
  socket, no GitHub/OIDC/environment/write tokens. Application commands never
  run in the publisher. A source change reported by `git diff` fails the build.
- Any failed host/native/verification/bundle step stops downstream work.
  Dry runs make only local bundles: no artifact upload, tag or release. A
  publication-admitted successful build may transfer its validated bundle via
  pinned upload/download-artifact actions (one-day retention).
- A fresh publisher checks out **only trusted K0**, downloads untrusted files,
  fetches policy/approval again and parses everything independently. Only its
  final publish step receives the job's contents-write token. Caller app code,
  Makefiles, hooks, scripts and artifact-supplied commands are never executed.

External actions are pinned commits. SDK input index is
`docker.io/devkitpro/devkitarm@sha256:116afba8df8453961de2936ffab20dd441edf4d682856c1ec8b0e53d7ed0bbf5`;
verified linux/amd64 child is
`sha256:15b79ce75822c289538d8153da5fa7aafe5e6adc32ad8a575a197beca0f0761b`.
The base provides GCC16.1/libctru2.7 and host gcc/python/make. Layer reuse caches
SDK inputs, not app outputs; no preexisting local image is retagged or pruned.
`releasekit/inputs.json` pins the actually downloaded single-member makerom
0.18.4 Ubuntu ZIP (SHA256 `dd596854718c195c6e3229286be485b122921715555af8ae5cf8e9a465d9f970`)
and Node22.16.0 runtime tarball. Both checksums were compared with actual bytes;
Node also matched upstream SHASUMS256. The recipe extracts only named binaries,
no arbitrary tar extraction, apt/latest installer or global host installation.
Bannertool is absent, not silently installed; apps requiring it fail. Existing
opaque banners are not made lawful by a successful makerom command.

## CLI and bundle validation

From the hub root (`python3 tools/release_hub/kit.py --help` and each subcommand's
`--help` describe the actual interface):

```sh
python3 -m unittest discover -s tests -p test_release_hub.py -v &&
actionlint .github/workflows/homebrew-release.yml
```

Local dry-run stages (variables must name a clean frozen source and new output;
run actual build commands in the isolated container as the workflow does):

```sh
python3 tools/release_hub/kit.py run --repo "$REPO" --config "$POLICY" --cwd "$APP_ROOT" --phase host &&
python3 tools/release_hub/kit.py run --repo "$REPO" --config "$POLICY" --cwd "$APP_ROOT" --phase native &&
python3 tools/release_hub/kit.py bundle --repo "$REPO" --tag "$TAG" --source-sha "$SOURCE_SHA" --kit-ref "$KIT_SHA" --config "$POLICY" --artifacts "$APP_ROOT/build/3ds" --output "$NEW_BUNDLE" --started-ns "$STARTED_NS" &&
python3 tools/release_hub/kit.py validate --repo "$REPO" --tag "$TAG" --source-sha "$SOURCE_SHA" --config "$POLICY" --bundle "$NEW_BUNDLE"
```

CLI `run` is not a sandbox itself; only invoke app commands inside the tokenless
container. Locally native-producing commands must use the existing shared
max-two `native_queue.py` **from the actual Git root**, never nested. Record
`STARTED_NS` before building. Preserve every full output and original exit;
never hide a failure behind `tee` or a trailing successful log write.
`bundle` rejects existing output rather than clearing/reusing stale files.

`admit` and `publish` additionally require `--kit-ref`, `--approval-ref` and
`--approval-id`; `publish` takes `--bundle`. They use the actual `gh` CLI and
GitHub API. Never run publication as a test against GitHub; tests replace only
transport with a blocked local process seam. No endpoint, executable override
or alternate approval registry is accepted through the production CLI.

Bundle files: `<repo>.cia`, optional matching `<repo>.3dsx`/`<repo>.smdh`,
`SHA256SUMS`, `release.json`. The canonical JSON manifest is schema1, exact repo,
tag, source_sha, policy_sha256, kit_sha, approval_ref/id, and sorted assets with
name/size/sha256; CIA also carries native_identity. Hashes are calculated from
actual bytes, not timestamps. SHA256SUMS covers binary assets; release.json
is not self-hashed. Bundles with the same inputs produce identical manifests.

Reject symlinks in path components, hardlinks, nonregular files, escapes,
unexpected/duplicate asset names, stale inputs, zero/oversized files (64 MiB
per binary), HTML, short/truncated archives and metadata/digest/size mismatches.
The CIA parser requires one unencrypted NCCH, sane bounded CIA/TMD/NCCH sections,
content-index bitmap, matching ticket/TMD/NCCH/exheader title IDs, product code,
content size/hash and ExeFS presence. SMDH is exactly 0x36c0; 3DSX header/segment
bounds are checked. This is **structure and identity**, not Nintendo signature
verification, behavior review or safety certification. Unsupported encrypted or
multi-content archives fail. A structurally valid but wrong/unapproved app is
rejected against independently approved asset hashes/identity in the publisher.

## Immutable publication and recovery

The publisher inventories all existing releases (including drafts), requires
absence of this version, snapshots validated bytes privately, then rechecks
source/tag/policy/approval. It uses real verified gh flags:

1. `gh release create TAG --repo REPO --verify-tag --draft ...` (no `--target`).
2. `gh release upload TAG --repo REPO FILES...` (never `--clobber`).
3. Verify remote draft tag and the exact names/sizes/GitHub SHA256 asset digests.
4. Recheck remote source/policy/tag, then `gh release edit TAG --repo REPO
   --draft=false --latest --verify-tag` for visibility.

An existing draft/release/asset blocks retries; there is no overwrite, force,
delete or automatic resume. A failed transfer/digest check leaves an unpublished
draft for explicit maintainer investigation; never delete it to make CI green.
No tag is implicitly created. GitHub APIs lack an atomic compare-and-release
transaction: serialize release operations and protect release tags against
updates/deletions via repository rules. Hostile concurrent administrators are
outside the token isolation guarantee. Configure GitHub immutable releases
where available. CLI flags were verified using installed `gh release
create/upload/edit --help`; no external release was created for validation.

After an authorized publish, independently verify remote annotated tag object
and peeled source, actual run ID/source/time, downloaded manifest/checksum/CIA
hashes and expected native identity. Only then refresh the hub: manually run its
Pages catalogue workflow or wait for minute-17 hourly discovery. Cross-repo
refresh is eventual, not a fictional automatic dispatch. Verify the catalogue's
versioned CIA download URL equals its independently decoded QR target and
returns CIA bytes, not release HTML. No binary mirrors on Pages.

For FBI: back up saves/SD/config first (timestamped backups, checksums and safe
restore procedures; preserve prior known-good installers locally). On a CFW
console the user opens FBI Remote Install and scans the direct versioned CIA
QR. Only an observed device installation/application result earns a physical
tier. Host HTTP/QR/native checks do not prove camera/TLS/install compatibility.
Updates are new immutable versions, never changed assets at old URLs. For a
rollback, choose an already known-good versioned installer, confirm title ID and
save-format compatibility, back up current saves first, then follow that app's
safe uninstall/install/restore guidance. Never blindly downgrade saves or
remove a current title assuming FBI preserves all data. A bad new release can
be excluded by reviewed catalogue policy; preserve immutable old assets and
record the advisory rather than overwrite history.

## Validation status and remaining limits

Local author validation includes actual subprocess CLI/bundle negatives,
cycle-free positive publication through the local GH transport seam, blocked
upload dispatch, host/native failure-stop, malformed/stale/HTML/symlink/oversize
archives and wrong source/tag/kit/policy/identity/hash controls. Exact inline
OIDC bootstrap is executed with replaced transport, not claimed as live OIDC.
A real public PadTest frozen-source SDK smoke was run using this new recipe,
networkless/tokenless containers and the shared native queue. Artifacts remain
local; its old banner provenance remains **uncleared**. Full private logs,
exits and source/artifact hashes are retained by the coordinator, not shipped
as binaries or personal paths in this repository.

Still owed: exact-candidate coordinator RUGGED, two fresh nonauthor correctness
passes, real GitHub dry-run execution, independent app qualification, any
publication/deployment, and physical FBI observation. Local green tests are not
CI execution, application approval, a self-review, or authorization to publish.
