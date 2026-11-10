#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_json(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if version != "4.3.0":
        errors.append(f"VERSION={version}, expected 4.3.0")

    policy = read_json("config/current/research_policy.json")
    limits = policy.get("structured_growth_limits") or {}
    expected = {"daily": 24, "deep": 100, "exhaustive": 220}
    if limits != expected:
        errors.append(f"structured growth limits {limits!r} != {expected!r}")

    # Test actual source-selection behaviour, not outdated identifier names.
    # Research yield must reward accepted evidence, not HTTP transport success.
    from engine.research.planner import _learning_yield
    def research_score(accepted: int, relevant: int, transport: int = 0) -> float:
        return _learning_yield({
            "families": {"integrators:official": {
                "attempts": 30, "accepted_evidence": accepted,
                "pages_relevant": relevant, "successes": transport,
            }}
        }, "integrators", "official")
    if not research_score(12, 14) > research_score(0, 0):
        errors.append("planner must prioritize accepted evidence over empty fetches")
    if research_score(0, 0, transport=30) != research_score(0, 0):
        errors.append("planner incorrectly rewards transport success without evidence")

    web = (ROOT / "engine/research/web_intelligence.py").read_text(encoding="utf-8")
    for marker in ("structured_entity_budget", "structured_entities_added", "accepted_evidence_per_fetch_attempt", "growth_pressure_ratio"):
        if marker not in web:
            errors.append(f"web research missing controlled-growth marker: {marker}")

    current_evidence_source = (ROOT / "engine/westcon_current_evidence.py").read_text(encoding="utf-8")
    if "v4.3.0 · current Westcon capability atomicity guard" not in current_evidence_source:
        errors.append("current-Westcon capability atomicity guard is missing")

    preservation_source = (ROOT / "engine/preservation.py").read_text(encoding="utf-8")
    for marker in (
        "def _relationship_is_hard_protected",
        "relations_skipped_provisional",
        "provisional_relations = set()",
    ):
        if marker not in preservation_source:
            errors.append(f"preservation missing provisional-relation marker: {marker}")

    preservation = read_json("data/current/knowledge_preservation_v410.json")
    if preservation.get("status") != "PASS":
        errors.append("knowledge preservation gate did not pass")
    if (preservation.get("missing") or {}).get("relations"):
        errors.append("hard-protected relationship loss remains after v4.3 rebuild")

    gaps = read_json("data/current/research_gaps.json")
    priority = gaps.get("business_priority") or {}
    if priority.get("controlled_growth_policy") != "bounded-structured-growth-v1":
        errors.append("business-priority report lacks bounded controlled-growth policy")

    workflow = (ROOT / ".github/workflows/research-run.yml").read_text(encoding="utf-8")
    if workflow.count("python -m scripts.audit_v430") != 2:
        errors.append("reusable research workflow must run audit_v430 before and after research")

    print("v4.3.0 research-ROI + controlled-growth audit:", "PASS" if not errors else "FAIL")
    print(" - structured growth budgets:", limits)
    print(" - gaps total:", len(gaps.get("gaps") or []))
    print(" - P0/P1:", priority.get("actionable_high_value_gaps"))
    print(" - business-weighted coverage %:", priority.get("business_weighted_coverage_pct"))
    print(" - low-context public gaps:", priority.get("low_context_public_gaps"))
    print(" - low-context public P0/P1:", priority.get("low_context_public_p0_p1"))
    print(" - context-rich public gaps:", priority.get("context_rich_public_gaps"))
    print(" - public-validation gaps:", gaps.get("public_validation_gaps"))
    print(" - hard relations before/after:",
          (preservation.get("before") or {}).get("relations"), "->",
          (preservation.get("after") or {}).get("relations"))
    print(" - provisional relation signals before/after:",
          (preservation.get("before") or {}).get("provisional_relations"), "->",
          (preservation.get("after") or {}).get("provisional_relations"))
    print(" - provisional relations skipped during reconciliation:",
          ((preservation.get("reconciliation") or {}).get("relations") or {}).get("relations_skipped_provisional"))
    for error in errors:
        print(" - ERROR:", error)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
