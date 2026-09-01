from __future__ import annotations

import hashlib
from copy import deepcopy
from typing import Any

from .settings import SECTIONS, VERSION
from .storage import atomic_write_many, json_bytes


def _evidence_key(ev: dict[str, Any]) -> str:
    raw = "|".join(str(ev.get(k) or "") for k in ("url", "title", "source", "date", "scope"))
    return "ev_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


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
                eid = _evidence_key(ev)
                registry.setdefault(eid, deepcopy(ev))
                if eid not in ids:
                    ids.append(eid)
            out["evidence_ids"] = ids
        else:
            out[key] = _compact_object(value, registry)
    return out


PUBLIC_IDENTITY_FIELDS = {"scope", "domain", "entity_type", "notice_id", "source_portal", "index_universe"}


def _has_public_evidence(rows: Any) -> bool:
    return any(
        isinstance(ev, dict) and str(ev.get("url") or "").startswith(("http://", "https://"))
        for ev in (rows or [])
    )


def _sanitize_public_field(field_id: str, field: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Remove unsupported substantive claims from the public projection.

    Internal values are retained as research state; the browser only receives claims it
    can actually trace. Structural identity fields may remain visible without a popover.
    """
    out = deepcopy(field)
    value = out.get("value")
    if value in (None, "", [], {}):
        return out, 0
    if field_id in PUBLIC_IDENTITY_FIELDS:
        return out, 0
    field_has_source = _has_public_evidence(out.get("evidence"))
    suppressed = 0
    if isinstance(value, list):
        if value and all(not isinstance(item, (dict, list)) for item in value):
            item_map = {
                str(item.get("value") or "").strip().casefold(): item
                for item in out.get("items") or []
                if isinstance(item, dict)
            }
            kept_values, kept_items = [], []
            for raw in value:
                key = str(raw or "").strip().casefold()
                item = item_map.get(key)
                if item and _has_public_evidence(item.get("evidence")):
                    kept_values.append(raw)
                    kept_items.append(item)
                elif len(value) == 1 and field_has_source:
                    # A single-value field has no ambiguity: its field evidence is atomic.
                    kept_values.append(raw)
                    copy_item = deepcopy(item or {"value": raw})
                    copy_item["evidence"] = deepcopy(out.get("evidence") or [])
                    kept_items.append(copy_item)
                else:
                    suppressed += 1
            out["value"] = kept_values
            out["items"] = kept_items
            if not kept_values:
                out["evidence"] = []
            return out, suppressed
        # Structured lists (e.g. architecture layers) need field-level provenance.
        if not field_has_source:
            suppressed += len(value)
            out["value"] = []
            out.pop("items", None)
        return out, suppressed
    if not field_has_source:
        out["value"] = None
        out.pop("items", None)
        suppressed += 1
    return out, suppressed


def _sanitize_public_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    output = deepcopy(rows)
    suppressed = 0
    for row in output:
        fields = row.get("fields") or {}
        for field_id, field in list(fields.items()):
            if not isinstance(field, dict):
                continue
            fields[field_id], removed = _sanitize_public_field(field_id, field)
            suppressed += removed
    return output, suppressed


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


def public_payloads(
    data: dict[str, Any],
    last_run: dict[str, Any] | None = None,
) -> tuple[dict[str, bytes], dict[str, Any]]:
    files: dict[str, bytes] = {}
    section_meta = {}
    unsupported_suppressed = 0
    sanitized_sections: dict[str, Any] = {}
    for section in SECTIONS:
        registry: dict[str, dict[str, Any]] = {}
        safe_rows, removed = _sanitize_public_rows(data.get(section) or [])
        unsupported_suppressed += removed
        sanitized_sections[section] = safe_rows
        rows = _compact_object(safe_rows, registry)
        payload = {"version": VERSION, "section": section, "rows": rows, "evidence": registry}
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
    meta["unsupported_claims_suppressed"] = unsupported_suppressed
    meta["public_provenance_policy"] = "No substantive value without a directly linked public URL; simple lists require atomic evidence per item."
    manifest = {
        "version": VERSION,
        "generated_at": meta.get("generated_at"),
        "meta": meta,
        "schemas": data.get("schemas") or {},
        "source_catalog": data.get("source_catalog") or [],
        "counts": {section: len(data.get(section) or []) for section in SECTIONS},
        "confidence_distribution": _confidence_distribution(sanitized_sections),
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
