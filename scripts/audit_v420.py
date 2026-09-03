#!/usr/bin/env python3
"""Independent v4.2 storage + research-priority audit."""
from __future__ import annotations

from pathlib import Path

from engine.intelligence_store import audit_store
from engine.storage import read_json

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    errors: list[str] = []
    storage = audit_store(root=ROOT)
    if storage.get("status") != "PASS":
        errors.extend(storage.get("errors") or ["intelligence store audit failed"])

    gaps = read_json("data/current/research_gaps.json", {})
    rows = list(gaps.get("gaps") or [])
    priority = gaps.get("business_priority") or {}
    tiers = priority.get("tiers") or {}
    if sum(int(tiers.get(tier) or 0) for tier in ("P0", "P1", "P2", "P3")) != len(rows):
        errors.append("P0-P3 tier counters do not reconcile with total gap rows")
    if "business_weighted_coverage_pct" not in priority:
        errors.append("business-weighted coverage KPI missing")
    if rows and not all(gap.get("priority_tier") and gap.get("priority_score") is not None for gap in rows):
        errors.append("one or more open gaps lack v4.2 priority metadata")
    actionable = [gap for gap in rows if gap.get("research_mode") != "derive-from-supported-inputs"]
    if actionable and not all((gap.get("source_strategy") or {}).get("preferred_families") for gap in actionable):
        errors.append("one or more actionable gaps lack a source playbook")

    print("v4.2 scalable-data + research-intelligence audit:", "PASS" if not errors else "FAIL")
    print(" - intelligence stub bytes:", storage.get("stub_bytes"))
    print(" - intelligence shards:", storage.get("shards"))
    print(" - largest shard bytes:", storage.get("largest_shard_bytes"))
    print(" - logical intelligence bytes:", storage.get("logical_bytes"))
    print(" - business-weighted coverage %:", priority.get("business_weighted_coverage_pct"))
    print(" - priority tiers:", {tier: int(tiers.get(tier) or 0) for tier in ("P0", "P1", "P2", "P3")})
    print(" - high-value actionable gaps (P0+P1):", priority.get("actionable_high_value_gaps"))
    print(" - public-validation gaps:", gaps.get("public_validation_gaps"))
    print(" - unknown-research gaps:", gaps.get("unknown_research_gaps"))
    print(" - clients-public share of P0/P1 %:", priority.get("clients_public_share_of_p0_p1_pct"))
    source_families = priority.get("source_families") or {}
    print(" - top source families:", dict(list(source_families.items())[:8]))
    for error in errors:
        print(" - ERROR:", error)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
