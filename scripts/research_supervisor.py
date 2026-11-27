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


def _worker_runtime(budget_s: int) -> tuple[int, int]:
    """Keep time for the worker's final atomic checkpoint before watchdog kill.

    The crawler can be inside a slow source request when its internal deadline
    is reached, and its final state/learning JSON flush is not instantaneous.
    A worker deadline equal to the process watchdog deadline repeatedly killed
    the Weekly just after hundreds of successful source checks.
    """
    total = max(40, int(budget_s))
    shutdown_reserve = min(120, max(30, total // 10))
    return max(20, total - shutdown_reserve), shutdown_reserve


def _run_research(profile: str, budget_s: int, *, max_tasks: int | None = None) -> dict[str, Any]:
    worker_budget, shutdown_reserve = _worker_runtime(budget_s)
    print(
        f"supervisor budget: {profile} · worker {worker_budget}s · "
        f"checkpoint reserve {shutdown_reserve}s · hard cap {budget_s+15}s",
        flush=True,
    )
    command = [
        sys.executable,
        "-m",
        "engine.research.web_intelligence",
        "--profile",
        profile,
        "--max-runtime",
        str(worker_budget),
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


def _run_bounded_build(timeout_s: int) -> dict[str, Any]:
    """Isolate the large canonical rebuild behind an explicit hard deadline.

    The crawler already has a process-group watchdog, but the subsequent
    in-process build was unbounded. If it stalled, a 65-minute GitHub runner
    could monopolize the single research queue without publishing diagnostics.
    """
    code = (
        "import json; from engine.pipeline import run; "
        "print('SUPERVISOR_METRICS_JSON=' + json.dumps(run()), flush=True)"
    )
    command = [sys.executable, "-c", code]
    process = subprocess.Popen(
        command, cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        start_new_session=os.name != "nt",
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )
    try:
        output, _ = process.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired as exc:
        _terminate(process)
        raise TimeoutError(
            f"Canonical rebuild exceeded {timeout_s}s; workflow should retry "
            "from the last valid snapshot, without pretending publication succeeded."
        ) from exc
    if process.returncode:
        raise RuntimeError(
            f"Canonical rebuild failed ({process.returncode}): {output[-1800:]}"
        )
    for line in reversed(output.splitlines()):
        if line.startswith("SUPERVISOR_METRICS_JSON="):
            metrics = json.loads(line.partition("=")[2])
            if isinstance(metrics, dict) and isinstance(metrics.get("after"), dict):
                return metrics
    raise RuntimeError("Canonical rebuild returned no machine-readable metrics")


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
            previous_quality = read_json("data/current/quality_report.json", {})
            previous_gap_count = (previous_quality.get("checks") or {}).get("gaps")
            result = _run_research(arguments.profile, research_budget)
            if (result.get("status") == "ok"
                    and int(previous_gap_count or 0) > 0
                    and int(result.get("fetch_attempts") or 0) == 0
                    and int(result.get("search_queries_attempted") or 0) == 0
                    and int(result.get("entities_added") or 0) == 0):
                result["status"] = "no-research-work"
                result["error"] = "Unresolved gaps remain, but no URLs or searches were attempted."
            if result.get("status") != "ok":
                # A successful rebuild must never hide failed or idle research.
                exit_code = 1
            status["stages"].append({
                "research": result.get("status"),
                "fetch_attempts": result.get("fetch_attempts", 0),
                "fetch_successes": result.get("fetch_successes", 0) - result.get("cache_hits", 0),
                "cache_hits": result.get("cache_hits", 0),
                "documents_processed": result.get("fetch_successes", 0),
                "search_queries_attempted": result.get("search_queries_attempted", 0),
                "search_queries_succeeded": result.get("search_queries_succeeded", 0),
                "search_urls_discovered": result.get("search_urls_discovered", 0),
                "candidate_values_seen": result.get("candidate_values_seen", 0),
                "candidate_values_promoted": result.get("candidate_values_promoted", 0),
                "candidate_values_rejected": result.get("candidate_values_rejected", 0),
                "candidate_fields_rejected": result.get("candidate_fields_rejected", 0),
                "structured_growth_paused_for_debt": result.get("structured_growth_paused_for_debt", False),
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

            build_timeout_s = max(240, min(480, reserve * 2))
            metrics = _run_bounded_build(build_timeout_s)
            after = metrics["after"]
            before = metrics["before"]
            quality = read_json("data/current/quality_report.json")
            status["stages"].append({
                "build": "ok",
                "build_timeout_s": build_timeout_s,
                "gaps": after["gaps_total"],
                "debt_breakdown": dict((metrics.get("debt_breakdown") or {})),
                "gaps_closed_vs_release_baseline": before["gaps_total"] - after["gaps_total"],
                "gaps_previous_run": previous_gap_count,
                "gaps_delta_vs_previous_run": (
                    after["gaps_total"] - previous_gap_count
                    if isinstance(previous_gap_count, int) else None
                ),
                "gaps_closed_vs_previous_run": (
                    previous_gap_count - after["gaps_total"]
                    if isinstance(previous_gap_count, int) else None
                ),
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
