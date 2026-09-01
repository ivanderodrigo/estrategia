"""Canonical evidence graph with item-level provenance."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from .entity_resolution import resolve
from .model import canonical, stable_id, values
from .provenance import evidence_for_relationship
from .settings import VERSION
from .storage import read_json


def _target(name: Any) -> str:
    text = str(name or "").strip()
    return re.split(
        r"\s+·\s+(?:Confirmada|Probable|Señal|Evidencia|ES|PT|IBERIA)",
        text,
        maxsplit=1,
        flags=re.I,
    )[0].strip()


def _scopes(country: Any) -> list[str]:
    raw = str(country or "GLOBAL").upper().replace("+", "/").replace(",", "/")
    result = []
    for part in re.split(r"[/; ]+", raw):
        if part in {"ES", "PT", "IBERIA", "GLOBAL"} and part not in result:
            result.append(part)
    return result or ["GLOBAL"]


def _clean_evidence(rows: Any) -> list[dict[str, Any]]:
    output: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows or []:
        if not isinstance(row, dict) or not row.get("url") or not row.get("source"):
            continue
        key = (str(row.get("url")), str(row.get("title") or ""), str(row.get("scope") or ""))
        output[key] = row
    return list(output.values())


def _item_evidence(field: dict[str, Any], value: Any) -> list[dict[str, Any]]:
    key = canonical(_target(value))
    for item in field.get("items") or []:
        if isinstance(item, dict) and canonical(_target(item.get("value"))) == key:
            return _clean_evidence(item.get("evidence") or [])
    field_values = values(field.get("value"))
    return _clean_evidence(field.get("evidence") or []) if len(field_values) == 1 else []


def build_graph(data: dict[str, Any]) -> dict[str, Any]:
    entities: dict[tuple[str, str], dict[str, Any]] = {}
    relationships: dict[tuple[str, str, str], dict[str, Any]] = {}

    def entity(kind: str, name: Any, country: Any = "") -> dict[str, Any]:
        canonical_name = resolve(_target(name))
        key = (kind, canonical(canonical_name))
        if key not in entities:
            entities[key] = {
                "id": stable_id(kind, canonical_name),
                "canonical_name": canonical_name,
                "entity_type": kind,
                "country": country,
                "aliases": [],
                "historical_names": [],
            }
        return entities[key]

    def add(
        source_kind: str,
        source_name: Any,
        relation: str,
        target_kind: str,
        target_name: Any,
        country: Any,
        evidence: Any,
        status: str = "CONFIRMADO",
        confidence: float = 0.84,
        derived: bool = False,
        validity: str = "current",
    ) -> None:
        source_name = resolve(_target(source_name))
        target_name = resolve(_target(target_name))
        if not source_name or not target_name or canonical(source_name) == canonical(target_name):
            return
        clean = _clean_evidence(evidence)
        if relation in {"distributes", "partners_with"}:
            clean = evidence_for_relationship(clean, source_name, target_name)
        if not clean:
            return
        source = entity(source_kind, source_name, country)
        target = entity(target_kind, target_name, country)
        key = (source["id"], relation, target["id"])
        scopes = _scopes(country)
        status = "CONFIRMADO" if status == "CONFIRMED" else status
        if key not in relationships:
            relationships[key] = {
                "id": "rel_" + stable_id("relation", "|".join(key))[5:],
                "entity_a_id": source["id"],
                "entity_a": source_name,
                "relation": relation,
                "entity_b_id": target["id"],
                "entity_b": target_name,
                "countries": scopes,
                "country": " + ".join(scopes),
                "evidence": clean,
                "source": clean[0].get("source"),
                "date": max(str(row.get("date") or "") for row in clean),
                "confidence": confidence,
                "status": status,
                "validity": validity or "current",
                "derived": derived,
            }
            return
        item = relationships[key]
        item["countries"] = list(dict.fromkeys((item.get("countries") or []) + scopes))
        item["country"] = " + ".join(item["countries"])
        item["evidence"] = _clean_evidence((item.get("evidence") or []) + clean)
        item["confidence"] = max(float(item.get("confidence") or 0), float(confidence or 0))
        if status == "CONFIRMADO":
            item["status"] = status
        item["derived"] = bool(item.get("derived")) and bool(derived)

    seed = read_json("config/current/relationship_seed.json", {"relationships": []})
    relation_kinds = {
        "distributes": ("distributor", "manufacturer"),
        "partners_with": ("integrator", "manufacturer"),
        "technology_signal": ("client", "technology"),
    }
    for relation in seed.get("relationships") or []:
        kinds = relation_kinds.get(relation.get("relation"))
        if not kinds:
            continue
        add(
            kinds[0],
            relation.get("entity_a"),
            relation.get("relation"),
            kinds[1],
            relation.get("entity_b"),
            relation.get("country"),
            relation.get("evidence"),
            relation.get("status", "CONFIRMADO"),
            relation.get("confidence", 0.84),
            relation.get("derived", False),
            relation.get("validity", "current"),
        )

    for section, kind, relation_name in (
        ("distributors", "distributor", "distributes"),
        ("integrators", "integrator", "partners_with"),
    ):
        for row in data.get(section) or []:
            field = (row.get("fields") or {}).get("vendor_relations") or {}
            scope = str(((row.get("fields") or {}).get("scope") or {}).get("value") or "IBERIA")
            for raw in values(field.get("value")):
                name = _target(raw)
                if not name or any(
                    phrase in canonical(name)
                    for phrase in (
                        "mas de", "catalogo", "fabricantes visibles", "ver catalogo",
                        "marcas nacionales", "hardware y software de marcas",
                    )
                ):
                    continue
                add(
                    kind,
                    row.get("name"),
                    relation_name,
                    "manufacturer",
                    name,
                    scope,
                    _item_evidence(field, raw),
                    "CONFIRMADO",
                    0.88,
                )

    for section in ("clients_public", "clients_private"):
        for row in data.get(section) or []:
            field = (row.get("fields") or {}).get("technology_signals") or {}
            scope = str(((row.get("fields") or {}).get("scope") or {}).get("value") or "IBERIA")
            for technology in values(field.get("value")):
                add(
                    "client",
                    row.get("name"),
                    "technology_signal",
                    "technology",
                    technology,
                    scope,
                    _item_evidence(field, technology),
                    "SEÑAL",
                    0.48,
                    True,
                    "needs-corroboration",
                )

    return {
        "version": VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "entities": sorted(entities.values(), key=lambda row: (row["entity_type"], row["canonical_name"])),
        "relationships": list(relationships.values()),
        "model": {
            "truth_source": "canonical relation graph",
            "item_level_evidence": True,
            "bidirectional_projection": True,
            "canonical_entity_ids": True,
            "single_edge_multi_scope": True,
            "weak_signals_do_not_promote": True,
            "baseline_migrated_once": True,
        },
    }
