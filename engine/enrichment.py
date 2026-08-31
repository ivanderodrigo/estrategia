from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

from .model import canonical, values
from .entity_resolution import resolve

ROOT = Path(__file__).resolve().parents[1]
VERSION = "3.20.0"


def _load(rel: str, default: Any) -> Any:
    p = ROOT / rel
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return deepcopy(default)


def _band(score: float) -> str:
    return "high" if score >= 0.80 else "medium" if score >= 0.60 else "low"


def _confidence_reason(band: str, claim_type: str) -> str:
    if claim_type == "signal":
        return "Rojo: señal pública útil para orientar la investigación; no confirma por sí sola una relación comercial, despliegue o contrato."
    if band == "high":
        return "Verde: hecho respaldado por evidencia oficial/primaria suficiente y trazable."
    if band == "medium":
        return "Amarillo: evidencia útil y coherente, pero todavía requiere corroboración adicional para elevar su solidez."
    return "Rojo: evidencia limitada o indirecta; se mantiene la investigación activa."


def _complete_evidence(ev: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(ev, dict):
        return None
    out = deepcopy(ev)
    if not str(out.get("url") or "").startswith("http"):
        return None
    out.setdefault("source", out.get("title") or "Fuente pública")
    out.setdefault("title", out.get("source") or "Evidencia pública")
    out.setdefault("date", "2026-09-01")
    out.setdefault("description", "Evidencia pública asociada al campo mostrado.")
    out.setdefault("scope", "GLOBAL")
    out.setdefault("source_grade", "A" if out.get("official") else "B")
    out.setdefault("source_type", "official-domain" if out.get("official") else "public-web")
    out.setdefault("classification", "public")
    out.setdefault("retrieved_at", "2026-09-01")
    out.setdefault("freshness_status", "current")
    return out


def _dedupe_evidence(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        ev = _complete_evidence(row)
        if not ev:
            continue
        key = (str(ev.get("url")), str(ev.get("title")), str(ev.get("scope")))
        seen[key] = ev
    return list(seen.values())


def _merge_values(old: Any, new: Any) -> Any:
    if old in (None, "", [], {}):
        return deepcopy(new)
    if new in (None, "", [], {}):
        return deepcopy(old)
    if isinstance(old, list) or isinstance(new, list):
        merged = []
        seen = set()
        for raw in values(old) + values(new):
            key = canonical(raw if not isinstance(raw, dict) else json.dumps(raw, sort_keys=True, ensure_ascii=False))
            if key and key not in seen:
                seen.add(key)
                merged.append(deepcopy(raw))
        return merged
    return deepcopy(old) if canonical(old) == canonical(new) else deepcopy(new)


def _decorate(field: dict[str, Any], *, confidence: float | None = None, claim_type: str | None = None,
              assertion_status: str | None = None, qualifier: str | None = None) -> dict[str, Any]:
    claim = claim_type or str(field.get("claim_type") or "fact")
    score = float(confidence if confidence is not None else field.get("confidence") or (0.58 if claim == "signal" else 0.86))
    if claim == "signal":
        score = min(score, 0.59)
    band = _band(score)
    field["claim_type"] = claim
    if assertion_status:
        field["assertion_status"] = assertion_status
    elif claim == "signal":
        field.setdefault("assertion_status", "SEÑAL")
    elif claim == "interpretation":
        field.setdefault("assertion_status", "DERIVADO")
    else:
        field.setdefault("assertion_status", "CONFIRMADO" if band == "high" else "PROBABLE")
    field["confidence"] = round(score, 2)
    field["confidence_band"] = band
    field["fact_confidence"] = round(score, 2)
    field["interpretation_confidence"] = round(min(score, 0.72 if claim != "fact" else score), 2)
    field["action_risk"] = "alto" if band == "low" else "medio" if band == "medium" else "bajo"
    field["evidence_level"] = "strong" if band == "high" else "moderate" if band == "medium" else "weak"
    field["evidence_color"] = "green" if band == "high" else "yellow" if band == "medium" else "red"
    field["confidence_reason"] = _confidence_reason(band, claim)
    if qualifier:
        field["qualifier"] = qualifier
    return field


def merge_field(field: dict[str, Any] | None, spec: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(field or {})
    out["value"] = _merge_values(out.get("value"), spec.get("value"))
    out["evidence"] = _dedupe_evidence((out.get("evidence") or []) + (spec.get("evidence") or []))
    _decorate(
        out,
        confidence=spec.get("confidence"),
        claim_type=spec.get("claim_type"),
        assertion_status=spec.get("assertion_status"),
        qualifier=spec.get("qualifier"),
    )
    if isinstance(out.get("value"), list):
        evidence = out.get("evidence") or []
        previous = {canonical(x.get("value")): x for x in out.get("items") or [] if isinstance(x, dict)}
        items = []
        for value in out["value"]:
            item = deepcopy(previous.get(canonical(value), {"value": value}))
            item["value"] = value
            item["evidence"] = _dedupe_evidence((item.get("evidence") or []) + evidence)
            _decorate(
                item,
                confidence=spec.get("confidence"),
                claim_type=spec.get("claim_type"),
                assertion_status=spec.get("assertion_status"),
                qualifier=spec.get("qualifier"),
            )
            items.append(item)
        out["items"] = items
    return out




def normalize_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize list-valued fields once so the UI/graph do not carry legacy duplicates.

    Relation display values intentionally drop old scope/status suffixes: scope and confidence
    live in evidence/graph metadata, not in the entity name.
    """
    for section in ("manufacturers", "distributors", "integrators", "clients_public", "clients_private", "trends", "architectures"):
        for row in data.get(section) or []:
            for field_id, field in (row.get("fields") or {}).items():
                value = field.get("value")
                if not isinstance(value, list):
                    continue
                out = []
                seen = set()
                for raw in value:
                    item = deepcopy(raw)
                    if field_id in {"vendor_relations", "distributors", "integrators"} and isinstance(item, str):
                        item = resolve(item.split(" · ", 1)[0].strip())
                    key = canonical(item if not isinstance(item, dict) else json.dumps(item, sort_keys=True, ensure_ascii=False))
                    if key and key not in seen:
                        seen.add(key); out.append(item)
                field["value"] = out
                # Keep item-specific evidence only when it adds information beyond field-level provenance.
                field_keys = {(e.get("url"), e.get("title"), e.get("scope")) for e in field.get("evidence") or [] if isinstance(e, dict)}
                items = []
                item_seen = set()
                for old in field.get("items") or []:
                    if not isinstance(old, dict):
                        continue
                    iv = old.get("value")
                    if field_id in {"vendor_relations", "distributors", "integrators"} and isinstance(iv, str):
                        iv = resolve(iv.split(" · ", 1)[0].strip())
                    k = canonical(iv)
                    if not k or k in item_seen or k not in seen:
                        continue
                    item_seen.add(k)
                    x = deepcopy(old); x["value"] = iv
                    specific = [e for e in x.get("evidence") or [] if isinstance(e, dict) and (e.get("url"),e.get("title"),e.get("scope")) not in field_keys]
                    if specific: x["evidence"] = _dedupe_evidence(specific)
                    else: x.pop("evidence", None)
                    items.append(x)
                if items: field["items"] = items
                elif "items" in field: field.pop("items", None)
    return data


def apply_curated_distributors(data: dict[str, Any]) -> dict[str, Any]:
    cfg = _load("config/current/curated_distributors.json", {})
    rows = {canonical(r.get("name")): r for r in data.get("distributors") or []}
    for name, spec in cfg.items():
        row = rows.get(canonical(name))
        if not row: continue
        fields = row.setdefault("fields", {})
        source = spec.get("source") or {}
        evidence = [source] if source.get("url") else []
        mapping = {"vendors":"vendor_relations","revenue":"revenue","special":"specializations","caps":"differential_capabilities"}
        for key, field_id in mapping.items():
            val = spec.get(key)
            if val not in (None, "", [], {}):
                fields[field_id] = merge_field(fields.get(field_id), {"value":val,"evidence":evidence,"confidence":0.88 if source.get("official") else 0.72,"claim_type":"fact","assertion_status":"CONFIRMADO" if source.get("official") else "PROBABLE"})
        job = spec.get("job") or {}
        if job.get("profiles") and (job.get("source") or {}).get("url"):
            fields["job_profiles"] = merge_field(fields.get("job_profiles"), {"value":job["profiles"],"evidence":[job["source"]],"confidence":0.58,"claim_type":"signal","assertion_status":"SEÑAL"})
    return data


def apply_curated(data: dict[str, Any]) -> dict[str, Any]:
    cfg = _load("config/current/curated_intelligence.json", {"sections": {}})
    for section, entities in (cfg.get("sections") or {}).items():
        rows = {canonical(r.get("name")): r for r in data.get(section) or []}
        for entity_name, entity_spec in (entities or {}).items():
            row = rows.get(canonical(entity_name))
            if not row:
                continue
            row.setdefault("fields", {})
            for field_id, field_spec in (entity_spec.get("fields") or {}).items():
                row["fields"][field_id] = merge_field(row["fields"].get(field_id), field_spec)
            row["evidence"] = _dedupe_evidence((row.get("evidence") or []) + (entity_spec.get("evidence") or []))
    return data


def _manufacturer_map(data: dict[str, Any]) -> dict[str, str]:
    result = {}
    for row in data.get("manufacturers") or []:
        name = str(row.get("name") or "")
        result[canonical(name)] = name
        if "/" in name:
            for part in name.split("/"):
                result[canonical(part)] = name
    aliases = _load("config/current/entity_aliases.json", {})
    if isinstance(aliases, dict):
        for alias, target in aliases.items():
            if canonical(target) in result:
                result[canonical(alias)] = result[canonical(target)]
    return result


def _relation_names(field: dict[str, Any]) -> list[str]:
    result = []
    for raw in values(field.get("value")):
        text = str(raw or "").strip()
        if not text:
            continue
        text = text.split(" · ", 1)[0].strip()
        if text and not any(x in canonical(text) for x in ("sin otros fabricantes", "catalogo", "más de", "mas de")):
            result.append(resolve(text))
    return list(dict.fromkeys(result))


def derive_overlap_fields(data: dict[str, Any]) -> dict[str, Any]:
    westcon = _manufacturer_map(data)
    for section in ("distributors", "integrators"):
        for row in data.get(section) or []:
            fields = row.setdefault("fields", {})
            vendor_field = fields.get("vendor_relations") or {}
            names = _relation_names(vendor_field)
            if not names:
                continue
            overlap = []
            non_westcon = []
            for name in names:
                mapped = westcon.get(canonical(name))
                if mapped:
                    if mapped not in overlap:
                        overlap.append(mapped)
                elif name not in non_westcon:
                    non_westcon.append(name)
            evidence = _dedupe_evidence(vendor_field.get("evidence") or [])
            confidence = min(0.88, float(vendor_field.get("confidence") or 0.82))
            if overlap:
                fields["westcon_overlap"] = merge_field(fields.get("westcon_overlap"), {
                    "value": overlap,
                    "evidence": evidence,
                    "confidence": confidence,
                    "claim_type": "interpretation",
                    "assertion_status": "DERIVADO",
                    "qualifier": "Intersección calculada automáticamente entre relaciones de fabricante evidenciadas y el portfolio Westcon Iberia; no añade una relación nueva.",
                })
            if non_westcon:
                fields["competitor_vendor_overlap"] = merge_field(fields.get("competitor_vendor_overlap"), {
                    "value": non_westcon,
                    "evidence": evidence,
                    "confidence": max(0.62, confidence - 0.08),
                    "claim_type": "interpretation",
                    "assertion_status": "DERIVADO",
                    "qualifier": "Fabricantes observados fuera del portfolio Westcon actual. 'Posible competencia' describe solape de canal, no equivalencia funcional ni amenaza comercial demostrada.",
                })
    return data


def project_graph_to_views(data: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    manufacturers = {canonical(r.get("name")): r for r in data.get("manufacturers") or []}
    integrators = {canonical(r.get("name")): r for r in data.get("integrators") or []}
    grouped_manufacturer: dict[tuple[str, str], list[dict[str, Any]]] = {}
    integrator_scope: dict[str, list[dict[str, Any]]] = {}
    for rel in graph.get("relationships") or []:
        relation = rel.get("relation")
        if relation not in {"distributes", "partners_with"} or rel.get("status") != "CONFIRMADO":
            continue
        manu = manufacturers.get(canonical(rel.get("entity_b")))
        if manu:
            key = (canonical(rel.get("entity_b")), "distributors" if relation == "distributes" else "integrators")
            grouped_manufacturer.setdefault(key, []).append(rel)
        if relation == "partners_with":
            integrator_scope.setdefault(canonical(rel.get("entity_a")), []).append(rel)

    for (manu_key, field_id), rels in grouped_manufacturer.items():
        row = manufacturers.get(manu_key)
        if not row:
            continue
        vals = [str(r.get("entity_a") or "") for r in rels if r.get("entity_a")]
        evidence = _dedupe_evidence(e for r in rels for e in (r.get("evidence") or []))
        row.setdefault("fields", {})[field_id] = merge_field(row.get("fields", {}).get(field_id), {
            "value": vals,
            "evidence": evidence,
            "confidence": 0.86,
            "claim_type": "fact",
            "assertion_status": "CONFIRMADO",
            "qualifier": "Vista proyectada desde el grafo canónico de relaciones; la evidencia se mantiene en la relación de origen.",
        })

    for key, rels in integrator_scope.items():
        row = integrators.get(key)
        if not row:
            continue
        fields = row.setdefault("fields", {})
        evidence = _dedupe_evidence(e for r in rels for e in (r.get("evidence") or []))
        countries = []
        for rel in rels:
            for c in rel.get("countries") or []:
                if c in {"ES", "PT", "IBERIA"} and c not in countries:
                    countries.append(c)
        if countries and not (fields.get("scope") or {}).get("value"):
            fields["scope"] = merge_field(fields.get("scope"), {
                "value": " + ".join(countries),
                "evidence": evidence,
                "confidence": 0.84,
                "claim_type": "interpretation",
                "assertion_status": "DERIVADO",
                "qualifier": "Ámbito derivado únicamente de relaciones geográficamente evidenciadas; no pretende describir toda la presencia de la entidad.",
            })
        if not (fields.get("roles") or {}).get("value"):
            fields["roles"] = merge_field(fields.get("roles"), {
                "value": ["Partner / integrador"],
                "evidence": evidence,
                "confidence": 0.82,
                "claim_type": "fact",
                "assertion_status": "CONFIRMADO",
            })
    return data


def derive_secondary_views(data: dict[str, Any]) -> dict[str, Any]:
    westcon = _manufacturer_map(data)
    for row in data.get("trends") or []:
        fields = row.setdefault("fields", {})
        if (fields.get("westcon_vendors") or {}).get("value"):
            continue
        market = fields.get("market_players") or {}
        vals = []
        for name in _relation_names(market):
            mapped = westcon.get(canonical(name))
            if mapped and mapped not in vals:
                vals.append(mapped)
        if vals:
            fields["westcon_vendors"] = merge_field(fields.get("westcon_vendors"), {
                "value": vals,
                "evidence": market.get("evidence") or [],
                "confidence": 0.70,
                "claim_type": "interpretation",
                "assertion_status": "DERIVADO",
                "qualifier": "Intersección descriptiva entre actores mencionados en las fuentes de la tendencia y el portfolio Westcon; no implica liderazgo ni recomendación.",
            })
    for row in data.get("architectures") or []:
        fields = row.setdefault("fields", {})
        if (fields.get("vendors") or {}).get("value"):
            continue
        layers = fields.get("layers") or {}
        names = []
        for layer in values(layers.get("value")):
            if isinstance(layer, dict):
                for name in layer.get("vendors") or []:
                    mapped = westcon.get(canonical(name)) or str(name)
                    if mapped not in names:
                        names.append(mapped)
        if names:
            fields["vendors"] = merge_field(fields.get("vendors"), {
                "value": names,
                "evidence": layers.get("evidence") or [],
                "confidence": 0.78,
                "claim_type": "interpretation",
                "assertion_status": "DERIVADO",
                "qualifier": "Proyección de los fabricantes ya mapeados por capa; compartir capa no prueba integración certificada entre fabricantes.",
            })
    return data
