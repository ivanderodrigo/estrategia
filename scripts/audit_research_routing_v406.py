#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.research.planner import plan


def load(rel: str, default):
    path = ROOT / rel
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    gaps = load("data/current/research_gaps.json", {})
    learning = load("data/current/research_learning.json", {})
    all_gaps = gaps.get("gaps") or []

    derivation_gaps = [
        g for g in all_gaps if g.get("gap_kind") == "derivation-support"
    ]
    evidence_gaps = [
        g for g in all_gaps if g.get("gap_kind") == "evidence-support"
    ]

    tasks = plan(gaps, learning, "exhaustive", max_tasks=10000)
    derivation_tasks = [
        t for t in tasks
        if "derivation-support" in set(t.get("gap_kinds") or [])
    ]
    evidence_tasks = [
        t for t in tasks
        if "evidence-support" in set(t.get("gap_kinds") or [])
    ]

    result = {
        "evidence_support_gaps": len(evidence_gaps),
        "derivation_support_gaps": len(derivation_gaps),
        "planned_entity_tasks_total": len(tasks),
        "planned_entity_tasks_with_evidence_support": len(evidence_tasks),
        "planned_entity_tasks_with_derivation_support": len(derivation_tasks),
        "derivation_web_routing_blocked": len(derivation_tasks) == 0,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["derivation_web_routing_blocked"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
