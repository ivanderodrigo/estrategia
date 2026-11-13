"""Curated *public* research verified against exact primary source pages.

Unlike a generic discovery search, each claim in the registry has its own link.
The topic rules match only the row title, never arbitrary prose, and attach no
source to an unrelated field or vendor/channel relation.
"""
from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from .enrichment import merge_field
from .model import canonical
from .storage import read_json


def _claim_field(field_id: str, claims: list[list[Any]]) -> dict[str, Any]:
    items = []
    for pair in claims:
        value, source = pair
        if not isinstance(value, str) or not isinstance(source, dict):
            continue
        ev = deepcopy(source)
        ev["field"] = field_id
        ev["item_value"] = value
        ev["atomic"] = True
        ev["source_binding"] = "claim-specific"
        items.append({"value": value, "evidence": [ev],
                      "confidence": 0.86, "claim_type": "fact",
                      "assertion_status": "CONFIRMADO"})
    return {"value": [x["value"] for x in items], "items": items,
            "evidence": [], "confidence": 0.86, "claim_type": "fact",
            "assertion_status": "CONFIRMADO"}


def _safe_research_merge(current: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Never replace an accredited scalar with a different claim.
    
    The same category can be described by multiple sources, but only list-valued
    fields are additive. A scalar text is immutable unless it is empty.
    """
    old_value = current.get("value")
    new_value = new.get("value")
    if old_value not in (None, "", [], {}) and not isinstance(old_value, list):
        candidates = new_value if isinstance(new_value, list) else [new_value]
        if not any(canonical(old_value) == canonical(value) for value in candidates):
            return current
        return merge_field(current, {**new, "value": old_value})
    return merge_field(current, new)


def apply_verified_research(data: dict[str, Any]) -> dict[str, int]:
    registry = read_json("config/current/verified_research_20261113.json", {})
    stats = {"manufacturer_values_added": 0, "trend_values_added": 0,
             "architecture_values_added": 0, "rows_enriched": 0}
    if not isinstance(registry, dict):
        return stats
    by_section = registry.get("entities") or {}
    for section, names in by_section.items():
        if section != "manufacturers":
            continue
        for row in data.get(section) or []:
            specs = names.get(row.get("name")) or {}
            if not specs:
                continue
            fields = row.setdefault("fields", {})
            touched = False
            for field_id, claims in specs.items():
                existing = fields.get(field_id) or {}
                old = {canonical(x) for x in (
                    existing.get("value") if isinstance(existing.get("value"), list)
                    else ([existing.get("value")] if existing.get("value") else [])
                )}
                facts = _claim_field(field_id, claims)
                fields[field_id] = _safe_research_merge(existing, facts)
                result_value = fields[field_id].get("value")
                actual = result_value if isinstance(result_value, list) else ([result_value] if result_value else [])
                newly = sum(1 for value in actual if canonical(value) not in old)
                stats["manufacturer_values_added"] += newly
                touched |= bool(newly)
            stats["rows_enriched"] += int(touched)

    # Topic evidence is attached to one *exact* field and claim; a report about
    # Zero Trust cannot substantiate an unrelated revenue, market-share or linecard.
    for section, counter in (("trends", "trend_values_added"),
                             ("architectures", "architecture_values_added")):
        rules = [rule for rule in registry.get("topic_rules") or []
                 if rule.get("section") == section]
        for row in data.get(section) or []:
            name = str(row.get("name") or "")
            fields = row.setdefault("fields", {})
            touched = False
            for rule in rules:
                pattern = str(rule.get("pattern") or "")
                if not pattern or not re.search(pattern, name, re.IGNORECASE):
                    continue
                field_id = str(rule.get("field") or "")
                if field_id not in (("sources", "drivers", "observed") if section == "trends"
                                    else ("analyst_basis", "principles", "context")):
                    continue
                claims = rule.get("values") or []
                old_field = fields.get(field_id) or {}
                old = {canonical(x) for x in (
                    old_field.get("value") if isinstance(old_field.get("value"), list)
                    else ([old_field.get("value")] if old_field.get("value") else [])
                )}
                fields[field_id] = _safe_research_merge(old_field, _claim_field(field_id, claims))
                result_value = fields[field_id].get("value")
                actual = result_value if isinstance(result_value, list) else ([result_value] if result_value else [])
                added = sum(1 for value in actual if canonical(value) not in old)
                stats[counter] += added
                touched |= bool(added)
            stats["rows_enriched"] += int(touched)
    return stats
