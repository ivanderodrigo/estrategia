#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.pipeline import run as rebuild
from engine.research.planner import plan
from engine.research.web_intelligence import run as research_run


def load(rel: str, default=None):
    path = ROOT / rel
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def count_kind(gaps, kind: str) -> int:
    return sum(
        1 for row in gaps.get("gaps") or []
        if row.get("gap_kind") == kind
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Piloto controlado SOLO sobre evidence-support. "
            "No incluye standard, historical-revalidation ni derivation-support."
        )
    )
    parser.add_argument("--max-runtime", type=int, default=180)
    parser.add_argument("--max-tasks", type=int, default=25)
    parser.add_argument(
        "--profile",
        choices=["daily", "deep", "exhaustive"],
        default="daily",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo muestra el plan evidence-support; no hace peticiones web.",
    )
    args = parser.parse_args()

    gaps = load("data/current/research_gaps.json", {})
    learning = load("data/current/research_learning.json", {})
    planned = plan(
        gaps,
        learning,
        args.profile,
        max_tasks=args.max_tasks,
        include_gap_kinds={"evidence-support"},
    )
    planned_kinds = sorted({
        kind
        for task in planned
        for kind in (task.get("gap_kinds") or [])
    })
    preflight = {
        "pilot_mode": "evidence-support-only",
        "planned_tasks": len(planned),
        "planned_gap_kinds": planned_kinds,
        "all_tasks_evidence_only": bool(planned) and planned_kinds == ["evidence-support"],
        "entities": [task.get("entity") for task in planned],
    }
    print("PREFLIGHT")
    print(json.dumps(preflight, ensure_ascii=False, indent=2))

    if planned and planned_kinds != ["evidence-support"]:
        raise SystemExit("ERROR: el piloto contiene gap kinds distintos de evidence-support")
    if args.dry_run:
        return 0

    before_external = count_kind(gaps, "evidence-support")
    before_derived = count_kind(gaps, "derivation-support")

    result = research_run(
        args.profile,
        max_runtime=args.max_runtime,
        max_tasks=args.max_tasks,
        include_gap_kinds={"evidence-support"},
    )
    metrics = rebuild()

    after = load("data/current/research_gaps.json", {})
    after_external = count_kind(after, "evidence-support")
    after_derived = count_kind(after, "derivation-support")

    summary = {
        "pilot_mode": "evidence-support-only",
        "profile": args.profile,
        "max_tasks": args.max_tasks,
        "max_runtime": args.max_runtime,
        "planned_entities": result.get("planned_entities"),
        "fetch_attempts": result.get("fetch_attempts"),
        "fetch_successes": result.get("fetch_successes"),
        "pages_relevant": result.get("pages_relevant"),
        "candidate_evidences": result.get("candidate_evidences"),
        "accepted_evidences": result.get("accepted_evidences"),
        "fields_enriched": result.get("fields_enriched"),
        "values_added": result.get("values_added"),
        "stop_reason": result.get("stop_reason"),
        "evidence_support_before": before_external,
        "evidence_support_after": after_external,
        "evidence_support_closed": before_external - after_external,
        "derivation_support_before": before_derived,
        "derivation_support_after": after_derived,
        "derivation_support_delta": after_derived - before_derived,
        "canonical_gaps_after": (metrics.get("after") or {}).get("gaps_total"),
    }
    print("RESULT")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
