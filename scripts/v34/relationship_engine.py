from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from .common import age_days, clamp, dedupe_evidence, domain_of, load_json, norm, number, stable_id, unique


STATUS_LABELS = {
    "CONFIRMED": "Confirmada",
    "PROBABLE": "Probable",
    "RESEARCH PRIORITY": "Prioridad de investigación",
    "INSUFFICIENT EVIDENCE": "Evidencia insuficiente",
}

RELATION_TERMS = re.compile(
    r"partner|partnership|socio|parceiro|reseller|distributor|distribui|certif|speciali[sz]|award|premio|alliance|alianza|case.study|customer",
    re.I,
)

PARTNER_DIRECTORY_TERMS = re.compile(r"partner.?locator|find.?a.?partner|partner.?directory|partners?/find|where.?to.?buy", re.I)
PARTNERSHIP_LEVEL_TERMS = re.compile(r"\b(gold|platinum|diamond|elite|premier|advanced|select|strategic|preferred)\b.{0,35}\bpartner\b|\bpartner\b.{0,35}\b(gold|platinum|diamond|elite|premier|advanced|select|strategic|preferred)\b", re.I)
CERTIFICATION_TERMS = re.compile(r"certif|speciali[sz]|competenc|accredit|badge", re.I)
CASE_TERMS = re.compile(r"case.?stud|customer.?stor|success.?stor|caso.?de.?exito|historia.?de.?exito|cliente", re.I)


def _evidence_roles(evidence: list[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    roles = {"partner_directory": [], "partnership_level": [], "certifications_specializations": [], "customer_cases": []}
    for row in evidence:
        text = " ".join(str(row.get(key) or "") for key in ("title", "url", "source", "classification"))
        reference = {key: row.get(key) for key in ("title", "source", "url", "date", "source_type")}
        if PARTNER_DIRECTORY_TERMS.search(text):
            roles["partner_directory"].append(reference)
        if PARTNERSHIP_LEVEL_TERMS.search(text):
            roles["partnership_level"].append(reference)
        if CERTIFICATION_TERMS.search(text):
            roles["certifications_specializations"].append(reference)
        if CASE_TERMS.search(text):
            roles["customer_cases"].append(reference)
    return roles


def _entity_index(entities: Mapping[str, Any], kind: str) -> dict[str, dict[str, Any]]:
    return {norm(row.get("name")): row for row in entities.get(kind, []) or []}


def _geography(profile: Mapping[str, Any]) -> dict[str, Any]:
    scope = profile.get("scope") or ""
    countries = unique(
        operation.get("scope") or operation.get("country")
        for operation in profile.get("operations", []) or []
        if (operation.get("scope") or operation.get("country")) in {"ES", "PT", "IBERIA"}
    )
    if not countries and scope in {"ES", "PT", "IBERIA"}:
        countries = [scope]
    return {
        "scope": scope,
        "countries": countries,
        "precision": "country" if scope in {"ES", "PT"} else "iberia" if scope == "IBERIA" else "not-country-specific",
        "note": "El ámbito se conserva tal como aparece en la evidencia; Iberia no se desdobla en ES/PT sin prueba específica.",
    }


def _movement_index(root: Path, kind: str) -> dict[tuple[str, str], dict[str, Any]]:
    document = load_json(root / "data/v33/relationship_movement.json", {})
    rows = (document.get(kind) or {}).get("changes") or []
    return {(norm(row.get("entity")), norm(row.get("vendor"))): row for row in rows}


def _relation_state(
    evidence: list[Mapping[str, Any]], old_status: str, priority: float, entity_tier: str,
) -> tuple[str, dict[str, Any]]:
    domains = {domain_of(row.get("url")) or norm(row.get("source")) for row in evidence}
    domains.discard("")
    direct = [
        row for row in evidence
        if row.get("source_type") in {"primary", "primary-or-company"}
        and domain_of(row.get("url")) not in {"news.google.com", ""}
    ]
    explicit = [row for row in evidence if RELATION_TERMS.search(" ".join(str(row.get(key) or "") for key in ("title", "url", "source", "classification")))]
    current = [row for row in evidence if age_days(row.get("date")) is not None and age_days(row.get("date")) <= 1095]
    avg_confidence = sum(number(row.get("confidence"), 0.5) for row in evidence) / max(1, len(evidence))
    direct_locator = any(
        re.search(r"partner|reseller|distributor|locator|certif|award|premio", str(row.get("url") or ""), re.I)
        for row in direct
    )
    if evidence and current and explicit and (direct_locator or (len(domains) >= 2 and avg_confidence >= 0.62)):
        status = "CONFIRMED"
        rationale = "Evidencia explícita, vigente y directa o corroborada por dominios distintos."
    elif evidence:
        status = "PROBABLE"
        rationale = "Existe señal pública, pero falta actualidad, evidencia directa o corroboración independiente suficiente."
    elif "WHITESPACE" in old_status or (entity_tier in {"T1", "T2"} and priority >= 65):
        status = "RESEARCH PRIORITY"
        rationale = "No se afirma ausencia: la combinación es material y requiere verificación dirigida."
    else:
        status = "INSUFFICIENT EVIDENCE"
        rationale = "No hay evidencia suficiente para clasificar la relación; esto no demuestra que no exista."
    return status, {
        "unique_evidence": len(evidence), "source_diversity": len(domains),
        "direct_evidence": len(direct), "explicit_relation_evidence": len(explicit),
        "current_evidence": len(current), "average_evidence_confidence": round(avg_confidence, 3),
        "rationale": rationale,
    }


def _intensity(evidence: list[Mapping[str, Any]], diagnostics: Mapping[str, Any]) -> tuple[int, str]:
    if not evidence:
        return 0, "Sin evidencia de relación: intensidad no calculable; 0 no significa que no exista."
    freshness = max(
        (1.0 if age_days(row.get("date")) is not None and age_days(row.get("date")) <= 365 else
         0.75 if age_days(row.get("date")) is not None and age_days(row.get("date")) <= 1095 else
         0.45 if age_days(row.get("date")) is not None else 0.3)
        for row in evidence
    )
    diversity = min(1.0, number(diagnostics.get("source_diversity")) / 3)
    count = min(1.0, number(diagnostics.get("unique_evidence")) / 4)
    direct = min(1.0, number(diagnostics.get("direct_evidence")) / 2)
    explicit = min(1.0, number(diagnostics.get("explicit_relation_evidence")) / 2)
    roles = _evidence_roles(evidence)
    directory_level = min(1.0, (len(roles["partner_directory"]) + len(roles["partnership_level"])) / 2)
    certification = min(1.0, len(roles["certifications_specializations"]) / 2)
    customer_case = min(1.0, len(roles["customer_cases"]) / 2)
    value = round(100 * (0.18 * freshness + 0.14 * diversity + 0.12 * count + 0.16 * direct + 0.10 * explicit + 0.12 * directory_level + 0.10 * certification + 0.08 * customer_case))
    formula = "18% actualidad + 14% diversidad + 12% evidencias únicas + 16% evidencia directa + 10% explicitud + 12% directorio/nivel + 10% certificaciones/especializaciones + 8% casos de éxito"
    return value, formula


def _fact_confidence(status: str, evidence: list[Mapping[str, Any]], diagnostics: Mapping[str, Any]) -> dict[str, Any]:
    if not evidence:
        score = 0.0
    else:
        base = max(number(row.get("confidence"), 0.5) for row in evidence)
        score = min(0.96, base + min(0.12, number(diagnostics.get("source_diversity")) * 0.04) + min(0.10, number(diagnostics.get("direct_evidence")) * 0.05))
    band = "alta" if score >= 0.82 else "media" if score >= 0.62 else "baja"
    return {
        "score": round(score, 3), "band": band,
        "explanation": f"Confianza en la existencia de la relación ({status}); separada de su intensidad comercial.",
    }


def _convert_rows(root: Path, entities: Mapping[str, Any], kind: str) -> tuple[list[dict[str, Any]], dict[str, int]]:
    is_integrator = kind == "integrator"
    filename = "integrator_vendor_matrix.json" if is_integrator else "distributor_vendor_matrix.json"
    collection = "integrators" if is_integrator else "distributors"
    name_key = "integrator" if is_integrator else "distributor"
    profiles = _entity_index(entities, collection)
    movement = _movement_index(root, kind)
    rows: list[dict[str, Any]] = []
    removed_duplicates = 0
    for raw in load_json(root / "data/v33" / filename, {}).get("rows", []) or []:
        profile = profiles.get(norm(raw.get(name_key)))
        if not profile:
            continue
        evidence, removed = dedupe_evidence(raw.get("evidence") or [])
        removed_duplicates += removed
        status, diagnostics = _relation_state(
            evidence, str(raw.get("status") or ""), number(raw.get("priority_score")), str(profile.get("entity_tier") or "T3"),
        )
        intensity, formula = _intensity(evidence, diagnostics)
        evidence_roles = _evidence_roles(evidence)
        relation_move = movement.get((norm(raw.get(name_key)), norm(raw.get("vendor"))))
        rows.append({
            "relationship_id": stable_id("rel", kind, raw.get(name_key), raw.get("vendor")),
            "relationship_type": "integrator-vendor" if is_integrator else "distributor-vendor",
            name_key: raw.get(name_key), "vendor": raw.get("vendor"),
            "status": status, "status_label": STATUS_LABELS[status],
            "relationship_intensity": intensity,
            "intensity_formula": formula,
            "fact_confidence": _fact_confidence(status, evidence, diagnostics),
            "geography": _geography(profile),
            "technology_fit": raw.get("technology_fit") or [],
            "priority_score": raw.get("priority_score"),
            "entity_tier": profile.get("entity_tier"),
            "westcon_relevance": profile.get("westcon_relevance"),
            "last_verified": max((str(row.get("date") or "") for row in evidence), default=""),
            "evidence": evidence,
            "relationship_evidence": evidence_roles,
            "partnership_level_evidence": evidence_roles["partnership_level"],
            "certification_specialization_evidence": evidence_roles["certifications_specializations"],
            "customer_case_evidence": evidence_roles["customer_cases"],
            "evidence_diagnostics": diagnostics,
            "change_recent": relation_move or None,
            "next_research": (
                "Revalidar alcance, país y nivel de partnership en fuente primaria." if status == "CONFIRMED" else
                "Buscar partner locator, certificación o caso oficial vigente y una fuente independiente." if status == "PROBABLE" else
                "Comprobar directorio oficial, certificaciones y casos por ES/PT; registrar también evidencia negativa de búsqueda." if status == "RESEARCH PRIORITY" else
                "Mantener en cola selectiva; ausencia pública no equivale a ausencia de relación."
            ),
            "caution": "La intensidad mide la riqueza de la evidencia pública, no ventas, pipeline ni volumen de negocio.",
            "provenance": {
                "derived_from": f"data/v33/{filename}",
                "deduplication_key": "URL; si falta, título + fuente + fecha",
                "status_and_intensity_separated": True,
            },
        })
    rows.sort(key=lambda row: (
        {"CONFIRMED": 4, "PROBABLE": 3, "RESEARCH PRIORITY": 2, "INSUFFICIENT EVIDENCE": 1}[row["status"]],
        number(row.get("priority_score")), number(row.get("relationship_intensity")),
    ), reverse=True)
    return rows, {"duplicate_evidence_removed": removed_duplicates}


def build_relationships(root: Path, entities: Mapping[str, Any]) -> dict[str, Any]:
    integrator_rows, integrator_metrics = _convert_rows(root, entities, "integrator")
    distributor_rows, distributor_metrics = _convert_rows(root, entities, "distributor")
    all_rows = integrator_rows + distributor_rows
    return {
        "meta": {
            "version": "3.4.0", "rows": len(all_rows),
            "status_distribution": dict(Counter(row["status"] for row in all_rows)),
            "duplicate_evidence_removed": integrator_metrics["duplicate_evidence_removed"] + distributor_metrics["duplicate_evidence_removed"],
            "principle": "Estado, intensidad y confianza son variables independientes. Falta de evidencia nunca se convierte en relación inexistente.",
        },
        "integrator_vendor": integrator_rows,
        "distributor_vendor": distributor_rows,
    }
