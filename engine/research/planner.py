from __future__ import annotations

from collections import defaultdict
from typing import Any

SECTION_WEIGHT = {
    "integrators": 1.55,
    "distributors": 1.45,
    "clients_private": 1.30,
    "manufacturers": 1.25,
    "clients_public": 1.15,
    "trends": 1.05,
    "architectures": 1.00,
}

FIELD_WEIGHT = {
    "vendor_relations": 1.45,
    "westcon_overlap": 1.40,
    "competitor_vendor_overlap": 1.35,
    "services": 1.30,
    "capabilities": 1.30,
    "specializations": 1.25,
    "public_cases": 1.22,
    "verticals": 1.18,
    "technology_signals": 1.18,
    "hiring_signals": 1.12,
    "job_profiles": 1.10,
    "job_vendors": 1.08,
    "revenue": 1.06,
}

FAMILY_BY_FIELD = {
    "vendor_relations": "partners",
    "westcon_overlap": "partners",
    "competitor_vendor_overlap": "partners",
    "specializations": "partners",
    "services": "services",
    "capabilities": "services",
    "verticals": "cases",
    "public_cases": "cases",
    "job_profiles": "careers",
    "job_vendors": "careers",
    "hiring_signals": "careers",
    "technology_signals": "technology",
    "revenue": "financial",
    "estimated_amount": "procurement",
    "renewal_window": "signals",
    "analyst_signals": "analyst",
    "recent_signals": "news",
}


def _learning_yield(learning: dict[str, Any], section: str, family: str) -> float:
    stats = (learning.get("families") or {}).get(f"{section}:{family}") or {}
    attempts = int(stats.get("pages_relevant") or 0)
    accepted = int(stats.get("accepted_evidence") or 0)
    if attempts <= 0:
        return 0.55  # exploration prior
    return min(1.0, 0.25 + accepted / max(1, attempts))


def plan(gaps: dict[str, Any], learning: dict[str, Any], profile: str, max_tasks: int | None = None) -> list[dict[str, Any]]:
    limits = {"daily": 90, "deep": 420, "exhaustive": 1200}
    limit = max_tasks or limits.get(profile, 90)
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for gap in gaps.get("gaps") or []:
        section = str(gap.get("section") or "")
        entity = str(gap.get("entity") or "")
        field = str(gap.get("field") or "")
        if not section or not entity or not field:
            continue
        family = FAMILY_BY_FIELD.get(field, "official")
        key = (section, entity)
        item = grouped.setdefault(key, {"section": section, "entity": entity, "entity_id": gap.get("entity_id"), "fields": [], "families": set(), "priority": 0.0})
        if field not in item["fields"]:
            item["fields"].append(field)
        item["families"].add(family)
        score = SECTION_WEIGHT.get(section, 1.0) * FIELD_WEIGHT.get(field, 1.0) * (1.15 if int(gap.get("priority") or 2) == 1 else 1.0)
        score *= _learning_yield(learning, section, family)
        item["priority"] = max(item["priority"], score)
    out = []
    for item in grouped.values():
        item["families"] = sorted(item["families"])
        item["priority"] = round(item["priority"], 4)
        out.append(item)
    out.sort(key=lambda x: (-x["priority"], -len(x["fields"]), x["section"], x["entity"].casefold()))
    return out[:limit]
