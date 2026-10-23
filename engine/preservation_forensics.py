"""Trace exact accredited claim-support losses on failed builds only.

Read-only: no evidence, values, or audit decisions are changed.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from . import preservation as preservation
from .settings import SECTIONS
from .provenance import evidence_for_item


def _find(data: Mapping[str, Any], fingerprints: set[str]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for section in SECTIONS:
        for row in data.get(section) or []:
            if not isinstance(row, Mapping):
                continue
            entity_key = preservation._entity_key(section, row)
            for field_id, field in (row.get("fields") or {}).items():
                if not isinstance(field, Mapping):
                    continue
                raw = field.get("value")
                is_list = isinstance(raw, list)
                vals = raw if is_list else ([] if raw in (None, "", [], {}) else [raw])
                for value in vals:
                    if value in (None, "", [], {}):
                        continue
                    fingerprint = preservation._claim_support_key(
                        section, entity_key, str(field_id), value=value,
                        scalar=not is_list,
                    )
                    if fingerprint not in fingerprints:
                        continue
                    items = [
                        item for item in field.get("items") or []
                        if isinstance(item, Mapping)
                        and preservation._semantic_scalar(item.get("value"))
                        == preservation._semantic_scalar(value)
                    ]
                    item_evidence = [
                        dict(ev) for item in items
                        for ev in item.get("evidence") or []
                        if isinstance(ev, Mapping)
                    ]
                    field_evidence = [
                        dict(ev) for ev in field.get("evidence") or []
                        if isinstance(ev, Mapping)
                    ]
                    rows = item_evidence + field_evidence
                    accepted = evidence_for_item(
                        rows, row.get("name"), value, field_id=str(field_id),
                    ) if is_list else preservation._target_evidence(field)
                    matches.append({
                        "fingerprint": fingerprint,
                        "section": section,
                        "entity": row.get("name"),
                        "entity_key": entity_key,
                        "field": str(field_id),
                        "value": value,
                        "list": is_list,
                        "build_owned": preservation._build_owned_field(data, section, str(field_id)),
                        "item_evidence": item_evidence[:12],
                        "field_evidence": field_evidence[:12],
                        "accepted_evidence_count": len(list(accepted)),
                    })
    return matches


def trace_missing_evidences(
    before_data: Mapping[str, Any],
    after_data: Mapping[str, Any],
    preservation_audit: Mapping[str, Any],
) -> dict[str, Any]:
    fingerprints = {
        str(fingerprint)
        for fingerprint in (preservation_audit.get("missing") or {}).get("evidences") or []
    }
    return {
        "missing_fingerprints": sorted(fingerprints),
        "before_claims": _find(before_data, fingerprints),
        "after_claims": _find(after_data, fingerprints),
        "note": "Claim identity is section/entity/field/value for lists and section/entity/field for scalars. This trace does not change the preservation verdict.",
    }
