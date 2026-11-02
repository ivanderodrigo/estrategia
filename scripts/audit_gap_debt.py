#!/usr/bin/env python3
"""Audit the existing research backlog without web calls or a full pipeline rebuild."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/current/research_gaps.json"
DEST = ROOT / "data/current/debt_diagnostic.json"


def analyze(report: dict) -> dict:
    gaps = report.get("gaps") or []
    kinds = Counter()
    by_section: dict[str, Counter] = {}
    by_field = Counter()
    evidence_targets = []
    tier_counts = Counter()
    for gap in gaps:
        if not isinstance(gap, dict):
            continue
        section = str(gap.get("section") or "unknown")
        category = (
            "derivation_support" if gap.get("gap_kind") == "derivation-support"
            else "claims_awaiting_evidence" if gap.get("target_values")
            else "empty_schema_fields" if gap.get("gap_kind") == "standard"
            else "other_open_debt"
        )
        kinds[category] += 1
        if category == "claims_awaiting_evidence":
            tier = str(gap.get("priority_tier") or "P3")
            tier_counts[tier] += 1
            evidence_targets.append({
                "gap_id": gap.get("id"),
                "section": section,
                "entity": gap.get("entity"),
                "field": gap.get("field"),
                "priority_tier": tier,
                "priority_score": float(gap.get("priority_score") or 0),
                "target_values": list(gap.get("target_values") or [])[:3],
                "research_mode": gap.get("research_mode"),
                "source_playbook": (gap.get("source_strategy") or {}).get("preferred_families") or [],
                "historical_leads": len(gap.get("revalidation_seeds") or []),
            })
        by_section.setdefault(section, Counter())[category] += 1
        by_field[f"{section}.{gap.get('field') or 'unknown'}"] += 1
    if sum(kinds.values()) != len(gaps):
        raise ValueError("Unclassified gaps: audit is not exhaustive")
    declared = report.get("total_gaps")
    if declared is not None and int(declared) != len(gaps):
        raise ValueError(f"Gap count mismatch: declared {declared}, actual {len(gaps)}")
    evidence_targets.sort(key=lambda row: (
        {"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(row["priority_tier"], 4),
        -row["priority_score"],
        -row["historical_leads"],
        str(row["section"]), str(row["entity"]),
    ))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_open_gaps": len(gaps),
        "debt_breakdown": dict(kinds),
        "evidence_priority_tiers": dict(tier_counts),
        "priority_evidence_queue": evidence_targets[:200],
        "actionable_by_section": {k: dict(v) for k, v in sorted(by_section.items())},
        "top_missing_fields": dict(by_field.most_common(50)),
        "definition": "Exhaustive gap audit; empty cells are not unsupported claims. No claims are accredited by this report.",
    }


def main() -> None:
    report = json.loads(SOURCE.read_text(encoding="utf-8"))
    diagnostic = analyze(report)
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(diagnostic, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in diagnostic.items() if k != "top_missing_fields"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
