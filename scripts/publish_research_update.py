#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys

p = argparse.ArgumentParser()
p.add_argument("--message", default="chore: update current decision intelligence")
p.add_argument("--attempts", type=int, default=3)
a = p.parse_args()

allowed = [
    "data/current/intelligence.json",
    "data/current/last_run.json",
    "data/current/relationship_graph.json",
    "data/current/research_gaps.json",
    "data/current/metrics_before_after.json",
    "data/current/coverage_report.json",
    "data/current/source_report.json",
    "data/current/research_learning.json",
    "data/current/research_ledger.json",
]

# GitHub-hosted runners do not have an author identity by default.
# Configure it locally for CI only; never overwrite a developer's local identity.
if os.environ.get("GITHUB_ACTIONS", "").lower() == "true":
    subprocess.run(
        ["git", "config", "--local", "user.name", "github-actions[bot]"],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "config",
            "--local",
            "user.email",
            "41898282+github-actions[bot]@users.noreply.github.com",
        ],
        check=True,
    )

subprocess.run(["git", "add", "--", *allowed], check=True)

if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode == 0:
    print("No canonical intelligence changes to publish")
    sys.exit(0)

subprocess.run(["git", "commit", "-m", a.message], check=True)

for _ in range(a.attempts):
    r = subprocess.run(["git", "push", "origin", "main"])
    if r.returncode == 0:
        sys.exit(0)

    subprocess.run(
        ["git", "pull", "--rebase", "origin", "main"],
        check=False,
    )

sys.exit(1)
