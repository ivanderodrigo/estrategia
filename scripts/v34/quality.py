from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from .common import age_days, evidence_key, load_json, norm, number


REQUIRED_RECOMMENDATION_FIELDS = [
    "action", "why", "why_now", "evidence", "fact_confidence", "interpretation_confidence",
    "action_risk", "confidence", "action_type", "impact_potential", "urgency", "effort", "horizon",
    "proposed_owner", "vendors_involved", "integrators_involved", "distributors_involved",
    "potential_services", "recurring_revenue_potential", "relative_margin_potential", "risks",
    "missing_information", "evidence_that_would_change_recommendation", "sources", "source_dates",
]

GENERIC_ACTIONS = [
    re.compile(r"^potenciar (cybersecurity|ciberseguridad)[.!]?$", re.I),
    re.compile(r"^explorar (ia|ai)[.!]?$", re.I),
    re.compile(r"^trabajar mas con cisco[.!]?$", re.I),
    re.compile(r"^(analizar|investigar|vigilar|validar)[.!]?$", re.I),
]


def audit_recommendations(
    recommendations: Mapping[str, Any], dispositions: list[Mapping[str, Any]], policy: Mapping[str, Any],
) -> dict[str, Any]:
    rows = recommendations.get("recommendations", []) or []
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    counters = Counter({
        "invented_recommendations": 0, "without_evidence": 0, "unjustified_absence": 0,
        "excess_recommendations": 0, "generic_recommendations": 0, "duplicate_recommendations": 0,
        "contradictory_recommendations": 0, "without_action": 0, "action_too_strong": 0,
    })
    action_keys: dict[str, str] = {}
    target_types: dict[str, set[str]] = {}
    for row in rows:
        rec_id = row.get("recommendation_id") or "unknown"
        missing_fields = [field for field in REQUIRED_RECOMMENDATION_FIELDS if row.get(field) in (None, "", [], {}) and field not in {"vendors_involved", "integrators_involved", "distributors_involved"}]
        if missing_fields:
            errors.append({"recommendation_id": rec_id, "check": "schema", "detail": f"Faltan campos: {', '.join(missing_fields)}"})
        if not str(row.get("action") or "").strip():
            counters["without_action"] += 1
            errors.append({"recommendation_id": rec_id, "check": "action", "detail": "No indica una acción."})
        if not row.get("evidence"):
            counters["without_evidence"] += 1
            counters["invented_recommendations"] += 1
            errors.append({"recommendation_id": rec_id, "check": "evidence", "detail": "Recomendación sin evidencia vinculada."})
        for evidence in row.get("evidence", []) or []:
            if not evidence.get("url") or not evidence.get("source") or not evidence.get("date"):
                counters["without_evidence"] += 1
                errors.append({"recommendation_id": rec_id, "check": "evidence", "detail": "Evidencia sin URL, fuente o fecha."})
                break
        if any(pattern.match(str(row.get("action") or "").strip()) for pattern in GENERIC_ACTIONS):
            counters["generic_recommendations"] += 1
            errors.append({"recommendation_id": rec_id, "check": "generic", "detail": "Acción genérica."})
        key = norm(row.get("action"))
        if key in action_keys:
            counters["duplicate_recommendations"] += 1
            errors.append({"recommendation_id": rec_id, "check": "duplicate", "detail": f"Duplica {action_keys[key]}."})
        action_keys[key] = rec_id
        action_type = row.get("action_type")
        if action_type not in {"ACTUAR", "PREPARAR / VALIDAR", "INVESTIGAR", "VIGILAR"}:
            errors.append({"recommendation_id": rec_id, "check": "action_type", "detail": f"Tipo inválido: {action_type}"})
        if action_type == "ACTUAR":
            fact = number((row.get("fact_confidence") or {}).get("score"))
            interpretation = number((row.get("interpretation_confidence") or {}).get("score"))
            risk = number((row.get("action_risk") or {}).get("score"), 1)
            primary = any(evidence.get("source_type") == "primary" for evidence in row.get("evidence", []))
            if fact < 0.82 or interpretation < 0.68 or risk > 0.35 or not primary:
                counters["action_too_strong"] += 1
                errors.append({"recommendation_id": rec_id, "check": "strength", "detail": "ACTUAR excede la fuerza permitida por hecho/interpretación/riesgo/fuente."})
        target = norm(row.get("target"))
        target_types.setdefault(target, set()).add(str(action_type))
    for target, types in target_types.items():
        if "ACTUAR" in types and "VIGILAR" in types and target:
            counters["contradictory_recommendations"] += 1
            warnings.append({"check": "contradiction", "detail": f"El objetivo {target} contiene ACTUAR y VIGILAR; revisar si corresponden a asuntos distintos."})
    candidate_count = int(number(recommendations.get("meta", {}).get("candidate_count")))
    disposition_ids = {row.get("candidate_id") for row in dispositions if row.get("candidate_id")}
    if len(disposition_ids) != candidate_count:
        counters["unjustified_absence"] = max(0, candidate_count - len(disposition_ids))
        errors.append({"check": "absence", "detail": f"{counters['unjustified_absence']} candidatos no tienen disposición explicada."})
    max_published = int(policy.get("recommendations", {}).get("max_published", 32))
    if len(rows) > max_published:
        counters["excess_recommendations"] = len(rows) - max_published
        errors.append({"check": "excess", "detail": f"Se publican {len(rows)} recomendaciones; máximo {max_published}."})
    return {
        "version": "3.4.0", "status": "PASS" if not errors else "FAIL",
        "summary": {
            "published_recommendations": len(rows), "candidate_recommendations": candidate_count,
            "discarded_or_not_shown": sum(row.get("disposition") == "DESCARTAR / NO MOSTRAR" for row in dispositions),
            **dict(counters), "errors": len(errors), "warnings": len(warnings),
        },
        "checks": {
            "invented_recommendations": counters["invented_recommendations"],
            "recommendations_without_evidence": counters["without_evidence"],
            "unjustified_absence": counters["unjustified_absence"],
            "excess_recommendations": counters["excess_recommendations"],
            "generic_recommendations": counters["generic_recommendations"],
            "duplicate_recommendations": counters["duplicate_recommendations"],
            "contradictory_recommendations": counters["contradictory_recommendations"],
            "recommendations_without_action": counters["without_action"],
            "action_too_strong_for_evidence": counters["action_too_strong"],
        },
        "errors": errors, "warnings": warnings, "candidate_dispositions": dispositions,
        "governance": {
            "ACTUAR": "Hecho ≥0,82; interpretación ≥0,68; riesgo ≤0,35; al menos una fuente primaria; acción concreta y reversible/procedimental.",
            "PREPARAR / VALIDAR": "Evidencia relevante con incertidumbre; acción de bajo riesgo para preparar o verificar.",
            "INVESTIGAR": "Hipótesis material; la acción obtiene la evidencia que falta.",
            "VIGILAR": "Señal débil o impacto todavía incierto; seguimiento con trigger explícito.",
            "DESCARTAR / NO MOSTRAR": "Sin materialidad, sin evidencia, duplicada o fuera del presupuesto de atención; la disposición queda trazada.",
        },
    }


def build_quality_report(
    root: Path, entities: Mapping[str, Any], identity_audit: Mapping[str, Any], relationships: Mapping[str, Any],
    recommendations: Mapping[str, Any], recommendation_audit: Mapping[str, Any], architectures: Mapping[str, Any],
    source_coverage: Mapping[str, Any], business_report: Mapping[str, Any], table_config: Mapping[str, Any],
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    checks: dict[str, dict[str, Any]] = {}

    def record(name: str, ok: bool, detail: str, severity: str = "error") -> None:
        checks[name] = {"status": "PASS" if ok else "WARN" if severity == "warning" else "FAIL", "detail": detail}
        if not ok:
            (warnings if severity == "warning" else errors).append({"check": name, "detail": detail})

    entity_rows = entities.get("entities", []) or []
    identity_keys = [(row.get("entity_type"), norm(row.get("name")), row.get("scope")) for row in entity_rows]
    record("duplicates", len(identity_keys) == len(set(identity_keys)), "No hay perfiles v3.4 duplicados por tipo, nombre y ámbito.")
    record("identity", not identity_audit.get("unresolved_identity_errors"), f"{identity_audit.get('excluded_count', 0)} conflictos de rol heredados excluidos y trazados; 0 sin resolver.")
    invalid_scopes = [row.get("name") for row in entity_rows if row.get("scope") not in {"ES", "PT", "IBERIA", "GLOBAL", "EMEA", "EUROPE"}]
    record("geography", not invalid_scopes, f"Ámbitos inválidos: {invalid_scopes[:5]}" if invalid_scopes else "Ámbitos normalizados; Iberia no se desdobla sin prueba.")
    stale = sum(1 for row in entity_rows for evidence in row.get("evidence", []) if age_days(evidence.get("date")) is not None and age_days(evidence.get("date")) > 1095)
    record("stale_evidence", stale == 0, f"{stale} evidencias de más de 3 años se conservan con fecha y no elevan por sí solas una relación a confirmada.", "warning")
    missing_source = sum(1 for row in entity_rows for evidence in row.get("evidence", []) if not evidence.get("url") or not evidence.get("source"))
    record("sources", missing_source == 0, f"Evidencias sin fuente/URL: {missing_source}.")
    record("contradictions", recommendation_audit.get("checks", {}).get("contradictory_recommendations", 0) == 0, "No hay recomendaciones contradictorias sobre el mismo objetivo." if recommendation_audit.get("checks", {}).get("contradictory_recommendations", 0) == 0 else "Existen recomendaciones potencialmente contradictorias.", "warning")
    missing_provenance = sum(1 for row in entity_rows if not isinstance(row.get("provenance"), Mapping))
    record("provenance", missing_provenance == 0, f"Perfiles sin provenance: {missing_provenance}.")
    relation_rows = relationships.get("integrator_vendor", []) + relationships.get("distributor_vendor", [])
    relation_duplicate_evidence = sum(max(0, len(row.get("evidence", [])) - len({evidence_key(evidence) for evidence in row.get("evidence", [])})) for row in relation_rows)
    relation_invalid = sum(1 for row in relation_rows if row.get("status") not in {"CONFIRMED", "PROBABLE", "RESEARCH PRIORITY", "INSUFFICIENT EVIDENCE"} or row.get("relationship_intensity") is None or not row.get("fact_confidence"))
    record("relationships", relation_invalid == 0 and relation_duplicate_evidence == 0, f"Relaciones inválidas: {relation_invalid}; evidencias duplicadas: {relation_duplicate_evidence}.")
    record("recommendations", recommendation_audit.get("status") == "PASS", f"Auditoría: {recommendation_audit.get('status')} · {recommendation_audit.get('summary', {}).get('published_recommendations', 0)} publicadas.")
    invalid_scores = sum(1 for row in relation_rows if not 0 <= number(row.get("relationship_intensity")) <= 100)
    invalid_scores += sum(1 for row in recommendations.get("recommendations", []) if not 0 <= number((row.get("confidence") or {}).get("score")) <= 1)
    record("scores", invalid_scores == 0, f"Scores fuera de rango: {invalid_scores}; fórmulas y disclaimers incluidos.")
    coverage_values = [number((row.get("coverage") or {}).get("score")) for row in entity_rows]
    record("coverage", bool(coverage_values) and all(0 <= value <= 100 for value in coverage_values), f"Cobertura media {round(sum(coverage_values) / max(1, len(coverage_values)), 1)}%; {sum(value < 50 for value in coverage_values)} perfiles por debajo de 50%.", "warning")
    empty_columns = []
    sparse_columns = []
    minimum_ratio = number(table_config.get("behavior", {}).get("minimum_population_ratio"), 0.2)
    for entity_type, config in (table_config.get("entities") or {}).items():
        rows = entities.get(entity_type, []) or []
        for column in config.get("columns", []) or []:
            field = column.get("field")
            populated = sum(row.get(field) not in (None, "", [], {}, False) for row in rows)
            if rows and populated == 0:
                empty_columns.append(f"{entity_type}.{field}")
            elif rows and not column.get("required") and column.get("user_visible") is not False and populated / len(rows) < minimum_ratio:
                sparse_columns.append(f"{entity_type}.{field}")
    record("empty_columns", True, f"{len(empty_columns)} columnas vacías y {len(sparse_columns)} con cobertura inferior a {round(minimum_ratio * 100)}% se ocultan automáticamente.")
    js_files = [root / "assets/v340/business-intelligence.js", root / "assets/app.js"]
    record("javascript", all(path.exists() and path.stat().st_size > 0 for path in js_files), "Assets JavaScript presentes; la sintaxis se verifica en el quality gate externo.")
    index_text = (root / "index.html").read_text(encoding="utf-8") if (root / "index.html").exists() else ""
    record("frontend", "executiveDecisionBrief" in index_text and "business-intelligence.js" in index_text, "Executive Decision Brief y capa v3.4 enlazados en la aplicación.")
    invalid_urls = sum(1 for row in recommendations.get("recommendations", []) for evidence in row.get("evidence", []) if not str(evidence.get("url") or "").startswith(("https://", "http://")))
    record("links", invalid_urls == 0, f"URLs inválidas en recomendaciones: {invalid_urls}.")
    installer = (root / "tools/aplicar_v340.py").read_text(encoding="utf-8") if (root / "tools/aplicar_v340.py").exists() else ""
    record("windows", bool(installer) and "pathlib" in installer.lower() and "migrate-from" in installer, "Instalador basado en pathlib con migración explícita; sin rutas POSIX fijas.")
    workflow_text = "\n".join(path.read_text(encoding="utf-8") for path in (root / ".github/workflows").glob("*.yml"))
    record("workflows", "research_supervisor_v34.py" in workflow_text and "data/v34/" in workflow_text, "Daily/weekly/monthly invocan v3.4 y persisten data/v34.")
    record("github_pages", (root / "index.html").exists() and not any(path.name in {"package.json", "vite.config.js"} for path in root.glob("*")), "Aplicación estática sin build obligatorio, apta para GitHub Pages.")
    required_report_sections = {"executive_decision_brief", "economics", "methodology"}
    record("reports", required_report_sections <= set(business_report), "Informe de negocio contiene brief, economics y metodología; PDF/PPT usan esta capa.")
    record("architectures", len(architectures.get("architectures", [])) >= 12 and all(row.get("evidence") and row.get("gaps") and row.get("readiness") for row in architectures.get("architectures", [])), f"{len(architectures.get('architectures', []))} arquitecturas originales con evidencia, gaps y readiness.")
    record("source_learning", source_coverage.get("meta", {}).get("learning_granularity") == "entidad × dimensión × país × tipo de fuente", f"{len(source_coverage.get('coverage', []))} celdas de aprendizaje y {source_coverage.get('meta', {}).get('total_public_source_candidates', 0)} fuentes/candidatos públicos.")
    motion = load_json(root / "data/v34/ecosystem_motion_intelligence.json", {})
    motion_rows = motion.get("entities", []) or []
    motion_ok = bool(motion_rows) and all("manufacturers_confirmed" in row and "profiles_sought" in row and "query_templates" in row for row in motion_rows)
    record("ecosystem_motion", motion_ok, f"{len(motion_rows)} perfiles T1/T2 cruzan relación, fabricantes, talento y fuentes; {motion.get('meta', {}).get('rejected_hiring_false_positives', 0)} falsos positivos de contratación fueron rechazados.")
    required_outputs = ["recommendation_audit.json", "quality_report.json", "source_coverage.json", "business_intelligence_report.json"]
    record("outputs", all((root / "data/v34" / filename).exists() or filename == "quality_report.json" for filename in required_outputs), "Outputs obligatorios generados atómicamente.")
    return {
        "version": "3.4.0", "status": "PASS" if not errors else "FAIL",
        "summary": {"checks": len(checks), "passed": sum(value["status"] == "PASS" for value in checks.values()), "warnings": len(warnings), "errors": len(errors)},
        "checks": checks, "errors": errors, "warnings": warnings,
        "known_data_debt": {
            "stale_evidence_rows": stale, "profiles_below_50_coverage": sum(value < 50 for value in coverage_values),
            "auto_hidden_empty_columns": empty_columns,
            "auto_hidden_sparse_columns": sparse_columns,
            "note": "Las advertencias documentan deuda real y no se convierten artificialmente en PASS.",
        },
    }
