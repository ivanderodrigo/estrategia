"""Current first-party Westcon evidence for v4.2.2.

This module is deliberately narrow. It lets *current* Westcon first-party material
accredit Westcon-owned facts (portfolio membership and the portfolio/capability taxonomy
that Westcon is actively presenting), while historical decks and recovered lineage remain
research seeds only.

It never uses the FY27 deck to accredit third-party relationships, market share, customer
usage, revenue, partner status, awards, or other facts that the deck does not establish.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .model import canonical

CURRENT_KINDS = {"WESTCON_DOCUMENT_CURRENT", "WESTCON_FIRST_PARTY_CURRENT"}


def _has_value(value: Any) -> bool:
    return value not in (None, "", [], {})


def _dedupe_evidence(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        ev = deepcopy(dict(raw))
        key = tuple(str(ev.get(k) or "") for k in (
            "provenance_origin", "document_id", "statement_id", "slide", "field", "item_value", "title", "url"
        ))
        if key in seen:
            continue
        seen.add(key)
        out.append(ev)
    return out


def _slug(name: str) -> str:
    value = canonical(name).replace(" ", "-")
    return "mfr-" + (value or "westcon-vendor")


def _norm_capability(value: Any) -> str:
    text = canonical(value or "")
    replacements = {
        "waap waf": "waf waap",
        "sse sase": "sase sse",
        "xdr edr": "edr xdr",
        "wifi": "wi fi",
        "high density wifi": "high density wi fi",
        "ai driven threat detection": "ai threat detection",
        "ai driven ndr xdr threat detection": "ai threat detection",
    }
    return replacements.get(text, text)


def _document_evidence(document: Mapping[str, Any], *, field: str, value: Any, slides: list[int]) -> dict[str, Any]:
    ev = deepcopy(dict(document))
    ev["field"] = field
    ev["item_value"] = value
    ev["atomic"] = True
    ev["slide"] = int(slides[0]) if slides else None
    if len(slides) > 1:
        ev["supporting_slides"] = [int(x) for x in slides]
    ev["title"] = f"{document.get('title')} · slide {ev.get('slide')}"
    ev["description"] = (
        f"Documentación corporativa Westcon FY2027 vigente que acredita de forma atómica "
        f"el dato «{value}» en {field}."
    )
    ev["source_role"] = "Fuente documental Westcon vigente"
    ev["intelligence_tier"] = "A1"
    return ev


def _rule_evidence(rule: Mapping[str, Any], *, field: str, value: Any) -> dict[str, Any]:
    ev = deepcopy(dict(rule))
    ev["field"] = field
    ev["item_value"] = value
    ev["atomic"] = True
    ev["source_role"] = "Fuente Westcon vigente"
    ev["intelligence_tier"] = "A1"
    return ev


def _field(row: dict[str, Any], field_id: str, value: Any) -> dict[str, Any]:
    fields = row.setdefault("fields", {})
    target = fields.get(field_id)
    if not isinstance(target, dict):
        target = {"value": deepcopy(value), "evidence": []}
        fields[field_id] = target
    else:
        target["value"] = deepcopy(value)
        target.setdefault("evidence", [])
    return target


def _attach_scalar(row: dict[str, Any], field_id: str, value: Any, evidence: Mapping[str, Any]) -> None:
    target = _field(row, field_id, value)
    target["evidence"] = _dedupe_evidence(list(target.get("evidence") or []) + [evidence])


def _ensure_capabilities(row: dict[str, Any], capabilities: list[str], document: Mapping[str, Any], slides: list[int]) -> tuple[int, int]:
    fields = row.setdefault("fields", {})
    field = fields.get("capabilities")
    if not isinstance(field, dict):
        field = {"value": [], "evidence": [], "items": []}
        fields["capabilities"] = field
    value = field.get("value")
    if not isinstance(value, list):
        value = [] if not _has_value(value) else [value]
    items = [dict(x) for x in (field.get("items") or []) if isinstance(x, Mapping)]

    # v4.3.0 · current Westcon capability atomicity guard
    # Aggregate capability evidence may list every documented item, but an atomic
    # item may retain current-Westcon evidence only when that item is documented
    # for this manufacturer and evidence.item_value matches it exactly.
    documented_keys = {_norm_capability(capability) for capability in capabilities}
    for item in items:
        item_key = _norm_capability(item.get("value"))
        clean_evidence: list[dict[str, Any]] = []
        for raw_ev in item.get("evidence") or []:
            if not isinstance(raw_ev, Mapping):
                continue
            ev = dict(raw_ev)
            origin = str(ev.get("provenance_origin") or "")
            if origin in CURRENT_KINDS and str(ev.get("field") or "") == "capabilities":
                evidence_key = _norm_capability(ev.get("item_value"))
                if item_key not in documented_keys or evidence_key != item_key:
                    continue
            clean_evidence.append(ev)
        item["evidence"] = _dedupe_evidence(clean_evidence)

    value_index = {_norm_capability(v): i for i, v in enumerate(value)}
    item_index = {_norm_capability(item.get("value")): item for item in items if _has_value(item.get("value"))}
    added = 0
    supported = 0
    aggregate: list[dict[str, Any]] = list(field.get("evidence") or [])

    for documented in capabilities:
        key = _norm_capability(documented)
        if key in value_index:
            actual = value[value_index[key]]
        else:
            value.append(documented)
            value_index[key] = len(value) - 1
            actual = documented
            added += 1
        ev = _document_evidence(document, field="capabilities", value=actual, slides=slides)
        item = item_index.get(key)
        if item is None:
            item = {"value": actual, "evidence": []}
            items.append(item)
            item_index[key] = item
        before = len(item.get("evidence") or [])
        item["evidence"] = _dedupe_evidence(list(item.get("evidence") or []) + [ev])
        if len(item["evidence"]) > before:
            supported += 1
        aggregate.append(ev)

    field["value"] = value
    field["items"] = items
    field["evidence"] = _dedupe_evidence(aggregate)
    return added, supported


def _find_row(rows: list[dict[str, Any]], names: list[str]) -> dict[str, Any] | None:
    wanted = {canonical(name) for name in names if name}
    for row in rows:
        if canonical(row.get("name") or "") in wanted:
            return row
    return None


def _correct_legacy_portfolio_clues(data: dict[str, Any]) -> int:
    changed = 0
    old_phrases = (
        "Portugal incorpora además Proofpoint y Check Point",
        "Portugal incorpora ademas Proofpoint y Check Point",
    )

    def visit(obj: Any) -> None:
        nonlocal changed
        if isinstance(obj, list):
            for value in obj:
                visit(value)
            return
        if not isinstance(obj, dict):
            return
        for key, value in list(obj.items()):
            if isinstance(value, str):
                new = value
                for old in old_phrases:
                    new = new.replace(old, "Portugal incorpora además Check Point")
                if new != value:
                    obj[key] = new
                    changed += 1
            elif isinstance(value, (dict, list)):
                visit(value)

    visit(data)
    return changed


def apply_westcon_current_evidence(data: dict[str, Any], config: Mapping[str, Any]) -> dict[str, int]:
    portfolio = config.get("portfolio_spain") or {}
    document = config.get("document") or {}
    portugal_rule = config.get("portugal_rule") or {}
    portugal_additional = [str(x) for x in (config.get("portugal_additional") or [])]
    explicit_non_spain = {canonical(x) for x in (config.get("explicit_non_spain") or [])}
    rows = [row for row in (data.get("manufacturers") or []) if isinstance(row, dict)]
    data["manufacturers"] = rows

    stats = {
        "portfolio_spain_rows": 0,
        "portfolio_portugal_rows": 0,
        "rows_created": 0,
        "capability_values_added": 0,
        "capability_items_documented": 0,
        "portfolio_fields_documented": 0,
        "legacy_clues_corrected": 0,
    }

    for canonical_name, raw_fact in portfolio.items():
        fact = dict(raw_fact or {})
        aliases = [canonical_name] + [str(x) for x in (fact.get("aliases") or [])]
        row = _find_row(rows, aliases)
        if row is None:
            row = {"id": _slug(canonical_name), "name": canonical_name, "evidence": [], "fields": {}}
            rows.append(row)
            stats["rows_created"] += 1
        slides = [int(x) for x in (fact.get("slides") or [])]
        portfolio_ev = _document_evidence(document, field="westcon_spain", value=True, slides=slides)
        _attach_scalar(row, "westcon_spain", True, portfolio_ev)
        _attach_scalar(row, "westcon_portugal", True, _rule_evidence(portugal_rule, field="westcon_portugal", value=True))
        _attach_scalar(row, "scope", "ES + PT", portfolio_ev)
        row["fields"]["scope"]["evidence"] = _dedupe_evidence(
            list(row["fields"]["scope"].get("evidence") or []) + [_rule_evidence(portugal_rule, field="scope", value="ES + PT")]
        )
        if fact.get("domain"):
            _attach_scalar(row, "domain", fact["domain"], _document_evidence(document, field="domain", value=fact["domain"], slides=slides))
        added, supported = _ensure_capabilities(row, [str(x) for x in (fact.get("capabilities") or [])], document, slides)
        stats["capability_values_added"] += added
        stats["capability_items_documented"] += supported
        stats["portfolio_fields_documented"] += 4
        stats["portfolio_spain_rows"] += 1
        stats["portfolio_portugal_rows"] += 1
        row["evidence"] = _dedupe_evidence(list(row.get("evidence") or []) + [portfolio_ev])

    for name in portugal_additional:
        row = _find_row(rows, [name])
        if row is None:
            row = {"id": _slug(name), "name": name, "evidence": [], "fields": {}}
            rows.append(row)
            stats["rows_created"] += 1
        _attach_scalar(row, "westcon_portugal", True, _rule_evidence(portugal_rule, field="westcon_portugal", value=True))
        _attach_scalar(row, "scope", "PT", _rule_evidence(portugal_rule, field="scope", value="PT"))
        if canonical(name) in explicit_non_spain:
            _attach_scalar(row, "westcon_spain", False, _rule_evidence(portugal_rule, field="westcon_spain", value=False))
        row["evidence"] = _dedupe_evidence(list(row.get("evidence") or []) + [_rule_evidence(portugal_rule, field="portfolio", value=name)])
        stats["portfolio_portugal_rows"] += 1

    # Do not silently keep the superseded "Proofpoint + Check Point" PT-only rule anywhere.
    stats["legacy_clues_corrected"] = _correct_legacy_portfolio_clues(data)

    services = config.get("westcon_services") or {}
    data.setdefault("meta", {})["portfolio_contract_fy27"] = {
        "spain": "Portfolio documentado en Westcon Comstor España FY2027",
        "portugal": "Mismo portfolio de España + Check Point",
        "spain_documented_rows": stats["portfolio_spain_rows"],
        "portugal_documented_rows": stats["portfolio_portugal_rows"],
        "document_id": document.get("document_id"),
        "document_sha256": document.get("sha256"),
    }
    data["meta"]["westcon_services_fy27"] = {
        "capabilities": list(services.get("capabilities") or []),
        "slides": list(services.get("slides") or []),
        "source": document.get("title"),
    }
    return stats
