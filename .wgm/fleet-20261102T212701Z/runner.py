#!/usr/bin/env python3
"""One fresh Pi JSON invocation, bounded process-group ownership and measured timing.

Transcripts, ownership receipts and the append-only metrics ledger stay in PRIVATE.
FLEET_PI_EXECUTABLE selects a disposable executable for subprocess fixtures only;
no shell is involved and this wrapper never reads credentials.
"""
import argparse
import ctypes
import fcntl
import json
import math
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import time
import uuid

RUN = Path(__file__).resolve().parent
PRIVATE = Path(os.environ.get("FLEET_PRIVATE", "/tmp/lafiabrew-fleet-20261102T212701Z"))
MAX_RECORD_BYTES = 8 * 1024 * 1024


def semantic_success(last, settled, aborted, rc):
    return rc == 0 and settled and not aborted and last.get("stopReason") == "stop"


def external_path(path):
    path = Path(path).resolve()
    # The run directory is inside the guarded workspace. Never write metrics there,
    # even through a symlink or an environment override.
    guarded = RUN.parent.parent
    if path == guarded or guarded in path.parents:
        raise ValueError(f"private output must be outside guarded workspace: {path}")
    return path


def append_record(record):
    ledger = external_path(os.environ.get("FLEET_METRICS_FILE", str(PRIVATE / "agent-metrics.jsonl")))
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as out:
        fcntl.flock(out, fcntl.LOCK_EX)
        out.write(json.dumps(record, separators=(",", ":"), allow_nan=False) + "\n")
        out.flush()
        fcntl.flock(out, fcntl.LOCK_UN)


class EventStream:
    """Strict binary LF framing, including UTF-8 split across arbitrary reads."""
    def __init__(self):
        self.buffer = bytearray()
        self.discarding = False
        self.last = {}
        self.settled = False
        self.aborted = False
        self.active_start = None
        self.turn_intervals = []
        self.missing_turns = 0
        self.turn_events = 0
        self.tool_ms = 0.0
        self.missing_tool_durations = 0
        self.malformed = 0

    def feed(self, data, now):
        # Do not use splitlines(): U+2028/U+2029 are JSON string contents.
        parts = data.split(b"\n")
        for index, part in enumerate(parts):
            complete = index < len(parts) - 1
            if not self.discarding:
                self.buffer.extend(part)
                if len(self.buffer) > MAX_RECORD_BYTES:
                    self.malformed += 1
                    self.buffer.clear()
                    self.discarding = True
            if complete:
                if not self.discarding:
                    self.consume(bytes(self.buffer), now)
                self.buffer.clear()
                self.discarding = False

    def eof(self):
        if self.buffer:  # A non-LF-terminated record is not a JSONL record.
            self.malformed += 1
        self.buffer.clear()
        self.discarding = False

    def consume(self, line, now):
        try:
            event = json.loads(line.decode("utf-8"), parse_constant=self.reject_constant)
            if not isinstance(event, dict) or not isinstance(event.get("type"), str):
                raise ValueError("record must be an event object")
            kind = event["type"]
            if kind in ("agent_start", "turn_start", "auto_retry_start", "message_start",
                        "tool_execution_start", "compaction_start"):
                self.settled = False
            if kind == "turn_start":
                self.turn_events += 1
                if self.active_start is not None:
                    self.missing_turns += 1
                self.active_start = now
            elif kind == "turn_end":
                self.turn_events += 1
                if self.active_start is None:
                    self.missing_turns += 1
                else:
                    self.turn_intervals.append([self.active_start, now])
                    self.active_start = None
            elif kind == "message_end":
                message = event.get("message")
                if not isinstance(message, dict):
                    raise ValueError("message must be an object")
                if message.get("role") == "assistant":
                    content = message.get("content", [])
                    if not isinstance(content, list) or any(
                        not isinstance(block, dict) or
                        (block.get("type") == "text" and not isinstance(block.get("text", ""), str))
                        for block in content
                    ):
                        raise ValueError("invalid assistant content")
                    self.last = message
                    self.settled = False
            elif kind == "tool_execution_end":
                duration = event.get("durationMs")
                if duration is None:
                    self.missing_tool_durations += 1
                elif (isinstance(duration, bool) or not isinstance(duration, (int, float))
                      or not math.isfinite(duration) or duration < 0):
                    raise ValueError("invalid tool duration")
                else:
                    total = self.tool_ms + duration
                    if not math.isfinite(total):
                        raise ValueError("tool duration total overflow")
                    self.tool_ms = total
            elif kind == "agent_settled":
                if not isinstance(event.get("aborted"), bool):
                    raise ValueError("settlement requires boolean aborted")
                self.settled = True
                self.aborted = self.aborted or event["aborted"]
        except (ValueError, UnicodeError, RecursionError):
            self.malformed += 1

    @staticmethod
    def reject_constant(value):
        raise ValueError(f"invalid JSON constant: {value}")

    def finish(self):
        if self.active_start is not None:
            self.missing_turns += 1
            self.active_start = None
        if not self.turn_events:
            self.missing_turns += 1


def enable_subreaper():
    """Adopt/reap orphaned same-group descendants on Linux, not unrelated groups."""
    if not sys.platform.startswith("linux"):
        return False
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        return False
    return True


class OwnedProcess:
    """A session/process group remains owned until both leader and group are gone.

    Repeated cancellation only latches a flag; it never restarts cleanup deadlines.
    KILL cannot bound kernel uninterruptible sleep: such a group is retained in the
    ownership receipt as cleanup_pending, with its PID/PGID and observed status.
    """
    def __init__(self, receipt, term_grace, kill_wait):
        self.receipt = receipt
        self.term_grace = term_grace
        self.kill_wait = kill_wait
        self.child = None
        self.cancel_signal = None
        self.reason = None
        self.stage = "not_started"
        self.errors = []
        self.subreaper = False
        self.complete = False
        self.term_deadline = None
        self.kill_deadline = None

    def cancel(self, signum, frame):
        if self.cancel_signal is None:
            self.cancel_signal = signum

    def group_exists(self):
        try:
            os.killpg(self.child.pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True

    def poll(self):
        rc = self.child.poll()  # Reap leader before waitpid can see it.
        if rc is not None and self.subreaper:
            while True:
                try:
                    pid, _ = os.waitpid(-self.child.pid, os.WNOHANG)
                    if pid == 0:
                        break
                except ChildProcessError:
                    break
        self.complete = rc is not None and not self.group_exists()
        return rc

    def snapshot(self):
        return {"pid": self.child.pid if self.child else None,
                "pgid": self.child.pid if self.child else None,
                "owned": self.child is not None and not self.complete,
                "status": "reaped" if self.complete else self.stage,
                "cleanup_complete": self.complete, "cleanup_reason": self.reason,
                "cancel_signal": self.cancel_signal,
                "process_rc": self.child.returncode if self.child else None,
                "subreaper": self.subreaper, "cleanup_errors": self.errors[:]}

    def persist(self):
        temp = self.receipt.with_suffix(".tmp")
        temp.write_text(json.dumps(self.snapshot(), allow_nan=False) + "\n", encoding="utf-8")
        temp.replace(self.receipt)

    def send(self, sig):
        try:
            os.killpg(self.child.pid, sig)
        except ProcessLookupError:
            pass
        except OSError as exc:
            self.errors.append(f"{signal.Signals(sig).name}: {exc}")

    def begin_term(self):
        if self.term_deadline is None:
            self.stage = "term_sent"
            self.term_deadline = time.monotonic() + self.term_grace
            self.send(signal.SIGTERM)
        return self.term_deadline

    def begin_kill(self):
        if self.kill_deadline is None:
            self.stage = "kill_sent"
            self.kill_deadline = time.monotonic() + self.kill_wait
            self.send(signal.SIGKILL)
        return self.kill_deadline

    def emergency_cleanup(self):
        """Bounded fallback, preserving any already-started cleanup deadlines."""
        self.poll()
        if self.complete:
            return
        self.reason = self.reason or "supervisor_error"
        self.begin_term()
        while not self.complete:
            self.poll()
            if self.complete:
                break
            now = time.monotonic()
            if now >= self.term_deadline:
                self.begin_kill()
                if now >= self.kill_deadline:
                    break
            deadline = self.kill_deadline if self.kill_deadline is not None else self.term_deadline
            time.sleep(min(0.02, max(0, deadline - now)))

    def run(self, cmd, raw, err, stream, timeout):
        previous = {sig: signal.signal(sig, self.cancel) for sig in (signal.SIGINT, signal.SIGTERM)}
        selector = selectors.DefaultSelector()
        try:
            self.subreaper = enable_subreaper()
            self.child = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                          stderr=err, start_new_session=True)
            self.stage = "running"
            self.persist()
            os.set_blocking(self.child.stdout.fileno(), False)
            selector.register(self.child.stdout, selectors.EVENT_READ)
            pipe_open = True
            deadline = time.monotonic() + timeout
            cleanup_deadline = None
            while True:
                now = time.monotonic()
                rc = self.poll()
                if self.cancel_signal is not None and self.reason is None:
                    self.reason = "cancelled"
                elif now >= deadline and self.reason is None:
                    self.reason = "timeout"
                elif rc is not None and not self.complete and self.reason is None:
                    self.reason = "descendants_after_exit"
                if self.reason is not None and cleanup_deadline is None:
                    cleanup_deadline = self.begin_term()
                    self.persist()
                if self.complete and not pipe_open:
                    break
                if cleanup_deadline is not None and now >= cleanup_deadline:
                    if self.stage == "term_sent":
                        cleanup_deadline = self.begin_kill()
                        self.persist()
                    else:
                        break
                # One bounded chunk per iteration: a flood cannot starve clocks/signals.
                until = cleanup_deadline if cleanup_deadline is not None else deadline
                ready = selector.select(max(0, min(0.025, until - now)))
                for key, _ in ready:
                    try:
                        data = os.read(key.fd, 65536)
                    except BlockingIOError:
                        continue
                    if data:
                        raw.write(data)
                        raw.flush()
                        stream.feed(data, time.monotonic())
                    else:
                        selector.unregister(key.fileobj)
                        pipe_open = False
                        stream.eof()
            self.poll()
        except Exception as exc:
            self.reason = self.reason or "supervisor_error"
            self.errors.append(f"{type(exc).__name__}: {exc}")
        finally:
            try:
                if self.child is not None:
                    if not self.complete:
                        self.emergency_cleanup()
                    self.poll()
                    self.stage = "reaped" if self.complete else "cleanup_pending"
                    self.persist()
            finally:
                selector.close()
                if self.child is not None and self.child.stdout is not None:
                    self.child.stdout.close()
                for sig, handler in previous.items():
                    signal.signal(sig, handler)
        return self.snapshot()


def positive_seconds(value):
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise argparse.ArgumentTypeError("must be finite and positive")
    return result


def self_test():
    assert semantic_success({"stopReason": "stop"}, True, False, 0)
    for reason in ("error", "aborted", "length", "toolUse", "pending"):
        assert not semantic_success({"stopReason": reason}, True, False, 0)
    assert not semantic_success({"stopReason": "stop"}, False, False, 0)
    assert not semantic_success({"stopReason": "stop"}, True, True, 0)
    assert not semantic_success({"stopReason": "stop"}, True, False, 1)
    stream = EventStream()
    data = json.dumps({"type": "message_end", "message": {"role": "assistant", "stopReason": "stop",
                      "content": [{"type": "text", "text": "é\u2028雪"}]}}, ensure_ascii=False).encode() + b"\n"
    for byte in data:
        stream.feed(bytes([byte]), time.monotonic())
    stream.feed(b'{"type":"agent_settled","aborted":false}\n', time.monotonic())
    assert stream.malformed == 0 and semantic_success(stream.last, stream.settled, stream.aborted, 0)
    stream.feed(b'[]\n\xff\n', time.monotonic())
    assert stream.malformed == 2
    print("PASS: semantic failures/unsettled exits fail closed; binary LF/fragmented UTF-8 framing")
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="gpt-6.1-sol")
    parser.add_argument("--role", default="author")
    parser.add_argument("--lane", default="coordinator")
    parser.add_argument("--phase", default="implementation")
    parser.add_argument("--thinking", default="medium")
    parser.add_argument("--timeout", type=positive_seconds, default=1800.0)
    parser.add_argument("--term-grace", type=positive_seconds, default=5.0)
    parser.add_argument("--kill-wait", type=positive_seconds, default=5.0)
    parser.add_argument("--prompt-file")
    parser.add_argument("prompt", nargs="?")
    args = parser.parse_args()
    prompt = Path(args.prompt_file).read_text() if args.prompt_file else args.prompt
    if not prompt:
        parser.error("a prompt or --prompt-file is required")
    try:
        private = external_path(PRIVATE)
        external_path(os.environ.get("FLEET_METRICS_FILE", str(private / "agent-metrics.jsonl")))
    except ValueError as exc:
        parser.error(str(exc))
    # User labels go in metrics, never in file paths.
    ident = uuid.uuid4().hex
    logs = external_path(private / "agents")
    logs.mkdir(parents=True, exist_ok=True)
    executable = os.environ.get("FLEET_PI_EXECUTABLE", "pi")
    cmd = [executable, "--mode", "json", "--no-session", "--no-extensions", "--no-mcp",
           "--no-skills", "--no-prompt-templates", "--no-approve", "--provider", "github-copilot",
           "--model", args.model, "--thinking", args.thinking, "--", prompt]
    started = time.monotonic()
    start_epoch = time.time()
    stream = EventStream()
    owner = OwnedProcess(logs / f"{ident}.ownership.json", args.term_grace, args.kill_wait)
    with (logs / f"{ident}.stderr").open("wb") as err, (logs / f"{ident}.jsonl").open("wb") as raw:
        lifecycle = owner.run(cmd, raw, err, stream, args.timeout)
    stream.eof()
    stream.finish()
    ended = time.monotonic()
    ok = (stream.malformed == 0 and lifecycle["cleanup_complete"] and
          lifecycle["cleanup_reason"] is None and lifecycle["cancel_signal"] is None and
          semantic_success(stream.last, stream.settled, stream.aborted, lifecycle["process_rc"]))
    text = "\n".join(block.get("text", "") for block in stream.last.get("content", [])
                     if block.get("type") == "text")
    (logs / f"{ident}.final.md").write_text(text + "\n", encoding="utf-8")
    append_record({"id": ident, "lane": args.lane, "role": args.role, "phase": args.phase,
                   "model": args.model, "start_epoch": start_epoch, "end_epoch": time.time(),
                   "start_monotonic": started, "end_monotonic": ended,
                   "invocation_s": ended - started,
                   "observed_active_turn_s_lower_bound": sum(end - start for start, end in stream.turn_intervals),
                   "turn_intervals_monotonic": stream.turn_intervals,
                   "timed_turns": len(stream.turn_intervals), "missing_turns": stream.missing_turns,
                   "tool_duration_ms": stream.tool_ms, "missing_tool_durations": stream.missing_tool_durations,
                   "settled": stream.settled, "aborted": stream.aborted,
                   "stop_reason": stream.last.get("stopReason"), "malformed_records": stream.malformed,
                   **lifecycle, "ok": ok})
    print(text)
    if not ok:
        print(f"Pi invocation failed closed: process_rc={lifecycle['process_rc']}, "
              f"settled={stream.settled}, stop_reason={stream.last.get('stopReason')}, "
              f"malformed={stream.malformed}, cleanup={lifecycle['status']}, "
              f"reason={lifecycle['cleanup_reason']}", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(self_test() if sys.argv[1:] == ["self-test"] else main())
