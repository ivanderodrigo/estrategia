#!/usr/bin/env python3
"""Release gate for active Westcon vendor membership in the *published* projection.

The prior deployment rebuilt data only inside an ephemeral GitHub runner, while
branch-based Pages continued to serve the old committed data/public snapshot.
This guard checks the exact artifacts destined for both Pages publishing modes.
"""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _norm(value: object) -> str:
    return " ".join("".join(
        char for char in unicodedata.normalize("NFKD", str(value or ""))
        if not unicodedata.combining(char)
    ).lower().replace("-", " ").split())


def _load(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def _value(row: dict, field: str):
    return ((row.get("fields") or {}).get(field) or {}).get("value")


def _named(rows: list[dict], names: set[str]) -> dict | None:
    return next((r for r in rows if _norm(r.get("name")) in names), None)


def validate() -> dict:
    config = _load("config/current/westcon_fy27_document_facts.json")
    override = config.get("portfolio_override_2026_11") or {}
    manifest = _load("data/public/manifest.json")
    manufacturer_payload = _load("data/public/sections/manufacturers.json")
    rows = manufacturer_payload.get("rows") or []
    assert len(rows) == manifest["sections"]["manufacturers"]["rows"], "Manifest/count mismatch"
    assert len(rows) == manifest["counts"]["manufacturers"], "Manifest top-level count mismatch"

    errors: list[str] = []
    excluded = {_norm(name) for name in override.get("excluded") or []}
    included = {_norm(name) for name in (override.get("included") or {})}
    for name in override.get("excluded") or []:
        row = _named(rows, {_norm(name)})
        if not row:
            errors.append(f"{name}: must remain a market entity to preserve competitor research")
            continue
        if _value(row, "westcon_spain") is not False or _value(row, "westcon_portugal") is not False:
            errors.append(f"{name}: still marked as active Westcon ES/PT")
    for name, details in (override.get("included") or {}).items():
        aliases = {_norm(name)} | {_norm(alias) for alias in (details.get("aliases") or [])}
        row = _named(rows, aliases)
        if not row:
            errors.append(f"{name}: missing from published manufacturers")
            continue
        if _value(row, "westcon_spain") is not True or _value(row, "westcon_portugal") is not True:
            errors.append(f"{name}: missing active ES/PT portfolio membership")
        for field in ("westcon_spain", "westcon_portugal"):
            if not ((row.get("fields") or {}).get(field) or {}).get("evidence_ids"):
                errors.append(f"{name}:{field}: no valid visible first-party support")
        if details.get("domain"):
            field = ((row.get("fields") or {}).get("domain") or {})
            if _value(row, "domain") != details["domain"]:
                errors.append(f"{name}: missing portfolio taxonomy domain")
            if not field.get("evidence_ids"):
                errors.append(f"{name}: domain has no visible official evidence")
        if details.get("capabilities"):
            field = ((row.get("fields") or {}).get("capabilities") or {})
            values = {_norm(x) for x in (field.get("value") or [])}
            expected = {_norm(x) for x in details["capabilities"]}
            if not expected <= values:
                errors.append(f"{name}: missing capability values: {sorted(expected - values)}")
            for item in field.get("items") or []:
                if _norm(item.get("value")) in expected and not item.get("evidence_ids"):
                    errors.append(f"{name}: capability {item.get('value')} missing official item evidence")

    active = {
        _norm(row.get("name")) for row in rows
        if _value(row, "westcon_spain") is True or _value(row, "westcon_portugal") is True
    }
    if excluded & active:
        errors.append(f"Superseded brands still active: {sorted(excluded & active)}")
    if not included <= active:
        errors.append(f"New brands not active: {sorted(included - active)}")
    for section, field_ids in {
        "distributors": ("westcon_overlap",),
        "integrators": ("westcon_overlap",),
        "trends": ("westcon_vendors",),
    }.items():
        payload = _load(f"data/public/sections/{section}.json")
        for row in payload.get("rows") or []:
            for field_id in field_ids:
                value = _value(row, field_id)
                values = value if isinstance(value, list) else ([value] if value else [])
                wrong = {_norm(x) for x in values} & excluded
                if wrong:
                    errors.append(f"{section}:{row.get('name')}:{field_id}: {sorted(wrong)}")
                    if len(errors) >= 25:
                        break

    metrics = {"rows": len(rows), "active_westcon": len(active),
               "added_verified": sorted(included & active),
               "excluded_verified": sorted(excluded - active),
               "errors": errors}
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit("Published portfolio verification FAILED")
    return metrics


if __name__ == "__main__":
    validate()
