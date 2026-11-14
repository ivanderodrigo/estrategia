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
    "data/current/intelligence_store",
    "data/current/knowledge_preservation_v410.json",
    "data/current/provenance_report.json",
    "data/current/source_rationalization.json",
    "data/current/last_run.json",
    "data/current/relationship_graph.json",
    "data/current/research_gaps.json",
    "data/current/metrics_before_after.json",
    "data/current/coverage_report.json",
    "data/current/debt_diagnostic.json",
    "data/current/source_report.json",
    "data/current/research_learning.json",
    "data/current/research_ledger.json",
    "data/current/ted_cpv_revalidation.json",
    "data/current/research_state.json",
    "data/current/discovery_queue.json",
    "data/current/run_history.json",
    "data/current/quality_report.json",
    "data/public/debt_overview.json",
    "data/public/audit_integrity.json",
    "data/public/manifest.json",
    "data/public/last_run.json",
    "data/public/procurement_lifecycle.json",
    "data/public/sections/manufacturers.json",
    "data/public/sections/distributors.json",
    "data/public/sections/integrators.json",
    "data/public/sections/clients_public.json",
    "data/public/sections/clients_private.json",
    "data/public/sections/trends.json",
    "data/public/sections/architectures.json",
    # Historical claim/source sidecars must advance atomically with each snapshot.
    "data/public/historical/current/summary.json",
    "data/public/historical/current/manufacturers.json",
    "data/public/historical/current/distributors.json",
    "data/public/historical/current/integrators.json",
    "data/public/historical/current/clients_public.json",
    "data/public/historical/current/clients_private.json",
    "data/public/historical/current/trends.json",
    "data/public/historical/current/architectures.json",
    "data/current/historical_source_checks.json",
    "data/public/historical/current/source_checks.json",
    # Persist the exact claim/source proof behind green confidence badges.
    # Without the canonical semantic registry, the next rebuild loses proof.
    "config/current/historical_semantic_verified.json",
    "data/public/historical/current/semantic_claim_audit.json",
    "config/current/historical_structured_verified.json",
    "data/public/historical/current/structured_verification.json",
    "data/public/historical/current/quarantined_links.json",
    "data/public/historical/current/claim_review.json",
]


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=check, text=True)


def output(command: list[str]) -> str:
    return subprocess.check_output(command, cwd=ROOT, text=True).strip()


# Only display-only changes may be rebased without recomputing research.
# Engine, config, scripts, tests, workflows and any published data change
# invalidates a long-running research snapshot and must trigger a fresh run.
PRESENTATION_PATHS=("assets/app/","assets/favicon.svg","index.html",
                    "404.html","memoria-historica.html")
UNRELATED_DIAGNOSTICS=("data/current/daily_workflow_health.json",
                       "data/current/gap_debt_audit.json",
                       # This independently sampled URL-health telemetry is
                       # not source accreditation and does not affect the
                       # canonical intelligence model or any claim binding.
                       "data/public/source_verification_status.json")


def safe_remote_only(paths: list[str]) -> bool:
    def allowed(path: str) -> bool:
        return path in UNRELATED_DIAGNOSTICS or any(
            path == prefix or path.startswith(prefix)
            for prefix in PRESENTATION_PATHS
        )
    return bool(paths) and all(allowed(path) for path in paths)


def accept_presentation_only_updates(local_sha: str, remote_sha: str) -> bool:
    changed=output(["git","diff","--name-only",local_sha,remote_sha]).splitlines()
    if not safe_remote_only(changed):
        print("Unsafe concurrent main changes; refusing stale research publication:",
              ", ".join(changed[:15]),file=sys.stderr)
        return False
    # --mixed adopts the latest remote index while preserving locally
    # validated research outputs in the worktree. Only ALLOWED data paths
    # are staged below; old UI bytes are never committed.
    run(["git","reset","--mixed",remote_sha])
    print("Adopted presentation-only main changes without overwriting UI.")
    return True


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
        if not accept_presentation_only_updates(local_before,remote_before):
            return 1

    existing = [path for path in ALLOWED if (ROOT / path).exists()]
    run(["git", "add", "-A", "--", *existing])
    if run(["git", "diff", "--cached", "--quiet"], check=False).returncode == 0:
        print("No canonical intelligence changes to publish")
        return 0
    run(["git", "commit", "-m", arguments.message])

    for attempt in range(1, max(1, arguments.attempts) + 1):
        pushed = run(["git", "push", "origin", "HEAD:main"], check=False)
        if pushed.returncode == 0:
            return 0
        run(["git", "fetch", "origin", "main"], check=False)
        advanced=output(["git", "rev-parse", "origin/main"])
        if advanced != remote_before:
            if not accept_presentation_only_updates(remote_before,advanced):
                print("Remote main advanced before push; generated snapshot remains unpublished.",file=sys.stderr)
                return 1
            remote_before=advanced
            run(["git","add","-A","--",*existing])
            if run(["git","diff","--cached","--quiet"],check=False).returncode:
                run(["git","commit","-m",arguments.message])
            else:
                return 0
        if attempt < arguments.attempts:
            time.sleep(min(8, 2 ** attempt))

    print("Unable to publish canonical intelligence after transient retries", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
