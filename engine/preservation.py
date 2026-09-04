"""Semantic non-destructive knowledge gate for canonical builds.

v4.1.0-HF6 keeps the HF4/HF5 semantic-preservation model, restores documentary support only to surviving baseline capabilities, and aligns release tests with the current evidence contract:
- build-owned/derived fields are recalculated and must not be compared as immutable facts;
- scalar external facts may be superseded by a new, still-accredited value;
- evidence preservation is claim-support based, not tied to fragile title/date fingerprints;
- relationship identity is semantic (canonical names when available), not raw transient ids;
- evidence on build-owned/derived projections is telemetry, not immutable external claim support.

The gate still blocks real losses of entities, set-valued external facts, accredited claim
support, graph relationships and Westcon-documented manufacturer capabilities.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from copy import deepcopy
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit, urlunsplit

from .knowledge_provenance import provenance_kind, typed_evidence_sufficient
from .model import canonical
from .settings import SECTIONS, VERSION

# These are projections/calculations owned by the build. Their source of truth is the graph,
# derivation logic or confidence model, so exact before/after value equality is not meaningful.
_RELATION_VIEW_FIELDS = {
    "distributors", "integrators", "vendor_relations",
    "westcon_overlap", "competitor_vendor_overlap",
}
_COMPUTED_FIELDS = {
    "confidence", "last_verified", "source_summary",
}
_DERIVED_CLASSES = {"DERIVED_FACT", "INTERNAL_CLASSIFICATION"}
_MANUFACTURER_FIELD_TOKENS = {
    "manufacturer", "manufacturers", "fabricante", "fabricantes", "vendor", "vendors",
    "vendorrelations", "manufacturerrelations", "westconoverlap", "competitorvendoroverlap",
    "westconmanufacturers", "portfoliomanufacturers",
}


def _value_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))


def _semantic_scalar(value: Any) -> str:
    if isinstance(value, str):
        return _value_key(["text", canonical(value)])
    return _value_key(value)


def _entity_key(section: str, row: Mapping[str, Any]) -> str:
    if section == "clients_public":
        notice = ((((row.get("fields") or {}).get("notice_id") or {}).get("value")) or "")
        return canonical(f"{row.get('name')}|{notice}")
    return canonical(row.get("id") or row.get("name"))


def _schema_column(data: Mapping[str, Any], section: str, field_id: str) -> Mapping[str, Any]:
    for column in ((data.get("schemas") or {}).get(section) or []):
        if isinstance(column, Mapping) and str(column.get("id") or "") == str(field_id):
            return column
    return {}


def _build_owned_field(data: Mapping[str, Any], section: str, field_id: str) -> bool:
    if field_id in _RELATION_VIEW_FIELDS or field_id in _COMPUTED_FIELDS:
        return True
    column = _schema_column(data, section, field_id)
    claim_class = str(column.get("claim_class") or "").upper()
    if claim_class in _DERIVED_CLASSES:
        return True
    if bool(column.get("derived")) or bool(column.get("computed")):
        return True
    return False


def _target_evidence(target: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    for ev in target.get("evidence") or []:
        if isinstance(ev, Mapping) and typed_evidence_sufficient(ev):
            yield ev


def _normalized_url(url: Any) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlsplit(raw)
        scheme = parsed.scheme.casefold()
        netloc = parsed.netloc.casefold()
        path = parsed.path.rstrip("/") or "/"
        # Query parameters are deliberately ignored for source identity because tracking and
        # locale parameters routinely change while the accredited page remains the same.
        return urlunsplit((scheme, netloc, path, "", ""))
    except Exception:
        return raw


def _source_identity(ev: Mapping[str, Any]) -> str:
    kind = provenance_kind(ev)
    if kind == "WESTCON_DOCUMENT":
        raw = [
            kind,
            canonical(ev.get("document_id") or ev.get("document") or ev.get("source") or ""),
            str(ev.get("slide") or ""),
        ]
    else:
        raw = [kind, _normalized_url(ev.get("url"))]
    return hashlib.sha1(_value_key(raw).encode("utf-8")).hexdigest()


def _claim_support_key(section: str, entity: str, field_id: str, *, value: Any = None, scalar: bool = False) -> str:
    # Scalar values are intentionally keyed to the field location rather than the exact value:
    # a newly researched, accredited scalar can supersede a stale scalar without being treated
    # as knowledge deletion. Set/list items remain value-specific and therefore non-destructive.
    raw = [section, entity, field_id, "scalar" if scalar else _semantic_scalar(value)]
    return hashlib.sha1(_value_key(raw).encode("utf-8")).hexdigest()


def _entity_lookup(data: Mapping[str, Any]) -> dict[str, tuple[str, str]]:
    """Resolve transient ids/aliases to the current canonical entity identity."""
    lookup: dict[str, tuple[str, str]] = {}
    for section in SECTIONS:
        for row in data.get(section) or []:
            if not isinstance(row, Mapping):
                continue
            row_id = str(row.get("id") or "").strip()
            name = str(row.get("name") or "").strip()
            canonical_name = canonical(name or row_id)
            current_id = row_id or canonical_name
            current_name = name or row_id
            for token in (row_id, name, canonical_name):
                key = canonical(token)
                if key:
                    lookup[key] = (current_id, current_name)
    return lookup


def _resolve_endpoint(value: Any, lookup: Mapping[str, tuple[str, str]]) -> tuple[str, str]:
    raw = str(value or "").strip()
    resolved = lookup.get(canonical(raw))
    if resolved:
        return resolved
    return raw, raw



def _relationship_is_hard_protected(rel: Mapping[str, Any]) -> bool:
    # Relations remain hard-protected by default. Explicitly provisional
    # or low-confidence derived signals are recalculable telemetry.
    validity = str(rel.get("validity") or "").strip().casefold().replace("_", "-")
    status = str(rel.get("status") or "").strip().casefold()
    try:
        confidence = float(rel.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    if validity in {"needs-corroboration", "needs corroboration", "provisional", "candidate"}:
        return False
    if bool(rel.get("derived")) and status in {"señal", "senal", "signal"} and confidence < 0.65:
        return False
    return True

def _relation_key(rel: Mapping[str, Any], lookup: Mapping[str, tuple[str, str]] | None = None) -> str:
    lookup = lookup or {}
    left_raw = rel.get("entity_a") or rel.get("entity_a_id") or ""
    right_raw = rel.get("entity_b") or rel.get("entity_b_id") or ""
    _, left_name = _resolve_endpoint(left_raw, lookup)
    _, right_name = _resolve_endpoint(right_raw, lookup)
    relation = canonical(rel.get("relation") or "")
    countries = sorted(canonical(x) for x in (rel.get("countries") or []) if str(x or "").strip())
    country = canonical(rel.get("country") or "")
    geo = countries or ([country] if country else [])
    return _value_key([canonical(left_name), relation, canonical(right_name), geo])


def _dedupe_evidence(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        item = deepcopy(dict(raw))
        key = _value_key([
            provenance_kind(item),
            _normalized_url(item.get("url")),
            canonical(item.get("document_id") or item.get("document") or ""),
            str(item.get("slide") or ""),
            canonical(item.get("title") or ""),
            canonical(item.get("description") or ""),
        ])
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _semantic_value_equal(left: Any, right: Any) -> bool:
    return _semantic_scalar(left) == _semantic_scalar(right)


def _row_index(data: Mapping[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for section in SECTIONS:
        for row in data.get(section) or []:
            if not isinstance(row, dict):
                continue
            result[(section, _entity_key(section, row))] = row
    return result


def _supported_rows(target: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [deepcopy(dict(ev)) for ev in _target_evidence(target)]


def _merge_supported_evidence(target: dict[str, Any], rows: Iterable[Mapping[str, Any]]) -> int:
    valid = [deepcopy(dict(ev)) for ev in rows if isinstance(ev, Mapping) and typed_evidence_sufficient(ev)]
    if not valid:
        return 0
    before = len(target.get("evidence") or [])
    target["evidence"] = _dedupe_evidence(list(target.get("evidence") or []) + valid)
    return max(0, len(target["evidence"]) - before)


_RESEARCH_SEED_KINDS = {
    "RESEARCH_SEED", "WESTCON_DOCUMENT", "HISTORICAL_RECOVERED", "ARCHIVE_RECOVERED",
    "ARCHIVE_CORROBORATION", "REPORT_CORROBORATION", "LEGACY_UNRESOLVED",
}


def _research_seed_rows(target: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return non-accrediting lineage rows that must remain as research memory."""
    return [
        deepcopy(dict(ev))
        for ev in target.get("evidence") or []
        if isinstance(ev, Mapping) and provenance_kind(ev) in _RESEARCH_SEED_KINDS
    ]


def _merge_research_seed_evidence(target: dict[str, Any], rows: Iterable[Mapping[str, Any]]) -> int:
    seeds = [
        deepcopy(dict(ev))
        for ev in rows
        if isinstance(ev, Mapping) and provenance_kind(ev) in _RESEARCH_SEED_KINDS
    ]
    if not seeds:
        return 0
    before = len(target.get("evidence") or [])
    target["evidence"] = _dedupe_evidence(list(target.get("evidence") or []) + seeds)
    return max(0, len(target["evidence"]) - before)


def _research_claim_key(section: str, entity: str, field_id: str, value: Any) -> str:
    return _value_key([section, entity, field_id, _semantic_scalar(value)])


def _seed_target_for_list(
    row: dict[str, Any], section: str, field_id: str, value: Any
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str]:
    """Find the surviving item for a research clue without recreating deleted knowledge.

    Exact semantic value matching is preferred.  The only relaxed identity is the existing
    quality-gate identity for vendor_relations, where multiple qualified variants are deliberately
    merged into one manufacturer row (e.g. ``Vendor · Gold`` + ``Vendor · Platinum``).
    """
    target_field, target_item, target_field_id = _find_list_target(row, field_id, value)
    if isinstance(target_item, dict):
        return target_field, target_item, target_field_id

    if section not in {"distributors", "integrators"} or str(field_id) != "vendor_relations" or not isinstance(value, str):
        return None, None, ""
    fields = row.get("fields") or {}
    direct = fields.get(field_id)
    if not isinstance(direct, dict) or not isinstance(direct.get("value"), list):
        return None, None, ""
    wanted_base, _display, _qual = _manufacturer_relation_parts(value)
    candidates: list[dict[str, Any]] = []
    for item in direct.get("items") or []:
        if not isinstance(item, dict) or not isinstance(item.get("value"), str):
            continue
        base, _display2, _qual2 = _manufacturer_relation_parts(item.get("value"))
        if base == wanted_base:
            candidates.append(item)
    if len(candidates) == 1:
        return direct, candidates[0], str(field_id)
    return None, None, ""


def restore_research_seed_support(current: dict[str, Any], baseline: Mapping[str, Any]) -> dict[str, int]:
    """Reattach non-accrediting research clues to the same surviving claim.

    This never creates a missing entity/value and never turns a research seed into accreditation.
    It only prevents canonical normalization/deduplication from detaching the internal clue that
    tells future research where to look for a public source.
    """
    current_rows = _row_index(current)
    stats = {
        "claims_examined": 0,
        "field_seed_rows_restored": 0,
        "item_seed_rows_restored": 0,
        "moved_item_seed_rows_restored": 0,
        "linecard_seed_rows_restored": 0,
    }
    for section in SECTIONS:
        for before_row in baseline.get(section) or []:
            if not isinstance(before_row, Mapping):
                continue
            entity_key = _entity_key(section, before_row)
            after_row = current_rows.get((section, entity_key))
            if not isinstance(after_row, dict):
                continue
            before_fields = before_row.get("fields") or {}
            after_fields = after_row.get("fields") or {}
            for field_id, before_field in before_fields.items():
                if not isinstance(before_field, Mapping):
                    continue
                raw = before_field.get("value")
                if raw in (None, "", [], {}):
                    continue
                field_seeds = _research_seed_rows(before_field)
                stats["claims_examined"] += 1
                if isinstance(raw, list):
                    item_map = {
                        _semantic_scalar(item.get("value")): item
                        for item in before_field.get("items") or []
                        if isinstance(item, Mapping) and item.get("value") not in (None, "", [], {})
                    }
                    for value in raw:
                        before_item = item_map.get(_semantic_scalar(value), {})
                        seed_rows = _research_seed_rows(before_item) + field_seeds
                        if not seed_rows:
                            continue
                        target_field, target_item, target_field_id = _seed_target_for_list(
                            after_row, section, str(field_id), value
                        )
                        if not isinstance(target_item, dict):
                            continue
                        added = _merge_research_seed_evidence(target_item, seed_rows)
                        stats["item_seed_rows_restored"] += added
                        if added and target_field_id != str(field_id):
                            stats["moved_item_seed_rows_restored"] += added
                        if added and section in {"distributors", "integrators"} and str(field_id) == "vendor_relations":
                            if not _semantic_value_equal(target_item.get("value"), value):
                                stats["linecard_seed_rows_restored"] += added
                else:
                    after_field = after_fields.get(field_id)
                    if not isinstance(after_field, dict) or not _semantic_value_equal(after_field.get("value"), raw):
                        continue
                    stats["field_seed_rows_restored"] += _merge_research_seed_evidence(
                        after_field, field_seeds
                    )
    stats["total_seed_rows_restored"] = (
        stats["field_seed_rows_restored"] + stats["item_seed_rows_restored"]
    )
    return stats


def _extract_seed_registry_records(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for section in SECTIONS:
        for row in data.get(section) or []:
            if not isinstance(row, Mapping):
                continue
            entity_key = _entity_key(section, row)
            entity_name = str(row.get("name") or row.get("id") or entity_key)
            for field_id, field in (row.get("fields") or {}).items():
                if not isinstance(field, Mapping):
                    continue
                raw = field.get("value")
                values = raw if isinstance(raw, list) else ([] if raw in (None, "", [], {}) else [raw])
                if not values:
                    continue
                field_seeds = _research_seed_rows(field)
                item_index = {
                    _semantic_scalar(item.get("value")): item
                    for item in field.get("items") or []
                    if isinstance(item, Mapping) and item.get("value") not in (None, "", [], {})
                }
                for value in values:
                    item = item_index.get(_semantic_scalar(value), {})
                    seed_rows = _dedupe_evidence(_research_seed_rows(item) + field_seeds)
                    if not seed_rows:
                        continue
                    claim_key = _research_claim_key(section, entity_key, str(field_id), value)
                    hints = []
                    for ev in seed_rows:
                        hints.append({
                            "provenance_origin": provenance_kind(ev),
                            "source": ev.get("source") or ev.get("title") or "",
                            "title": ev.get("title") or "",
                            "date": ev.get("date") or "",
                            "url": ev.get("url") or "",
                            "document_id": ev.get("document_id") or ev.get("document") or "",
                            "slide": ev.get("slide") or "",
                        })
                    record = {
                        "claim_key": claim_key,
                        "section": section,
                        "entity": entity_name,
                        "entity_key": entity_key,
                        "field": str(field_id),
                        "value": deepcopy(value),
                        "classification": "research-seed",
                        "accrediting": False,
                        "hints": hints,
                    }
                    previous = records.get(claim_key)
                    if previous is None:
                        records[claim_key] = record
                    else:
                        previous["hints"] = _dedupe_evidence(
                            [h for h in previous.get("hints") or [] if isinstance(h, Mapping)] + hints
                        )
    return list(records.values())


def sync_research_seed_registry(current: dict[str, Any], source: Mapping[str, Any] | None = None) -> dict[str, int]:
    """Persist research clues independently from table projection details.

    The registry is internal-only memory. It is not evidence, is not projected as a public source,
    and cannot close a gap. It guarantees that PPT/portfolio/history can guide later web research
    even when a canonical build changes field/item representation.
    """
    merged: dict[str, dict[str, Any]] = {}

    def ingest(records: Iterable[Mapping[str, Any]]) -> None:
        for raw in records:
            if not isinstance(raw, Mapping):
                continue
            claim_key = str(raw.get("claim_key") or "")
            if not claim_key:
                continue
            item = deepcopy(dict(raw))
            item["classification"] = "research-seed"
            item["accrediting"] = False
            previous = merged.get(claim_key)
            if previous is None:
                merged[claim_key] = item
                continue
            hints = _dedupe_evidence(
                [h for h in (previous.get("hints") or []) if isinstance(h, Mapping)]
                + [h for h in (item.get("hints") or []) if isinstance(h, Mapping)]
            )
            previous["hints"] = hints

    ingest(current.get("research_seed_registry") or [])
    if source is not None:
        ingest(source.get("research_seed_registry") or [])
        ingest(_extract_seed_registry_records(source))
    ingest(_extract_seed_registry_records(current))
    current["research_seed_registry"] = sorted(
        merged.values(), key=lambda row: (str(row.get("section")), str(row.get("entity_key")), str(row.get("field")), str(row.get("claim_key")))
    )
    return {
        "registry_claims": len(current["research_seed_registry"]),
        "source_claims_preserved": len({str(r.get("claim_key")) for r in (source or {}).get("research_seed_registry") or [] if isinstance(r, Mapping)}),
    }


def _find_list_target(row: dict[str, Any], field_id: str, value: Any) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str]:
    fields = row.get("fields") or {}
    direct = fields.get(field_id)
    if isinstance(direct, dict) and isinstance(direct.get("value"), list):
        for item in direct.get("items") or []:
            if isinstance(item, dict) and _semantic_value_equal(item.get("value"), value):
                return direct, item, field_id
        if any(_semantic_value_equal(candidate, value) for candidate in direct.get("value") or []):
            new_item = {"value": deepcopy(value), "evidence": []}
            direct.setdefault("items", []).append(new_item)
            return direct, new_item, field_id

    # Field-id migrations are allowed only when the same semantic value occurs in exactly one
    # list field of the same entity. This prevents generic values from being attached broadly.
    candidates: list[tuple[dict[str, Any], dict[str, Any] | None, str]] = []
    for candidate_id, field in fields.items():
        if not isinstance(field, dict) or not isinstance(field.get("value"), list):
            continue
        if not any(_semantic_value_equal(candidate, value) for candidate in field.get("value") or []):
            continue
        found_item = next((
            item for item in field.get("items") or []
            if isinstance(item, dict) and _semantic_value_equal(item.get("value"), value)
        ), None)
        candidates.append((field, found_item, str(candidate_id)))
    if len(candidates) != 1:
        return None, None, ""
    field, item, candidate_id = candidates[0]
    if item is None:
        item = {"value": deepcopy(value), "evidence": []}
        field.setdefault("items", []).append(item)
    return field, item, candidate_id


def restore_accredited_support(current: dict[str, Any], baseline: Mapping[str, Any]) -> dict[str, Any]:
    """Reattach valid input evidence when the exact knowledge item survived the build.

    This is deliberately not a data-restoration mechanism: values/entities that disappeared are
    never recreated here. It only prevents canonical normalization from detaching already-valid
    evidence from a value that is still present after the build.
    """
    current_rows = _row_index(current)
    stats = {
        "field_evidence_restored": 0,
        "item_evidence_restored": 0,
        "moved_item_support_restored": 0,
        "claims_examined": 0,
    }
    for section in SECTIONS:
        for before_row in baseline.get(section) or []:
            if not isinstance(before_row, Mapping):
                continue
            entity_key = _entity_key(section, before_row)
            after_row = current_rows.get((section, entity_key))
            if not isinstance(after_row, dict):
                continue
            before_fields = before_row.get("fields") or {}
            after_fields = after_row.get("fields") or {}
            for field_id, before_field in before_fields.items():
                if not isinstance(before_field, Mapping):
                    continue
                raw = before_field.get("value")
                if raw in (None, "", [], {}):
                    continue
                stats["claims_examined"] += 1
                if isinstance(raw, list):
                    item_map = {
                        _semantic_scalar(item.get("value")): item
                        for item in before_field.get("items") or []
                        if isinstance(item, Mapping) and item.get("value") not in (None, "", [], {})
                    }
                    field_support = _supported_rows(before_field)
                    for value in raw:
                        before_item = item_map.get(_semantic_scalar(value), {})
                        support = _supported_rows(before_item) or field_support
                        if not support:
                            continue
                        target_field, target_item, target_field_id = _find_list_target(after_row, str(field_id), value)
                        if not isinstance(target_item, dict):
                            continue
                        added = _merge_supported_evidence(target_item, support)
                        stats["item_evidence_restored"] += added
                        if added and target_field_id != str(field_id):
                            stats["moved_item_support_restored"] += added
                else:
                    after_field = after_fields.get(field_id)
                    if not isinstance(after_field, dict):
                        continue
                    if not _semantic_value_equal(after_field.get("value"), raw):
                        # A legitimate scalar supersession must be accredited by its new evidence;
                        # old evidence must never be copied onto a changed scalar value.
                        continue
                    stats["field_evidence_restored"] += _merge_supported_evidence(
                        after_field, _supported_rows(before_field)
                    )
    stats["total_evidence_restored"] = stats["field_evidence_restored"] + stats["item_evidence_restored"]
    return stats


def _is_manufacturer_list_field(data: Mapping[str, Any], section: str, field_id: str) -> bool:
    token = canonical(field_id).replace(" ", "").replace("_", "").replace("-", "")
    if token in _MANUFACTURER_FIELD_TOKENS:
        return True
    column = _schema_column(data, section, field_id)
    label = canonical(column.get("label") or column.get("name") or "")
    words = {part for part in label.replace("/", " ").replace("-", " ").split() if part}
    return bool(words & {"manufacturer", "manufacturers", "fabricante", "fabricantes", "vendor", "vendors"})


def _manufacturer_relation_parts(value: Any) -> tuple[str, str, str]:
    """Return (semantic base key, display base, qualifier) for a vendor relation value.

    quality.audit intentionally treats ``Vendor`` and ``Vendor · qualifier`` as the same
    manufacturer. Deep research can discover the same vendor through several relationship
    variants (country, tier, programme, etc.), so canonicalization must collapse those variants
    without discarding the qualifier information.
    """
    text = str(value or "").strip()
    if " · " in text:
        base, qualifier = text.split(" · ", 1)
    else:
        base, qualifier = text, ""
    return canonical(base), base.strip(), qualifier.strip()


def _merged_manufacturer_relation_value(rows: list[Any]) -> Any:
    """Create one UI value per manufacturer while preserving all distinct qualifiers."""
    if not rows:
        return ""
    # Non-string values are not expected in vendor line cards; preserve the first verbatim.
    if not all(isinstance(row, str) for row in rows):
        return deepcopy(rows[0])
    _key, base, _qual = _manufacturer_relation_parts(rows[0])
    qualifiers: list[str] = []
    seen_qualifiers: set[str] = set()
    for raw in rows:
        _row_key, row_base, qualifier = _manufacturer_relation_parts(raw)
        if not base and row_base:
            base = row_base
        qkey = canonical(qualifier)
        if qualifier and qkey not in seen_qualifiers:
            seen_qualifiers.add(qkey)
            qualifiers.append(qualifier)
    return f"{base} · {' / '.join(qualifiers)}" if qualifiers else base


def dedupe_manufacturer_lists(data: dict[str, Any]) -> dict[str, int]:
    """Collapse manufacturer duplicates exactly as the quality gate defines them.

    The quality invariant for distributor/integrator ``vendor_relations`` uses the canonical
    manufacturer name *before* the first ``" · "`` separator. Therefore values such as
    ``"Fortinet · Expert"`` and ``"Fortinet · Advanced"`` are duplicates for line-card
    purposes even though their full strings differ. HF4 emits one manufacturer row, keeps every
    distinct qualifier in the merged display value, and merges all atomic evidence. No unique
    manufacturer, qualifier or evidence row is discarded.
    """
    stats = {
        "fields_examined": 0,
        "duplicates_removed": 0,
        "evidence_merged": 0,
        "qualified_variants_merged": 0,
    }
    for section in SECTIONS:
        for row in data.get(section) or []:
            if not isinstance(row, dict):
                continue
            for field_id, field in (row.get("fields") or {}).items():
                if not isinstance(field, dict) or not isinstance(field.get("value"), list):
                    continue
                if not _is_manufacturer_list_field(data, section, str(field_id)):
                    continue
                stats["fields_examined"] += 1

                raw_values = [deepcopy(v) for v in (field.get("value") or []) if str(v or "").strip()]
                # Only vendor_relations has the special base-name invariant in engine.quality.
                # Other manufacturer lists retain exact semantic-value grouping.
                quality_linecard = section in {"distributors", "integrators"} and str(field_id) == "vendor_relations"
                grouped_values: dict[str, list[Any]] = defaultdict(list)
                group_order: list[str] = []
                for value in raw_values:
                    if quality_linecard and isinstance(value, str):
                        base_key, _base, _qualifier = _manufacturer_relation_parts(value)
                    else:
                        base_key = _semantic_scalar(value)
                    if base_key not in grouped_values:
                        group_order.append(base_key)
                    grouped_values[base_key].append(value)

                # Index atomic items by both their exact semantic value and their manufacturer base.
                items = [item for item in (field.get("items") or []) if isinstance(item, Mapping)]
                exact_items: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
                base_items: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
                for item in items:
                    ivalue = item.get("value")
                    if ivalue in (None, "", [], {}):
                        continue
                    exact_items[_semantic_scalar(ivalue)].append(item)
                    if quality_linecard and isinstance(ivalue, str):
                        base_key, _base, _qualifier = _manufacturer_relation_parts(ivalue)
                    else:
                        base_key = _semantic_scalar(ivalue)
                    base_items[base_key].append(item)

                values_out: list[Any] = []
                items_out: list[dict[str, Any]] = []
                for base_key in group_order:
                    variants = grouped_values[base_key]
                    merged_value = (
                        _merged_manufacturer_relation_value(variants)
                        if quality_linecard
                        else deepcopy(variants[0])
                    )
                    values_out.append(merged_value)
                    if len(variants) > 1:
                        stats["duplicates_removed"] += len(variants) - 1
                        # Count only genuinely different suffix/display variants here; pure case/space
                        # aliases are still tracked by duplicates_removed.
                        if len({_semantic_scalar(v) for v in variants}) > 1:
                            stats["qualified_variants_merged"] += len(variants) - 1

                    matching: list[Mapping[str, Any]] = []
                    for variant in variants:
                        matching.extend(exact_items.get(_semantic_scalar(variant)) or [])
                    # Projection code can sometimes normalize item.value separately from field.value;
                    # include same-base items so their evidence is not orphaned.
                    for candidate in base_items.get(base_key) or []:
                        if candidate not in matching:
                            matching.append(candidate)

                    merged_item: dict[str, Any] = {"value": deepcopy(merged_value), "evidence": []}
                    if matching:
                        # Preserve all non-identity metadata from the first item and explicitly retain
                        # the original relation variants for audit/debugging.
                        merged_item = deepcopy(dict(matching[0]))
                        merged_item["value"] = deepcopy(merged_value)
                        merged_evidence = _dedupe_evidence(
                            ev for item in matching for ev in (item.get("evidence") or [])
                        )
                        before_max = max((len(item.get("evidence") or []) for item in matching), default=0)
                        stats["evidence_merged"] += max(0, len(merged_evidence) - before_max)
                        merged_item["evidence"] = merged_evidence
                    variant_text = [str(v).strip() for v in variants if str(v).strip()]
                    if len(variant_text) > 1:
                        merged_item["relation_variants"] = variant_text
                    items_out.append(merged_item)

                field["value"] = values_out
                # Atomic traceability requires one item for every emitted value. Always write items,
                # even when the projection arrived without them; evidence remains empty if none existed
                # and the normal quality gate will then correctly reject it.
                field["items"] = items_out
    return stats



def restore_documented_capability_support(data: dict[str, Any], preservation_source: Mapping[str, Any]) -> dict[str, int]:
    """Reattach WESTCON_DOCUMENT evidence to the *same surviving* manufacturer capability.

    The canonical build is allowed to normalize item containers, but it must never detach the
    Westcon-document provenance that was already attached to a capability in the post-research
    input. This reconciliation is deliberately narrow:
    - same manufacturer identity;
    - same semantic capability value;
    - only evidence already present in the preservation source;
    - only WESTCON_DOCUMENT rows;
    - never recreates a capability value that disappeared.

    This prevents false attribution of newly researched capabilities while preserving the exact
    documentary lineage of baseline capabilities such as the Check Point capabilities detected
    by HF5.
    """
    stats = {
        "source_documented_capabilities": 0,
        "surviving_documented_capabilities": 0,
        "document_evidence_restored": 0,
        "atomic_items_created": 0,
        "manufacturers_unresolved": 0,
        "capabilities_missing_after_build": 0,
    }

    current_rows = [row for row in (data.get("manufacturers") or []) if isinstance(row, dict)]
    current_index: dict[str, dict[str, Any]] = {}
    for row in current_rows:
        for token in (row.get("id"), row.get("name")):
            key = canonical(token or "")
            if key:
                current_index[key] = row

    for source_row in preservation_source.get("manufacturers") or []:
        if not isinstance(source_row, Mapping):
            continue
        current = None
        for token in (source_row.get("id"), source_row.get("name")):
            current = current_index.get(canonical(token or ""))
            if current is not None:
                break
        if current is None:
            stats["manufacturers_unresolved"] += 1
            continue

        source_field = ((source_row.get("fields") or {}).get("capabilities") or {})
        current_field = ((current.get("fields") or {}).get("capabilities") or {})
        if not isinstance(source_field, Mapping) or not isinstance(current_field, dict):
            continue

        source_items = [item for item in (source_field.get("items") or []) if isinstance(item, Mapping)]
        source_field_docs = [
            deepcopy(dict(ev)) for ev in (source_field.get("evidence") or [])
            if isinstance(ev, Mapping)
            and provenance_kind(ev) == "WESTCON_DOCUMENT"
            and typed_evidence_sufficient(ev)
        ]

        current_values = current_field.get("value")
        current_values = current_values if isinstance(current_values, list) else ([] if current_values in (None, "", [], {}) else [current_values])
        current_items = [item for item in (current_field.get("items") or []) if isinstance(item, dict)]

        for source_item in source_items:
            value = source_item.get("value")
            if value in (None, "", [], {}):
                continue
            docs = [
                deepcopy(dict(ev)) for ev in (source_item.get("evidence") or [])
                if isinstance(ev, Mapping)
                and provenance_kind(ev) == "WESTCON_DOCUMENT"
                and typed_evidence_sufficient(ev)
            ]
            # Snapshot semantics treat field-level support as support for an item only when the
            # item has no own accredited support. Preserve that behaviour without inventing docs.
            if not docs:
                item_has_accrediting = any(
                    isinstance(ev, Mapping) and typed_evidence_sufficient(ev)
                    for ev in (source_item.get("evidence") or [])
                )
                if not item_has_accrediting:
                    docs = list(source_field_docs)
            if not docs:
                continue

            stats["source_documented_capabilities"] += 1
            if not any(_semantic_value_equal(candidate, value) for candidate in current_values):
                stats["capabilities_missing_after_build"] += 1
                continue

            target = next((
                item for item in current_items
                if _semantic_value_equal(item.get("value"), value)
            ), None)
            if target is None:
                target = {"value": deepcopy(value), "evidence": []}
                current_field.setdefault("items", []).append(target)
                current_items.append(target)
                stats["atomic_items_created"] += 1

            stats["surviving_documented_capabilities"] += 1
            before = len(target.get("evidence") or [])
            target["evidence"] = _dedupe_evidence(list(target.get("evidence") or []) + docs)
            stats["document_evidence_restored"] += max(0, len(target["evidence"]) - before)

    return stats

def restore_preserved_relations(current_graph: dict[str, Any], baseline_graph: Mapping[str, Any], data: Mapping[str, Any]) -> dict[str, Any]:
    """Carry forward graph relations across deterministic id re-keying/rebuilds.

    A relation is restored only when both endpoints still resolve to entities in the current
    intelligence dataset. Missing entities therefore remain a hard preservation failure.
    """
    lookup = _entity_lookup(data)
    relationships = [rel for rel in (current_graph.get("relationships") or []) if isinstance(rel, dict)]
    seen = {_relation_key(rel, lookup) for rel in relationships}
    restored = 0
    skipped_unresolved = 0
    skipped_provisional = 0
    for raw in baseline_graph.get("relationships") or []:
        if not isinstance(raw, Mapping):
            continue
        if not _relationship_is_hard_protected(raw):
            skipped_provisional += 1
            continue
        key = _relation_key(raw, lookup)
        if key in seen:
            continue
        left_token = raw.get("entity_a") or raw.get("entity_a_id") or ""
        right_token = raw.get("entity_b") or raw.get("entity_b_id") or ""
        left = lookup.get(canonical(left_token))
        right = lookup.get(canonical(right_token))
        if not left or not right:
            skipped_unresolved += 1
            continue
        rel = deepcopy(dict(raw))
        rel["entity_a_id"], rel["entity_a"] = left
        rel["entity_b_id"], rel["entity_b"] = right
        relationships.append(rel)
        seen.add(key)
        restored += 1
    current_graph["relationships"] = relationships
    return {
        "relations_restored": restored,
        "relations_skipped_unresolved_endpoints": skipped_unresolved,
        "relations_skipped_provisional": skipped_provisional,
        "relations_after": len(relationships),
    }


def snapshot(data: Mapping[str, Any], graph: Mapping[str, Any] | None = None) -> dict[str, Any]:
    entities: dict[str, set[str]] = defaultdict(set)
    values: dict[str, set[str]] = defaultdict(set)
    derived_values: dict[str, set[str]] = defaultdict(set)
    value_modes: dict[str, str] = {}
    supported_scalar_fields: set[str] = set()
    # Compatibility name: "evidences" now represents accredited claim-support fingerprints.
    # This is intentionally stable when a source title/date changes or a stronger source replaces it.
    evidences: set[str] = set()
    evidence_sources: set[str] = set()
    derived_evidences: set[str] = set()
    research_seed_claims: set[str] = set()

    for section in SECTIONS:
        for row in data.get(section) or []:
            if not isinstance(row, Mapping):
                continue
            entity = _entity_key(section, row)
            entities[section].add(entity)
            for field_id, field in (row.get("fields") or {}).items():
                if not isinstance(field, Mapping):
                    continue
                raw = field.get("value")
                is_list = isinstance(raw, list)
                field_values = raw if is_list else ([] if raw in (None, "", [], {}) else [raw])
                if not field_values:
                    continue

                field_key = f"{section}:{entity}:{field_id}"
                build_owned = _build_owned_field(data, section, field_id)
                target_values = derived_values if build_owned else values
                value_modes[field_key] = "list" if is_list else "scalar"

                items = [item for item in field.get("items") or [] if isinstance(item, Mapping)]
                item_index = {
                    _semantic_scalar(item.get("value")): item
                    for item in items
                    if item.get("value") not in (None, "", [], {})
                }
                field_supported_rows = list(_target_evidence(field))

                for value in field_values:
                    normalized = _semantic_scalar(value)
                    target_values[field_key].add(normalized)
                    claim = _value_key([section, entity, field_id, normalized])

                    item = item_index.get(normalized, {})
                    item_supported_rows = list(_target_evidence(item)) if item else []
                    support_rows = item_supported_rows or field_supported_rows
                    if support_rows:
                        support_key = _claim_support_key(
                            section,
                            entity,
                            field_id,
                            value=value,
                            scalar=not is_list,
                        )
                        # Build-owned fields (graph projections, confidence, derived/internal
                        # classifications) are regenerated from protected inputs. Their attached
                        # evidence may legitimately be reshaped with the projection and therefore
                        # is telemetry, not immutable external claim support. External facts remain
                        # fully protected by the strict evidence gate below.
                        if build_owned:
                            derived_evidences.add(support_key)
                        else:
                            evidences.add(support_key)
                            if not is_list:
                                supported_scalar_fields.add(field_key)
                        for ev in support_rows:
                            evidence_sources.add(_source_identity(ev))

                    # Internal deck/historical lineage is not proof, but the clue itself is
                    # protected. Audit at claim level so representation/source metadata may evolve
                    # without silently deleting the research memory.
                    raw_rows = list(field.get("evidence") or []) + list((item or {}).get("evidence") or [])
                    if any(
                        provenance_kind(ev) in _RESEARCH_SEED_KINDS
                        for ev in raw_rows if isinstance(ev, Mapping)
                    ):
                        research_seed_claims.add(claim)

    # HF8: the internal research-memory registry protects clues independently from
    # presentation/field normalization. Registry rows are non-accrediting by contract.
    for record in data.get("research_seed_registry") or []:
        if not isinstance(record, Mapping):
            continue
        claim_key = str(record.get("claim_key") or "")
        if claim_key:
            research_seed_claims.add(claim_key)

    relations = set()
    provisional_relations = set()
    relation_lookup = _entity_lookup(data)
    for rel in (graph or {}).get("relationships") or []:
        if not isinstance(rel, Mapping):
            continue
        key = _relation_key(rel, relation_lookup)
        if _relationship_is_hard_protected(rel):
            relations.add(key)
        else:
            provisional_relations.add(key)

    return {
        "version": VERSION,
        "entities": {key: sorted(value) for key, value in entities.items()},
        "values": {key: sorted(value) for key, value in values.items()},
        "derived_values": {key: sorted(value) for key, value in derived_values.items()},
        "value_modes": value_modes,
        "supported_scalar_fields": sorted(supported_scalar_fields),
        "evidences": sorted(evidences),
        "evidence_sources": sorted(evidence_sources),
        "derived_evidences": sorted(derived_evidences),
        "relations": sorted(relations),
        "provisional_relations": sorted(provisional_relations),
        "research_seed_claims": sorted(research_seed_claims),
    }


def audit(before: Mapping[str, Any], after: Mapping[str, Any], exceptions: Mapping[str, Any] | None = None) -> dict[str, Any]:
    allowed = exceptions or {}
    allowed_entities = set(allowed.get("entities") or [])
    allowed_values = set(allowed.get("values") or [])
    allowed_evidences = set(allowed.get("evidences") or [])
    allowed_relations = set(allowed.get("relations") or [])

    missing_entities = []
    for section in SECTIONS:
        old = set((before.get("entities") or {}).get(section) or [])
        new = set((after.get("entities") or {}).get(section) or [])
        missing_entities.extend(
            f"{section}:{value}"
            for value in sorted(old - new)
            if f"{section}:{value}" not in allowed_entities
        )

    missing_values = []
    superseded_values = []
    after_values = after.get("values") or {}
    before_modes = before.get("value_modes") or {}
    after_supported_scalars = set(after.get("supported_scalar_fields") or [])
    for field_key, old_rows in (before.get("values") or {}).items():
        old_set = set(old_rows or [])
        new_set = set(after_values.get(field_key) or [])
        lost = old_set - new_set
        if not lost:
            continue

        mode = before_modes.get(field_key) or "list"
        # A scalar is allowed to evolve only when the replacement is still populated and
        # accredited. Unsupported overwrites remain a hard preservation failure.
        if mode == "scalar" and new_set and field_key in after_supported_scalars:
            superseded_values.extend(f"{field_key}:{value}" for value in sorted(lost))
            continue

        for value in sorted(lost):
            full = f"{field_key}:{value}"
            if full not in allowed_values:
                missing_values.append(full)

    # Evidence is audited at claim-support level, not at raw source-row level. Replacing a stale
    # source with another valid source is legitimate; dropping all accredited support is not.
    missing_evidences = sorted(
        set(before.get("evidences") or [])
        - set(after.get("evidences") or [])
        - allowed_evidences
    )
    replaced_evidence_sources = sorted(
        set(before.get("evidence_sources") or []) - set(after.get("evidence_sources") or [])
    )
    missing_relations = sorted(
        set(before.get("relations") or [])
        - set(after.get("relations") or [])
        - allowed_relations
    )
    missing_research_seeds = sorted(
        set(before.get("research_seed_claims") or [])
        - set(after.get("research_seed_claims") or [])
    )

    floors = {"trends": 15, "architectures": 12, "manufacturers": 36}
    floor_failures = []
    for section, floor in floors.items():
        count = len((after.get("entities") or {}).get(section) or [])
        if count < floor:
            floor_failures.append(f"{section}:{count}<{floor}")

    errors = []
    if missing_entities:
        errors.append(f"Entidades desaparecidas sin excepción: {len(missing_entities)}")
    if missing_values:
        errors.append(f"Valores poblados desaparecidos sin excepción: {len(missing_values)}")
    if missing_relations:
        errors.append(f"Relaciones válidas desaparecidas sin excepción: {len(missing_relations)}")
    if missing_evidences:
        errors.append(f"Soportes acreditativos desaparecidos sin excepción: {len(missing_evidences)}")
    if missing_research_seeds:
        errors.append(f"Pistas internas/históricas de investigación desaparecidas: {len(missing_research_seeds)}")
    if floor_failures:
        errors.append("Mínimos de conocimiento incumplidos: " + ", ".join(floor_failures))

    before_derived = sum(len(rows) for rows in (before.get("derived_values") or {}).values())
    after_derived = sum(len(rows) for rows in (after.get("derived_values") or {}).values())
    before_derived_evidence = len(before.get("derived_evidences") or [])
    after_derived_evidence = len(after.get("derived_evidences") or [])

    return {
        "version": VERSION,
        "hotfix": "v4.1.0-HF8-public-evidence-memory",
        "status": "PASS" if not errors else "FAIL",
        "policy": (
            "preserve entities, external set-valued facts, accredited claim support, semantic graph relations "
            "and internal/historical research clues; public web evidence is the only external accreditation; "
            "reconcile detached support/id re-keying before audit; "
            "audit build-owned evidence as derived telemetry; allow accredited scalar supersession and build-owned recalculation"
        ),
        "errors": errors,
        "before": {
            "entities": {section: len((before.get("entities") or {}).get(section) or []) for section in SECTIONS},
            "values": sum(len(rows) for rows in (before.get("values") or {}).values()),
            "evidences": len(before.get("evidences") or []),
            "relations": len(before.get("relations") or []),
            "provisional_relations": len(before.get("provisional_relations") or []),
            "research_seed_claims": len(before.get("research_seed_claims") or []),
            "derived_values": before_derived,
            "derived_evidence_support": before_derived_evidence,
        },
        "after": {
            "entities": {section: len((after.get("entities") or {}).get(section) or []) for section in SECTIONS},
            "values": sum(len(rows) for rows in (after.get("values") or {}).values()),
            "evidences": len(after.get("evidences") or []),
            "relations": len(after.get("relations") or []),
            "provisional_relations": len(after.get("provisional_relations") or []),
            "research_seed_claims": len(after.get("research_seed_claims") or []),
            "derived_values": after_derived,
            "derived_evidence_support": after_derived_evidence,
        },
        "semantic_changes": {
            "accredited_scalar_supersessions": superseded_values[:200],
            "raw_evidence_sources_replaced_or_removed": replaced_evidence_sources[:200],
            "derived_values_before": before_derived,
            "provisional_relationship_signals_before": len(before.get("provisional_relations") or []),
            "provisional_relationship_signals_after": len(after.get("provisional_relations") or []),
            "derived_values_after": after_derived,
            "derived_evidence_support_before": before_derived_evidence,
            "derived_evidence_support_after": after_derived_evidence,
        },
        "missing": {
            "entities": missing_entities[:200],
            "values": missing_values[:200],
            "evidences": missing_evidences[:200],
            "relations": missing_relations[:200],
            "research_seed_claims": missing_research_seeds[:200],
            "floor_failures": floor_failures,
        },
    }
