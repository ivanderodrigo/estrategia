from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

from .model import canonical, values
from .entity_resolution import resolve
from .provenance import evidence_for_relationship
from .settings import SECTIONS, VERSION
from .storage import read_json


def _load(rel: str, default: Any) -> Any:
    return deepcopy(read_json(rel, default))


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
    url = str(out.get("url") or "").strip()
    origin = str(out.get("provenance_origin") or "").strip().upper()
    source_type = str(out.get("source_type") or out.get("type") or "").strip().casefold()

    document_kind = (
        origin == "WESTCON_DOCUMENT"
        or source_type in {"westcon-document", "internal-document", "user-provided", "curated-westcon"}
    )
    typed_non_web = origin in {
        "WESTCON_DOCUMENT", "CURATED", "HISTORICAL_RECOVERED",
        "ARCHIVE_RECOVERED", "REPORT_CORROBORATION", "ARCHIVE_CORROBORATION",
        "LEGACY_UNRESOLVED",
    }
    has_public_url = url.startswith(("http://", "https://"))
    has_document_identity = bool(str(out.get("document") or out.get("document_id") or "").strip())

    if not has_public_url and not (document_kind and has_document_identity) and not typed_non_web:
        return None

    out.setdefault("source", out.get("title") or ("Westcon Comstor España" if document_kind else "Evidencia trazable"))
    out.setdefault("title", out.get("source") or "Evidencia")
    out.setdefault("date", "2026-09-01")
    out.setdefault("description", "Evidencia asociada al campo mostrado.")
    out.setdefault("scope", "ES" if document_kind else "GLOBAL")
    out.setdefault("retrieved_at", "2026-09-01")
    out.setdefault("freshness_status", "current")

    if document_kind:
        out.setdefault("source_grade", "A-WESTCON")
        out.setdefault("source_type", "westcon-document")
        out.setdefault("classification", "internal-document")
        out.setdefault("official", True)
        out.setdefault("provenance_origin", "WESTCON_DOCUMENT")
    else:
        out.setdefault("source_grade", "A" if out.get("official") else "B")
        out.setdefault("source_type", "official-domain" if out.get("official") else "public-web")
        out.setdefault("classification", "public" if has_public_url else "typed-provenance")
    return out

def _dedupe_evidence(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[tuple[str, ...], dict[str, Any]] = {}
    for row in rows:
        ev = _complete_evidence(row)
        if not ev:
            continue
        key = (
            str(ev.get("url") or ""),
            str(ev.get("title") or ""),
            str(ev.get("scope") or ""),
            str(ev.get("provenance_origin") or ev.get("source_type") or ""),
            str(ev.get("document_id") or ev.get("document") or ""),
            str(ev.get("slide") or ""),
            str(ev.get("field") or ""),
            str(ev.get("item_value") or ""),
            str(ev.get("historical_commit") or ev.get("archive_version") or ""),
        )
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
            key = canonical(raw)
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
    old_values = values(out.get("value"))
    new_values = values(spec.get("value"))
    old_evidence = _dedupe_evidence(out.get("evidence") or [])
    new_evidence = _dedupe_evidence(spec.get("evidence") or [])
    out["value"] = _merge_values(out.get("value"), spec.get("value"))
    out["evidence"] = _dedupe_evidence(old_evidence + new_evidence)
    _decorate(
        out,
        confidence=spec.get("confidence"),
        claim_type=spec.get("claim_type"),
        assertion_status=spec.get("assertion_status"),
        qualifier=spec.get("qualifier"),
    )
    if isinstance(out.get("value"), list):
        previous = {canonical(x.get("value")): x for x in out.get("items") or [] if isinstance(x, dict)}
        if len(old_values) == 1 and canonical(old_values[0]) not in previous:
            previous[canonical(old_values[0])] = {"value": old_values[0], "evidence": old_evidence}
        supplied = {
            canonical(item.get("value")): item
            for item in spec.get("items") or []
            if isinstance(item, dict) and canonical(item.get("value"))
        }
        new_keys = {canonical(value) for value in new_values}
        items = []
        for value in out["value"]:
            key = canonical(value)
            item = deepcopy(previous.get(key, {"value": value}))
            item["value"] = value
            item_spec = supplied.get(key) or {}
            evidence_to_add = item_spec.get("evidence") or (new_evidence if key in new_keys else [])
            item["evidence"] = _dedupe_evidence((item.get("evidence") or []) + evidence_to_add)
            _decorate(
                item,
                confidence=item_spec.get("confidence", spec.get("confidence")),
                claim_type=item_spec.get("claim_type", spec.get("claim_type")),
                assertion_status=item_spec.get("assertion_status", spec.get("assertion_status")),
                qualifier=item_spec.get("qualifier", spec.get("qualifier")),
            )
            items.append(item)
        out["items"] = items
    return out


def itemized_field(
    rows: Iterable[dict[str, Any]],
    *,
    confidence: float,
    claim_type: str,
    assertion_status: str,
    qualifier: str = "",
) -> dict[str, Any]:
    """Build a list field whose evidence remains attached to each value."""

    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for raw in rows:
        value = str(raw.get("value") or "").strip()
        key = canonical(value)
        if not key:
            continue
        if key not in merged:
            merged[key] = {
                "value": value,
                "evidence": [],
                "confidence": raw.get("confidence", confidence),
                "claim_type": raw.get("claim_type", claim_type),
                "assertion_status": raw.get("assertion_status", assertion_status),
                "qualifier": raw.get("qualifier", qualifier),
            }
            order.append(key)
        merged[key]["evidence"] = _dedupe_evidence(
            (merged[key].get("evidence") or []) + (raw.get("evidence") or [])
        )

    items = []
    for key in order:
        item = merged[key]
        _decorate(
            item,
            confidence=item.get("confidence"),
            claim_type=item.get("claim_type"),
            assertion_status=item.get("assertion_status"),
            qualifier=item.get("qualifier"),
        )
        items.append(item)
    evidence = _dedupe_evidence(
        evidence
        for item in items
        for evidence in item.get("evidence") or []
    )
    field = {
        "value": [item["value"] for item in items],
        "items": items,
        "evidence": evidence,
    }
    return _decorate(
        field,
        confidence=confidence,
        claim_type=claim_type,
        assertion_status=assertion_status,
        qualifier=qualifier,
    )


def normalize_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize list-valued fields once so the UI/graph do not carry legacy duplicates.

    Relation display values intentionally drop old scope/status suffixes: scope and confidence
    live in evidence/graph metadata, not in the entity name.
    """
    for section in SECTIONS:
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
                    item_key = canonical(item)
                    if field_id in {"vendor_relations", "distributors", "integrators"} and item_key == canonical(row.get("name")):
                        continue
                    if field_id in {"vendor_relations", "distributors", "integrators", "westcon_overlap", "competitor_vendor_overlap"} and any(
                        phrase in item_key
                        for phrase in (
                            "sin coincidencias", "sin otros fabricantes", "sin fabricantes",
                            "no equivale", "line card puede no ser", "linecard completo por validar",
                            "mas de marcas", "marcas nacionales", "hardware y software de marcas",
                        )
                    ):
                        continue
                    key = canonical(item)
                    if key and key not in seen:
                        seen.add(key); out.append(item)
                field["value"] = out
                items = []
                item_seen = set()
                field_evidence = _dedupe_evidence(field.get("evidence") or [])
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
                    existing = _dedupe_evidence(x.get("evidence") or [])
                    specific = evidence_for_relationship(existing, row.get("name"), iv)
                    # A single source already attached to this exact item is an atomic
                    # assertion even when its title is terse. Multiple legacy sources must
                    # be scope-filtered because old releases copied whole-field provenance.
                    if not specific and len(existing) == 1:
                        specific = existing
                    if not specific:
                        specific = evidence_for_relationship(field_evidence, row.get("name"), iv)
                    if not specific and len(out) == 1 and len(field_evidence) == 1:
                        specific = field_evidence
                    x["evidence"] = _dedupe_evidence(specific)
                    items.append(x)
                for missing_value in out:
                    missing_key = canonical(missing_value)
                    if missing_key in item_seen:
                        continue
                    specific = evidence_for_relationship(field_evidence, row.get("name"), missing_value)
                    if not specific and len(out) == 1 and len(field_evidence) == 1:
                        specific = field_evidence
                    items.append({"value": missing_value, "evidence": _dedupe_evidence(specific)})
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
        for target, alias_rows in aliases.items():
            mapped = result.get(canonical(target))
            if not mapped:
                continue
            for alias in alias_rows if isinstance(alias_rows, list) else [alias_rows]:
                result[canonical(alias)] = mapped
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
            relation_items = {
                canonical(item.get("value")): item
                for item in vendor_field.get("items") or []
                if isinstance(item, dict)
            }
            overlap: list[dict[str, Any]] = []
            non_westcon: list[dict[str, Any]] = []
            for name in names:
                mapped = westcon.get(canonical(name))
                source_item = relation_items.get(canonical(name)) or {}
                atomic_evidence = source_item.get("evidence") or []
                if mapped:
                    overlap.append({"value": mapped, "evidence": atomic_evidence})
                else:
                    non_westcon.append({"value": name, "evidence": atomic_evidence})
            confidence = min(0.88, float(vendor_field.get("confidence") or 0.82))
            if overlap:
                fields["westcon_overlap"] = itemized_field(
                    overlap,
                    confidence=confidence,
                    claim_type="interpretation",
                    assertion_status="DERIVADO",
                    qualifier="Intersección calculada entre relaciones evidenciadas y portfolio Westcon; cada fabricante conserva su evidencia de origen.",
                )
            if non_westcon:
                fields["competitor_vendor_overlap"] = itemized_field(
                    non_westcon,
                    confidence=max(0.62, confidence - 0.08),
                    claim_type="interpretation",
                    assertion_status="DERIVADO",
                    qualifier="Fabricantes observados fuera del portfolio actual; el solape de canal no prueba equivalencia funcional ni amenaza comercial.",
                )
    return data


def project_graph_to_views(data: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    manufacturers = {canonical(r.get("name")): r for r in data.get("manufacturers") or []}
    integrators = {canonical(r.get("name")): r for r in data.get("integrators") or []}
    distributors = {canonical(r.get("name")): r for r in data.get("distributors") or []}
    grouped_manufacturer: dict[tuple[str, str], list[dict[str, Any]]] = {}
    integrator_scope: dict[str, list[dict[str, Any]]] = {}
    distributor_scope: dict[str, list[dict[str, Any]]] = {}
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
        elif relation == "distributes":
            distributor_scope.setdefault(canonical(rel.get("entity_a")), []).append(rel)

    for (manu_key, field_id), rels in grouped_manufacturer.items():
        row = manufacturers.get(manu_key)
        if not row:
            continue
        row.setdefault("fields", {})[field_id] = itemized_field(
            (
                {
                    "value": relation.get("entity_a"),
                    "evidence": relation.get("evidence") or [],
                    "confidence": relation.get("confidence", 0.86),
                }
                for relation in rels
            ),
            confidence=0.86,
            claim_type="fact",
            assertion_status="CONFIRMADO",
            qualifier="Vista proyectada desde el grafo canónico; cada entidad conserva solo la evidencia de su relación.",
        )

    for key, rels in integrator_scope.items():
        row = integrators.get(key)
        if not row:
            continue
        fields = row.setdefault("fields", {})
        fields["vendor_relations"] = itemized_field(
            (
                {
                    "value": relation.get("entity_b"),
                    "evidence": relation.get("evidence") or [],
                    "confidence": relation.get("confidence", 0.86),
                }
                for relation in rels
            ),
            confidence=0.86,
            claim_type="fact",
            assertion_status="CONFIRMADO",
            qualifier="Relaciones proyectadas desde el grafo; la trazabilidad se conserva por fabricante.",
        )
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

    for key, rels in distributor_scope.items():
        row = distributors.get(key)
        if not row:
            continue
        row.setdefault("fields", {})["vendor_relations"] = itemized_field(
            (
                {
                    "value": relation.get("entity_b"),
                    "evidence": relation.get("evidence") or [],
                    "confidence": relation.get("confidence", 0.88),
                }
                for relation in rels
            ),
            confidence=0.88,
            claim_type="fact",
            assertion_status="CONFIRMADO",
            qualifier="Linecard proyectado desde el grafo; cada fabricante abre únicamente sus evidencias aplicables.",
        )
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
