#!/usr/bin/env python3
"""Bounded supervisor for GitHub Actions research runs.

The collector owns checkpoints and partial publication. This supervisor adds a
hard outer deadline, progress heartbeats, validation, last-known-good rollback
and a diagnostic log that can be uploaded as a workflow artifact.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import re
import selectors
import shutil
import signal
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DIAGNOSTICS = ROOT / "diagnostics"
OUT = DATA / "research.latest.json"
STATUS = DATA / "research_status.json"
SUPERVISOR = DATA / "supervisor.latest.json"


def atomic_json(path: pathlib.Path, value: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def redact(text: str) -> str:
    text = re.sub(r"(?i)(api[_-]?key|token|authorization)(\s*[:=]\s*)\S+", r"\1\2[REDACTED]", text)
    text = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~-]+", r"\1[REDACTED]", text)
    return text.rstrip()


def valid_json(path: pathlib.Path) -> bool:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return isinstance(value, dict) and isinstance(value.get("evidence"), list)
    except Exception:
        return False


# V325_WINDOWS_STREAM_COMPAT

def run_streamed(command, env, max_runtime, log_path, profile):
    """Portable subprocess streaming: thread+queue instead of selectors on pipes."""
    import queue as _queue
    import subprocess as _subprocess
    import threading as _threading
    import time as _time

    started = _time.monotonic()
    deadline = started + max(1, float(max_runtime))
    last_heartbeat = started
    q = _queue.Queue()
    eof = object()
    timed_out = False
    line_count = 0

    process = _subprocess.Popen(
        command,
        cwd=globals().get("ROOT"),
        env=env,
        stdout=_subprocess.PIPE,
        stderr=_subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    def _reader():
        try:
            if process.stdout is not None:
                for line in iter(process.stdout.readline, ""):
                    q.put(line)
        finally:
            q.put(eof)

    reader = _threading.Thread(
        target=_reader,
        name="legacy-stdout-reader",
        daemon=True,
    )
    reader.start()

    try:
        parent = getattr(log_path, "parent", None)
        if parent is not None:
            parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    saw_eof = False
    with open(log_path, "a", encoding="utf-8", errors="replace") as log_handle:
        while True:
            now = _time.monotonic()
            if process.poll() is None and now >= deadline:
                timed_out = True
                print(
                    f"supervisor timeout: {profile} · {int(now-started)}s elapsed · terminating child",
                    flush=True,
                )
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except Exception:
                    try:
                        process.kill()
                    except Exception:
                        pass

            try:
                item = q.get(timeout=0.5)
                if item is eof:
                    saw_eof = True
                else:
                    line_count += 1
                    print(item, end="", flush=True)
                    log_handle.write(item)
                    log_handle.flush()
            except _queue.Empty:
                pass

            now = _time.monotonic()
            if process.poll() is None and now - last_heartbeat >= 30:
                print(
                    f"supervisor heartbeat: {profile} · {int(now-started)}s elapsed · process active",
                    flush=True,
                )
                last_heartbeat = now

            if process.poll() is not None and (saw_eof or not reader.is_alive()) and q.empty():
                break

        while True:
            try:
                item = q.get_nowait()
            except _queue.Empty:
                break
            if item is eof:
                continue
            line_count += 1
            print(item, end="", flush=True)
            log_handle.write(item)

    try:
        if process.stdout is not None:
            process.stdout.close()
    except Exception:
        pass

    rc = process.wait()
    elapsed = round(_time.monotonic() - started, 1)
    return rc, {
        "status": "timeout" if timed_out else ("success" if rc == 0 else "failed"),
        "timed_out": timed_out,
        "returncode": rc,
        "elapsed_seconds": elapsed,
        "lines": line_count,
        "stream_backend": "thread_queue",
    }



def run_validation(log_path: pathlib.Path) -> tuple[bool, str]:
    result = subprocess.run([sys.executable, "scripts/validate.py"], cwd=ROOT, capture_output=True, text=True)
    output = redact((result.stdout or "") + (result.stderr or ""))
    with log_path.open("a", encoding="utf-8") as log: log.write("\n[validation]\n" + output + "\n")
    print(output, flush=True)
    return result.returncode == 0 and valid_json(OUT), output[-1600:]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=["daily", "deep", "exhaustive"], default=os.getenv("RESEARCH_PROFILE", "deep"))
    parser.add_argument("--max-runtime", type=int, default=1800)
    parser.add_argument("--fallback-runtime", type=int, default=240)
    args = parser.parse_args()
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    DIAGNOSTICS.mkdir(exist_ok=True)
    log_path = DIAGNOSTICS / f"research-{run_id}-{args.profile}.log"
    backup = DIAGNOSTICS / f"last-good-{run_id}.json"
    had_last_good = valid_json(OUT)
    if had_last_good: shutil.copy2(OUT, backup)
    env = os.environ.copy();env["PYTHONUNBUFFERED"] = "1";env["RESEARCH_PROFILE"] = args.profile;env["RESEARCH_MAX_RUNTIME_SECONDS"] = str(args.max_runtime)
    started = time.monotonic()
    command = [sys.executable, "scripts/research.py", f"--profile={args.profile}", f"--max-runtime={args.max_runtime}"]
    code, process_outcome = run_streamed(command, env, args.max_runtime + 120, log_path, args.profile)
    fallback_used = False
    if code != 0 and args.profile != "daily" and args.fallback_runtime > 0:
        fallback_used = True
        env["RESEARCH_PROFILE"] = "daily";env["RESEARCH_MAX_RUNTIME_SECONDS"] = str(args.fallback_runtime)
        fallback = [sys.executable, "scripts/research.py", "--profile=daily", f"--max-runtime={args.fallback_runtime}"]
        code, process_outcome = run_streamed(fallback, env, args.fallback_runtime + 90, log_path, "daily-recovery")
    valid, validation_tail = run_validation(log_path) if code == 0 else (False, f"collector exit code {code}")
    outcome = "complete-or-partial-valid" if code == 0 and valid else "failed-last-good-preserved"
    restored = False
    if outcome != "complete-or-partial-valid" and had_last_good:
        shutil.copy2(backup, OUT);restored = True
        valid, validation_tail = run_validation(log_path)
    manifest = {
        "version": 2, "runId": run_id, "profileRequested": args.profile, "startedAt": dt.datetime.fromtimestamp(time.time()-(time.monotonic()-started),dt.timezone.utc).isoformat(),
        "finishedAt": dt.datetime.now(dt.timezone.utc).isoformat(), "elapsedSeconds": round(time.monotonic()-started,2), "outcome": outcome,
        "processOutcome": process_outcome, "exitCode": code, "fallbackUsed": fallback_used, "lastGoodRestored": restored,
        "datasetValid": valid, "diagnosticLog": str(log_path.relative_to(ROOT)), "validationTail": validation_tail
    }
    atomic_json(SUPERVISOR, manifest)
    status = {}
    try: status = json.loads(STATUS.read_text(encoding="utf-8"))
    except Exception: pass
    status.update({"supervisor": manifest, "outcome": status.get("outcome") if outcome == "complete-or-partial-valid" else outcome})
    atomic_json(STATUS, status)
    if backup.exists(): backup.unlink()
    print(f"supervisor result: {outcome} · valid={valid} · fallback={fallback_used} · restored={restored}", flush=True)
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
