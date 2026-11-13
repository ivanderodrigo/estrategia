#!/usr/bin/env python3
"""Measure exact historical revalidation leads for the CURRENT rebuilt gaps."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.research.historical_leads import (  # noqa: E402
    historical_revalidation_seeds,
    history_by_gap,
    history_by_identity,
)
from engine.storage import read_json  # noqa: E402

def main() -> None:
    gaps = (read_json("data/current/research_gaps.json", {}) or {}).get("gaps") or []
    index = history_by_gap()
    identity = history_by_identity()
    counts = Counter()
    examples: dict[str, list[dict]] = {}
    for gap in gaps:
        section = str(gap.get("section") or "")
        if section not in ("manufacturers", "distributors", "integrators", "clients_private", "trends", "architectures"):
            continue
        leads = historical_revalidation_seeds(gap, index)
        counts[f"gaps_{section}"] += 1
        if not leads:
            continue
        counts[f"matched_{section}"] += 1
        counts["total_matched"] += 1
        counts["total_revalidation_urls"] += len(leads)
        if len(examples.setdefault(section, [])) < 3:
            examples[section].append({
                "entity": gap.get("entity"), "field": gap.get("field"),
                "target_values": str(gap.get("target_values") or "")[:180],
                "source_urls": [lead["url"] for lead in leads[:2]],
            })
    print("CURRENT HISTORICAL REVALIDATION", json.dumps({
        "historical_index_entries": len(index),
        "exact_claim_index_entries": len(identity),
        "counts": dict(counts),
        "examples": examples,
        "policy": "URLs are independent revalidation leads, NOT accredited evidence.",
    }, ensure_ascii=False))
if __name__ == "__main__":
    main()
