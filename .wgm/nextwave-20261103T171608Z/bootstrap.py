#!/usr/bin/env python3
"""Create twelve independent WIP repositories with a real shared-runtime signal.
No game/port is marked implemented by this bootstrap.
"""
import hashlib
import json
from pathlib import Path
import subprocess

RUN=Path(__file__).resolve().parent
ROOT=RUN.parent.parent
JOURNAL_PIN='7446e605aeca206733262ab563e7b4a4a43e60f5'
FEATURES={
 '3ds_pinball':('Original stereo pinball: one playable table, L/R and touch flippers, motion nudge option, scoring/drain/restart and ghost replay.', 'Drive seeded ball movement, collision/flippers/drain/restart through real core tests; native two-eye rendering and HID input must actually call the game. Built-in assets are original/procedural.'),
 '3ds_rhythm':('Original rhythm game: one original tune/chart, stylus/button play, scoring/retry and a small chart editor.', 'Audio buffers, note timing/scoring, input/reset and native NDSP lifecycle are real; calibration is measured/labeled, not imaginary hardware latency. Built-in music is original; missing DSP support is visible.'),
 '3ds_gridblast':('Original two-player bomb arena using own-peer LAN transport, playable movement/bombs/win/restart and touch controls.', 'Real two-peer host exchange, sequence/malformed/timeout recovery and deterministic arena mechanics; native controls/sockets invoke the actual session. No four-console or UDS claim unless actually implemented/tested.'),
 '3ds_foldquest':('Original one-room clamshell puzzle whose state changes on actual suspend/resume, with touch/buttons and a complete solve/reset path.', 'Actual APT lifecycle plus shared transition tests; no hidden work while lid closed. State stays in RAM through normal sleep; no saved-campaign/power-loss promise or misuse of diagnostic journaling as game-save storage.'),
 '3ds_voxeltoy':('Bounded original voxel editor: 16x16x16 world, block palette/edit/orbit/stereo preview and export.', 'Mesh bounds/culling/edit/reset tests, actual native geometry rendering and input; measured counts/times. Not Minecraft/infinite worlds. Optional model exports are new immutable files, not user-file replacements.'),
 '3ds_orrery':('Original stereo solar-system playground with a bounded body set, orbit trails, zoom/orbit controls and reset.', 'Deterministic orbit/simulation/camera tests and real PICA scene; units and approximations explicit, not NASA ephemeris accuracy or invented frame performance.'),
 '3ds_capturekit':('Opt-in correlated sensor recorder with actual HID accel/gyro, bounded sessions and Drop-readable metadata; optional camera/mic captures only if truly implemented.', 'Real SDK acquisition/sample/cleanup paths, visible record/stop/unavailable state; explicit clock domains/raw units, no perfect-sync or fake sensor data. Media files are immutable segments; no default audio/image capture/upload.'),
 '3ds_cartdash':('Read-only own-cartridge inspector: insertion/removal, accessible title metadata and service/error diagnostics.', 'Real SDK card/title query path with unavailable handling, no ROM dump/card writes/save modification/default unique-ID collection. Host models are labeled, no physical-card observations invented.'),
 '3ds_pockettracker':('Touch/button module-music workstation with genuine libxmp-compatible playback and a small original pattern/sample test tune.', 'Actual declared decoder/mixer source and native NDSP integration, PCM bounds/safe file/error/shutdown tests; source and original/open tune licenses verified. No commercial music packs.'),
 '3ds_neverball':('Genuine Neverball adaptation: reuse lawful engine lineage, one real level/session, appropriate 3DS controls and rendering.', 'Find/pin actual upstream/existing ports, source+asset licenses, real engine compile/link and meaningful session, not an original imitation or launcher. Prove PICA/OpenGL compatibility early; unsupported pipeline stays blocked.'),
 '3ds_tuxpuck':('Genuine TuxPuck adaptation: compact air hockey with native stylus/buttons, real engine/session and restart.', 'Pin actual source/licenses and allowed data; real engine compile/link/input, malformed file/bounds/lifecycle tests. No static console wrapper represented as a port.'),
 '3ds_supaplex':('Genuine OpenSupaplex adaptation: deterministic puzzle engine, bottom-screen map and input/replay.', 'Pin actual engine/licensing and verify data redistribution separately; user assets if not licensed. Real engine compile/link/session, not copied marketing or a launcher. Keep unavailable asset gameplay unverified.')}
IGNORE='''/build/
/.jj/
/.wgm/.wgm-ignore-probe
/.wgm/.loop-*
/.wgm/.last-harvest-hash
/.wgm/metrics.tsv
/.wgm/metrics/
/.wgm/swarm-logs/
/.wgm/worktrees/
/.wgm/memories.md
/.wgm/STOP
/.wgm/*.log
__pycache__/
*.pyc
*.bak
*.tmp
'''
CONSENT='consent: true\nauto_report: true\nsources:\n  - dogfood\n  - swarm\n  - issues\n  - cross-pollinate\n'
LICENSE='''MIT License

Copyright (c) 2026 lafiabrew contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''
SMOKE=r'''#define _GNU_SOURCE
#include "native_log_store.h"
#include "native_log_backend.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
int main(void) {
 char dir[]="build/journal-smoke-XXXXXX"; assert(mkdtemp(dir));
 char active[512]; assert(snprintf(active,sizeof(active),"%s/shared-runtime.log",dir)>0);
 const NlsBackend* backend=NULL; assert(linklab_native_fs_acquire(&backend)==0);
 NativeLogStore store; assert(nls_init(&store,active,backend)==0);
 const unsigned char first[]="{\"shared_runtime_fixture\":1}\n";
 const unsigned char next[]="{\"shared_runtime_fixture\":1}\n{\"append\":2}\n";
 assert(nls_commit(&store,first,sizeof(first)-1,false)==NLS_STABLE);
 assert(nls_commit(&store,next,sizeof(next)-1,false)==NLS_STABLE);
 assert(nls_recover(&store)==NLS_STABLE);
 unsigned char data[512];size_t len=0; assert(nls_read_active(&store,data,sizeof(data),&len)==0);
 assert(len==sizeof(next)-1 && !memcmp(data,next,len));
 assert(linklab_native_fs_release()==0);assert(unlink(active)==0);assert(rmdir(dir)==0);
 puts("PASS shared runtime fixture only: real journal create/append/recovery; NOT an implemented app or device test");
 return 0;
}
'''

def call(*args,cwd=None):
 return subprocess.check_output(args,cwd=cwd,stderr=subprocess.STDOUT).decode()

def put(repo,name,text):
 p=repo/name;p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():raise RuntimeError('refuse overwrite '+str(p))
 p.write_text(text)

def main():
 manifest=json.loads((RUN/'manifest.json').read_text())
 identity={k:call('git','config','--get',k,cwd=ROOT).strip() for k in ['user.name','user.email']}
 vendor_files=['include/native_log_store.h','include/native_log_backend.h','src/native_log_store.c','src/native_fs_host.c','src/native_fs_3ds.c']
 for lane in manifest['lanes']:
  name=lane['repo'];repo=ROOT/name;assert not repo.exists(),name;repo.mkdir()
  goal,proof=FEATURES[name];port=lane['port'];audio=lane['data_or_audio_engine']
  put(repo,'.gitignore',IGNORE);put(repo,'.github/wgm-hive.yml',CONSENT)
  put(repo,'LICENSE',LICENSE)
  hashes={}
  for rel in vendor_files:
   data=subprocess.check_output(['git','-C',str(ROOT/'3ds_linklab'),'show',JOURNAL_PIN+':'+rel])
   p=repo/'vendor/lafiabrew_journal'/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);hashes[rel]=hashlib.sha256(data).hexdigest()
  put(repo,'vendor/lafiabrew_journal/LICENSE',LICENSE)
  put(repo,'vendor/lafiabrew_journal/PROVENANCE.json',json.dumps({'source':'lafiabrew/3ds_linklab','commit':JOURNAL_PIN,'scope':'validated generic diagnostic journal/backend only; per-app integration still needs tests','legacy_function_prefix':'linklab_native_fs_* retained internally','files':hashes},indent=2)+'\n')
  put(repo,'tests/journal_smoke.c',SMOKE)
  for folder in ['src','include','meta','scripts','tests/fixtures']:put(repo,folder+'/.gitkeep','')
  put(repo,'Makefile','''# Shared-runtime bootstrap signal; NOT completed app build targets.
.PHONY: journal-check test 3ds verify-3ds
journal-check:
\tmkdir -p build/host
\tgcc -std=c11 -Wall -Wextra -Werror -O2 -g -fsanitize=address,undefined -Ivendor/lafiabrew_journal/include vendor/lafiabrew_journal/src/native_log_store.c vendor/lafiabrew_journal/src/native_fs_host.c tests/journal_smoke.c -o build/host/journal_smoke
\t./build/host/journal_smoke
test: journal-check
\t@echo 'FAIL: app behavior/native integration not implemented yet; runtime smoke is not app acceptance' >&2
\t@exit 1
3ds verify-3ds:
\t@echo 'FAIL: genuine app native artifacts are not implemented yet' >&2
\t@exit 1
''')
  put(repo,'README.md',f'''# {lane['title']} for Nintendo 3DS

**WIP — implementation lane assigned; not a playable/released/device-tested app yet.**

{goal}

Part of [lafiabrew](https://github.com/lafiabrew). UniqueId `{lane['unique_id']}`, ProductCode `{lane['code']}`. Each app is a separate repository. Native logging reuses the reviewed journal with per-app integration tests; media/replays are new immutable files, not replacements of user saves. No private capture/upload by default.

## Build status and source license
`make journal-check` is a real shared-runtime signal only. Current `make test`, `make 3ds` and `make verify-3ds` deliberately fail until the lane implements actual behavior and artifacts. Passing the smoke is not a completed app.

New original code/runtime scaffold is MIT. {'Actual engine code and assets must retain their separately checked upstream licenses; no game data is bundled by this scaffold.' if port or audio else 'Built-in artwork/music/levels must be original or explicitly licensed.'}

## Required first-release gate
```sh
make test && python3 -m unittest discover -s tests -p test_contract.py -v && make 3ds && make verify-3ds && git diff --check
```

{'Engine proof additionally requires `python3 tests/verify_engine.py`, including a compiled ARM launcher-negative control and real upstream object/map/symbol provenance.' if port or audio else ''}

See [scope](specs/app.md), [operational instructions](AGENTS.md), [shared safety](specs/CONSTITUTION.md), and [plan](IMPLEMENTATION_PLAN.md). All current status is WIP until verified; no 3DS hardware claims from host models.
''')
  put(repo,'AGENTS.md',f'''# Agent operations — {lane['title']}

Own only this repository/jj lane. Read IMPLEMENTATION_PLAN.md and specs/app.md. Do not modify sibling/parent repositories or any existing root AGENTS. Search actual upstream/dependencies before duplicating capability.

- Deliver actual interactive native behavior: {proof}
- Exact gate: make test && python3 -m unittest discover -s tests -p test_contract.py -v && make 3ds && make verify-3ds && git diff --check.
- Engine/audio lanes must prove genuine declared source/build/asset licensing via tests/verify_engine.py. No wrappers/lookalikes advertised as ports. No proprietary/unknown assets or user ROM data downloaded/bundled.
- Preserve vendored runtime origin/hashes/notices. New per-app log formatter/adapter tests must validate actual journal integration, not blindly copy LinkLab metadata/seed rules.
- Diagnostic JSONL uses schema/app/build/event/elapsed_us/seed/settings/capabilities, first record<=199 ASCII bytes, active<=256KiB, fixed own app .log in 3ds/logs for existing Drop API. No user identities/addresses/home paths; relative owned artifact names may identify opt-in capture outputs.
- No default raw camera/mic recording/uploads. Immutable media/replay segments use exclusive new files and validated diagnostic manifests, not save/config modification.
- Original3DS baseline, 2D fallback, optional New3DS enhancements labeled. Real SDK APIs and cleanup/error paths, no fake sensors/audio/network/benchmarks.
- No holdout/scenario reading during implementation. All tests explain why; never weaken/skip/delete existing tests. Ordinary source smoke tests remain as regression signal.
- Loop alone commits: stage only exact OWNED individual files before finish; emit WGM_OWNERSHIP_MANIFEST. No git commit/stash/reset, jj new/rebase/switch or pinned branch moves. LC_ALL=C avoids mixed guard sorting.
- Leave code candidate in_progress for coordinator exact-pin RUGGED, independent spec/quality PASS, API/demo and final docs audit. No push/merge/remotes in author lane. Keep complete execution evidence and source checkpoints in durable project storage.
''')
  put(repo,'specs/CONSTITUTION.md','''# Shared safety

Preserve user save/config bytes, backup/surgical/checksum requirements and scoped root constitution. Native diagnostic logs ONLY may use the explicitly approved checked crash-recoverable journal, never call SDK existing-path rename atomic. Reuse immutable validated journal source but test per-app formatter/root/caller/integration. No automatic private-data capture/upload. Nonblocking bounded network work, aptMainLoop/HOME/lid cleanup, buttons and touch. Source/assets licenses and provenance retained; actual ARM build, not fake console stubs, with host ASan/UBSan and strict warnings. Models/compile/physical/release tiers remain separate. New code is not done without exact gate0, current RUGGED and two independent non-author PASS reviews. Evidence/source not temp-only. No exceptions other than approved native diagnostic log recovery.
''')
  put(repo,'specs/app.md',f'''# First slice: {lane['title']}

## Goal / magic moment
{goal}

## Demonstrable first slice
{proof} A user can start, interact, complete/reset or stop, and explicitly export truthful diagnostics. Source smoke alone is insufficient. Host scenario/core tests and actual native backend/artifacts required; physical observations separate.

## Exact observable acceptance
- `make test` drives actual feature core/UI/input and boundary/error/lifecycle assertions under ASan/UBSan.
- `python3 -m unittest discover -s tests -p test_contract.py -v` selects all named tests with no skips; dynamic/runner counts, not source-name guesses. Include deterministic behavior, invalid inputs, native acquisitions/cleanup and per-app journal recovery/adversarial tail/size/type tests.
- `make 3ds && make verify-3ds` builds genuine ARM ELF/SMDH/3DSX/CIA with ID `{lane['unique_id']}` / `{lane['code']}`, proper SMDH/CIA metadata and real application/SDK call graph. Test verifier with same-architecture stub/mutant, not only magic bytes.
- Diagnostic export actually creates `build/test_sd/3ds/logs/{name}.log` using correct own app schema/build/seed/time/capabilities. Native journal code reused with per-app tests; active<=256KiB, first JSON record<=199 ASCII bytes, corruption never silently trimmed.
- Real Drop-host discovery/pull byte parity and exact source/log binding required by coordinator. No new duplicate server.
- {'`python3 tests/verify_engine.py` proves actual source commit/license/compiled objects/map/defined reachable engine path, rejecting same-ARM launcher; data licensing separate. Unsupported ports remain blocked rather than rewritten as imitations.' if port or audio else 'Original assets/tunes and no copyrighted game packs; seeded/replay/simulation output reproducible where relevant.'}

## Boundaries
No save/config updates in this slice, no fake metrics/runtime backend, no host stub advertised as native functionality, no user-root paths/IDs in published text. Media/replay exports are new immutable files. Never claim physical functionality or finished asset-driven gameplay from compilation. Bounded work and visible failure, no infinite test loops. All required acceptance atomic expectations must clear>=95 plus deterministic/review gates.

## Exact field/recovery design
Run the full make/unittest chain above on an immutable pin. Deliberately invoke malformed/out-of-range input, unavailable native acquisition, shutdown/retry and unwritable/corrupt/oversize log state; assert visible failure and retained bytes then valid retry. Real SDK backend/header compile and actual production native control flow must exist. Hardware action/observation logs remain unverified until a real owner-console run.
''')
  put(repo,'IMPLEMENTATION_PLAN.md',f'''# {lane['title']} — parallel first-release plan

## T1 — Usable first slice, not bootstrap acceptance
- Status: pending.
- Objective: {goal}
- Areas: src/include/tests/Makefile/meta/scripts/README/specs, declared actual engine/dependencies where applicable; vendor shared journal only as reviewed dependency.
- Validation: make test && python3 -m unittest discover -s tests -p test_contract.py -v && make 3ds && make verify-3ds && git diff --check. {'Additionally python3 tests/verify_engine.py for genuine engine/audio provenance.' if port or audio else ''}
- Acceptance: {proof} Native module must be called by main, not only linked. Correct UID/artifacts, new error/retry/cleanup tests and actual own-app emitted log. Existing journal smoke preserved. Native data/device tests clearly labeled. Candidate stays in_progress after local checks until external exact-pin review.
- Demo: start real session, exercise actual controls/objective or recording/query/player, end/reset, explicitly export actual diagnostics; no synthetic runtime success markers.

## T2 — Review/API/demo/publication handoff
- Status: pending.
- Areas: exact code pin/real logs/native artifacts, review/report/doc evidence; no author moves to parent/root.
- Validation: repeat explicit T1 chain on final SHA; coordinator real Drop daemon api/logs/api/pull byte parity; current scoped RUGGED, fresh spec and quality PASS, mean atomic acceptance>=95; final docs audit. Confirm remote source SHA when coordinator publishes.
- Acceptance: source/license/privacy/genuine engine and actual behavior proved; source/evidence refs persistent. Public WIP is not accepted release. Physical tier remains separate, no phantom time/serial speedup.

## Boundaries and shared state
Read specs/app.md and AGENTS.md. User consent extends to this repo; no data upload by default. Source/failure evidence stays in durable workspace/ref, no temp-only work. Root constitution approved diagnostic journal exception only; old saves remain protected. The coordinator supplies read-only references/current image and owns timing, independent reviewers and publication. Work exactly one task/iteration; loop commits exact owned paths. Author model `{lane['model']}`; source identity `{lane['unique_id']}` / `{lane['code']}`.
''')
  call('git','init','-q','-b','main',cwd=repo)
  for key,value in identity.items():call('git','config',key,value,cwd=repo)
  call('git','add','.',cwd=repo);call('git','commit','-qm','docs: define WIP first slice and vendor verified journal runtime',cwd=repo)
  call('jj','git','init','--colocate',cwd=repo)
  lane['base_sha']=call('git','rev-parse','HEAD',cwd=repo).strip();lane['state']='scaffold_runtime_signal_pending'
  print(name,'created, clean Git/jj baseline; no app acceptance claimed')
 (RUN/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')

if __name__=='__main__':main()
