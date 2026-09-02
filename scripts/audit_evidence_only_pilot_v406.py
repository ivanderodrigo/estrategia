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
    p = ROOT / rel
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8-sig"))


def main() -> int:
    gaps = load("data/current/research_gaps.json", {})
    learning = load("data/current/research_learning.json", {})
    tasks = plan(
        gaps,
        learning,
        "daily",
        max_tasks=25,
        include_gap_kinds={"evidence-support"},
    )
    kinds = sorted({
        k for t in tasks for k in (t.get("gap_kinds") or [])
    })
    result = {
        "planned_tasks": len(tasks),
        "planned_gap_kinds": kinds,
        "evidence_only": bool(tasks) and kinds == ["evidence-support"],
        "entities": [t.get("entity") for t in tasks],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["evidence_only"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
