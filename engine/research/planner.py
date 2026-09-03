"""Adaptive prioritisation of open intelligence gaps."""

from __future__ import annotations

from typing import Any

from ..settings import RESEARCH_PROFILES


SECTION_WEIGHT = {
    "clients_public": 1.70,
    "clients_private": 1.65,
    "integrators": 1.50,
    "distributors": 1.40,
    "manufacturers": 1.30,
    "trends": 1.05,
    "architectures": 1.00,
}

WEB_EXCLUDED_GAP_KINDS = {"derivation-support"}

FIELD_WEIGHT = {
    "vendor_relations": 1.45,
    "westcon_overlap": 1.40,
    "competitor_vendor_overlap": 1.35,
    "services": 1.30,
    "capabilities": 1.30,
    "specializations": 1.25,
    "public_cases": 1.22,
    "verticals": 1.18,
    "westcon_fit": 1.75,
    "westcon_area": 1.70,
    "technology_signals": 1.58,
    "hiring_signals": 1.34,
    "job_profiles": 1.10,
    "job_vendors": 1.08,
    "revenue": 1.06,
    "market_share": 1.18,
    "market_position": 1.16,
    "products_platforms": 1.20,
    "partner_program": 1.15,
    "partner_levels": 1.18,
    "channel_model": 1.12,
    "cloud_marketplace": 1.13,
    "subscription_recurrence": 1.10,
    "employee_count": 1.04,
    "known_customers": 1.18,
    "public_contracts": 1.32,
    "alliances": 1.15,
    "acquisitions": 1.12,
    "growth_areas": 1.14,
    "identified_vendors": 1.24,
    "identified_integrators": 1.26,
    "strategic_programs": 1.20,
    "investment_signals": 1.18,
    "evidenced_needs": 1.28,
}

FAMILY_BY_FIELD = {
    "vendor_relations": "partners",
    "westcon_overlap": "partners",
    "competitor_vendor_overlap": "partners",
    "specializations": "partners",
    "services": "services",
    "differential_capabilities": "services",
    "capabilities": "services",
    "verticals": "cases",
    "public_cases": "cases",
    "job_profiles": "careers",
    "job_vendors": "careers",
    "hiring_signals": "careers",
    "technology_signals": "technology",
    "westcon_area": "technology",
    "westcon_fit": "technology",
    "revenue": "financial",
    "employee_count": "financial",
    "organization_size": "financial",
    "market_share": "analyst",
    "market_position": "analyst",
    "products_platforms": "technology",
    "subcategories": "technology",
    "use_cases": "cases",
    "partner_program": "partners",
    "partner_levels": "partners",
    "channel_model": "partners",
    "certifications": "certifications",
    "cloud_marketplace": "marketplace",
    "subscription_recurrence": "financial",
    "managed_services": "services",
    "msp_mssp": "services",
    "technology_domains": "technology",
    "known_customers": "cases",
    "public_contracts": "procurement",
    "alliances": "partners",
    "acquisitions": "news",
    "growth_areas": "news",
    "geographic_presence": "official",
    "training": "training",
    "financing": "financial",
    "logistics": "services",
    "marketplace": "marketplace",
    "lifecycle_services": "services",
    "demand_generation": "marketing",
    "presales_capability": "services",
    "technical_capability": "services",
    "local_presence": "official",
    "identified_vendors": "technology",
    "identified_integrators": "cases",
    "known_architectures": "technology",
    "strategic_programs": "news",
    "technology_partners": "partners",
    "investment_signals": "financial",
    "evidenced_needs": "technology",
    "contracts": "procurement",
    "public_projects": "procurement",
    "estimated_amount": "procurement",
    "renewal_window": "signals",
    "analyst_signals": "analyst",
    "recent_signals": "news",
    "trend_market_metrics": "analyst",
    "adjacent_market_metrics": "analyst",
    "market_players": "analyst",
    "iberia_context": "news",
    "analyst_basis": "analyst",
    "layers": "technology",
    "vendors": "technology",
    "limits": "analyst",
}


def _learning_yield(learning: dict[str, Any], section: str, family: str) -> float:
    stats = (learning.get("families") or {}).get(f"{section}:{family}") or {}
    relevant = int(stats.get("pages_relevant") or 0)
    accepted = int(stats.get("accepted_evidence") or 0)
    if relevant <= 0:
        return 0.62
    return min(1.15, 0.30 + accepted / max(1, relevant))


def plan(
    gaps: dict[str, Any],
    learning: dict[str, Any],
    profile: str,
    *,
    state: Any = None,
    max_tasks: int | None = None,
    include_gap_kinds: set[str] | None = None,
) -> list[dict[str, Any]]:
    profile_config = RESEARCH_PROFILES[profile]
    limit = max_tasks or profile_config.entity_limit
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    research_rows = list(gaps.get("gaps") or []) + list(gaps.get("relationship_revalidation_debt") or [])
    for gap in research_rows:
        section = str(gap.get("section") or "")
        entity = str(gap.get("entity") or "")
        field = str(gap.get("field") or "")
        gap_id = str(gap.get("id") or "")
        if not section or not entity or not field or not gap_id:
            continue
        kind = str(gap.get("gap_kind") or "standard")
        if kind in WEB_EXCLUDED_GAP_KINDS:
            continue
        if include_gap_kinds is not None and kind not in include_gap_kinds:
            continue
        if state is not None and not state.gap_due(gap_id, profile=profile):
            continue
        family = FAMILY_BY_FIELD.get(field, "official")
        key = (section, entity)
        item = grouped.setdefault(key, {
            "section": section,
            "entity": entity,
            "entity_id": gap.get("entity_id"),
            "fields": [],
            "families": set(),
            "gap_ids": [],
            "gap_kinds": set(),
            "target_values": {},
            "revalidation_seeds": [],
            "priority": 0.0,
        })
        if field not in item["fields"]:
            item["fields"].append(field)
        if gap_id not in item["gap_ids"]:
            item["gap_ids"].append(gap_id)
        item["families"].add(family)
        item["gap_kinds"].add(kind)
        wanted = item["target_values"].setdefault(field, [])
        for value in gap.get("target_values") or []:
            if value not in wanted:
                wanted.append(value)
        for seed in gap.get("revalidation_seeds") or []:
            if isinstance(seed, dict) and seed.get("url") and seed not in item["revalidation_seeds"]:
                item["revalidation_seeds"].append(seed)
        score = SECTION_WEIGHT.get(section, 1.0) * FIELD_WEIGHT.get(field, 1.0)
        if int(gap.get("priority") or 2) == 1:
            score *= 1.18
        if kind in {"historical-revalidation", "historical-relationship-revalidation"}:
            score *= 1.55
        if gap.get("historical_lineage_present") and kind in {"evidence-support", "public-validation"}:
            # HF7: a concrete internal/historical clue is high-value research debt because
            # the target value is already known; public research only needs to validate it.
            score *= 1.75
        score *= _learning_yield(learning, section, family)
        if state is not None:
            misses = int(state.gap(gap_id).get("consecutive_no_yield") or 0)
            score *= max(0.45, 1.0 - misses * 0.09)
        item["priority"] = max(item["priority"], score)
    output = []
    for item in grouped.values():
        item["families"] = sorted(item["families"])
        item["gap_kinds"] = sorted(item["gap_kinds"])
        item["priority"] = round(item["priority"], 4)
        output.append(item)
    output.sort(key=lambda value: (-value["priority"], -len(value["fields"]), value["section"], value["entity"].casefold()))
    return output[:limit]
