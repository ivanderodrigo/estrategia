#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8-sig"))


def main() -> int:
    support = load("data/current/source_rationalization_v406.json")
    gaps = load("data/current/research_gaps.json")
    evidence = [g for g in gaps.get("gaps") or [] if g.get("gap_kind") == "evidence-support"]
    derived = [g for g in gaps.get("gaps") or [] if g.get("gap_kind") == "derivation-support"]

    expected_external = int(support.get("external_search_required_unique") or 0)
    expected_derived = int(support.get("derived_support_required_unique") or 0)

    result = {
        "support_pending_occurrences": support.get("support_pending_occurrences"),
        "support_pending_unique_claims": support.get("support_pending_unique_claims"),
        "duplicate_pending_occurrences": support.get("duplicate_pending_occurrences"),
        "external_search_required_unique": expected_external,
        "evidence_support_gaps": len(evidence),
        "external_orphans": expected_external - len(evidence),
        "derived_support_required_unique": expected_derived,
        "derivation_support_gaps": len(derived),
        "derived_orphans": expected_derived - len(derived),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["external_orphans"] == 0 and result["derived_orphans"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
