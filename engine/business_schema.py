"""Business-facing schema enrichment for the canonical intelligence model.

The schema is additive: existing fields and metadata are never removed. Empty new
dimensions remain honest research debt and the browser hides columns that have no
values in the current result set.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .settings import SECTIONS
from .storage import read_json


SCHEMA_PATH = "config/current/business_intelligence_schema.json"


def _merge_column(current: Mapping[str, Any] | None, wanted: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(current or {}))
    # v4.1 metadata is the public contract, while unknown historical metadata is retained.
    result.update(deepcopy(dict(wanted)))
    return result


def apply_business_schema(data: dict[str, Any]) -> dict[str, int]:
    """Merge the current business schema without deleting rows, fields or old columns."""
    configured = read_json(SCHEMA_PATH, {})
    sections = configured.get("sections") if isinstance(configured, Mapping) else {}
    stats = {"columns_added": 0, "columns_updated": 0, "sections": 0}
    schemas = data.setdefault("schemas", {})

    for section in SECTIONS:
        wanted_rows = (sections or {}).get(section) or []
        if not wanted_rows:
            continue
        current_rows = [row for row in schemas.get(section) or [] if isinstance(row, Mapping)]
        current_by_id = {str(row.get("id") or ""): row for row in current_rows if row.get("id")}
        merged = []
        seen = set()
        for wanted in wanted_rows:
            if not isinstance(wanted, Mapping) or not wanted.get("id"):
                continue
            field_id = str(wanted["id"])
            seen.add(field_id)
            existing = current_by_id.get(field_id)
            merged.append(_merge_column(existing, wanted))
            stats["columns_added" if existing is None else "columns_updated"] += 1
        # Preserve any non-v4.1 column after the canonical comparison order.
        for current in current_rows:
            field_id = str(current.get("id") or "")
            if field_id and field_id not in seen:
                merged.append(deepcopy(dict(current)))
        schemas[section] = merged
        stats["sections"] += 1
    return stats

