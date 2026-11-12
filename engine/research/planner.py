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
from urllib.parse import urlsplit
from typing import Any

from ..gap_intelligence import FAMILY_BY_FIELD as GAP_FAMILY_BY_FIELD
from ..settings import RESEARCH_POLICY, RESEARCH_PROFILES

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
    "distributors": 1.90,
    "clients_private": 1.30,
    "manufacturers": 1.25,
    "clients_public": 1.00,
    "trends": 1.05,
    "architectures": 0.95,
}
FIELD_WEIGHT = {
    "competitors": 1.55,
    "vendor_relations": 1.72,
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
    "recent_signals": 1.22,
    "job_profiles": 1.10,
    "job_vendors": 1.14,
    "revenue": 1.20,
}

# Prevent a single large section (currently public clients) from consuming every
# bounded run. The second fill pass can exceed these shares only when other
# sections do not have enough due work.
SECTION_MAX_SHARE = {
    "integrators": 0.32,
    "distributors": 0.30,
    "manufacturers": 0.20,
    "clients_private": 0.18,
    "clients_public": 0.22,
    "trends": 0.14,
    "architectures": 0.08,
}


def _learning_yield(learning: dict[str, Any], section: str, family: str) -> float:
    """Use evidence per attempt, with a prior, not HTTP success alone.

    The prior prevents an unfamiliar source family from being starved. A family
    with thousands of failed requests loses priority, while an effective family
    earns more budget. Raw accepted counts may exceed attempts when one page
    yields several claims, so this is a bounded yield rather than a probability.
    """
    stats = (learning.get("families") or {}).get(f"{section}:{family}") or {}
    attempts = max(0, int(stats.get("attempts") or 0))
    accepted = max(0, int(stats.get("accepted_evidence") or 0))
    relevant = max(0, int(stats.get("pages_relevant") or 0))
    if attempts == 0:
        return 0.74
    # Empirical-Bayes smoothing: ten synthetic attempts at modest yield,
    # limiting the influence of tiny samples and permitting exploration.
    accepted_yield = (accepted + 1.5) / (attempts + 10)
    relevant_yield = (relevant + 2.0) / (attempts + 10)
    score = 0.30 + min(0.72, accepted_yield * 3.0) + min(0.16, relevant_yield * 0.4)
    return max(0.32, min(1.18, score))


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


def _task_key(item: dict[str, Any]) -> tuple[str, str]:
    return (
        str(item.get("section") or ""),
        str(item.get("task_entity_key") or item.get("entity_id") or item.get("entity") or ""),
    )


def _with_manufacturer_revenue_reserve(
    items: list[dict[str, Any]],
    limit: int,
    profile: str,
) -> list[dict[str, Any]]:
    """Reserve bounded capacity for manufacturer revenue without starving other BI domains."""
    if limit <= 0:
        return []
    reserve_defaults = {"daily": 8, "deep": 24, "exhaustive": 37}
    requested = min(limit, int(reserve_defaults.get(profile, 8)))
    revenue = [
        item for item in items
        if item.get("section") == "manufacturers" and "revenue" in (item.get("fields") or [])
    ]
    preferred = revenue[:requested]
    selected = list(preferred)
    seen = {_task_key(item) for item in selected}
    for item in _balanced_limit(items, limit):
        key = _task_key(item)
        if key in seen:
            continue
        selected.append(item)
        seen.add(key)
        if len(selected) >= limit:
            return selected[:limit]
    for item in items:
        key = _task_key(item)
        if key in seen:
            continue
        selected.append(item)
        seen.add(key)
        if len(selected) >= limit:
            break
    return selected[:limit]

# Presentation-derived research vocabulary, not evidence. Each query must lead to
# independently fetched, claim-specific, publicly verifiable documentation.
PRESENTATION_SEARCH_CONTEXT = {
    "capabilities": ("soluciones", "soluções", "solution", "technology"),
    "specializations": ("especialización", "especialização", "certification"),
    "vendor_relations": ("partner", "technology alliance", "alianza tecnológica", "parceiro certificado"),
    "partners": ("partner", "distribuidor autorizado", "parceiro"),
    "services": ("servicios gestionados", "serviços geridos", "professional services"),
    "public_cases": ("caso de éxito", "caso de sucesso", "customer story"),
    "technology_signals": ("project", "deployment", "tender"),
    "identified_vendors": ("awarded", "contract", "deployment"),
}

SYSTEMATIC_FIELD_TERMS = {
    "vendor_relations": ("partner", "alianza", "parceiro"),
    "westcon_overlap": ("partner", "portfolio", "fabricante"),
    "competitor_vendor_overlap": ("portfolio", "vendor", "fabricante"),
    "competitors": ("competing vendors alternatives", "competidores fabricantes", "concorrentes fornecedores"),
    "products_platforms": ("platform products datasheet", "plataformas ficha técnica", "plataformas tecnologia"),
    "use_cases": ("customer story deployment", "caso de uso solución", "caso de sucesso solução"),
    "recent_signals": ("news press release launch", "novedades anuncios", "notícias lançamento"),
    "services": ("managed services", "servicios", "serviços"),
    "capabilities": ("cybersecurity networking cloud", "ciberseguridad redes nube", "cibersegurança rede nuvem"),
    "specializations": ("certification", "especialización", "especialização"),
    "public_cases": ("customer story", "caso de éxito", "caso de sucesso"),
    "technology_signals": ("cybersecurity networking cloud", "ciberseguridad redes nube", "cibersegurança rede nuvem"),
    "identified_vendors": ("technology vendor", "fabricante tecnología", "fabricante tecnologia"),
    "request_or_need": ("licitación tecnología", "concurso tecnologia", "tender technology"),
    "hiring_signals": ("cybersecurity networking cloud jobs", "empleo tecnología", "emprego tecnologia"),
    "revenue": ("annual report revenue", "resultados ingresos", "relatório receita"),
}


def systematic_discovery_queries(
    section: str,
    entity: str,
    fields: list[str],
    *,
    profile: str,
) -> list[str]:
    """Build systematic source-lane searches that complement exact revalidation.

    These are discovery instructions only. A result still has to be fetched,
    semantically bound to the subject and exact value, and pass provenance gates.
    """
    policy = RESEARCH_POLICY.get("systematic_discovery") or {}
    if not policy.get("enabled", True):
        return []
    lanes = policy.get("lanes") or {}
    max_by_profile = policy.get("max_domain_queries_per_target") or {}
    limit = max(0, int(max_by_profile.get(profile) or 0))
    if limit <= 0:
        return []

    if section == "clients_public":
        lane_names = ("public_procurement", "cyber_security_public", "cybersecurity_media")
    elif section in {"manufacturers", "distributors", "integrators"}:
        lane_names = ("spain_channel_press", "portugal_channel_press", "cybersecurity_media", "cyber_security_public")
    elif section == "clients_private":
        lane_names = ("spain_channel_press", "portugal_channel_press", "technology_research", "cybersecurity_media")
    elif section in {"trends", "architectures"}:
        lane_names = ("technology_research", "cybersecurity_media", "cyber_security_public")
    else:
        lane_names = tuple(lanes)

    terms: list[str] = []
    for field in fields:
        for term in SYSTEMATIC_FIELD_TERMS.get(field, ()):
            if term not in terms:
                terms.append(term)
    if not terms:
        terms = ["cybersecurity networking cloud"]

    output: list[str] = []
    # Breadth-first across domains so the budget samples independent publishers
    # instead of spending every query on one site or one vocabulary variant.
    selected_domains: list[str] = []
    lane_domains = [
        [str(domain).strip() for domain in (lanes.get(lane_name) or []) if str(domain).strip()]
        for lane_name in lane_names
    ]
    # Round-robin lanes: a daily 3-query budget still samples different
    # geographies/source classes instead of three publishers from one lane.
    domain_depth = 0
    while any(domain_depth < len(bucket) for bucket in lane_domains):
        for bucket in lane_domains:
            if domain_depth < len(bucket):
                domain = bucket[domain_depth]
                if domain not in selected_domains:
                    selected_domains.append(domain)
        domain_depth += 1
    depth = 0
    while len(output) < limit and selected_domains:
        for index, domain in enumerate(selected_domains):
            term = terms[(depth + index) % len(terms)]
            query = f'"{entity}" {term} site:{domain}'
            if query not in output:
                output.append(query)
                if len(output) >= limit:
                    break
        depth += 1
        if depth >= max(1, len(terms)):
            break
    return output


def presentation_signal_queries(entity: str, targets: dict[str, list], limit: int = 8) -> list[str]:
    """Convert already preserved claim values into field-aware search leads.

    No presentation assertion or numeric marketing promise is promoted to a
    verified fact. Neither the presentation itself nor a search snippet is proof.
    """
    output: list[str] = []
    # Distribute searches across independent fields and all language contexts.
    # A field with many values must not consume the entire budget before
    # Portuguese/English alternatives or the next field are considered.
    buckets: list[list[str]] = []
    for field, values in targets.items():
        contexts = PRESENTATION_SEARCH_CONTEXT.get(field, ())
        for raw in values[:2]:
            value = str(raw).strip()
            if not 3 <= len(value) <= 100 or value.casefold() in {"unknown", "por investigar"}:
                continue
            buckets.append([f'"{entity}" "{value}" {context}' for context in contexts])
    depth = 0
    while len(output) < limit and any(depth < len(bucket) for bucket in buckets):
        for bucket in buckets:
            if depth < len(bucket) and bucket[depth] not in output:
                output.append(bucket[depth])
                if len(output) >= limit:
                    break
        depth += 1
    return output


def historical_exact_queries(entity: str, targets: dict[str, list], leads: list[dict], limit: int = 8) -> list[str]:
    """Build focused searches from exact historical clues, without treating clues as facts."""
    output: list[str] = []
    seen: set[str] = set()

    def push(query: str) -> None:
        key = query.casefold().strip()
        if query and key not in seen and len(output) < limit:
            seen.add(key)
            output.append(query)

    for field, values in targets.items():
        for raw in values[:3]:
            value = str(raw).strip()
            if not value or len(value) > 160 or value.casefold() in {"none", "unknown", "por investigar"}:
                continue
            push(f'"{entity}" "{value}"')
            push(f'"{entity}" "{value}" {str(field).replace("_", " ")}')
    for seed in leads[:5]:
        url = str(seed.get("url") or "")
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        if host and "." in host and not host.endswith((".local", ".internal")):
            # Search the original domain for the actual historical assertion,
            # not merely any page mentioning the entity.
            for values in targets.values():
                for raw in values[:1]:
                    value = str(raw).strip()
                    if 3 <= len(value) <= 120:
                        push(f'"{entity}" "{value}" site:{host}')
            push(f'"{entity}" site:{host}')
    return output


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
    from .historical_leads import historical_revalidation_seeds, history_by_gap
    historical_index = history_by_gap()

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
        for seed in list(gap.get("revalidation_seeds") or []) + historical_revalidation_seeds(gap, historical_index):
            if isinstance(seed, dict) and seed.get("url") and str(seed.get("url")) not in seen_seed_urls:
                item["revalidation_seeds"].append(dict(seed))
                seen_seed_urls.add(str(seed.get("url")))

        for hint in strategy.get("query_hints") or []:
            if hint not in item["query_hints"]:
                item["query_hints"].append(str(hint))

        score = float(gap.get("priority_score") or _fallback_score(gap, section, field))
        # A concrete unsupported claim is much more actionable than an empty
        # schema cell: recover evidence before endlessly exploring unknowns.
        # This only affects work ordering; no claim is marked verified.
        has_claim = bool(gap.get("target_values"))
        # Include recovered archived leads: they are attached to the grouped
        # task above, not necessarily present on the original gap record.
        has_lead = bool(gap.get("revalidation_seeds")) or bool(historical_index.get(gap_id))
        if has_claim and has_lead:
            score *= 2.15
        elif has_claim:
            score *= 1.75
        elif has_lead:
            score *= 1.35
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
        # Source recovery is not confined to the "historical" gap kind:
        # many unsupported items are classified as not-found / insufficient-support.
        # A remembered exact value is a search lead, never self-accrediting.
        exact = historical_exact_queries(
            item["entity"], item["target_values_by_field"], item["revalidation_seeds"]
        ) if item["target_values_by_field"] or item["revalidation_seeds"] else []
        contextual = presentation_signal_queries(item["entity"], item["target_values_by_field"])
        systematic = systematic_discovery_queries(
            item["section"], item["entity"], item["fields"], profile=profile
        )
        query_cap = {"daily": 48, "deep": 72, "exhaustive": 96}.get(profile, 48)
        item["query_hints"] = list(dict.fromkeys(
            exact + contextual + systematic + item["query_hints"]
        ))[:query_cap]
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
    if include_gap_kinds is None:
        return _with_manufacturer_revenue_reserve(output, int(limit), profile)
    return _balanced_limit(output, int(limit))
