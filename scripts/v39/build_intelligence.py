#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]

from v38.build_intelligence import (
    build_architectures,
    build_ecosystem,
    build_manufacturers,
    build_trends,
    dedupe_evidence,
    evidence,
    field,
    load,
    merge_source_catalog as merge_source_catalog_v38,
    write,
    SCHEMAS as BASE_SCHEMAS,
)

CLIENT_FIELD_QUALIFIERS = {
    "scope": "Ámbito geográfico explícito de la cuenta u oportunidad observado en la evidencia enlazada.",
    "entity_type": "Clasificación de la entidad pública desde la óptica comercial/opportunity management.",
    "request_or_need": "Necesidad pública interpretada desde pliegos, perfiles de contratación, programas o estrategia digital.",
    "opportunity_area": "Áreas tecnológicas relevantes para Westcon asociadas a la oportunidad. La presencia no implica adjudicación.",
    "estimated_amount": "Importe observado o estimado a partir de anuncios, lotes o documentación pública trazable.",
    "milestone_date": "Fecha observada o ventana temporal útil para priorizar seguimiento comercial.",
    "procurement_stage": "Fase de la oportunidad pública observada en fuentes oficiales o semioficiales.",
    "technology_signals": "Tecnologías o ámbitos funcionales mencionados por la fuente. Orientan el encaje de portfolio.",
    "westcon_fit": "Encaje funcional con portfolio Westcon. Es descriptivo, no una recomendación ni una garantía de oportunidad.",
    "opportunity_notes": "Lectura comercial descriptiva basada en la evidencia disponible.",
    "segment": "Sector o segmento de la gran cuenta privada observado en fuentes corporativas.",
    "account_priority": "Clasificación descriptiva para priorización comercial; no implica decisión automática.",
    "hiring_signals": "Señales procedentes de portales de empleo y carreras; indican foco y skills buscados, nunca despliegue confirmado por sí solo.",
    "renewal_window": "Ventana o ritmo esperable de renovación/compra a partir de señales públicas.",
}

CLIENT_SCHEMAS = {
    "clients_public": [
        {"id": "scope", "label": "País", "help": "España o Portugal, según la oportunidad pública observada.", "clarify": True},
        {"id": "entity_type", "label": "Tipo de entidad", "help": "Administración local, autonómica, salud, educación u otro organismo público.", "clarify": True},
        {"id": "request_or_need", "label": "Petición / necesidad", "help": "Necesidad pública derivada de pliego, estrategia digital, contrato o actividad observada.", "clarify": True},
        {"id": "opportunity_area", "label": "Área Westcon", "help": "Áreas de negocio relacionadas con la oportunidad: ciberseguridad, networking, cloud, identity, etc.", "clarify": True},
        {"id": "estimated_amount", "label": "Monto", "help": "Importe observado o estimado desde fuentes trazables; no todos los expedientes publican el mismo nivel de detalle.", "clarify": True},
        {"id": "milestone_date", "label": "Fecha / hito", "help": "Fecha relevante para seguimiento: publicación, adjudicación esperada o ventana de renovación.", "clarify": True},
        {"id": "procurement_stage", "label": "Estado", "help": "Situación de la oportunidad: planificado, abierto, recurrente, renovación, etc.", "clarify": True},
        {"id": "technology_signals", "label": "Señales tecnológicas", "help": "Tecnologías o capacidades citadas por la fuente o inferidas descriptivamente desde el contexto público.", "clarify": True},
        {"id": "westcon_fit", "label": "Encaje portfolio Westcon", "help": "Fabricantes o capacidades del portfolio con encaje funcional frente a la oportunidad.", "clarify": True},
        {"id": "opportunity_notes", "label": "Lectura comercial", "help": "Contexto adicional útil para tratar la fila como oportunidad, siempre apoyado en evidencia trazable.", "clarify": True},
    ],
    "clients_private": [
        {"id": "scope", "label": "País", "help": "España o Portugal, según la gran cuenta objetivo.", "clarify": True},
        {"id": "segment", "label": "Segmento", "help": "Sector o industria de la gran cuenta privada.", "clarify": True},
        {"id": "account_priority", "label": "Prioridad de cuenta", "help": "Priorización descriptiva para Westcon según tamaño, afinidad y densidad de señales públicas.", "clarify": True},
        {"id": "technology_signals", "label": "Señales tecnológicas", "help": "Tecnologías compatibles o del mismo ámbito observadas en webs corporativas, empleo y otras fuentes públicas.", "clarify": True},
        {"id": "hiring_signals", "label": "Perfiles / skills buscados", "help": "Perfiles y skills publicados en portales de empleo que ayudan a detectar foco tecnológico.", "clarify": True},
        {"id": "renewal_window", "label": "Ventana de renovación", "help": "Ritmo o ventana probable de compra o renovación deducida desde señales públicas.", "clarify": True},
        {"id": "westcon_fit", "label": "Encaje portfolio Westcon", "help": "Fabricantes o capacidades de Westcon con mayor compatibilidad funcional con las señales observadas.", "clarify": True},
        {"id": "opportunity_notes", "label": "Lectura comercial", "help": "Comentario descriptivo para tratar la cuenta como oportunidad; no es una recomendación automática.", "clarify": True},
    ],
}


def merge_source_catalog() -> list[dict[str, Any]]:
    rows = {item.get("id"): dict(item) for item in merge_source_catalog_v38()}
    for raw in load("config/v39/source_additions.json", {}).get("sources", []) or []:
        sid = raw.get("source_id") or raw.get("id")
        if not sid:
            continue
        rows[sid] = {
            "id": sid,
            "name": raw.get("name"),
            "url": raw.get("url"),
            "class": raw.get("source_class") or raw.get("class"),
            "scope": raw.get("scope") or [],
            "dimensions": raw.get("dimensions") or [],
            "access_policy": raw.get("access_policy"),
        }
    return sorted(rows.values(), key=lambda x: (str(x.get("class") or ""), str(x.get("name") or "")))


def _seed_evidence(rows: list[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    out = []
    for row in rows or []:
        item = evidence(dict(row))
        if item:
            out.append(item)
    return dedupe_evidence(out, 12)


def _client_field(field_id: str, raw: Mapping[str, Any]) -> dict[str, Any] | None:
    value = raw.get("value")
    sources = _seed_evidence(raw.get("sources") or [])
    qualifier = raw.get("qualifier") or CLIENT_FIELD_QUALIFIERS.get(field_id)
    confidence = raw.get("confidence")
    return field(value, sources, confidence, qualifier)


def build_clients(kind: str) -> list[dict[str, Any]]:
    seeds = load("config/v39/client_intelligence_seeds.json", {})
    rows = []
    for idx, entry in enumerate(seeds.get(kind, []) or [], start=1):
        built_fields: dict[str, Any] = {}
        identity_sources = []
        for field_id, spec in (entry.get("fields") or {}).items():
            built = _client_field(field_id, dict(spec))
            if built:
                built_fields[field_id] = built
                identity_sources.extend(built.get("evidence") or [])
        identity = dedupe_evidence(identity_sources, 10)
        if not identity:
            continue
        prefix = "pub" if kind == "public" else "priv"
        rows.append({
            "id": f"{prefix}-client-{idx:02d}",
            "name": entry.get("name"),
            "evidence": identity,
            "fields": built_fields,
        })
    return rows


SCHEMAS = copy.deepcopy(BASE_SCHEMAS)
SCHEMAS.update(CLIENT_SCHEMAS)


def build() -> dict[str, Any]:
    sources = merge_source_catalog()
    return {
        "meta": {
            "version": "3.9.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "scope": "España + Portugal",
            "principle": "Inteligencia de negocio descriptiva para Fabricantes, Mayoristas, Integradores, Clientes, Tendencias y Arquitecturas.",
            "traceability": "Cada campo visible conserva la evidencia específica que sostiene el dato; la lectura comercial propia se identifica como síntesis interna trazable.",
            "source_count": len(sources),
        },
        "schemas": SCHEMAS,
        "manufacturers": build_manufacturers(),
        "distributors": build_ecosystem("distributor"),
        "integrators": build_ecosystem("integrator"),
        "clients_public": build_clients("public"),
        "clients_private": build_clients("private"),
        "trends": build_trends(),
        "architectures": build_architectures(),
        "source_catalog": sources,
    }


if __name__ == "__main__":
    data = build()
    write("data/v39/intelligence.json", data)
    legacy_gaps = load("data/v38/research_gaps.json", {}) or {}
    traceable_fields = sum(
        1
        for section in ("manufacturers", "distributors", "integrators", "clients_public", "clients_private", "trends", "architectures")
        for row in data.get(section, [])
        for value in (row.get("fields") or {}).values()
        if value and value.get("evidence")
    )
    write("data/v39/research_gaps.json", {
        **legacy_gaps,
        "version": "3.9.0",
        "note": "La cola interna v3.9.0 hereda la investigación de v3.8 y amplía el universo de clientes públicos y privados.",
    })
    write("data/v39/last_run.json", {
        "version": "3.9.0",
        "generated_at": data["meta"]["generated_at"],
        "finished_at": data["meta"]["generated_at"],
        "profile": "snapshot",
        "status": "published",
        "manufacturers": len(data["manufacturers"]),
        "distributors": len(data["distributors"]),
        "integrators": len(data["integrators"]),
        "clients": len(data["clients_public"]) + len(data["clients_private"]),
        "clients_public": len(data["clients_public"]),
        "clients_private": len(data["clients_private"]),
        "trends": len(data["trends"]),
        "architectures": len(data["architectures"]),
        "source_count": len(data["source_catalog"]),
        "traceable_fields": traceable_fields,
        "research_gaps": legacy_gaps.get("total_gaps", 0),
        "high_priority_research_gaps": legacy_gaps.get("high_priority_gaps", 0),
    })
    print(json.dumps(load("data/v39/last_run.json", {}), ensure_ascii=False))
