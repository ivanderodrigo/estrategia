"""Business-value prioritisation and source playbooks for open intelligence gaps."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime
from typing import Any, Mapping

SECTION_VALUE = {
    "integrators": 1.55,
    "distributors": 1.50,
    "manufacturers": 1.40,
    "clients_private": 1.35,
    "trends": 1.25,
    "clients_public": 1.00,
    "architectures": 0.95,
}

FIELD_VALUE = {
    # Channel / competitive intelligence
    "vendor_relations": 1.90,
    "westcon_overlap": 1.85,
    "competitor_vendor_overlap": 1.75,
    "competitors": 1.70,
    "integrators": 1.65,
    "distributors": 1.65,
    "specializations": 1.60,
    "capabilities": 1.60,
    "differential_capabilities": 1.55,
    "services": 1.50,
    "managed_services": 1.45,
    "msp_mssp": 1.45,
    "market_position": 1.40,
    "market_share": 1.35,
    "revenue": 1.30,
    "public_cases": 1.30,
    "known_customers": 1.30,
    "verticals": 1.20,
    "job_vendors": 1.25,
    "job_profiles": 1.15,
    "hiring_signals": 1.15,
    # Client opportunity intelligence
    "request_or_need": 1.95,
    "technology_signals": 1.85,
    "identified_vendors": 1.75,
    "identified_integrators": 1.70,
    "known_architectures": 1.55,
    "estimated_amount": 1.75,
    "procurement_stage": 1.70,
    "milestone_date": 1.55,
    "strategic_programs": 1.35,
    "investment_signals": 1.30,
    "contracts": 1.35,
    "public_projects": 1.30,
    "notice_id": 1.50,
    # Trends / architectures
    "trend_market_metrics": 1.60,
    "adjacent_market_metrics": 1.45,
    "market_players": 1.45,
    "analyst_signals": 1.40,
    "recent_signals": 1.35,
    "iberia_context": 1.35,
    "analyst_basis": 1.25,
    "vendors": 1.30,
    "layers": 1.20,
    # Identity / lower-value completeness fields
    "scope": 0.90,
    "entity_type": 0.75,
    "organization_size": 0.70,
    "source_portal": 1.15,
    "cpv_codes": 1.05,
}

PLAYBOOKS = {
    "partners": {
        "families": ["partners", "cases", "careers", "official"],
        "source_types": ["vendor partner locator", "entity line card / alliances", "official case study", "careers"],
        "rationale": "Las relaciones de canal se acreditan mejor en directorios oficiales del fabricante y páginas de alianzas del partner.",
    },
    "procurement": {
        "families": ["procurement", "official", "news"],
        "source_types": ["TED", "PLACSP", "BASE.gov.pt", "portal oficial del comprador"],
        "rationale": "Importes, adjudicatarios, fechas y necesidades deben priorizar contratación pública estructurada y portales oficiales.",
    },
    "cases": {
        "families": ["cases", "official", "partners"],
        "source_types": ["official case study", "customer story", "success story"],
        "rationale": "Casos de éxito y clientes conocidos requieren atribución explícita de entidad, tecnología y relación en una fuente pública.",
    },
    "careers": {
        "families": ["careers", "technology", "official"],
        "source_types": ["career portal", "vacante oficial", "perfil técnico público"],
        "rationale": "Las ofertas de empleo son una señal directa de tecnologías, perfiles y áreas de inversión activas.",
    },
    "financial": {
        "families": ["financial", "official", "news"],
        "source_types": ["annual report", "investor relations", "registro / cuentas públicas", "nota oficial"],
        "rationale": "Facturación y escala requieren periodo, entidad y unidad claramente identificados.",
    },
    "services": {
        "families": ["services", "cases", "official"],
        "source_types": ["service catalogue", "solution page", "case study"],
        "rationale": "Capacidades y servicios deben provenir de catálogos o páginas de solución de la propia entidad.",
    },
    "analyst": {
        "families": ["analyst", "news", "official"],
        "source_types": ["analyst report", "market report", "official market material"],
        "rationale": "Métricas y posición de mercado requieren contexto de mercado, periodo, geografía y metodología.",
    },
    "technology": {
        "families": ["technology", "services", "cases", "official"],
        "source_types": ["product / technology page", "architecture page", "case study"],
        "rationale": "Tecnologías y plataformas se validan mejor en páginas técnicas y casos de uso explícitos.",
    },
    "news": {
        "families": ["news", "official", "cases"],
        "source_types": ["press release", "official news", "reliable trade press"],
        "rationale": "Movimientos recientes necesitan fuentes fechadas y atribuibles.",
    },
    "official": {
        "families": ["official", "services", "news"],
        "source_types": ["official website", "official documentation"],
        "rationale": "Priorizar siempre una fuente primaria explícita antes de recurrir a fuentes secundarias.",
    },
}

FAMILY_BY_FIELD = {
    "vendor_relations": "partners", "westcon_overlap": "partners", "competitor_vendor_overlap": "partners",
    "competitors": "partners", "integrators": "partners", "distributors": "partners", "specializations": "partners",
    "services": "services", "capabilities": "services", "differential_capabilities": "services",
    "managed_services": "services", "msp_mssp": "services",
    "public_cases": "cases", "known_customers": "cases", "verticals": "cases",
    "job_profiles": "careers", "job_vendors": "careers", "hiring_signals": "careers",
    "revenue": "financial", "market_share": "analyst", "market_position": "analyst",
    "estimated_amount": "procurement", "procurement_stage": "procurement", "milestone_date": "procurement",
    "notice_id": "procurement", "request_or_need": "procurement", "identified_integrators": "procurement",
    "technology_signals": "technology", "identified_vendors": "technology", "known_architectures": "technology",
    "strategic_programs": "technology", "investment_signals": "news", "public_projects": "news", "contracts": "news",
    "analyst_signals": "analyst", "trend_market_metrics": "analyst", "adjacent_market_metrics": "analyst",
    "market_players": "analyst", "analyst_basis": "analyst", "recent_signals": "news", "iberia_context": "news",
    "layers": "technology", "vendors": "technology",
}


PUBLIC_PROCUREMENT_FIELDS = {
    "notice_id", "request_or_need", "technology_signals", "identified_vendors",
    "identified_integrators", "known_architectures", "technology_domains",
    "estimated_amount", "milestone_date", "procurement_stage", "source_portal",
    "cpv_codes", "evidenced_needs", "opportunity_area",
}


def family_for(field: str, section: str = "") -> str:
    field = str(field or "")
    if str(section or "") == "clients_public" and field in PUBLIC_PROCUREMENT_FIELDS:
        return "procurement"
    return FAMILY_BY_FIELD.get(field, "official")


def business_weight(section: str, field: str, *, decision_required: bool = False) -> float:
    weight = SECTION_VALUE.get(section, 1.0) * FIELD_VALUE.get(field, 1.0)
    if decision_required:
        weight *= 1.18
    return weight


def _researchability(gap: Mapping[str, Any]) -> float:
    value = 0.78
    if gap.get("gap_kind") == "public-validation":
        value += 0.24
    if gap.get("target_values"):
        value += 0.10
    if gap.get("revalidation_seeds"):
        value += 0.14
    if gap.get("historical_lineage_present"):
        value += 0.08
    family = family_for(str(gap.get("field") or ""), str(gap.get("section") or ""))
    if family in {"partners", "procurement", "careers", "financial", "services", "technology"}:
        value += 0.06
    misses = int(gap.get("consecutive_no_yield") or 0)
    value *= max(0.42, 1.0 - misses * 0.075)
    return max(0.20, min(1.35, value))


def _tier(score: float) -> str:
    if score >= 78:
        return "P0"
    if score >= 58:
        return "P1"
    if score >= 38:
        return "P2"
    return "P3"


def _query_hints(gap: Mapping[str, Any], family: str) -> list[str]:
    entity = str(gap.get("entity") or "").strip()
    field = str(gap.get("field") or "").strip().replace("_", " ")
    targets = [str(value).strip() for value in (gap.get("target_values") or []) if str(value).strip()]
    hints: list[str] = []
    for target in targets[:3]:
        hints.extend([f'"{entity}" "{target}"', f'"{entity}" {field} "{target}"'])
    if family == "partners":
        hints.extend([f'"{entity}" partners vendors', f'"{entity}" alianzas fabricantes'])
    elif family == "procurement":
        hints.extend([f'"{entity}" contratación tecnología', f'"{entity}" concurso adjudicación'])
    elif family == "careers":
        hints.extend([f'"{entity}" careers {field}', f'"{entity}" empleo tecnología'])
    elif family == "financial":
        hints.extend([f'"{entity}" annual report revenue', f'"{entity}" facturación resultados'])
    elif family in {"services", "technology"}:
        hints.extend([f'"{entity}" {field}', f'"{entity}" solutions services'])
    elif family == "analyst":
        hints.extend([f'"{entity}" market share report', f'"{entity}" analyst report'])
    else:
        hints.append(f'"{entity}" {field}')
    output: list[str] = []
    seen = set()
    for hint in hints:
        key = hint.casefold()
        if hint and key not in seen:
            seen.add(key)
            output.append(hint)
    return output[:6]


def _field_value(row: Mapping[str, Any], field: str) -> Any:
    raw = ((row.get("fields") or {}).get(field) or {})
    return raw.get("value") if isinstance(raw, Mapping) else None


def _present(value: Any) -> bool:
    return value not in (None, "", [], {})


def _numeric_amount(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, Mapping):
        for key in ("amount", "value", "estimated", "total"):
            parsed = _numeric_amount(value.get(key))
            if parsed is not None:
                return parsed
        return None
    raw = str(value or "").strip().replace("€", "").replace("EUR", "").replace("eur", "")
    raw = raw.replace(" ", "")
    if not raw:
        return None
    # Iberian public-data feeds may use either 1.234.567,89 or 1234567.89.
    if "," in raw and "." in raw and raw.rfind(",") > raw.rfind("."):
        raw = raw.replace(".", "").replace(",", ".")
    elif raw.count(",") == 1 and raw.count(".") == 0:
        raw = raw.replace(",", ".")
    else:
        raw = raw.replace(",", "")
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = str(value or "").strip()
    if not raw:
        return None
    for candidate in (raw[:10], raw):
        try:
            return date.fromisoformat(candidate)
        except ValueError:
            pass
    return None


def _entity_row(public: Mapping[str, Any], gap: Mapping[str, Any]) -> Mapping[str, Any] | None:
    section = str(gap.get("section") or "")
    rows = [row for row in (public.get(section) or []) if isinstance(row, Mapping)]
    entity_id = str(gap.get("entity_id") or "").strip()
    if entity_id:
        for row in rows:
            if str(row.get("id") or "").strip() == entity_id:
                return row
    entity = str(gap.get("entity") or "").strip().casefold()
    matches = [row for row in rows if str(row.get("name") or "").strip().casefold() == entity]
    return matches[0] if len(matches) == 1 else None


def _public_opportunity_context(gap: Mapping[str, Any], public: Mapping[str, Any]) -> tuple[float, list[str]]:
    if str(gap.get("section") or "") != "clients_public":
        return 1.0, []
    row = _entity_row(public, gap)
    if not row:
        return 1.0, ["sin contexto de expediente inequívoco"]

    multiplier = 1.0
    reasons: list[str] = []
    if _present(_field_value(row, "notice_id")) or _present(_field_value(row, "source_portal")):
        multiplier += 0.06
        reasons.append("expediente/portal oficial identificado")
    if _present(_field_value(row, "request_or_need")):
        multiplier += 0.07
        reasons.append("necesidad tecnológica descrita")
    if _present(_field_value(row, "technology_signals")) or _present(_field_value(row, "technology_domains")):
        multiplier += 0.07
        reasons.append("señal tecnológica existente")
    if _present(_field_value(row, "identified_vendors")) or _present(_field_value(row, "identified_integrators")):
        multiplier += 0.07
        reasons.append("fabricante/integrador identificado")
    if _present(_field_value(row, "westcon_fit")) or _present(_field_value(row, "westcon_area")):
        multiplier += 0.05
        reasons.append("afinidad funcional Westcon ya derivada")

    amount = _numeric_amount(_field_value(row, "estimated_amount"))
    if amount is not None and amount > 0:
        if amount >= 5_000_000:
            multiplier += 0.18
            reasons.append("importe >= 5 M€")
        elif amount >= 1_000_000:
            multiplier += 0.14
            reasons.append("importe >= 1 M€")
        elif amount >= 250_000:
            multiplier += 0.09
            reasons.append("importe >= 250 k€")
        else:
            multiplier += 0.04
            reasons.append("importe conocido")

    stage = str(_field_value(row, "procurement_stage") or "").casefold()
    if any(token in stage for token in ("abiert", "open", "active", "activo", "em curso", "planned", "planific", "licit")):
        multiplier += 0.10
        reasons.append("oportunidad activa/planificada")
    elif any(token in stage for token in ("cancel", "desist", "closed", "cerrad", "anulad")):
        multiplier -= 0.10
        reasons.append("oportunidad cerrada/cancelada")

    milestone = _parse_date(_field_value(row, "milestone_date"))
    if milestone is not None:
        days = (milestone - date.today()).days
        if 0 <= days <= 120:
            multiplier += 0.14
            reasons.append("hito <= 120 días")
        elif 120 < days <= 365:
            multiplier += 0.07
            reasons.append("hito <= 12 meses")
        elif days < -180:
            multiplier -= 0.06
            reasons.append("hito histórico")

    return max(0.85, min(1.55, multiplier)), reasons


def annotate_gap(gap: dict[str, Any], public: Mapping[str, Any]) -> None:
    section = str(gap.get("section") or "")
    field = str(gap.get("field") or "")
    schema_rows = ((public.get("schemas") or {}).get(section) or [])
    column = next((row for row in schema_rows if isinstance(row, Mapping) and row.get("id") == field), {})
    decision_required = bool(column.get("decision_required")) or int(gap.get("priority") or 2) == 1
    business = business_weight(section, field, decision_required=decision_required)
    researchability = _researchability(gap)
    exact_claim = 1.10 if gap.get("gap_kind") == "public-validation" else 1.0
    opportunity_multiplier, opportunity_reasons = _public_opportunity_context(gap, public)
    raw = business * researchability * exact_claim * opportunity_multiplier
    # 3.5 is intentionally above normal raw scores; P0 is reserved for genuinely valuable, researchable debt.
    score = round(min(100.0, raw / 3.5 * 100), 1)
    # v4.3 controlled-growth guard: a newly discovered public buyer with little
    # opportunity context must not become high-priority merely because the schema
    # contains valuable fields. Exact public-validation debt is exempt.
    low_context_public = (
        section == "clients_public"
        and gap.get("gap_kind") != "public-validation"
        and opportunity_multiplier <= 1.05
    )
    if low_context_public:
        score = min(score, 57.9)  # P2 ceiling; no artificial section quota.
    family = family_for(field, section)
    playbook = PLAYBOOKS.get(family, PLAYBOOKS["official"])
    gap["business_value_score"] = round(min(100.0, business / 3.0 * 100), 1)
    gap["researchability_score"] = round(researchability / 1.35 * 100, 1)
    gap["priority_score"] = score
    gap["priority_tier"] = _tier(score)
    gap["opportunity_context_multiplier"] = round(opportunity_multiplier, 2)
    gap["opportunity_context"] = opportunity_reasons
    gap["source_family"] = family
    gap["source_strategy"] = {
        "preferred_families": list(playbook["families"]),
        "source_types": list(playbook["source_types"]),
        "rationale": playbook["rationale"],
        "query_hints": _query_hints(gap, family),
    }
    gap["priority_reason"] = (
        f"valor={gap['business_value_score']}/100; investigabilidad={gap['researchability_score']}/100; "
        f"contexto_oportunidad=x{gap['opportunity_context_multiplier']}; familia óptima={family}; "
        f"estado={gap.get('research_state') or 'abierto'}"
    )


def enrich_gap_report(gaps: list[dict[str, Any]], public: Mapping[str, Any]) -> dict[str, Any]:
    for gap in gaps:
        annotate_gap(gap, public)

    tier_counts = Counter(str(gap.get("priority_tier") or "P3") for gap in gaps)
    family_counts = Counter(str(gap.get("source_family") or "official") for gap in gaps)
    by_section_tier: dict[str, Counter[str]] = defaultdict(Counter)
    for gap in gaps:
        by_section_tier[str(gap.get("section") or "unknown")][str(gap.get("priority_tier") or "P3")] += 1

    open_fields = {
        (str(gap.get("section") or ""), str(gap.get("entity_id") or gap.get("entity") or ""), str(gap.get("field") or ""))
        for gap in gaps
    }
    expected_weight = 0.0
    open_weight = 0.0
    for section, rows in ((key, public.get(key) or []) for key in SECTION_VALUE):
        schema = [column for column in ((public.get("schemas") or {}).get(section) or []) if isinstance(column, Mapping) and not column.get("virtual")]
        for row in rows:
            entity_key = str(row.get("id") or row.get("name") or "")
            for column in schema:
                field = str(column.get("id") or "")
                if not field:
                    continue
                weight = business_weight(section, field, decision_required=bool(column.get("decision_required")))
                expected_weight += weight
                if (section, entity_key, field) in open_fields:
                    open_weight += weight

    weighted_coverage = round(max(0.0, 100.0 * (1.0 - open_weight / max(1.0, expected_weight))), 2)
    p0p1 = [gap for gap in gaps if gap.get("priority_tier") in {"P0", "P1"}]
    public_p0p1 = sum(1 for gap in p0p1 if gap.get("section") == "clients_public")
    low_context_public = [
        gap for gap in gaps
        if gap.get("section") == "clients_public"
        and float(gap.get("opportunity_context_multiplier") or 1.0) <= 1.05
    ]
    context_rich_public = [
        gap for gap in gaps
        if gap.get("section") == "clients_public"
        and float(gap.get("opportunity_context_multiplier") or 1.0) > 1.15
    ]
    low_context_public_high = [gap for gap in low_context_public if gap.get("priority_tier") in {"P0", "P1"}]
    return {
        "model": "business-value-x-researchability-opportunity-v2",
        "tiers": {tier: tier_counts.get(tier, 0) for tier in ("P0", "P1", "P2", "P3")},
        "actionable_high_value_gaps": len(p0p1),
        "weighted_expected_debt": round(expected_weight, 2),
        "weighted_open_debt": round(open_weight, 2),
        "business_weighted_coverage_pct": weighted_coverage,
        "source_families": dict(family_counts.most_common()),
        "by_section_tier": {section: dict(counts) for section, counts in by_section_tier.items()},
        "clients_public_share_of_p0_p1_pct": round(public_p0p1 * 100 / max(1, len(p0p1)), 2),
        "low_context_public_gaps": len(low_context_public),
        "low_context_public_p0_p1": len(low_context_public_high),
        "context_rich_public_gaps": len(context_rich_public),
        "controlled_growth_policy": "bounded-structured-growth-v1",
    }
