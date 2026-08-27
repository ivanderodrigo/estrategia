from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import load_json, number


REQUIRED = [
    "entities.json", "identity_audit.json", "relationships.json", "recommendations.json",
    "recommendation_audit.json", "quality_report.json", "source_coverage.json",
    "business_intelligence_report.json", "historical_intelligence.json", "architectures.json",
    "research_queue.json", "metrics_before_after.json", "last_run.json",
    "ecosystem_motion_intelligence.json",
    "source_catalog.json",
]


def validate(root: str | Path) -> list[str]:
    root = Path(root)
    errors: list[str] = []
    out = root / "data/v34"
    for filename in REQUIRED:
        path = out / filename
        if not path.exists():
            errors.append(f"Falta data/v34/{filename}")
            continue
        if load_json(path, None) is None:
            errors.append(f"JSON inválido data/v34/{filename}")
    recommendations = load_json(out / "recommendations.json", {})
    rows = recommendations.get("recommendations", []) or []
    if not rows:
        errors.append("No hay recomendaciones v3.4 pese a existir señales materiales")
    for row in rows:
        if row.get("action_type") not in {"ACTUAR", "PREPARAR / VALIDAR", "INVESTIGAR", "VIGILAR"}:
            errors.append(f"Tipo de acción inválido en {row.get('recommendation_id')}")
        if not row.get("action") or not row.get("why") or not row.get("why_now"):
            errors.append(f"Recomendación no ejecutiva en {row.get('recommendation_id')}")
        if not row.get("evidence") or any(not evidence.get("url") for evidence in row.get("evidence", [])):
            errors.append(f"Recomendación sin evidencia enlazada en {row.get('recommendation_id')}")
        if row.get("action_type") == "ACTUAR" and (
            number((row.get("fact_confidence") or {}).get("score")) < 0.82
            or number((row.get("interpretation_confidence") or {}).get("score")) < 0.68
            or number((row.get("action_risk") or {}).get("score"), 1) > 0.35
        ):
            errors.append(f"ACTUAR demasiado fuerte en {row.get('recommendation_id')}")
    recommendation_audit = load_json(out / "recommendation_audit.json", {})
    if recommendation_audit.get("status") != "PASS":
        errors.append(f"recommendation_audit={recommendation_audit.get('status')}")
    quality = load_json(out / "quality_report.json", {})
    if quality.get("status") != "PASS":
        errors.append(f"quality_report={quality.get('status')}")
    relationships = load_json(out / "relationships.json", {})
    for row in (relationships.get("integrator_vendor", []) + relationships.get("distributor_vendor", [])):
        if row.get("status") not in {"CONFIRMED", "PROBABLE", "RESEARCH PRIORITY", "INSUFFICIENT EVIDENCE"}:
            errors.append(f"Estado de relación inválido {row.get('relationship_id')}")
        if row.get("relationship_intensity") is None or not row.get("fact_confidence"):
            errors.append(f"Relación sin intensidad/confianza separadas {row.get('relationship_id')}")
    architectures = load_json(out / "architectures.json", {}).get("architectures", []) or []
    if len(architectures) < 12:
        errors.append(f"Solo hay {len(architectures)} arquitecturas; mínimo 12")
    for architecture in architectures:
        if not all(architecture.get(field) for field in ("problem", "opportunity", "layers", "gaps", "westcon_services", "monetization", "kpis", "risks", "readiness", "evidence")):
            errors.append(f"Arquitectura incompleta {architecture.get('architecture_id')}")
    source_coverage = load_json(out / "source_coverage.json", {})
    if source_coverage.get("meta", {}).get("learning_granularity") != "entidad × dimensión × país × tipo de fuente":
        errors.append("Source learning no tiene granularidad requerida")
    source_catalog = load_json(out / "source_catalog.json", {})
    if not 100 <= len(source_catalog.get("sources", [])) <= 150:
        errors.append(f"Catálogo operativo fuera del rango 100-150: {len(source_catalog.get('sources', []))}")
    motion = load_json(out / "ecosystem_motion_intelligence.json", {})
    if not motion.get("entities") or not motion.get("source_policy"):
        errors.append("Falta inteligencia de fabricantes movidos y perfiles buscados")
    for row in motion.get("entities", []):
        if not all(key in row for key in ("manufacturers_confirmed", "manufacturers_probable", "manufacturers_to_research", "manufacturers_in_job_profiles", "profiles_sought", "query_templates")):
            errors.append(f"Inteligencia de movimiento incompleta en {row.get('entity')}")
    if (root / "VERSION").read_text(encoding="utf-8").strip() != "3.4.0":
        errors.append("VERSION no es 3.4.0")
    return errors
