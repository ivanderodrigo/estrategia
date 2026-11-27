from __future__ import annotations

import hashlib
from copy import deepcopy
from typing import Any

from .settings import SECTIONS, VERSION
from .knowledge_provenance import accrediting_evidence, provenance_kind
from .storage import atomic_write_many, json_bytes, read_json
from .vendor_labels import non_vendor_reason
from .vendor_claims import VENDOR_RELATION_FIELDS, exact_vendor_source


_VENDOR_RELATION_FIELDS = VENDOR_RELATION_FIELDS


def _quarantine_public_vendor_labels(
    rows: list[dict[str, Any]], section: str,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Suppress provably non-vendor labels in publication, not in provenance.

    The canonical snapshot, research clues and historical source archive remain
    untouched. Rebuilds can still audit those origins, but users must never see
    'Marketing', image filenames or product categories as GREEN manufacturers.
    """
    output = deepcopy(rows)
    exceptions: list[dict[str, str]] = []
    if section not in {"distributors", "integrators"}:
        return output, exceptions
    for row in output:
        entity = str(row.get("name") or "")
        fields = row.get("fields") or {}
        for field_name in _VENDOR_RELATION_FIELDS:
            field = fields.get(field_name)
            if not isinstance(field, dict):
                continue
            values = field.get("value")
            if not isinstance(values, list):
                continue
            filtered = []
            for value in values:
                reason = non_vendor_reason(value) if isinstance(value, str) else None
                if reason:
                    exceptions.append({
                        "section": section, "entity": entity, "field": field_name,
                        "value": value, "reason": reason,
                    })
                else:
                    filtered.append(value)
            if len(filtered) == len(values):
                continue
            field["value"] = filtered
            if isinstance(field.get("items"), list):
                field["items"] = [
                    item for item in field["items"]
                    if not isinstance(item, dict)
                    or not non_vendor_reason(item.get("value"))
                ]
            field["evidence"] = [
                ev for ev in field.get("evidence") or []
                if not isinstance(ev, dict)
                or not (str(ev.get("field") or field_name) == field_name
                        and ev.get("item_value")
                        and non_vendor_reason(ev.get("item_value")))
            ]
            if not filtered:
                # Leave the field in the schema, but with no falsely accredited
                # manufacturer. _compact_object will downgrade it to pending.
                field["evidence"] = []
        # Exact claim-bound noise can also be present on entity-level evidence.
        if exceptions and isinstance(row.get("evidence"), list):
            row["evidence"] = [
                ev for ev in row["evidence"]
                if not isinstance(ev, dict)
                or str(ev.get("field") or "") not in _VENDOR_RELATION_FIELDS
                or not non_vendor_reason(ev.get("item_value"))
            ]
    return output, exceptions


def _downgrade_unbound_public_vendor_claims(
    rows: list[dict[str, Any]], section: str,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Never display a vendor in green based on a generic/unrelated URL.

    This operates on the already-copied public view. Canonical per-item
    evidence, including rejected leads, remains in data/current.
    """
    exceptions: list[dict[str, str]] = []
    if section not in {"distributors", "integrators"}:
        return rows, exceptions
    for row in rows:
        for field_name in _VENDOR_RELATION_FIELDS:
            field = (row.get("fields") or {}).get(field_name)
            if not isinstance(field, dict):
                continue
            items = field.get("items") or []
            if not isinstance(items, list):
                continue
            supported: set[str] = set()
            for item in items:
                if not isinstance(item, dict) or not isinstance(item.get("value"), str):
                    continue
                value = item["value"]
                exact = [ev for ev in item.get("evidence") or []
                         if exact_vendor_source(ev, field_name, value)]
                if exact:
                    supported.add(value.casefold())
                    item["evidence"] = exact
                    continue
                # Explicitly mark the item as pending even if a legacy graph
                # score or unrelated official link had granted a green pill.
                if item.get("evidence_color") == "green" or item.get("assertion_status") == "CONFIRMADO":
                    exceptions.append({"section": section, "entity": str(row.get("name") or ""),
                                       "field": field_name, "value": value,
                                       "reason": "no_atomic_item_bound_source"})
                item["evidence"] = []
                _downgrade_unproven_public_claim(item)
            if isinstance(field.get("evidence"), list):
                field["evidence"] = [
                    ev for ev in field["evidence"]
                    if isinstance(ev, dict)
                    and str(ev.get("item_value") or "").casefold() in supported
                    and exact_vendor_source(ev, field_name, str(ev.get("item_value") or ""))
                ]
            if items and not supported:
                _downgrade_unproven_public_claim(field)
    return rows, exceptions


def _downgrade_unproven_public_claim(claim: dict[str, Any]) -> None:
    for key in ("confidence", "fact_confidence", "interpretation_confidence"):
        if key in claim:
            claim[key] = min(float(claim.get(key) or 0), 0.38)
    claim["confidence_band"] = "low"
    claim["evidence_color"] = "red"
    claim["evidence_level"] = "weak"
    claim["action_risk"] = "alto"
    if claim.get("assertion_status") == "CONFIRMADO":
        claim["assertion_status"] = "PENDIENTE_DE_CONTRASTAR_AFIRMACION"
    claim["confidence_reason"] = (
        "No hay prueba atómica pública específica de esta relación entidad–fabricante; "
        "los enlaces genéricos permanecen como pistas para investigación."
    )


def _evidence_key(ev: dict[str, Any]) -> str:
    if provenance_kind(ev) in {"WESTCON_DOCUMENT", "WESTCON_DOCUMENT_CURRENT", "WESTCON_FIRST_PARTY_CURRENT"}:
        raw = "|".join(str(ev.get(k) or "") for k in ("document_id", "statement_id", "document", "slide", "field", "item_value"))
    else:
        # One URL can carry a legacy mention and a later individually verified
        # relationship. Do not let registry.setdefault silently replace the
        # checked proof with whichever generic record was serialized first.
        raw = "|".join(str(ev.get(k) or "") for k in (
            "url", "field", "item_value", "scope", "researched_entity",
            "source_type", "verification_method",
        ))
    return "ev_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _document_identity(ev: dict[str, Any]) -> str:
    explicit = str(ev.get("document_id") or "").strip()
    if explicit:
        return explicit
    filename = str(ev.get("document") or "").casefold()
    if "vertical" in filename:
        return "westcon-verticals-fy27"
    return "westcon-corporate-fy27"


def _public_evidence(ev: dict[str, Any]) -> dict[str, Any] | None:
    """Return the simple accrediting representation used by normal users."""
    if not accrediting_evidence(ev):
        return None
    out = deepcopy(ev)
    kind = provenance_kind(out)
    if kind in {"WESTCON_DOCUMENT_CURRENT", "WESTCON_FIRST_PARTY_CURRENT"}:
        if out.get("document_id"):
            out["document_id"] = _document_identity(out)
            out.setdefault("document", "Westcon_Comstor_Espana_FY27_completa.pptx")
            out["source"] = "Westcon Comstor España · documentación FY2027 vigente"
            out["source_role"] = "Fuente documental Westcon vigente"
        else:
            out["source"] = out.get("source") or "Westcon Iberia · regla operativa vigente"
            out["source_role"] = "Fuente Westcon vigente"
        out["intelligence_tier"] = "A1"
    elif kind == "WESTCON_DOCUMENT":
        # Old "Portfolio" and "Presentation" labels may refer to the same supplied deck.
        # One document identity prevents them appearing as independent sources.
        out["document_id"] = _document_identity(out)
        out.setdefault("document", "Westcon_Comstor_Espana_FY27_completa.pptx")
        out["source"] = "Documentación oficial Westcon aportada"
        if not out.get("slide"):
            out["title"] = "Westcon Comstor España - Presentación Corporativa FY2027"
        out["source_role"] = "Fuente documental Westcon"
        out["intelligence_tier"] = "A1"
    elif provenance_kind(out) == "PUBLIC_PRIMARY":
        out["source_role"] = "Fuente pública primaria"
        out["intelligence_tier"] = "A2"
    else:
        out["source_role"] = "Fuente pública secundaria / analista"
        out["intelligence_tier"] = "B" if any(
            marker in " ".join(str(out.get(k) or "") for k in ("source", "title", "url")).casefold()
            for marker in ("gartner", "forrester", "idc", "omdia", "canalys", "isg", "gigaom")
        ) else "C"
    # Internal archaeology stays in data/current only.
    for key in (
        "historical_commit", "historical_path", "historical_archive", "historical_version",
        "archive_version", "archive_member", "match_mode", "revalidation_status",
    ):
        out.pop(key, None)
    return out


def _compact_object(obj: Any, registry: dict[str, dict[str, Any]]) -> Any:
    if isinstance(obj, list):
        return [_compact_object(x, registry) for x in obj]
    if not isinstance(obj, dict):
        return obj
    out = {}
    for key, value in obj.items():
        if key == "confidence_factors":
            continue  # Derivable in the browser; avoid repeating prose thousands of times.
        if key == "evidence" and isinstance(value, list):
            ids = []
            for ev in value:
                if not isinstance(ev, dict):
                    continue
                public = _public_evidence(ev)
                if public is None:
                    continue
                eid = _evidence_key(public)
                registry.setdefault(eid, public)
                if eid not in ids:
                    ids.append(eid)
            out["evidence_ids"] = ids
        else:
            out[key] = _compact_object(value, registry)
    # A claim can lose its only evidence when non-accrediting historical/internal
    # provenance is removed from the public projection. Its inherited confidence
    # must not continue to show 0.99 / "high" next to zero public sources.
    if "value" in out and "confidence" in out and not out.get("evidence_ids"):
        out["confidence"] = min(float(out.get("confidence") or 0), 0.38)
        out["fact_confidence"] = min(float(out.get("fact_confidence") or 0), 0.38)
        out["interpretation_confidence"] = min(float(out.get("interpretation_confidence") or 0), 0.38)
        if out.get("assertion_status") == "CONFIRMADO":
            out["assertion_status"] = "PENDIENTE_DE_CONTRASTAR_AFIRMACION"
        out["confidence_band"] = "low"
        out["evidence_level"] = "weak"
        out["evidence_color"] = "red"
        out["action_risk"] = "alto"
        out["confidence_reason"] = "Sin fuente acreditativa pública o documental vigente específica para este valor."
    return out


def _source_coverage(rows: Any, evidence: dict[str, dict[str, Any]]) -> dict[str, int]:
    """Count actual public claim support after source filtering, not internal confidence."""
    counts = {"claims": 0, "sourced": 0, "unsourced": 0, "broken_references": 0}
    def walk(obj: Any) -> None:
        if isinstance(obj, list):
            for part in obj:
                walk(part)
        elif isinstance(obj, dict):
            if "value" in obj and "confidence" in obj and obj.get("value") not in (None, "", [], {}):
                counts["claims"] += 1
                references = obj.get("evidence_ids") or []
                valid = [ref for ref in references if ref in evidence]
                counts["broken_references"] += len(references) - len(valid)
                counts["sourced" if valid else "unsourced"] += 1
            for part in obj.values():
                if isinstance(part, (list, dict)):
                    walk(part)
    walk(rows)
    return counts


def _rebind_exact_item_evidence(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Restore only explicit field+item-value source associations inside one entity.

    Historical leads and evidence without an exact item_value never become
    accrediting merely because they are on the same field.
    """
    output = deepcopy(rows)
    rebound = 0
    for row in output:
        if not isinstance(row, dict):
            continue
        for field_name, field in (row.get("fields") or {}).items():
            if not isinstance(field, dict):
                continue
            exact_sources: dict[str, list[dict[str, Any]]] = {}
            # Entity-level sources sometimes already declare the exact field
            # and item, but their original ingestion lost the field binding.
            # No source may cross the containing entity boundary.
            candidates = list(field.get("evidence") or []) + list(row.get("evidence") or [])
            for ev in candidates:
                if not isinstance(ev, dict) or not accrediting_evidence(ev):
                    continue
                if str(ev.get("field") or "").strip() != field_name:
                    continue
                value = ev.get("item_value")
                if not isinstance(value, str) or not value.strip():
                    continue
                exact_sources.setdefault(value.strip().casefold(), []).append(ev)
            # Scalar fields can also recover a source already held at entity
            # level, but only with identical explicit item_value.
            scalar = field.get("value")
            if isinstance(scalar, str) and scalar.strip() and not any(
                isinstance(ev, dict) and accrediting_evidence(ev)
                for ev in field.get("evidence") or []
            ):
                for ev in exact_sources.get(scalar.strip().casefold(), []):
                    current = field.setdefault("evidence", [])
                    if ev not in current:
                        current.append(deepcopy(ev))
                        rebound += 1
            for item in field.get("items") or []:
                if not isinstance(item, dict):
                    continue
                value = item.get("value")
                if not isinstance(value, str) or not value.strip():
                    continue
                existing = item.setdefault("evidence", [])
                if any(isinstance(ev, dict) and accrediting_evidence(ev) for ev in existing):
                    continue
                for ev in exact_sources.get(value.strip().casefold(), []):
                    if ev not in existing:
                        existing.append(deepcopy(ev))
                        rebound += 1
    return output, rebound


def _confidence_distribution(data: dict[str, Any]) -> dict[str, int]:
    counts = {"high": 0, "medium": 0, "low": 0}
    for section in SECTIONS:
        for row in data.get(section) or []:
            for field in (row.get("fields") or {}).values():
                items = field.get("items") or []
                if items:
                    for item in items:
                        band = str(item.get("confidence_band") or "low")
                        counts[band] = counts.get(band, 0) + 1
                elif field.get("confidence_band"):
                    band = str(field.get("confidence_band"))
                    counts[band] = counts.get(band, 0) + 1
    return counts


def _iter_evidence(data: dict[str, Any]):
    for section in SECTIONS:
        for row in data.get(section) or []:
            targets = [row]
            for field in (row.get("fields") or {}).values():
                if not isinstance(field, dict):
                    continue
                targets.append(field)
                targets.extend(item for item in field.get("items") or [] if isinstance(item, dict))
            for target in targets:
                for evidence in target.get("evidence") or []:
                    if isinstance(evidence, dict):
                        yield section, evidence


def _public_source_catalog(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Build the UI catalogue only from evidence that accredits an actual claim."""
    output: dict[str, dict[str, Any]] = {}
    for section, raw in _iter_evidence(data):
        public = _public_evidence(raw)
        if public is None:
            continue
        kind = provenance_kind(public)
        if kind in {"WESTCON_DOCUMENT_CURRENT", "WESTCON_FIRST_PARTY_CURRENT"}:
            identity = public.get("document_id") or public.get("statement_id") or public.get("source")
            key = f"westcon-current:{identity}"
            item = output.setdefault(key, {
                "document_id": public.get("document_id"),
                "statement_id": public.get("statement_id"),
                "name": public.get("source") or "Fuente Westcon vigente",
                "class": public.get("source_role") or "Fuente Westcon vigente",
                "scope": [],
                "dimensions": [],
                "url": str(public.get("url") or ""),
                "document": public.get("document"),
            })
        elif kind == "WESTCON_DOCUMENT":
            document_id = _document_identity(public)
            key = f"doc:{document_id}"
            item = output.setdefault(key, {
                "document_id": document_id,
                "name": "Documentación oficial Westcon aportada",
                "class": "WESTCON_DOCUMENT",
                "scope": [],
                "dimensions": [],
                "url": "",
                "document": public.get("document"),
            })
        else:
            url = str(public.get("url") or "").strip()
            if not url.startswith(("http://", "https://")):
                continue
            key = f"url:{url}"
            item = output.setdefault(key, {
                "name": public.get("source") or public.get("title") or "Fuente pública",
                "class": public.get("source_role") or "Fuente pública",
                "scope": [],
                "dimensions": [],
                "url": url,
            })
        scope = public.get("country") or public.get("scope")
        for value in (scope if isinstance(scope, list) else [scope] if scope else []):
            if value not in item["scope"]:
                item["scope"].append(value)
        if section not in item["dimensions"]:
            item["dimensions"].append(section)
    return sorted(output.values(), key=lambda row: (str(row.get("class") or ""), str(row.get("name") or "").casefold(), str(row.get("url") or "")))


def public_payloads(
    data: dict[str, Any],
    last_run: dict[str, Any] | None = None,
) -> tuple[dict[str, bytes], dict[str, Any]]:
    files: dict[str, bytes] = {}
    section_meta = {}
    coverage_meta: dict[str, dict[str, int]] = {}
    rebound_meta: dict[str, int] = {}
    publication_data = dict(data)
    quarantined: list[dict[str, str]] = []
    unbound_vendor_claims: list[dict[str, str]] = []
    for section in SECTIONS:
        registry: dict[str, dict[str, Any]] = {}
        repaired, rebound = _rebind_exact_item_evidence(data.get(section) or [])
        rebound_meta[section] = rebound
        clean_rows, exceptions = _quarantine_public_vendor_labels(repaired, section)
        quarantined.extend(exceptions)
        clean_rows, unbound = _downgrade_unbound_public_vendor_claims(clean_rows, section)
        unbound_vendor_claims.extend(unbound)
        publication_data[section] = clean_rows
        rows = _compact_object(clean_rows, registry)
        payload = {"version": VERSION, "section": section, "rows": rows, "evidence": registry}
        coverage_meta[section] = _source_coverage(rows, registry)
        relative = f"data/public/sections/{section}.json"
        encoded = json_bytes(payload, pretty=False)
        files[relative] = encoded
        section_meta[section] = {
            "file": relative,
            "rows": len(rows),
            "evidence": len(registry),
            "bytes": len(encoded),
        }

    meta = deepcopy(data.get("meta") or {})
    # Never expose internal engine diagnostics or old release plumbing in the public manifest.
    for key in list(meta):
        if key.endswith("_research") or key in {"research_model", "claim_model", "relationship_truth_source", "portfolio_fit_cleanup", "distributor_validation", "integrator_graph"}:
            meta.pop(key, None)
    meta["version"] = VERSION
    meta["source_coverage"] = coverage_meta
    meta["exact_source_rebindings"] = rebound_meta
    meta["vendor_label_quarantine"] = {
        "removed_from_public_views": len(quarantined),
        "by_section": {
            section: sum(1 for item in quarantined if item["section"] == section)
            for section in ("distributors", "integrators")
        },
        "examples": quarantined[:40],
        "policy": "Sólo etiquetas genéricas; el valor y sus fuentes permanecen en la memoria interna/histórica, no se acreditan como fabricantes.",
    }
    meta["vendor_relation_evidence_quarantine"] = {
        "downgraded_from_unproven": len(unbound_vendor_claims),
        "by_section": {
            section: sum(1 for item in unbound_vendor_claims if item["section"] == section)
            for section in ("distributors", "integrators")
        },
        "examples": unbound_vendor_claims[:40],
        "policy": "Relaciones conservadas como hipótesis; verde sólo con evidencia atómica de entidad, campo y fabricante.",
    }
    semantic_registry = read_json("config/current/historical_semantic_verified.json", {})
    misclassified = [
        claim for claim in semantic_registry.get("existing_claim_sources") or []
        if claim.get("section") in {"distributors", "integrators"}
        and claim.get("field") in VENDOR_RELATION_FIELDS
        and non_vendor_reason(claim.get("value"))
    ]
    meta["historical_semantic_misclassification"] = {
        "excluded_claim_source_pairs": len(misclassified),
        "examples": [{"entity": x.get("entity"), "value": x.get("value"),
                      "field": x.get("field"), "url": (x.get("source") or {}).get("url")}
                     for x in misclassified[:20]],
        "policy": "Antiguas verificaciones de categorías que no son fabricantes: se conserva la fuente histórica, nunca se acredita la relación de fabricante.",
    }
    manifest = {
        "version": VERSION,
        "generated_at": meta.get("generated_at"),
        "meta": meta,
        "schemas": data.get("schemas") or {},
        "source_catalog": _public_source_catalog(publication_data),
        "counts": {section: len(data.get(section) or []) for section in SECTIONS},
        "confidence_distribution": _confidence_distribution(publication_data),
        "sections": section_meta,
    }
    files["data/public/manifest.json"] = json_bytes(manifest, pretty=False)
    run = deepcopy(last_run or {})
    run["version"] = VERSION
    files["data/public/last_run.json"] = json_bytes(run, pretty=False)
    return files, manifest


def build_public(data: dict[str, Any], last_run: dict[str, Any] | None = None) -> dict[str, Any]:
    files, manifest = public_payloads(data, last_run)
    atomic_write_many(files)
    return manifest
