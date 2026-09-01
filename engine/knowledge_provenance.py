"""Typed provenance and non-destructive knowledge protection for v4.0.2."""
from __future__ import annotations

import json
import subprocess
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .model import canonical

ROOT = Path(__file__).resolve().parents[1]
PROTECTED_SECTIONS = ("trends", "architectures")
DYNAMIC_MANUFACTURER_FIELDS = {
    "distributors", "integrators", "vendor_relations", "westcon_overlap",
    "competitor_vendor_overlap", "competitors", "competitor_distributors",
    "direct_sales", "relationship_summary", "recent_signals", "analyst_signals",
}
DOCUMENT_SOURCE_TYPES = {
    "westcon-document", "internal-document", "user-provided", "curated", "curated-westcon",
}
LEGACY_SOURCE_TYPE = "legacy-unresolved"

CORPORATE_DOCUMENT = {
    "id": "westcon-corporate-fy27",
    "title": "Westcon Comstor España - Presentación Corporativa FY2027",
    "filename": "Westcon_Comstor_Espana_FY27_completa.pptx",
    "scope": "ES",
}

# Slides are based on the FY27 corporate deck supplied to the project.
VENDOR_SLIDES: dict[str, int] = {
    "anomali": 8, "attackiq": 9, "certes networks": 10, "cisco": 11,
    "claroty": 12, "crowdstrike": 13, "f5": 14, "firemon": 15,
    "fortanix": 16, "ivanti": 17, "levelblue": 18, "menlo security": 19,
    "netscout": 20, "noname akamai": 21, "akamai noname": 21, "okta": 22,
    "palo alto networks": 23, "ping identity": 24, "proofpoint": 25,
    "vectra ai": 26, "xm cyber": 27, "zscaler": 28, "1password": 29,
    "ciena": 40, "cisco meraki": 41, "efficientip": 42,
    "ericsson cradlepoint": 43, "cradlepoint ericsson": 43,
    "extreme networks": 44, "juniper networks": 45, "juniper": 45,
    "nokia": 46, "ruckus networks": 47, "ruckus": 47, "weblib": 48,
    "audiocodes": 59, "avaya": 60, "aws": 61, "microsoft azure": 62,
    "azure": 62, "stratus penguin solutions": 63, "stratus": 63,
    "penguin solutions": 63, "uipath": 64,
}


def _has_value(value: Any) -> bool:
    return value not in (None, "", [], {})


def _value_key(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except TypeError:
        return str(value)


def _row_key(row: Mapping[str, Any]) -> str:
    return str(row.get("id") or canonical(row.get("name")) or "")


def dedupe_evidence(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, str, str]] = set()
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        item = deepcopy(dict(raw))
        key = (
            str(item.get("url") or ""), str(item.get("title") or ""),
            str(item.get("source") or ""), str(item.get("date") or ""),
            str(item.get("provenance_origin") or item.get("source_type") or item.get("type") or ""),
            str(item.get("document_id") or item.get("historical_commit") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def provenance_kind(evidence: Mapping[str, Any]) -> str:
    origin = str(evidence.get("provenance_origin") or "").strip().upper()
    if origin:
        return origin
    source_type = str(evidence.get("source_type") or evidence.get("type") or "").casefold()
    if source_type == LEGACY_SOURCE_TYPE:
        return "LEGACY_UNRESOLVED"
    if source_type in DOCUMENT_SOURCE_TYPES or "westcon-document" in source_type:
        return "WESTCON_DOCUMENT"
    url = str(evidence.get("url") or "").strip()
    if url.startswith(("http://", "https://")):
        if evidence.get("official") is True or str(evidence.get("source_grade") or "").startswith("A"):
            return "PUBLIC_PRIMARY"
        return "PUBLIC_SECONDARY"
    if "curated" in source_type:
        return "CURATED"
    return "UNKNOWN"


def typed_evidence_sufficient(evidence: Mapping[str, Any]) -> bool:
    """Return True when evidence can close a gap under the typed provenance policy."""
    if not isinstance(evidence, Mapping):
        return False
    kind = provenance_kind(evidence)
    if kind == "LEGACY_UNRESOLVED":
        return False
    common = all(str(evidence.get(key) or "").strip() for key in ("source", "title", "date", "description"))
    if not common:
        return False
    url = str(evidence.get("url") or "").strip()
    if url.startswith(("http://", "https://")):
        return True
    source_type = str(evidence.get("source_type") or evidence.get("type") or "").casefold()
    if kind == "WESTCON_DOCUMENT" or source_type in DOCUMENT_SOURCE_TYPES:
        return bool(str(evidence.get("document") or evidence.get("document_id") or "").strip())
    return False


def real_evidence(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows if isinstance(row, Mapping) and provenance_kind(row) != "LEGACY_UNRESOLVED"]


def _merge_item(current: Mapping[str, Any], baseline: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(current))
    if not _has_value(result.get("value")) and _has_value(baseline.get("value")):
        result["value"] = deepcopy(baseline.get("value"))
    result["evidence"] = dedupe_evidence(list(result.get("evidence") or []) + list(baseline.get("evidence") or []))
    for key in (
        "confidence", "confidence_band", "confidence_reason", "claim_type", "assertion_status",
        "qualifier", "fact_confidence", "interpretation_confidence", "action_risk",
        "evidence_level", "evidence_color",
    ):
        if result.get(key) in (None, "") and baseline.get(key) not in (None, ""):
            result[key] = deepcopy(baseline.get(key))
    return result


def _merge_field(current: Mapping[str, Any] | None, baseline: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
    stats = {"fields_restored": 0, "items_restored": 0, "evidence_restored": 0}
    if not isinstance(current, Mapping) or not _has_value(current.get("value")):
        return deepcopy(dict(baseline)), {
            "fields_restored": 1,
            "items_restored": len(baseline.get("items") or []),
            "evidence_restored": len(baseline.get("evidence") or []),
        }
    result = deepcopy(dict(current))
    before_evidence = len(result.get("evidence") or [])
    result["evidence"] = dedupe_evidence(list(result.get("evidence") or []) + list(baseline.get("evidence") or []))
    stats["evidence_restored"] += max(0, len(result["evidence"]) - before_evidence)

    current_value = result.get("value")
    baseline_value = baseline.get("value")
    if isinstance(current_value, list) and isinstance(baseline_value, list):
        existing = {_value_key(value) for value in current_value}
        for value in baseline_value:
            key = _value_key(value)
            if key not in existing:
                current_value.append(deepcopy(value))
                existing.add(key)
                stats["items_restored"] += 1

        current_items = {
            _value_key(item.get("value")): item
            for item in result.get("items") or []
            if isinstance(item, Mapping) and "value" in item
        }
        ordered = [deepcopy(dict(item)) for item in result.get("items") or [] if isinstance(item, Mapping)]
        for base_item in baseline.get("items") or []:
            if not isinstance(base_item, Mapping) or "value" not in base_item:
                continue
            key = _value_key(base_item.get("value"))
            if key in current_items:
                merged = _merge_item(current_items[key], base_item)
                for index, existing_item in enumerate(ordered):
                    if _value_key(existing_item.get("value")) == key:
                        ordered[index] = merged
                        break
            else:
                ordered.append(deepcopy(dict(base_item)))
                stats["items_restored"] += 1
        if ordered:
            result["items"] = ordered

    for key in (
        "confidence", "confidence_band", "confidence_reason", "claim_type", "assertion_status",
        "qualifier", "fact_confidence", "interpretation_confidence", "action_risk",
        "evidence_level", "evidence_color",
    ):
        if result.get(key) in (None, "") and baseline.get(key) not in (None, ""):
            result[key] = deepcopy(baseline.get(key))
    return result, stats


def build_knowledge_baseline(data: Mapping[str, Any], *, version: str = "4.0.2") -> dict[str, Any]:
    protected: dict[str, Any] = {}
    for section in PROTECTED_SECTIONS:
        protected[section] = deepcopy(list(data.get(section) or []))

    manufacturers = []
    for row in data.get("manufacturers") or []:
        if not isinstance(row, Mapping):
            continue
        fields = {}
        for field_id, field in (row.get("fields") or {}).items():
            if field_id in DYNAMIC_MANUFACTURER_FIELDS or not isinstance(field, Mapping):
                continue
            if _has_value(field.get("value")):
                fields[field_id] = deepcopy(dict(field))
        manufacturers.append({
            "id": row.get("id"), "name": row.get("name"),
            "evidence": deepcopy(list(row.get("evidence") or [])), "fields": fields,
        })
    protected["manufacturers"] = manufacturers
    return {
        "version": version,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "policy": "non-destructive-canonical-knowledge",
        "protected": protected,
    }


def load_knowledge_baseline(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path else ROOT / "config/current/knowledge_baseline.json"
    if not target.exists():
        return {}
    return json.loads(target.read_text(encoding="utf-8-sig"))


def restore_protected_knowledge(data: dict[str, Any], baseline: Mapping[str, Any]) -> dict[str, int]:
    stats = {"rows_restored": 0, "fields_restored": 0, "items_restored": 0, "evidence_restored": 0}
    protected = baseline.get("protected") or {}
    for section in ("trends", "architectures", "manufacturers"):
        base_rows = protected.get(section) or []
        if not base_rows:
            continue
        rows = data.setdefault(section, [])
        index = {_row_key(row): row for row in rows if isinstance(row, Mapping) and _row_key(row)}
        for base_row in base_rows:
            if not isinstance(base_row, Mapping):
                continue
            key = _row_key(base_row)
            current = index.get(key)
            if current is None:
                rows.append(deepcopy(dict(base_row)))
                index[key] = rows[-1]
                stats["rows_restored"] += 1
                continue
            before = len(current.get("evidence") or [])
            current["evidence"] = dedupe_evidence(list(current.get("evidence") or []) + list(base_row.get("evidence") or []))
            stats["evidence_restored"] += max(0, len(current["evidence"]) - before)
            if section in PROTECTED_SECTIONS and not current.get("analytics") and base_row.get("analytics"):
                current["analytics"] = deepcopy(base_row.get("analytics"))
            fields = current.setdefault("fields", {})
            for field_id, base_field in (base_row.get("fields") or {}).items():
                if not isinstance(base_field, Mapping):
                    continue
                merged, delta = _merge_field(fields.get(field_id), base_field)
                fields[field_id] = merged
                for stat_key, amount in delta.items():
                    stats[stat_key] += amount
    return stats


def _historical_commits(root: Path, limit: int) -> list[str]:
    # Only inspect commits that touched an intelligence snapshot; this avoids repeatedly
    # decoding large JSON files from unrelated source-code commits.
    result = subprocess.run(
        [
            "git", "-C", str(root), "log", "--all", "--format=%H",
            f"--max-count={limit}", "--",
            "data/current/intelligence.json", "data/public/intelligence.json",
            "data/intelligence.json", "data/current/public_intelligence.json",
        ],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        encoding="utf-8", errors="replace", check=False,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _git_json(root: Path, commit: str, candidate_paths: Iterable[str]) -> tuple[dict[str, Any] | None, str | None]:
    for relative in candidate_paths:
        result = subprocess.run(
            ["git", "-C", str(root), "show", f"{commit}:{relative}"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
        )
        if result.returncode != 0 or not result.stdout:
            continue
        for encoding in ("utf-8-sig", "utf-8"):
            try:
                return json.loads(result.stdout.decode(encoding, errors="strict")), relative
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
    return None, None


def _field_matches(current: Mapping[str, Any], old: Mapping[str, Any]) -> bool:
    return _has_value(current.get("value")) and _value_key(current.get("value")) == _value_key(old.get("value"))


def _historicalize(rows: Iterable[Mapping[str, Any]], commit: str, path: str) -> list[dict[str, Any]]:
    output = []
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        item = deepcopy(dict(raw))
        item["provenance_origin"] = "HISTORICAL_RECOVERED"
        item["historical_commit"] = commit
        item["historical_path"] = path
        item.setdefault("method", "git-history-provenance-recovery")
        output.append(item)
    return dedupe_evidence(output)


def recover_historical_provenance(data: dict[str, Any], root: Path | None = None, *, max_commits: int = 100) -> dict[str, int]:
    """Recover evidence from prior snapshots only when entity/field/value matches exactly."""
    root = root or ROOT
    stats = {"commits_scanned": 0, "fields_recovered": 0, "items_recovered": 0, "evidence_recovered": 0}
    targets: dict[tuple[str, str, str], dict[str, Any]] = {}
    sections = ("manufacturers", "distributors", "integrators", "clients_public", "clients_private", "trends", "architectures")
    for section in sections:
        for row in data.get(section) or []:
            if not isinstance(row, Mapping):
                continue
            row_key = _row_key(row)
            for field_id, field in (row.get("fields") or {}).items():
                if not isinstance(field, dict) or not _has_value(field.get("value")):
                    continue
                missing_field = not any(typed_evidence_sufficient(ev) for ev in field.get("evidence") or [] if isinstance(ev, Mapping))
                missing_item = any(
                    isinstance(item, Mapping) and _has_value(item.get("value"))
                    and not any(typed_evidence_sufficient(ev) for ev in item.get("evidence") or [] if isinstance(ev, Mapping))
                    for item in field.get("items") or []
                )
                if missing_field or missing_item:
                    targets[(section, row_key, field_id)] = field
    if not targets:
        return stats

    candidate_paths = (
        "data/current/intelligence.json", "data/public/intelligence.json",
        "data/intelligence.json", "data/current/public_intelligence.json",
    )
    for commit in _historical_commits(root, max_commits):
        historical, source_path = _git_json(root, commit, candidate_paths)
        if not historical or not source_path:
            continue
        version = str(((historical.get("meta") or {}).get("version") or historical.get("version") or ""))
        if version.startswith("4.0.1"):
            continue
        stats["commits_scanned"] += 1
        hist_index: dict[tuple[str, str], Mapping[str, Any]] = {}
        for section in sections:
            for row in historical.get(section) or []:
                if isinstance(row, Mapping) and _row_key(row):
                    hist_index[(section, _row_key(row))] = row

        for target_key, target in list(targets.items()):
            section, row_key, field_id = target_key
            hist_row = hist_index.get((section, row_key))
            if not hist_row:
                continue
            hist_field = ((hist_row.get("fields") or {}).get(field_id) or {})
            if not isinstance(hist_field, Mapping) or not _field_matches(target, hist_field):
                continue

            changed = False
            if not any(typed_evidence_sufficient(ev) for ev in target.get("evidence") or [] if isinstance(ev, Mapping)):
                old_rows = [ev for ev in hist_field.get("evidence") or [] if isinstance(ev, Mapping) and provenance_kind(ev) != "LEGACY_UNRESOLVED"]
                if old_rows:
                    recovered = _historicalize(old_rows, commit, source_path)
                    before = len(target.get("evidence") or [])
                    target["evidence"] = dedupe_evidence(list(target.get("evidence") or []) + recovered)
                    stats["evidence_recovered"] += max(0, len(target["evidence"]) - before)
                    stats["fields_recovered"] += 1
                    changed = True

            current_items = {
                _value_key(item.get("value")): item
                for item in target.get("items") or []
                if isinstance(item, dict) and _has_value(item.get("value"))
            }
            hist_items = {
                _value_key(item.get("value")): item
                for item in hist_field.get("items") or []
                if isinstance(item, Mapping) and _has_value(item.get("value"))
            }
            for value_key, current_item in current_items.items():
                if any(typed_evidence_sufficient(ev) for ev in current_item.get("evidence") or [] if isinstance(ev, Mapping)):
                    continue
                historical_item = hist_items.get(value_key)
                if not historical_item:
                    continue
                old_rows = [ev for ev in historical_item.get("evidence") or [] if isinstance(ev, Mapping) and provenance_kind(ev) != "LEGACY_UNRESOLVED"]
                if not old_rows:
                    continue
                recovered = _historicalize(old_rows, commit, source_path)
                before = len(current_item.get("evidence") or [])
                current_item["evidence"] = dedupe_evidence(list(current_item.get("evidence") or []) + recovered)
                stats["evidence_recovered"] += max(0, len(current_item["evidence"]) - before)
                stats["items_recovered"] += 1
                changed = True

            if changed:
                still_missing = (
                    not any(typed_evidence_sufficient(ev) for ev in target.get("evidence") or [] if isinstance(ev, Mapping))
                    or any(
                        isinstance(item, Mapping) and _has_value(item.get("value"))
                        and not any(typed_evidence_sufficient(ev) for ev in item.get("evidence") or [] if isinstance(ev, Mapping))
                        for item in target.get("items") or []
                    )
                )
                if not still_missing:
                    targets.pop(target_key, None)
        if not targets:
            break
    return stats


def _slide_for_vendor(name: str) -> int | None:
    key = canonical(name)
    if key in VENDOR_SLIDES:
        return VENDOR_SLIDES[key]
    for alias, slide in VENDOR_SLIDES.items():
        if alias and (alias in key or key in alias):
            return slide
    return None


def _document_evidence(vendor_name: str, slide: int) -> dict[str, Any]:
    return {
        "source": "Westcon Comstor España",
        "title": f"{CORPORATE_DOCUMENT['title']} · slide {slide}",
        "url": "",
        "date": "FY2027",
        "description": (
            f"Documento corporativo aportado al proyecto que describe el posicionamiento y capacidades de {vendor_name}. "
            "Se usa como fuente primaria documental Westcon; no requiere una URL pública para ser trazable."
        ),
        "scope": CORPORATE_DOCUMENT["scope"],
        "source_grade": "A-WESTCON",
        "source_type": "westcon-document",
        "official": True,
        "classification": "internal-document",
        "freshness_status": "current",
        "method": "document-provenance",
        "document_id": CORPORATE_DOCUMENT["id"],
        "document": CORPORATE_DOCUMENT["filename"],
        "slide": slide,
        "provenance_origin": "WESTCON_DOCUMENT",
    }


def apply_westcon_document_provenance(data: dict[str, Any]) -> dict[str, int]:
    """Attach the supplied corporate deck only where it directly supports vendor capabilities."""
    stats = {"manufacturer_fields_documented": 0, "manufacturer_rows_documented": 0}
    supported_fields = {"domain", "capabilities", "services", "specializations", "verticals"}
    for row in data.get("manufacturers") or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        slide = _slide_for_vendor(name)
        if slide is None:
            continue
        evidence = _document_evidence(name, slide)
        if not real_evidence(row.get("evidence") or []):
            row["evidence"] = dedupe_evidence(list(row.get("evidence") or []) + [evidence])
            stats["manufacturer_rows_documented"] += 1
        for field_id in supported_fields:
            field = ((row.get("fields") or {}).get(field_id) or {})
            if not isinstance(field, dict) or not _has_value(field.get("value")):
                continue
            if any(typed_evidence_sufficient(ev) for ev in field.get("evidence") or [] if isinstance(ev, Mapping)):
                continue
            field["evidence"] = dedupe_evidence(list(field.get("evidence") or []) + [evidence])
            stats["manufacturer_fields_documented"] += 1
    return stats


def _legacy_evidence(section: str, row: Mapping[str, Any], field_id: str, value: Any = None) -> dict[str, Any]:
    suffix = f" · elemento: {value}" if value not in (None, "") else ""
    return {
        "source": "Histórico del proyecto Westcon Decision Intelligence",
        "title": f"Procedencia histórica pendiente de reconstrucción · {row.get('name')} · {field_id}{suffix}",
        "url": "",
        "date": "2026-09-01",
        "description": (
            "El dato ya existía en una versión estable del proyecto, pero todavía no se ha reconstruido una fuente "
            "primaria/documental específica para este elemento. Se conserva para no destruir inteligencia previa y "
            "permanece como gap de investigación hasta ser revalidado."
        ),
        "scope": "INTERNAL",
        "source_grade": "L",
        "source_type": LEGACY_SOURCE_TYPE,
        "official": False,
        "classification": "legacy",
        "freshness_status": "needs-revalidation",
        "method": "non-destructive-legacy-preservation",
        "provenance_origin": "LEGACY_UNRESOLVED",
        "section": section,
        "entity": row.get("name"),
        "field": field_id,
    }


def mark_legacy_unresolved(data: dict[str, Any]) -> dict[str, int]:
    """Make lost provenance explicit without pretending it is sufficient evidence."""
    stats = {"fields_marked": 0, "items_marked": 0}
    atomic_relations = {
        "distributors", "integrators", "vendor_relations", "westcon_overlap", "competitor_vendor_overlap",
    }
    for section in ("manufacturers", "distributors", "integrators", "clients_public", "clients_private", "trends", "architectures"):
        for row in data.get(section) or []:
            if not isinstance(row, Mapping):
                continue
            for field_id, field in (row.get("fields") or {}).items():
                if not isinstance(field, dict) or not _has_value(field.get("value")):
                    continue
                if field_id in atomic_relations:
                    # Relationship assertions remain URL-backed and atomic; never manufacture fallback evidence here.
                    continue
                if not any(typed_evidence_sufficient(ev) for ev in field.get("evidence") or [] if isinstance(ev, Mapping)):
                    field["evidence"] = dedupe_evidence(list(field.get("evidence") or []) + [_legacy_evidence(section, row, field_id)])
                    field["confidence"] = min(float(field.get("confidence") or 0.45), 0.49)
                    field["confidence_band"] = "low"
                    field["evidence_level"] = "weak"
                    field["evidence_color"] = "red"
                    field["confidence_reason"] = "Origen histórico conservado, pero la fuente específica todavía debe reconstruirse o revalidarse."
                    field["qualifier"] = "Dato histórico preservado; procedencia específica pendiente de reconstrucción."
                    stats["fields_marked"] += 1
                for item in field.get("items") or []:
                    if not isinstance(item, dict) or not _has_value(item.get("value")):
                        continue
                    if not any(typed_evidence_sufficient(ev) for ev in item.get("evidence") or [] if isinstance(ev, Mapping)):
                        item["evidence"] = dedupe_evidence(
                            list(item.get("evidence") or []) + [_legacy_evidence(section, row, field_id, item.get("value"))]
                        )
                        item["confidence"] = min(float(item.get("confidence") or 0.45), 0.49)
                        item["confidence_band"] = "low"
                        item["evidence_level"] = "weak"
                        item["evidence_color"] = "red"
                        item["confidence_reason"] = "Origen histórico conservado, pero la fuente específica todavía debe reconstruirse o revalidarse."
                        item["qualifier"] = "Dato histórico preservado; procedencia específica pendiente de reconstrucción."
                        stats["items_marked"] += 1
    return stats


def provenance_summary(data: Mapping[str, Any]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    unresolved_fields = 0
    unresolved_items = 0
    for section in ("manufacturers", "distributors", "integrators", "clients_public", "clients_private", "trends", "architectures"):
        for row in data.get(section) or []:
            if not isinstance(row, Mapping):
                continue
            for field in (row.get("fields") or {}).values():
                if not isinstance(field, Mapping) or not _has_value(field.get("value")):
                    continue
                kinds = {provenance_kind(ev) for ev in field.get("evidence") or [] if isinstance(ev, Mapping)}
                if kinds == {"LEGACY_UNRESOLVED"}:
                    unresolved_fields += 1
                for ev in field.get("evidence") or []:
                    if isinstance(ev, Mapping):
                        kind = provenance_kind(ev)
                        counts[kind] = counts.get(kind, 0) + 1
                for item in field.get("items") or []:
                    if not isinstance(item, Mapping):
                        continue
                    item_kinds = {provenance_kind(ev) for ev in item.get("evidence") or [] if isinstance(ev, Mapping)}
                    if item_kinds == {"LEGACY_UNRESOLVED"}:
                        unresolved_items += 1
                    for ev in item.get("evidence") or []:
                        if isinstance(ev, Mapping):
                            kind = provenance_kind(ev)
                            counts[kind] = counts.get(kind, 0) + 1
    return {
        "policy": "typed-provenance-non-destructive",
        "types": counts,
        "legacy_unresolved_fields": unresolved_fields,
        "legacy_unresolved_items": unresolved_items,
        "documents_are_valid_primary_sources": True,
        "legacy_unresolved_remains_research_gap": True,
    }


def sync_document_sources(data: dict[str, Any]) -> None:
    """Expose typed documentary sources in the source catalogue without inventing a URL."""
    catalog = data.setdefault("source_catalog", [])
    existing = {
        str(item.get("document_id") or item.get("name") or "").casefold()
        for item in catalog if isinstance(item, Mapping)
    }
    documents = (
        {
            "document_id": "westcon-corporate-fy27",
            "name": "Westcon Comstor España - Presentación Corporativa FY2027",
            "class": "WESTCON_DOCUMENT",
            "scope": ["ES"],
            "dimensions": ["manufacturers", "architectures", "trends", "services"],
            "url": "",
            "document": "Westcon_Comstor_Espana_FY27_completa.pptx",
        },
        {
            "document_id": "westcon-verticals-fy27",
            "name": "Datasheets verticales Westcon Comstor España FY27",
            "class": "WESTCON_DOCUMENT",
            "scope": ["ES"],
            "dimensions": ["architectures", "trends", "clients_public", "clients_private"],
            "url": "",
            "document": "Westcon_Datasheets_Verticales_FY27.pptx",
        },
    )
    for item in documents:
        key = str(item["document_id"]).casefold()
        if key not in existing:
            catalog.append(dict(item))
            existing.add(key)
