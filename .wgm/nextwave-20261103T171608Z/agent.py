#!/usr/bin/env python3
"""Fresh Pi JSON invocation with reused reviewed process ownership/event parser.

Logs live durably outside the ACTUAL candidate Git root, not outside the entire
project volume. They remain private/ignored and are never published as source.
"""
import argparse
import datetime
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

RUN = Path(__file__).resolve().parent
PROJECT = RUN.parent.parent
OLD = PROJECT / '.wgm/fleet-20261102T212701Z/runner.py'
spec = importlib.util.spec_from_file_location('reviewed_fleet_runner', OLD)
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)
MAX_OUTPUT = 128 * 1024 * 1024


def candidate_root():
    result = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], stderr=subprocess.PIPE)
    root = Path(result.decode().strip()).resolve()
    if Path.cwd().resolve() != root:
        raise ValueError('run from the actual isolated candidate/snapshot repository root')
    return root


def check_log_root(root, guarded):
    root = root.resolve()
    if root == guarded or guarded in root.parents:
        raise ValueError('private logs cannot be written inside the guarded candidate tree')
    if root != (RUN / 'runtime').resolve() and (RUN / 'runtime').resolve() not in root.parents:
        raise ValueError('private logs must stay in this durable wave runtime area')
    return root


class CappedOutput:
    def __init__(self, stream, limit=MAX_OUTPUT):
        self.stream = stream
        self.limit = limit
        self.count = 0
        self.lost = False

    def write(self, data):
        if self.count + len(data) > self.limit:
            self.lost = True
            raise OSError('full JSON output budget exceeded; evidence incomplete, not success')
        self.stream.write(data)
        self.count += len(data)

    def flush(self):
        self.stream.flush()


def append(row):
    path = RUN / 'runtime/agent-metrics.jsonl'
    with path.open('a') as out:
        fcntl.flock(out, fcntl.LOCK_EX)
        out.write(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n')
        out.flush()


def self_test():
    assert core.semantic_success({'stopReason': 'stop'}, True, False, 0)
    for reason in ['error', 'length', 'aborted', 'toolUse']:
        assert not core.semantic_success({'stopReason': reason}, True, False, 0)
    root = RUN / 'runtime'
    assert check_log_root(root, RUN / 'snapshots/example') == root.resolve()
    for bad, guard in [(root, RUN), (PROJECT, PROJECT), (RUN / 'foreign', RUN / 'snapshots/example')]:
        try: check_log_root(bad, guard)
        except ValueError: pass
        else: raise AssertionError('unsafe/foreign log root accepted')
    stream = core.EventStream()
    data = json.dumps({'type':'message_end','message':{'role':'assistant','stopReason':'stop','content':[{'type':'text','text':'READY\u2028雪'}]}}, ensure_ascii=False).encode()+b'\n'
    for value in data: stream.feed(bytes([value]), time.monotonic())
    stream.feed(b'{"type":"agent_settled","aborted":false}\n', time.monotonic())
    assert stream.malformed == 0 and core.semantic_success(stream.last,stream.settled,stream.aborted,0)
    print('PASS: terminal semantics, strict fragmented LF/UTF8 framing, durable log-root isolation')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--lane', required=True)
    parser.add_argument('--role', default='author')
    parser.add_argument('--phase', default='implementation')
    parser.add_argument('--model', default='gpt-6.1-sol')
    parser.add_argument('--thinking', default='medium')
    parser.add_argument('--timeout', type=core.positive_seconds, default=1800)
    parser.add_argument('--prompt-file')
    parser.add_argument('--max-output-bytes', type=int, default=MAX_OUTPUT)
    parser.add_argument('--executable', default=os.environ.get('WAVE_PI_EXECUTABLE','pi'), help='Pi executable; controlled fixture injection only in tests')
    parser.add_argument('prompt', nargs='?')
    args = parser.parse_args()
    prompt = Path(args.prompt_file).read_text() if args.prompt_file else args.prompt
    if not prompt: parser.error('prompt required')
    if args.max_output_bytes <= 0: parser.error('positive output budget required')
    guarded = candidate_root()
    logs = check_log_root(RUN / 'runtime/agents', guarded)
    logs.mkdir(parents=True, exist_ok=True)
    (RUN / 'runtime').chmod(0o700)
    ident = uuid.uuid4().hex
    events = core.EventStream()
    owner = core.OwnedProcess(logs / (ident+'.ownership.json'), 5, 5)
    cmd=[args.executable,'--mode','json','--no-session','--no-extensions','--no-mcp','--no-skills',
         '--no-prompt-templates','--no-approve','--provider','github-copilot',
         '--model',args.model,'--thinking',args.thinking,'--',prompt]
    start=time.monotonic();epoch=time.time()
    with (logs/(ident+'.stderr')).open('wb') as err,(logs/(ident+'.jsonl')).open('wb') as raw:
        capped=CappedOutput(raw,args.max_output_bytes)
        state=owner.run(cmd,capped,err,events,args.timeout)
    events.eof();events.finish();end=time.monotonic()
    ok=(not capped.lost and not events.malformed and state['cleanup_complete'] and
        state['cleanup_reason'] is None and state['cancel_signal'] is None and
        core.semantic_success(events.last,events.settled,events.aborted,state['process_rc']))
    text='\n'.join(b.get('text','') for b in events.last.get('content',[]) if b.get('type')=='text')
    (logs/(ident+'.final.md')).write_text(text+'\n')
    append({'id':ident,'lane':args.lane,'role':args.role,'phase':args.phase,'model':args.model,
            'start_epoch':epoch,'end_epoch':time.time(),'start_monotonic':start,'end_monotonic':end,
            'invocation_s':end-start,'observed_active_turn_s_lower_bound':sum(b-a for a,b in events.turn_intervals),
            'turn_intervals_monotonic':events.turn_intervals,'timed_turns':len(events.turn_intervals),
            'missing_turns':events.missing_turns,'tool_duration_ms':events.tool_ms,
            'missing_tool_durations':events.missing_tool_durations,'settled':events.settled,
            'aborted':events.aborted,'stop_reason':events.last.get('stopReason'),
            'malformed_records':events.malformed,'evidence_lost':capped.lost,**state,'ok':ok})
    print(text)
    if not ok: print('FAIL: invocation/evidence/cleanup semantic gate; inspect retained private receipt',file=sys.stderr)
    return 0 if ok else 1


if __name__=='__main__':
    if sys.argv[1:]==['self-test']: self_test()
    else: raise SystemExit(main())
