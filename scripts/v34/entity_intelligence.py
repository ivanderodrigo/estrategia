from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .common import age_days, clamp, dedupe_evidence, domain_of, load_json, norm, number, stable_id, unique


CAPABILITIES = {
    "soc": (" soc ", "security operations", "centro de operaciones de seguridad"),
    "noc": (" noc ", "network operations", "centro de operaciones de red"),
    "mssp": ("mssp", "managed security service"),
    "msp": ("msp", "managed service provider"),
    "professional_services": ("servicios profesionales", "professional services", "consulting", "consultoria"),
    "networking": ("network", "redes", "conectividad", "sd wan", "wifi", "wi fi"),
    "cybersecurity": ("cyber", "ciber", "security", "seguridad", "soc"),
    "cloud": ("cloud", "nube", "aws", "azure"),
    "data_center": ("data center", "datacenter", "centro de datos"),
    "observability": ("observability", "observabilidad", "monitoring", "telemetria"),
    "ai": ("inteligencia artificial", " artificial intelligence", " ia ", " ai ", "agentic"),
    "automation": ("automation", "automatizacion", "rpa", "orchestration"),
}

VALUE_ADDED = {
    "financing": ("financiacion", "financing", "as a service"),
    "marketplace": ("marketplace", "plataforma de compra"),
    "cloud_marketplace": ("cloud marketplace", "aws marketplace", "azure marketplace"),
    "training_enablement": ("formacion", "training", "enablement", "academy"),
    "labs_demos": ("lab", "laboratorio", "demo", "demostracion"),
    "poc": ("proof of concept", "prueba de concepto", " poc "),
    "staging_configuration": ("staging", "configuracion", "preconfiguracion"),
    "logistics": ("logistica", "logistics"),
}


def _blob(profile: Mapping[str, Any], evidence: list[Mapping[str, Any]]) -> str:
    values: list[Any] = [
        profile.get("name"), profile.get("technology_focus"), profile.get("services"),
        profile.get("managed_services"), profile.get("value_added"), profile.get("certifications"),
        profile.get("verticals"), profile.get("customer_cases"),
    ]
    values.extend(f"{row.get('title', '')} {row.get('source', '')}" for row in evidence)
    return f" {norm(' '.join(str(value) for value in values))} "


def _flags(blob: str, dictionary: Mapping[str, tuple[str, ...]]) -> dict[str, bool]:
    return {key: any(norm(term) in blob for term in terms) for key, terms in dictionary.items()}


def _momentum(evidence: list[Mapping[str, Any]], days: int) -> dict[str, Any]:
    current = [row for row in evidence if age_days(row.get("date")) is not None and age_days(row.get("date")) <= days]
    source_count = len({domain_of(row.get("url")) or norm(row.get("source")) for row in current})
    score = min(100, len(current) * 8 + source_count * 7)
    return {"score": score, "signals": len(current), "sources": source_count, "window_days": days}


def _explicit_columns(entity_type: str, row: Mapping[str, Any], flags: Mapping[str, bool], value_flags: Mapping[str, bool]) -> dict[str, Any]:
    common = {
        "corporate_group": row.get("canonical_group") if norm(row.get("canonical_group")) != norm(row.get("name")) else "",
        "relative_size": "",
        "partnership_levels": [],
        "specializations": unique(row.get("certifications") or row.get("certification_signals") or []),
        "competencies": unique(row.get("technology_focus") or []),
        "soc": bool(flags.get("soc")), "noc": bool(flags.get("noc")),
        "mssp": bool(flags.get("mssp")), "msp": bool(flags.get("msp")),
        "professional_services": bool(flags.get("professional_services")),
        "networking": bool(flags.get("networking")), "cybersecurity": bool(flags.get("cybersecurity")),
        "cloud": bool(flags.get("cloud")), "data_center": bool(flags.get("data_center")),
        "observability": bool(flags.get("observability")), "ai": bool(flags.get("ai")),
        "automation": bool(flags.get("automation")),
        "alliances": [], "acquisitions": [], "expansion": [], "relevant_hiring": [],
    }
    if entity_type == "distributor":
        common.update({
            "confirmed_linecard": unique(row.get("vendors") or []),
            "probable_linecard": [],
            "vendor_country_relations": [],
            "financing": bool(value_flags.get("financing")),
            "marketplace": bool(value_flags.get("marketplace")),
            "cloud_marketplace": bool(value_flags.get("cloud_marketplace")),
            "training_enablement": bool(value_flags.get("training_enablement")),
            "labs_demos": bool(value_flags.get("labs_demos")),
            "poc": bool(value_flags.get("poc")),
            "staging_configuration": bool(value_flags.get("staging_configuration")),
            "logistics": bool(value_flags.get("logistics")),
        })
    else:
        common.update({
            "customers_public_cases": unique(row.get("customer_cases") or row.get("customer_case_examples") or []),
            "public_procurement_awards": int(number(row.get("public_sector_events"))),
        })
    return common


def _coverage(entity_type: str, result: Mapping[str, Any]) -> dict[str, Any]:
    fields = [
        "vendors", "specializations", "competencies", "verticals", "customers_public_cases",
        "managed_services", "professional_services", "soc", "noc", "mssp", "msp",
        "alliances", "acquisitions", "expansion", "relevant_hiring",
    ] if entity_type == "integrator" else [
        "confirmed_linecard", "probable_linecard", "technology_focus", "managed_services",
        "financing", "marketplace", "cloud_marketplace", "training_enablement", "labs_demos",
        "poc", "staging_configuration", "logistics", "alliances", "acquisitions", "expansion",
    ]
    populated = [field for field in fields if result.get(field) not in (None, "", [], {}, False, 0)]
    return {
        "score": round(100 * len(populated) / len(fields)),
        "populated_fields": populated,
        "missing_fields": [field for field in fields if field not in populated],
        "field_count": len(fields),
        "formula": "100 × campos de negocio con evidencia / campos prioritarios del tipo de entidad",
    }


def build_entities(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    source = load_json(root / "data/v33/ecosystem_profiles.json", {})
    known_vendor_names = {
        norm(row.get("name")) for row in load_json(root / "data/v31/entity_intelligence.json", {}).get("vendors", [])
    }
    excluded: list[dict[str, Any]] = []
    entities: list[dict[str, Any]] = []
    duplicate_evidence_removed = 0
    rejected_untraceable_evidence = 0
    for profile in source.get("profiles", []) or []:
        entity_type = profile.get("entity_type")
        if entity_type == "integrator" and norm(profile.get("name")) in known_vendor_names:
            excluded.append({
                "name": profile.get("name"), "reason": "La entidad coincide con un fabricante conocido; se excluye de la vista de integradores v3.4.",
                "preserved_in": "data/v33/ecosystem_profiles.json",
            })
            continue
        evidence, removed = dedupe_evidence(profile.get("evidence") or [])
        duplicate_evidence_removed += removed
        traceable_evidence = [row for row in evidence if row.get("url") and row.get("source")]
        rejected_untraceable_evidence += len(evidence) - len(traceable_evidence)
        evidence = traceable_evidence
        blob = _blob(profile, evidence)
        capability_flags = _flags(blob, CAPABILITIES)
        value_flags = _flags(blob, VALUE_ADDED)
        result = {
            "entity_id": stable_id("entity", entity_type, profile.get("name"), profile.get("scope")),
            "name": profile.get("name"), "entity_type": entity_type,
            "scope": profile.get("scope"), "operations": profile.get("operations") or [],
            "entity_tier": profile.get("entity_tier"),
            "strategic_importance_score": profile.get("strategic_importance_score"),
            "westcon_relevance": profile.get("westcon_relevance"),
            "activation_priority": profile.get("activation_priority") if entity_type == "integrator" else None,
            "competitive_pressure": profile.get("competitive_pressure") if entity_type == "distributor" else None,
            "competitive_response_priority": profile.get("competitive_response_priority") if entity_type == "distributor" else None,
            "vendors": unique(profile.get("vendors") or []),
            "westcon_overlap": unique(profile.get("westcon_overlap") or []),
            "technology_focus": unique(profile.get("technology_focus") or []),
            "managed_services": unique(profile.get("managed_services") or []),
            "services": unique(profile.get("services") or []),
            "verticals": unique(profile.get("verticals") or []),
            "recurring_services_potential": profile.get("recurring_services_potential"),
            "potential_services": unique((profile.get("managed_services") or []) + (profile.get("services") or [])),
            "whitespace_candidates": profile.get("whitespace_candidates") or [],
            "whitespace_score": profile.get("whitespace_score"),
            "relationship_confirmed_count": profile.get("relationship_confirmed_count", 0),
            "relationship_probable_count": profile.get("relationship_probable_count", 0),
            "relationship_research_count": profile.get("relationship_research_count", 0),
            "confidence": round(clamp(profile.get("confidence")), 3),
            "evidence_grade": profile.get("evidence_grade"),
            "evidence_count": len(evidence),
            "source_diversity": len({domain_of(row.get("url")) or norm(row.get("source")) for row in evidence}),
            "evidence": evidence[:40],
            "last_verified": max((str(row.get("date") or "") for row in evidence), default=profile.get("last_verified") or ""),
            "momentum_30d": _momentum(evidence, 30),
            "momentum_90d": _momentum(evidence, 90),
            "momentum_365d": _momentum(evidence, 365),
            "provenance": {
                "derived_from": "data/v33/ecosystem_profiles.json",
                "method": "deduplicación por URL/título; enriquecimiento conservador por señales explícitas",
                "scores_are_relative": True,
            },
        }
        result.update(_explicit_columns(entity_type, profile, capability_flags, value_flags))
        result["coverage"] = _coverage(entity_type, result)
        result["research_gaps"] = result["coverage"]["missing_fields"]
        entities.append(result)
    entities.sort(key=lambda row: (row.get("entity_type"), -number(row.get("strategic_importance_score")), norm(row.get("name"))))
    distribution = Counter(row.get("entity_tier") for row in entities)
    document = {
        "meta": {
            "version": "3.4.0", "generated_at": datetime.now(timezone.utc).isoformat(),
            "entities": len(entities), "integrators": sum(row["entity_type"] == "integrator" for row in entities),
            "distributors": sum(row["entity_type"] == "distributor" for row in entities),
            "tier_distribution": dict(distribution), "duplicate_evidence_removed": duplicate_evidence_removed,
            "rejected_untraceable_evidence": rejected_untraceable_evidence,
            "principle": "Dato ausente significa información pendiente; nunca se convierte en ausencia de capacidad o relación.",
        },
        "entities": entities,
        "integrators": [row for row in entities if row["entity_type"] == "integrator"],
        "distributors": [row for row in entities if row["entity_type"] == "distributor"],
    }
    identity_audit = {
        "version": "3.4.0", "excluded_role_conflicts": excluded,
        "excluded_count": len(excluded), "unresolved_identity_errors": 0,
        "note": "Las filas heredadas permanecen intactas en v3.3 para trazabilidad; la vista v3.4 corrige el rol sin borrar evidencia.",
    }
    return document, identity_audit
