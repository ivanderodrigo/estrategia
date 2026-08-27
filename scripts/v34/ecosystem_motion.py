from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .common import age_days, dedupe_evidence, domain_of, load_json, norm, number, source_type, stable_id, unique


ROLE_FAMILIES = {
    "ventas_canal": ("account manager", "sales", "ventas", "comercial", "channel", "canal", "business development", "psm", "vendor manager"),
    "preventa_arquitectura": ("presales", "preventa", "solution architect", "arquitect", "consultor", "sales engineer"),
    "ingenieria_operaciones": ("engineer", "ingenier", "operations", "operaciones", "administrator", "administrador", "devops", "sre"),
    "servicios_gestionados": ("soc", "noc", "mssp", "msp", "managed service", "servicio gestionado", "incident response"),
    "cloud_datos_ia": ("cloud", "aws", "azure", "data", "datos", "machine learning", "artificial intelligence", "inteligencia artificial", " ia ", " ai "),
    "ciberseguridad": ("cyber", "ciber", "security", "seguridad", "zero trust", "sase", "siem", "xdr"),
    "networking_datacenter": ("network", "redes", "wifi", "wi fi", "sd wan", "data center", "datacenter"),
    "liderazgo": ("director", "head of", "chief ", "country manager", "vice president", "vp "),
}

VACANCY_PATTERNS = (
    r"\bvacant(?:e|es)\b", r"\boferta(?:s)? de empleo\b", r"\bjob(?:s)?\b", r"\bcareer(?:s)?\b",
    r"\bse busca\b", r"\bbuscamos\b", r"\bwe are hiring\b", r"\bhiring for\b", r"\brecruit(?:ing|ment)?\b",
    r"\bpuesto(?:s)?\b", r"\bposição\b", r"\bvaga(?:s)?\b", r"\bcontratar\b", r"\bcontratacao\b",
)
WORKFORCE_PATTERNS = (
    r"\bcontratacion ha crecido\b", r"\bcreacion de empleo\b", r"\bnuevas contrataciones\b",
    r"\bplan de contratacion\b", r"\breforzar(?:a|á)? (?:su )?equipo\b", r"\bcentro de innovacion y talento\b",
)


def _matches(text: str, patterns: Iterable[str]) -> bool:
    return any(re.search(pattern, text, re.I) for pattern in patterns)


def _role_families(text: str) -> list[str]:
    blob = f" {norm(text)} "
    return [family for family, tokens in ROLE_FAMILIES.items() if any(norm(token) in blob for token in tokens)]


def _vendor_mentions(text: str, vendors: list[str], entity: str) -> list[str]:
    blob = f" {norm(text)} "
    entity_norm = norm(entity)
    return [vendor for vendor in vendors if norm(vendor) != entity_norm and f" {norm(vendor)} " in blob]


def _evidence_pool(root: Path, entities: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entity in entities.get("entities", []) or []:
        for evidence in entity.get("evidence", []) or []:
            rows.append({**evidence, "entity": entity.get("name"), "entity_type": entity.get("entity_type"), "scope": entity.get("scope")})
    for event in load_json(root / "data/v32/events.json", {}).get("events", []) or []:
        if event.get("entity_type") not in {"integrator", "distributor", "vendor"}:
            continue
        rows.append({
            "title": event.get("title"), "summary": event.get("summary"), "source": event.get("source"),
            "url": event.get("url"), "date": event.get("published_at"), "confidence": event.get("confidence"),
            "entity": event.get("entity_name"), "entity_type": event.get("entity_type"),
            "scope": event.get("market_scope"), "source_type": event.get("source_type"),
        })
    return rows


def build_ecosystem_motion(root: Path, entities: Mapping[str, Any], relationships: Mapping[str, Any], audience_routes: Mapping[str, Any], relationship_playbook: Mapping[str, Any]) -> dict[str, Any]:
    vendor_names = [row.get("name") for row in load_json(root / "data/vendor_intelligence.json", {}).get("vendors", []) or [] if row.get("name")]
    raw_evidence = _evidence_pool(root, entities)
    accepted: list[dict[str, Any]] = []
    rejected_false_positive: list[dict[str, Any]] = []
    for evidence in raw_evidence:
        text = " ".join(str(evidence.get(key) or "") for key in ("title", "summary"))
        normalized = norm(text)
        vacancy = _matches(normalized, VACANCY_PATTERNS)
        workforce = _matches(normalized, WORKFORCE_PATTERNS)
        classified_hiring = norm(evidence.get("classification")) == "hiring"
        if not vacancy and not workforce:
            if classified_hiring:
                rejected_false_positive.append({
                    "entity": evidence.get("entity"), "title": evidence.get("title"), "url": evidence.get("url"),
                    "reason": "Clasificación heredada 'hiring' sin lenguaje explícito de vacante o inversión en plantilla.",
                })
            continue
        if not evidence.get("url") or not evidence.get("source"):
            continue
        accepted.append({
            **evidence,
            "signal_id": stable_id("talent", evidence.get("entity"), evidence.get("url"), evidence.get("title")),
            "signal_type": "vacancy" if vacancy else "workforce_momentum",
            "role_families": _role_families(text),
            "vendor_mentions": _vendor_mentions(text, vendor_names, str(evidence.get("entity") or "")),
            "source_type": source_type(evidence),
            "interpretation_rule": "Una mención en una vacante demuestra demanda de la competencia en ese perfil; no prueba partnership ni volumen de negocio.",
        })
    accepted, removed = dedupe_evidence(accepted)

    relation_by_entity: dict[str, list[dict[str, Any]]] = {}
    for relation in relationships.get("integrator_vendor", []) + relationships.get("distributor_vendor", []):
        entity = relation.get("integrator") or relation.get("distributor")
        relation_by_entity.setdefault(norm(entity), []).append(relation)
    evidence_by_entity: dict[str, list[dict[str, Any]]] = {}
    for evidence in accepted:
        evidence_by_entity.setdefault(norm(evidence.get("entity")), []).append(evidence)

    source_ids = [source.get("id") for source in audience_routes.get("sources", []) or [] if "hiring" in (source.get("dimensions") or []) or "skills_demand" in (source.get("dimensions") or [])]
    profiles: list[dict[str, Any]] = []
    for entity in entities.get("entities", []) or []:
        if entity.get("entity_tier") not in {"T1", "T2"}:
            continue
        relations = relation_by_entity.get(norm(entity.get("name")), [])
        signals = evidence_by_entity.get(norm(entity.get("name")), [])
        confirmed = [row for row in relations if row.get("status") == "CONFIRMED"]
        probable = [row for row in relations if row.get("status") == "PROBABLE"]
        research = [row for row in relations if row.get("status") == "RESEARCH PRIORITY"]
        vendor_demand = Counter(vendor for signal in signals for vendor in signal.get("vendor_mentions") or [])
        role_demand = Counter(role for signal in signals for role in signal.get("role_families") or [])
        countries = unique([entity.get("scope")] + [signal.get("scope") for signal in signals])
        profiles.append({
            "entity_id": entity.get("entity_id"), "entity": entity.get("name"), "entity_type": entity.get("entity_type"),
            "entity_tier": entity.get("entity_tier"), "scope": entity.get("scope"),
            "manufacturers_confirmed": [{"vendor": row.get("vendor"), "intensity": row.get("relationship_intensity"), "confidence": row.get("fact_confidence"), "scope": (row.get("geography") or {}).get("scope"), "last_verified": row.get("last_verified")} for row in sorted(confirmed, key=lambda item: number(item.get("relationship_intensity")), reverse=True)],
            "manufacturers_probable": [{"vendor": row.get("vendor"), "intensity": row.get("relationship_intensity"), "confidence": row.get("fact_confidence"), "scope": (row.get("geography") or {}).get("scope"), "last_verified": row.get("last_verified")} for row in sorted(probable, key=lambda item: number(item.get("relationship_intensity")), reverse=True)],
            "manufacturers_to_research": [{"vendor": row.get("vendor"), "priority": row.get("priority_score"), "why": row.get("next_research")} for row in sorted(research, key=lambda item: number(item.get("priority_score")), reverse=True)[:12]],
            "manufacturers_in_job_profiles": [{"vendor": vendor, "signals": count, "status": "EMPLOYMENT INDICATOR — NOT PARTNERSHIP"} for vendor, count in vendor_demand.most_common()],
            "profiles_sought": [{"family": family, "signals": count} for family, count in role_demand.most_common()],
            "talent_signals": signals,
            "talent_momentum": {
                str(days): sum(age_days(signal.get("date")) is not None and age_days(signal.get("date")) <= days for signal in signals)
                for days in (30, 90, 365)
            },
            "countries_observed": countries,
            "next_source_ids": source_ids,
            "query_templates": [
                f'"{entity.get("name")}" (jobs OR careers OR empleo OR vagas) (Cisco OR Palo Alto OR Fortinet OR Check Point OR AWS OR Azure)',
                f'site:linkedin.com/jobs "{entity.get("name")}" (security OR cloud OR network OR SOC OR presales)',
                f'"{entity.get("name")}" (CCNP OR PCNSE OR NSE OR CCSA OR AWS certified OR Azure) (España OR Portugal)',
            ],
            "decision_use": "Cruzar fabricante/certificación demandados, recurrencia, país y familia de rol con locator, casos, certificaciones y contratación pública para priorizar activación o investigación.",
            "caution": "Las vacantes prueban demanda de competencias; no partnership, ventas, headcount efectivo ni contrato ganado.",
        })
    profiles.sort(key=lambda row: ({"T1": 0, "T2": 1}.get(row.get("entity_tier"), 2), -len(row.get("talent_signals") or []), norm(row.get("entity"))))
    return {
        "meta": {
            "version": "3.4.0", "generated_at": datetime.now(timezone.utc).isoformat(),
            "entities": len(profiles), "accepted_talent_signals": len(accepted),
            "deduplicated_signals": removed, "rejected_hiring_false_positives": len(rejected_false_positive),
            "principle": "El talento es una señal adelantada: se triangula con evidencia de relación, casos, certificaciones y país antes de elevar una decisión.",
        },
        "entities": profiles,
        "talent_signals": accepted,
        "rejected_false_positives": rejected_false_positive[:80],
        "source_policy": {
            "priority": ["portal corporativo/ATS", "servicio público de empleo", "portal tecnológico especializado", "portal general", "red social/agregador"],
            "deduplication": "empresa + título + país + ubicación + ventana temporal",
            "negative_evidence": "La ausencia de vacantes públicas no demuestra ausencia de capacidad o inversión.",
            "fields": ["empresa", "país", "ubicación", "fecha", "rol", "seniority", "fabricantes", "certificaciones", "tecnologías", "función", "modelo remoto", "fuente original", "fecha de retirada"],
        },
        "relationship_source_playbook": relationship_playbook,
    }
