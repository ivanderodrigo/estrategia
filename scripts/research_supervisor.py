#!/usr/bin/env python3
"""Watchdog for bounded research, fallback, build and diagnostics."""

from __future__ import annotations

import argparse
import json
import os
import queue
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.pipeline import run as build  # noqa: E402
from engine.settings import VERSION  # noqa: E402
from engine.storage import ProcessLock, atomic_write_json, read_json  # noqa: E402


def _terminate(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            process.terminate()
        else:
            os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=8)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            if os.name == "nt":
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _run_research(profile: str, budget_s: int, *, max_tasks: int | None = None) -> dict[str, Any]:
    command = [
        sys.executable,
        "-m",
        "engine.research.web_intelligence",
        "--profile",
        profile,
        "--max-runtime",
        str(max(20, budget_s)),
    ]
    if max_tasks:
        command.extend(["--max-tasks", str(max_tasks)])
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        start_new_session=os.name != "nt",
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )
    lines: queue.Queue[str] = queue.Queue()

    def reader() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            lines.put(line.rstrip())

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    started = time.monotonic()
    deadline = started + budget_s + 15
    next_heartbeat = started + 25
    json_result: dict[str, Any] = {}
    tail: list[str] = []
    timed_out = False

    while process.poll() is None:
        while True:
            try:
                line = lines.get_nowait()
            except queue.Empty:
                break
            if line:
                print(line, flush=True)
                tail.append(line)
                tail = tail[-20:]
                if line.startswith("{"):
                    try:
                        parsed = json.loads(line)
                        if isinstance(parsed, dict):
                            json_result = parsed
                    except json.JSONDecodeError:
                        pass
        now = time.monotonic()
        if now >= deadline:
            timed_out = True
            _terminate(process)
            break
        if now >= next_heartbeat:
            print(
                f"supervisor heartbeat: {profile} · {round(now-started)}s · process active",
                flush=True,
            )
            next_heartbeat = now + 25
        time.sleep(0.35)

    thread.join(timeout=2)
    while not lines.empty():
        line = lines.get_nowait()
        if line:
            print(line, flush=True)
            tail.append(line)
            if line.startswith("{"):
                try:
                    parsed = json.loads(line)
                    if isinstance(parsed, dict):
                        json_result = parsed
                except json.JSONDecodeError:
                    pass

    if timed_out:
        return {
            "status": "checkpoint-timeout",
            "budget_s": budget_s,
            "note": "Watchdog stopped the subprocess; atomic checkpoints remain valid.",
        }
    if process.returncode != 0:
        return {
            "status": "degraded",
            "returncode": process.returncode,
            "error": "\n".join(tail[-8:])[-1_500:],
        }
    return {"status": "ok", **json_result}


def _append_history(status: dict[str, Any]) -> None:
    raw = read_json("data/current/run_history.json", {"version": VERSION, "runs": []})
    runs = list(raw.get("runs") or [])
    runs.append(status)
    atomic_write_json(
        "data/current/run_history.json",
        {"version": VERSION, "updated_at": time.time(), "runs": runs[-120:]},
    )


def _allocate_budgets(max_runtime: int, requested_fallback: int) -> tuple[int, int, int, int]:
    """Reserve build time without ever reporting a budget larger than the total."""

    total = max(40, int(max_runtime))
    reserve = min(240, max(15, total // 8), total - 20)
    fallback = max(0, min(int(requested_fallback), total - reserve - 20))
    research = total - reserve - fallback
    return total, research, fallback, reserve


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=["daily", "deep", "exhaustive"], default="daily")
    parser.add_argument("--max-runtime", type=int, default=720)
    parser.add_argument("--fallback-runtime", type=int, default=0)
    arguments = parser.parse_args()

    started = time.monotonic()
    effective_runtime, research_budget, fallback_budget, reserve = _allocate_budgets(
        arguments.max_runtime, arguments.fallback_runtime
    )
    status: dict[str, Any] = {
        "version": VERSION,
        "profile": arguments.profile,
        "started_at": time.time(),
        "requested_max_runtime_s": arguments.max_runtime,
        "effective_max_runtime_s": effective_runtime,
        "budgets": {
            "research_s": research_budget,
            "fallback_s": fallback_budget,
            "build_reserve_s": reserve,
        },
        "stages": [],
    }
    exit_code = 0

    try:
        with ProcessLock(timeout_s=5):
            result = _run_research(arguments.profile, research_budget)
            status["stages"].append({
                "research": result.get("status"),
                "fetch_attempts": result.get("fetch_attempts", 0),
                "fetch_successes": result.get("fetch_successes", 0),
                "pages_relevant": result.get("pages_relevant", 0),
                "candidate_evidences": result.get("candidate_evidences", 0),
                "accepted_evidences": result.get("accepted_evidences", 0),
                "fields_enriched": result.get("fields_enriched", 0),
                "values_added": result.get("values_added", 0),
                "entities_added": result.get("entities_added", 0),
                "stop_reason": result.get("stop_reason"),
                "error": result.get("error", ""),
            })

            if result.get("status") != "ok" and fallback_budget:
                fallback = _run_research("daily", fallback_budget, max_tasks=80)
                status["stages"].append({
                    "fallback": fallback.get("status"),
                    "fetch_attempts": fallback.get("fetch_attempts", 0),
                    "accepted_evidences": fallback.get("accepted_evidences", 0),
                    "fields_enriched": fallback.get("fields_enriched", 0),
                    "error": fallback.get("error", ""),
                })

            metrics = build()
            after = metrics["after"]
            before = metrics["before"]
            quality = read_json("data/current/quality_report.json")
            status["stages"].append({
                "build": "ok",
                "gaps": after["gaps_total"],
                "gaps_closed_vs_release_baseline": before["gaps_total"] - after["gaps_total"],
                "distributor_gaps": after["gaps_by_section"]["distributors"],
                "integrator_gaps": after["gaps_by_section"]["integrators"],
                "quality_score": quality.get("score"),
            })
    except TimeoutError as exc:
        status["stages"].append({"lock": "busy", "error": str(exc)})
        exit_code = 2
    except Exception as exc:
        status["stages"].append({"build": "failed", "error": f"{type(exc).__name__}: {exc}"[:1_000]})
        exit_code = 1
    finally:
        status["elapsed_s"] = round(time.monotonic() - started, 2)
        status["finished_at"] = time.time()
        atomic_write_json("data/current/supervisor.json", status)
        _append_history(status)

    print(json.dumps(status, ensure_ascii=False, indent=2), flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
