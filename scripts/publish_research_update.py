#!/usr/bin/env python3
"""Publish only validated canonical intelligence, never stale snapshots."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALLOWED = [
    "data/current/intelligence.json",
    "data/current/last_run.json",
    "data/current/relationship_graph.json",
    "data/current/research_gaps.json",
    "data/current/metrics_before_after.json",
    "data/current/coverage_report.json",
    "data/current/source_report.json",
    "data/current/research_learning.json",
    "data/current/research_ledger.json",
    "data/current/research_state.json",
    "data/current/discovery_queue.json",
    "data/current/run_history.json",
    "data/current/quality_report.json",
    "data/public/manifest.json",
    "data/public/last_run.json",
    "data/public/sections/manufacturers.json",
    "data/public/sections/distributors.json",
    "data/public/sections/integrators.json",
    "data/public/sections/clients_public.json",
    "data/public/sections/clients_private.json",
    "data/public/sections/trends.json",
    "data/public/sections/architectures.json",
]


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=check, text=True)


def output(command: list[str]) -> str:
    return subprocess.check_output(command, cwd=ROOT, text=True).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--message", default="chore: update current decision intelligence")
    parser.add_argument("--attempts", type=int, default=3)
    arguments = parser.parse_args()

    if os.environ.get("GITHUB_ACTIONS", "").casefold() == "true":
        run(["git", "config", "--local", "user.name", "github-actions[bot]"])
        run([
            "git",
            "config",
            "--local",
            "user.email",
            "41898282+github-actions[bot]@users.noreply.github.com",
        ])

    run(["git", "fetch", "origin", "main"])
    local_before = output(["git", "rev-parse", "HEAD"])
    remote_before = output(["git", "rev-parse", "origin/main"])
    if local_before != remote_before:
        print("Remote main changed during research; stale snapshot was not published safely.")
        return 0

    existing = [path for path in ALLOWED if (ROOT / path).exists()]
    run(["git", "add", "--", *existing])
    if run(["git", "diff", "--cached", "--quiet"], check=False).returncode == 0:
        print("No canonical intelligence changes to publish")
        return 0
    run(["git", "commit", "-m", arguments.message])

    for attempt in range(1, max(1, arguments.attempts) + 1):
        pushed = run(["git", "push", "origin", "HEAD:main"], check=False)
        if pushed.returncode == 0:
            return 0
        run(["git", "fetch", "origin", "main"], check=False)
        if output(["git", "rev-parse", "origin/main"]) != remote_before:
            print("Remote main advanced before push; generated snapshot remains unpublished.")
            return 0
        if attempt < arguments.attempts:
            time.sleep(min(8, 2 ** attempt))

    print("Unable to publish canonical intelligence after transient retries", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
