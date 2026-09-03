"""Typed provenance and non-destructive knowledge protection for v4.1.0."""
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
INTERNAL_RESEARCH_SEED_KINDS = {"RESEARCH_SEED", "WESTCON_DOCUMENT"}
CURRENT_WESTCON_EVIDENCE_KINDS = {"WESTCON_DOCUMENT_CURRENT", "WESTCON_FIRST_PARTY_CURRENT"}
CURRENT_WESTCON_CLAIM_SCOPES = {"portfolio-membership", "portfolio-and-capability", "westcon-services"}
CURRENT_WESTCON_ALLOWED_FIELDS_BY_SCOPE = {
    "portfolio-membership": {"portfolio", "scope", "westcon_spain", "westcon_portugal"},
    "portfolio-and-capability": {"portfolio", "scope", "westcon_spain", "domain", "capabilities"},
    "westcon-services": {"services", "capabilities", "westcon_services"},
}
HISTORICAL_PROVENANCE_KINDS = {
    "HISTORICAL_RECOVERED",
    "ARCHIVE_RECOVERED",
    "ARCHIVE_CORROBORATION",
    "REPORT_CORROBORATION",
    "LEGACY_UNRESOLVED",
}
DISCOVERY_SOURCE_MARKERS = {
    "discovery-candidate", "discovery-only", "candidate", "search-result",
    "unverified-discovery", "corroborated-candidate",
}

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


def discovery_only(evidence: Mapping[str, Any]) -> bool:
    """Discovery can route research but can never accredit a visible claim."""
    if provenance_kind(evidence) in INTERNAL_RESEARCH_SEED_KINDS:
        return True
    binding = str(evidence.get("source_binding") or "").strip().casefold()
    if binding == "discovery-only":
        return True
    source_type = str(evidence.get("source_type") or evidence.get("type") or "").strip().casefold()
    classification = str(evidence.get("classification") or "").strip().casefold()
    return source_type in DISCOVERY_SOURCE_MARKERS or classification in DISCOVERY_SOURCE_MARKERS


def typed_evidence_sufficient(evidence: Mapping[str, Any]) -> bool:
    """Return True when evidence can close a gap under the typed provenance policy."""
    if not isinstance(evidence, Mapping):
        return False
    kind = provenance_kind(evidence)
    # Contextual archive/report corroboration is useful provenance but cannot close a gap.
    if kind in HISTORICAL_PROVENANCE_KINDS | INTERNAL_RESEARCH_SEED_KINDS | {"DISCOVERY_ONLY"} or discovery_only(evidence):
        return False
    common = all(str(evidence.get(key) or "").strip() for key in ("source", "title", "date", "description"))
    if not common:
        return False
    if kind in CURRENT_WESTCON_EVIDENCE_KINDS:
        scope = str(evidence.get("westcon_claim_scope") or "").strip().casefold()
        if evidence.get("accrediting") is not True or scope not in CURRENT_WESTCON_CLAIM_SCOPES:
            return False
        field = str(evidence.get("field") or "").strip()
        allowed = CURRENT_WESTCON_ALLOWED_FIELDS_BY_SCOPE.get(scope) or set()
        return bool(field and field in allowed)
    url = str(evidence.get("url") or "").strip()
    if url.startswith(("http://", "https://")):
        return True
    source_type = str(evidence.get("source_type") or evidence.get("type") or "").casefold()
    if kind == "WESTCON_DOCUMENT" or source_type in DOCUMENT_SOURCE_TYPES:
        return False
    return False


def accrediting_evidence(evidence: Mapping[str, Any]) -> bool:
    """Evidence allowed in the normal user-facing source UI."""
    if not typed_evidence_sufficient(evidence):
        return False
    return provenance_kind(evidence) in {"PUBLIC_PRIMARY", "PUBLIC_SECONDARY"} | CURRENT_WESTCON_EVIDENCE_KINDS


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


def _document_evidence(
    vendor_name: str,
    slide: int,
    *,
    field_id: str | None = None,
    item_value: Any = None,
) -> dict[str, Any]:
    evidence = {
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
        "method": "document-provenance-atomic-v404",
        "document_id": CORPORATE_DOCUMENT["id"],
        "document": CORPORATE_DOCUMENT["filename"],
        "slide": slide,
        "provenance_origin": "WESTCON_DOCUMENT",
    }
    if field_id:
        evidence["field"] = field_id
    if item_value not in (None, ""):
        evidence["item_value"] = deepcopy(item_value)
        evidence["atomic"] = True
        evidence["description"] = (
            f"Documento corporativo Westcon FY2027 que respalda de forma específica la capacidad "
            f"«{item_value}» de {vendor_name}. Se conserva junto con cualquier evidencia pública existente."
        )
    return evidence


def _drop_legacy_placeholders(rows: Iterable[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    kept: list[dict[str, Any]] = []
    removed = 0
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if provenance_kind(row) == "LEGACY_UNRESOLVED":
            removed += 1
            continue
        kept.append(dict(row))
    return kept, removed


def _promote_document_supported_claim(target: dict[str, Any]) -> None:
    current = float(target.get("confidence") or 0.0)
    score = max(current, 0.92)
    target["confidence"] = score
    target["confidence_band"] = "high"
    target["claim_type"] = target.get("claim_type") or "fact"
    target["assertion_status"] = "CONFIRMADO"
    target["fact_confidence"] = max(float(target.get("fact_confidence") or 0.0), score)
    target["interpretation_confidence"] = max(float(target.get("interpretation_confidence") or 0.0), 0.88)
    target["action_risk"] = "bajo"
    target["evidence_level"] = "strong"
    target["evidence_color"] = "green"
    target["confidence_reason"] = (
        "Verde: capacidad respaldada de forma explícita por documentación corporativa Westcon FY2027. "
        "La evidencia documental puede coexistir con fuentes públicas del fabricante."
    )
    target["qualifier"] = (
        "Capacidad documentada por Westcon; la presentación es una fuente primaria documental "
        "y no sustituye otras evidencias públicas."
    )


def _baseline_capabilities() -> dict[str, set[str]]:
    output: dict[str, set[str]] = {}
    baseline = load_knowledge_baseline()
    manufacturers = (((baseline.get("protected") or {}).get("manufacturers")) or [])
    for row in manufacturers:
        if not isinstance(row, Mapping):
            continue
        key = canonical(row.get("name"))
        field = ((row.get("fields") or {}).get("capabilities") or {})
        value = field.get("value") if isinstance(field, Mapping) else None
        values = value if isinstance(value, list) else ([value] if _has_value(value) else [])
        if key and values:
            output[key] = {_value_key(item) for item in values}
    return output


def apply_westcon_document_provenance(data: dict[str, Any]) -> dict[str, int]:
    """v4.0.4: additive + atomic documentary provenance for manufacturer capabilities."""
    stats = {
        "manufacturer_fields_documented": 0,
        "manufacturer_rows_documented": 0,
        "manufacturer_capability_items_documented": 0,
        "capability_items_with_public_and_document": 0,
        "legacy_placeholders_removed": 0,
    }
    baseline_caps = _baseline_capabilities()
    supported_fields = {"domain", "capabilities", "services", "specializations", "verticals"}
    for row in data.get("manufacturers") or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        slide = _slide_for_vendor(name)
        if slide is None:
            continue
        row_ev = _document_evidence(name, slide)
        before_row = len(row.get("evidence") or [])
        row["evidence"] = dedupe_evidence(list(row.get("evidence") or []) + [row_ev])
        if len(row["evidence"]) > before_row:
            stats["manufacturer_rows_documented"] += 1
        fields = row.get("fields") or {}
        for field_id in supported_fields:
            field = fields.get(field_id) or {}
            if not isinstance(field, dict) or not _has_value(field.get("value")):
                continue
            must_coexist = field_id in {"domain", "capabilities"}
            if must_coexist or not any(
                typed_evidence_sufficient(ev)
                for ev in field.get("evidence") or []
                if isinstance(ev, Mapping)
            ):
                clean, removed = _drop_legacy_placeholders(field.get("evidence") or [])
                stats["legacy_placeholders_removed"] += removed
                field_ev = _document_evidence(name, slide, field_id=field_id)
                before = len(clean)
                field["evidence"] = dedupe_evidence(clean + [field_ev])
                if len(field["evidence"]) > before:
                    stats["manufacturer_fields_documented"] += 1
            if field_id != "capabilities":
                continue
            values = field.get("value")
            values = values if isinstance(values, list) else [values]
            items = [item for item in field.get("items") or [] if isinstance(item, dict)]
            item_index = {_value_key(item.get("value")): item for item in items if _has_value(item.get("value"))}
            for value in values:
                key = _value_key(value)
                if key not in item_index:
                    item = {"value": deepcopy(value), "evidence": []}
                    items.append(item)
                    item_index[key] = item
            field["items"] = items
            vendor_key = canonical(name)
            allowed = baseline_caps.get(vendor_key)
            if not allowed:
                allowed = {_value_key(value) for value in values if _has_value(value)}
            documented = 0
            for value in values:
                value_key = _value_key(value)
                if value_key not in allowed:
                    continue
                item = item_index[value_key]
                old_evidence = [
                    ev for ev in item.get("evidence") or []
                    if isinstance(ev, Mapping) and provenance_kind(ev) != "LEGACY_UNRESOLVED"
                ]
                removed = len(item.get("evidence") or []) - len(old_evidence)
                stats["legacy_placeholders_removed"] += max(0, removed)
                had_public = any(
                    provenance_kind(ev) in {"PUBLIC_PRIMARY", "PUBLIC_SECONDARY"}
                    for ev in old_evidence
                )
                item_ev = _document_evidence(name, slide, field_id="capabilities", item_value=value)
                before = len(old_evidence)
                item["evidence"] = dedupe_evidence(old_evidence + [item_ev])
                if len(item["evidence"]) > before:
                    stats["manufacturer_capability_items_documented"] += 1
                if had_public:
                    stats["capability_items_with_public_and_document"] += 1
                _promote_document_supported_claim(item)
                documented += 1
            if documented and documented == len(values):
                clean, removed = _drop_legacy_placeholders(field.get("evidence") or [])
                stats["legacy_placeholders_removed"] += removed
                field["evidence"] = dedupe_evidence(clean + [_document_evidence(name, slide, field_id="capabilities")])
                _promote_document_supported_claim(field)
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



def convert_internal_lineage_to_research_seeds(data: dict[str, Any]) -> dict[str, int]:
    """Keep PPT/internal lineage as non-accrediting research memory.

    No row is deleted. WESTCON_DOCUMENT is converted to RESEARCH_SEED so the
    claim/value and documentary clue survive future research, while public UI and
    support gates can only be closed by public evidence. Historical/archive rows
    remain historical and are explicitly discovery-only.
    """
    stats = {"document_rows_converted": 0, "historical_rows_marked": 0}

    def visit(obj: Any) -> None:
        if isinstance(obj, list):
            for item in obj:
                visit(item)
            return
        if not isinstance(obj, dict):
            return
        evidence = obj.get("evidence")
        if isinstance(evidence, list):
            for ev in evidence:
                if not isinstance(ev, dict):
                    continue
                kind = provenance_kind(ev)
                if kind == "WESTCON_DOCUMENT":
                    ev["original_provenance_origin"] = "WESTCON_DOCUMENT"
                    ev["provenance_origin"] = "RESEARCH_SEED"
                    ev["source_binding"] = "discovery-only"
                    ev["classification"] = "research-seed"
                    ev["source_role"] = "Pista interna de investigación; no acreditativa"
                    ev["accrediting"] = False
                    stats["document_rows_converted"] += 1
                elif kind in HISTORICAL_PROVENANCE_KINDS:
                    ev["source_binding"] = "discovery-only"
                    ev["source_role"] = "Linaje histórico; pista de investigación"
                    ev["accrediting"] = False
                    stats["historical_rows_marked"] += 1
        for value in obj.values():
            if isinstance(value, (dict, list)):
                visit(value)

    visit(data)
    return stats



def seed_from_knowledge_baseline(data: dict[str, Any], baseline: Mapping[str, Any] | None) -> dict[str, int]:
    """Ensure preserved baseline knowledge remains usable as a non-accrediting research clue.

    This does not claim the baseline is a public source and does not create missing values.
    It only attaches a RESEARCH_SEED marker to an exact value that still exists.
    """
    stats = {"baseline_claims_seen": 0, "seed_rows_added": 0, "unmatched_values": 0}
    protected = (baseline or {}).get("protected") or {}
    sections = tuple(protected.keys())

    def semantic(value: Any) -> str:
        return canonical(value) if isinstance(value, str) else _value_key(value)

    for section in sections:
        current_rows = [row for row in data.get(section) or [] if isinstance(row, dict)]
        current_index = {}
        for row in current_rows:
            for token in (row.get("id"), row.get("name")):
                key = canonical(token or "")
                if key:
                    current_index[key] = row
        for base_row in protected.get(section) or []:
            if not isinstance(base_row, Mapping):
                continue
            current = None
            for token in (base_row.get("id"), base_row.get("name")):
                current = current_index.get(canonical(token or ""))
                if current is not None:
                    break
            if current is None:
                continue
            for field_id, base_field in (base_row.get("fields") or {}).items():
                if not isinstance(base_field, Mapping):
                    continue
                raw = base_field.get("value")
                base_values = raw if isinstance(raw, list) else ([] if raw in (None, "", [], {}) else [raw])
                if not base_values:
                    continue
                current_field = ((current.get("fields") or {}).get(field_id) or {})
                if not isinstance(current_field, dict):
                    continue
                current_raw = current_field.get("value")
                current_values = current_raw if isinstance(current_raw, list) else ([] if current_raw in (None, "", [], {}) else [current_raw])
                items = [item for item in current_field.get("items") or [] if isinstance(item, dict)]
                for value in base_values:
                    stats["baseline_claims_seen"] += 1
                    actual = next((candidate for candidate in current_values if semantic(candidate) == semantic(value)), None)
                    if actual is None:
                        stats["unmatched_values"] += 1
                        continue
                    target = next((item for item in items if semantic(item.get("value")) == semantic(value)), None)
                    if target is None:
                        target = {"value": deepcopy(actual), "evidence": []}
                        current_field.setdefault("items", []).append(target)
                        items.append(target)
                    evidence = [ev for ev in target.get("evidence") or [] if isinstance(ev, Mapping)]
                    if any(provenance_kind(ev) in INTERNAL_RESEARCH_SEED_KINDS | HISTORICAL_PROVENANCE_KINDS for ev in evidence):
                        continue
                    seed = {
                        "source": "Memoria interna Westcon Decision Intelligence",
                        "title": "Pista preservada del baseline de conocimiento",
                        "date": str((baseline or {}).get("captured_at") or (baseline or {}).get("version") or "baseline"),
                        "description": "Valor conocido previamente; se conserva solo como pista para localizar y validar una fuente pública actual.",
                        "source_type": "research-seed",
                        "provenance_origin": "RESEARCH_SEED",
                        "source_binding": "discovery-only",
                        "classification": "research-seed",
                        "seed_origin": "knowledge_baseline",
                        "accrediting": False,
                    }
                    target["evidence"] = dedupe_evidence(list(target.get("evidence") or []) + [seed])
                    stats["seed_rows_added"] += 1
    return stats

def apply_public_evidence_migrations(data: dict[str, Any], migrations: Mapping[str, Any] | None) -> dict[str, int]:
    """Attach curated *public* primary evidence to exact known claims.

    Migrations are intentionally claim-specific (section + entity + field + value) and
    never create new values. They are a bootstrap bridge from internal research memory
    to public accreditation; normal research can later add/replace stronger public sources.
    """
    stats = {"configured": 0, "matched": 0, "evidence_added": 0, "unmatched": 0}
    rows = list((migrations or {}).get("claims") or [])
    stats["configured"] = len(rows)
    for rule in rows:
        if not isinstance(rule, Mapping):
            continue
        section = str(rule.get("section") or "")
        entity = canonical(rule.get("entity") or "")
        field_id = str(rule.get("field") or "")
        wanted = canonical(rule.get("value") or "")
        evidence = rule.get("evidence") or {}
        matched = False
        for row in data.get(section) or []:
            if not isinstance(row, dict) or canonical(row.get("name") or row.get("id") or "") != entity:
                continue
            field = ((row.get("fields") or {}).get(field_id) or {})
            if not isinstance(field, dict):
                continue
            raw = field.get("value")
            values = raw if isinstance(raw, list) else ([] if raw in (None, "", [], {}) else [raw])
            actual = next((value for value in values if canonical(value) == wanted), None)
            if actual is None:
                continue
            items = [item for item in field.get("items") or [] if isinstance(item, dict)]
            target = next((item for item in items if canonical(item.get("value") or "") == wanted), None)
            if target is None:
                target = {"value": deepcopy(actual), "evidence": []}
                field.setdefault("items", []).append(target)
            ev = deepcopy(dict(evidence))
            ev.setdefault("official", True)
            ev.setdefault("source_grade", "A2")
            ev.setdefault("source_type", "official-vendor-web")
            ev["provenance_origin"] = "PUBLIC_PRIMARY"
            ev["source_binding"] = "claim-specific"
            before = len(target.get("evidence") or [])
            target["evidence"] = dedupe_evidence(list(target.get("evidence") or []) + [ev])
            stats["evidence_added"] += max(0, len(target["evidence"]) - before)
            stats["matched"] += 1
            matched = True
            break
        if not matched:
            stats["unmatched"] += 1
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
