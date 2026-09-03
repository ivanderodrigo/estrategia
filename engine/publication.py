from __future__ import annotations

import hashlib
from copy import deepcopy
from typing import Any

from .settings import SECTIONS, VERSION
from .knowledge_provenance import accrediting_evidence, provenance_kind
from .storage import atomic_write_many, json_bytes


def _evidence_key(ev: dict[str, Any]) -> str:
    if provenance_kind(ev) in {"WESTCON_DOCUMENT", "WESTCON_DOCUMENT_CURRENT", "WESTCON_FIRST_PARTY_CURRENT"}:
        raw = "|".join(str(ev.get(k) or "") for k in ("document_id", "statement_id", "document", "slide", "field", "item_value"))
    else:
        raw = "|".join(str(ev.get(k) or "") for k in ("url", "field", "item_value", "scope"))
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
        "source_catalog": _public_source_catalog(data),
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
