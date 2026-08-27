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


def run_streamed(command: list[str], env: dict, hard_timeout: int, log_path: pathlib.Path, label: str) -> tuple[int, str]:
    started = time.monotonic()
    last_heartbeat = started
    proc = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, start_new_session=True)
    selector = selectors.DefaultSelector()
    selector.register(proc.stdout, selectors.EVENT_READ)
    outcome = "completed"
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n[{dt.datetime.now(dt.timezone.utc).isoformat()}] {label} command started\n")
        while proc.poll() is None:
            now = time.monotonic()
            if now - started >= hard_timeout:
                outcome = "outer-timeout"
                print(f"supervisor: {label} reached outer deadline; requesting graceful publication", flush=True)
                log.write(f"[{dt.datetime.now(dt.timezone.utc).isoformat()}] outer deadline; SIGINT sent\n")
                os.killpg(proc.pid, signal.SIGINT)
                try:
                    proc.wait(timeout=90)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGTERM)
                    try: proc.wait(timeout=20)
                    except subprocess.TimeoutExpired: os.killpg(proc.pid, signal.SIGKILL)
                break
            events = selector.select(timeout=2)
            for key, _ in events:
                line = key.fileobj.readline()
                if line:
                    safe = redact(line)
                    print(safe, flush=True)
                    log.write(safe + "\n")
            if now - last_heartbeat >= 30:
                heartbeat = f"supervisor heartbeat: {label} · {round(now-started)}s elapsed · process active"
                print(heartbeat, flush=True);log.write(heartbeat + "\n");last_heartbeat = now
        if proc.stdout:
            for line in proc.stdout:
                safe = redact(line);print(safe, flush=True);log.write(safe + "\n")
    return int(proc.returncode or 0), outcome


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
