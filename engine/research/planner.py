"""Business-value-aware adaptive prioritisation of open intelligence gaps.

v4.2 deliberately preserves the v4.0.6/v4.1 routing contract:
- derived-support debt never enters public web research;
- callers may isolate gap kinds with ``include_gap_kinds``;
- historical relationship revalidation debt remains routable;
- legacy ``target_values`` output remains available.

On top of that contract it adds business-value scores, source playbooks and
bounded-run fairness so one large section cannot monopolise research.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from ..gap_intelligence import FAMILY_BY_FIELD as GAP_FAMILY_BY_FIELD
from ..settings import RESEARCH_PROFILES

# Backwards-compatible export used by engine.research.sources.
FAMILY_BY_FIELD = dict(GAP_FAMILY_BY_FIELD)
FAMILY_BY_FIELD.update({
    "renewal_window": "signals",
    "limits": "analyst",
})

# Web research must never be used to manufacture facts that are derived from
# already-supported inputs. This is a hard routing invariant inherited from v4.0.6.
WEB_EXCLUDED_GAP_KINDS = {"derivation-support"}

PUBLIC_PROCUREMENT_FIELDS = {
    "notice_id", "request_or_need", "technology_signals", "identified_vendors",
    "identified_integrators", "known_architectures", "technology_domains",
    "estimated_amount", "milestone_date", "procurement_stage", "source_portal",
    "cpv_codes", "evidenced_needs", "opportunity_area",
}

SECTION_WEIGHT = {
    "integrators": 1.55,
    "distributors": 1.45,
    "clients_private": 1.30,
    "manufacturers": 1.25,
    "clients_public": 1.00,
    "trends": 1.05,
    "architectures": 0.95,
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
    "technology_signals": 1.25,
    "request_or_need": 1.28,
    "identified_vendors": 1.24,
    "identified_integrators": 1.20,
    "estimated_amount": 1.18,
    "hiring_signals": 1.12,
    "job_profiles": 1.10,
    "job_vendors": 1.14,
    "revenue": 1.06,
}

# Prevent a single large section (currently public clients) from consuming every
# bounded run. The second fill pass can exceed these shares only when other
# sections do not have enough due work.
SECTION_MAX_SHARE = {
    "integrators": 0.32,
    "distributors": 0.24,
    "manufacturers": 0.20,
    "clients_private": 0.18,
    "clients_public": 0.22,
    "trends": 0.14,
    "architectures": 0.08,
}


def _learning_yield(learning: dict[str, Any], section: str, family: str) -> float:
    stats = (learning.get("families") or {}).get(f"{section}:{family}") or {}
    relevant = int(stats.get("pages_relevant") or 0)
    accepted = int(stats.get("accepted_evidence") or 0)
    if relevant <= 0:
        return 0.62
    return min(1.15, 0.30 + accepted / max(1, relevant))


def _fallback_score(gap: dict[str, Any], section: str, field: str) -> float:
    score = SECTION_WEIGHT.get(section, 1.0) * FIELD_WEIGHT.get(field, 1.0)
    if int(gap.get("priority") or 2) == 1:
        score *= 1.18
    kind = str(gap.get("gap_kind") or "standard")
    if kind == "public-validation":
        score *= 1.16
    if kind in {"historical-revalidation", "historical-relationship-revalidation"}:
        score *= 1.55
    if gap.get("historical_lineage_present") and kind in {"evidence-support", "public-validation"}:
        score *= 1.75
    return score * 30.0


def _balanced_limit(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if len(items) <= limit:
        return items
    caps = {section: max(1, int(limit * share)) for section, share in SECTION_MAX_SHARE.items()}
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    counts: dict[str, int] = defaultdict(int)
    for item in items:
        section = str(item.get("section") or "")
        cap = caps.get(section, limit)
        if counts[section] < cap and len(selected) < limit:
            selected.append(item)
            counts[section] += 1
        else:
            skipped.append(item)
    if len(selected) < limit:
        selected.extend(skipped[: limit - len(selected)])
    return selected[:limit]


def _family_for(section: str, field: str, gap: dict[str, Any]) -> str:
    explicit = str(gap.get("source_family") or "").strip()
    if explicit:
        return explicit
    if section == "clients_public" and field in PUBLIC_PROCUREMENT_FIELDS:
        return "procurement"
    return FAMILY_BY_FIELD.get(field, "official")


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

    # Historical relationship debt is intentionally part of the web-research plan.
    # It may contain exact public URLs that need revalidation and was part of the
    # pre-v4.2 routing contract.
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
        if gap.get("research_mode") == "derive-from-supported-inputs":
            continue
        if include_gap_kinds is not None and kind not in include_gap_kinds:
            continue
        if state is not None and not state.gap_due(gap_id, profile=profile):
            continue

        family = _family_for(section, field, gap)
        entity_key = str(gap.get("entity_id") or entity).strip()
        key = (section, entity_key)
        item = grouped.setdefault(
            key,
            {
                "section": section,
                "entity": entity,
                "entity_id": gap.get("entity_id"),
                "task_entity_key": entity_key,
                "fields": [],
                "families": set(),
                "source_families": set(),
                "gap_ids": [],
                "gap_kinds": set(),
                "research_states": set(),
                "priority_tiers": set(),
                # Keep both names: target_values is the legacy web-engine contract;
                # target_values_by_field is the explicit v4.2 representation.
                "target_values": defaultdict(list),
                "target_values_by_field": defaultdict(list),
                "revalidation_seeds": [],
                "query_hints": [],
                "priority": 0.0,
            },
        )
        if field not in item["fields"]:
            item["fields"].append(field)
        if gap_id not in item["gap_ids"]:
            item["gap_ids"].append(gap_id)
        item["families"].add(family)

        strategy = gap.get("source_strategy") or {}
        for candidate in strategy.get("preferred_families") or []:
            item["source_families"].add(str(candidate))
        item["source_families"].add(family)
        item["gap_kinds"].add(kind)
        item["research_states"].add(str(gap.get("research_state") or "Por investigar"))
        item["priority_tiers"].add(str(gap.get("priority_tier") or "P2"))

        for value in gap.get("target_values") or []:
            for target_map in (item["target_values"], item["target_values_by_field"]):
                if value not in target_map[field]:
                    target_map[field].append(value)

        seen_seed_urls = {
            str(seed.get("url") or "")
            for seed in item["revalidation_seeds"]
            if isinstance(seed, dict)
        }
        for seed in gap.get("revalidation_seeds") or []:
            if isinstance(seed, dict) and seed.get("url") and str(seed.get("url")) not in seen_seed_urls:
                item["revalidation_seeds"].append(dict(seed))
                seen_seed_urls.add(str(seed.get("url")))

        for hint in strategy.get("query_hints") or []:
            if hint not in item["query_hints"]:
                item["query_hints"].append(str(hint))

        score = float(gap.get("priority_score") or _fallback_score(gap, section, field))
        score *= _learning_yield(learning, section, family)
        if kind == "public-validation":
            score *= 1.12
        if state is not None:
            misses = int(state.gap(gap_id).get("consecutive_no_yield") or 0)
            score *= max(0.42, 1.0 - misses * 0.08)
        item["priority"] = max(item["priority"], score)

    output: list[dict[str, Any]] = []
    for item in grouped.values():
        item["families"] = sorted(item["families"])
        item["source_families"] = sorted(item["source_families"])
        item["gap_kinds"] = sorted(item["gap_kinds"])
        item["research_states"] = sorted(item["research_states"])
        item["priority_tiers"] = sorted(item["priority_tiers"])
        item["target_values"] = dict(item["target_values"])
        item["target_values_by_field"] = dict(item["target_values_by_field"])
        item["query_hints"] = item["query_hints"][:12]
        item["priority"] = round(item["priority"], 4)
        output.append(item)

    output.sort(
        key=lambda value: (
            -value["priority"],
            -len(value["fields"]),
            value["section"],
            value["entity"].casefold(),
        )
    )
    return _balanced_limit(output, int(limit))
