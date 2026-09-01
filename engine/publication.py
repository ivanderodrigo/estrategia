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
    for section in SECTIONS:
        registry: dict[str, dict[str, Any]] = {}
        rows = _compact_object(data.get(section) or [], registry)
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
    manifest = {
        "version": VERSION,
        "generated_at": meta.get("generated_at"),
        "meta": meta,
        "schemas": data.get("schemas") or {},
        "source_catalog": data.get("source_catalog") or [],
        "counts": {section: len(data.get(section) or []) for section in SECTIONS},
        "confidence_distribution": _confidence_distribution(data),
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
