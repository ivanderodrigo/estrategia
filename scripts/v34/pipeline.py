from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .common import load_json, number, write_json
from .entity_intelligence import build_entities
from .ecosystem_motion import build_ecosystem_motion
from .intelligence_outputs import (
    build_adaptive_queue, build_architectures, build_business_report, build_history, build_source_catalog, build_source_coverage,
)
from .quality import audit_recommendations, build_quality_report
from .recommendation_engine import build_recommendations
from .relationship_engine import build_relationships


def _baseline_metrics(root: Path) -> dict[str, Any]:
    profiles = load_json(root / "data/v33/ecosystem_profiles.json", {}).get("profiles", []) or []
    coverage = [number(row.get("coverage_score")) for row in profiles]
    relation_docs = [
        load_json(root / "data/v33/integrator_vendor_matrix.json", {}),
        load_json(root / "data/v33/distributor_vendor_matrix.json", {}),
    ]
    duplicate_relation_evidence = 0
    relation_rows = 0
    for document in relation_docs:
        for row in document.get("rows", []) or []:
            evidence = row.get("evidence") or []
            keys = [str(item.get("url") or "") or f"{item.get('title')}|{item.get('source')}|{item.get('date')}" for item in evidence]
            duplicate_relation_evidence += max(0, len(keys) - len(set(keys)))
            relation_rows += 1
    reality = load_json(root / "data/market_reality.json", {})
    absolute_gate_actions = sum(
        number(value.get("confidence")) == 100 and len(value.get("evidenceIds") or []) >= 3
        for value in (reality.get("vendors") or {}).values()
    )
    return {
        "version": "3.3.3a", "profiles": len(profiles),
        "integrators": sum(row.get("entity_type") == "integrator" for row in profiles),
        "distributors": sum(row.get("entity_type") == "distributor" for row in profiles),
        "average_profile_coverage": round(sum(coverage) / max(1, len(coverage)), 1),
        "profiles_below_50_coverage": sum(value < 50 for value in coverage),
        "relation_rows": relation_rows, "duplicate_relation_evidence": duplicate_relation_evidence,
        "published_actions_under_absolute_100_gate": absolute_gate_actions,
        "recommendation_model": "Una recomendación solo se mostraba con confianza exactamente 100 y ≥3 evidencias en el contrato de realidad.",
        "known_test_baseline": {"unit_tests_total": 106, "unit_tests_failed": 2, "ui_smoke_failed": 1, "source": "Ejecución inicial documentada en README_V340.md"},
    }


def run(root: Path, profile: str = "daily") -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    policy = load_json(root / "config/v34/policy.json", {})
    source_expansion = load_json(root / "config/v34/source_expansion.json", {})
    audience_routes = load_json(root / "config/v34/audience_source_routes.json", {})
    relationship_playbook = load_json(root / "config/v34/relationship_source_playbook.json", {})
    source_expansion = {
        **source_expansion,
        "sources": (source_expansion.get("sources") or []) + (audience_routes.get("sources") or []),
        "audience_routes": audience_routes.get("routes") or [],
        "audience_rules": audience_routes.get("rules") or [],
    }
    table_config = load_json(root / "config/v34/table_config.json", {})
    entities, identity_audit = build_entities(root)
    relationships = build_relationships(root, entities)
    ecosystem_motion = build_ecosystem_motion(root, entities, relationships, audience_routes, relationship_playbook)
    source_coverage = build_source_coverage(root, entities, source_expansion)
    source_catalog = build_source_catalog(source_expansion)
    history = build_history(root)
    architectures = build_architectures(root, entities)
    adaptive_queue = build_adaptive_queue(entities, relationships, source_coverage)
    recommendations, dispositions = build_recommendations(root, entities, relationships, policy)
    recommendation_audit = audit_recommendations(recommendations, dispositions, policy)
    business_report = build_business_report(recommendations, entities, relationships, architectures, history, source_coverage)
    business_report["ecosystem_motion"] = {
        "principle": ecosystem_motion.get("meta", {}).get("principle"),
        "manufacturers_by_integrator_or_distributor": ecosystem_motion.get("entities", []),
        "talent_signal_summary": ecosystem_motion.get("meta", {}),
        "source_policy": ecosystem_motion.get("source_policy", {}),
    }

    out = root / "data/v34"
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "entities.json", entities)
    write_json(out / "identity_audit.json", identity_audit)
    write_json(out / "relationships.json", relationships)
    write_json(out / "ecosystem_motion_intelligence.json", ecosystem_motion)
    write_json(out / "recommendations.json", recommendations)
    write_json(out / "recommendation_audit.json", recommendation_audit)
    write_json(out / "source_coverage.json", source_coverage)
    write_json(out / "source_catalog.json", source_catalog)
    write_json(out / "historical_intelligence.json", history)
    write_json(out / "architectures.json", architectures)
    write_json(out / "research_queue.json", adaptive_queue)
    write_json(out / "business_intelligence_report.json", business_report)

    quality_report = build_quality_report(
        root, entities, identity_audit, relationships, recommendations, recommendation_audit,
        architectures, source_coverage, business_report, table_config,
    )
    write_json(out / "quality_report.json", quality_report)

    after_coverage = [number((row.get("coverage") or {}).get("score")) for row in entities.get("entities", [])]
    before = _baseline_metrics(root)
    action_distribution = dict(Counter(row.get("action_type") for row in recommendations.get("recommendations", [])))
    metrics = {
        "version": "3.4.0", "generated_at": datetime.now(timezone.utc).isoformat(),
        "before": before,
        "after": {
            "version": "3.4.0", "profiles": len(entities.get("entities", [])),
            "integrators": len(entities.get("integrators", [])), "distributors": len(entities.get("distributors", [])),
            "average_profile_coverage": round(sum(after_coverage) / max(1, len(after_coverage)), 1),
            "profiles_below_50_coverage": sum(value < 50 for value in after_coverage),
            "relation_rows": relationships.get("meta", {}).get("rows"),
            "duplicate_relation_evidence": 0,
            "duplicate_relation_evidence_removed": relationships.get("meta", {}).get("duplicate_evidence_removed"),
            "published_recommendations": len(recommendations.get("recommendations", [])),
            "recommendation_action_distribution": action_distribution,
            "recommendation_audit_errors": recommendation_audit.get("summary", {}).get("errors"),
            "quality_errors": quality_report.get("summary", {}).get("errors"),
            "architectures": len(architectures.get("architectures", [])),
            "public_source_candidates": source_coverage.get("meta", {}).get("total_public_source_candidates"),
            "v34_operational_source_catalog": source_catalog.get("meta", {}).get("sources"),
            "source_learning_cells": len(source_coverage.get("coverage", [])),
            "ecosystem_motion_profiles": len(ecosystem_motion.get("entities", [])),
            "accepted_talent_signals": ecosystem_motion.get("meta", {}).get("accepted_talent_signals", 0),
            "rejected_hiring_false_positives": ecosystem_motion.get("meta", {}).get("rejected_hiring_false_positives", 0),
        },
        "interpretation": {
            "coverage": "La cobertura v3.4 usa más campos de negocio que v3.3; una bajada puede significar medición más exigente, no pérdida de datos.",
            "integrators": "Los fabricantes mal clasificados se excluyen de la vista v3.4 y permanecen en v3.3 para auditoría.",
            "recommendations": "La mejora buscada es utilidad con evidencia, no maximizar el número publicado.",
        },
    }
    write_json(out / "metrics_before_after.json", metrics)
    finished = datetime.now(timezone.utc)
    last_run = {
        "version": "3.4.0", "profile": profile, "status": "published" if quality_report.get("status") == "PASS" and recommendation_audit.get("status") == "PASS" else "validation_failed",
        "started_at": started.isoformat(), "finished_at": finished.isoformat(), "runtime_seconds": round((finished - started).total_seconds(), 3),
        "entities": len(entities.get("entities", [])), "relationships": relationships.get("meta", {}).get("rows"),
        "recommendations": len(recommendations.get("recommendations", [])), "action_distribution": action_distribution,
        "architectures": len(architectures.get("architectures", [])), "quality_status": quality_report.get("status"),
        "ecosystem_motion_profiles": len(ecosystem_motion.get("entities", [])),
        "recommendation_audit_status": recommendation_audit.get("status"),
    }
    write_json(out / "last_run.json", last_run)
    return last_run
