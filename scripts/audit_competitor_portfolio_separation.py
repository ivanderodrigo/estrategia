#!/usr/bin/env python3
"""Block duplicate Westcon vendors in external-competitor projections.

A manufacturer can be a technological peer of another Westcon manufacturer.
Only channel-facing external-competitor fields must exclude active brands.
This check uses the PUBLIC JSON shown by the browser, not a synthetic fixture.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from engine.model import canonical
PUBLIC = ROOT / "data/public/sections"
ALIAS_GROUPS = {
    "sonar": {"sonar", "sonarqube", "sonarsource"},
    "ericsson cradlepoint": {"ericsson cradlepoint", "cradlepoint"},
    "akamai noname": {"akamai noname", "akamai", "noname", "noname security"},
    "stratus penguin solutions": {"stratus penguin solutions", "stratus", "penguin solutions"},
    "f5": {"f5", "f5 networks"},
}

def values(field):
    raw = (field or {}).get("value") if isinstance(field, dict) else []
    return raw if isinstance(raw, list) else ([raw] if raw else [])

def run():
    manufacturers = json.loads((PUBLIC / "manufacturers.json").read_text(encoding="utf-8"))["rows"]
    active = set()
    for row in manufacturers:
        fields = row.get("fields") or {}
        if fields.get("westcon_spain", {}).get("value") is True or fields.get("westcon_portugal", {}).get("value") is True:
            name = canonical(row.get("name") or "")
            active.add(name)
            for root, aliases in ALIAS_GROUPS.items():
                if name == canonical(root):
                    active.update(canonical(a) for a in aliases)
    errors = []
    summary = {}
    for section in ("distributors", "integrators"):
        rows = json.loads((PUBLIC / f"{section}.json").read_text(encoding="utf-8"))["rows"]
        external = 0
        overlaps = 0
        for row in rows:
            fields = row.get("fields") or {}
            overlap = {canonical(v) for v in values(fields.get("westcon_overlap")) if isinstance(v, str)}
            competitors = {canonical(v) for v in values(fields.get("competitor_vendor_overlap")) if isinstance(v, str)}
            external += len(competitors)
            overlaps += len(overlap)
            for name in sorted(competitors & (active | overlap)):
                errors.append(f"{section}/{row.get('name')}: active or overlapping manufacturer wrongly classified external: {name}")
        summary[section] = {"entities": len(rows), "westcon_matches": overlaps, "external_competitor_matches": external}
    print(json.dumps({"audit": "external-competitor-portfolio-separation", "areas": summary,
                      "errors": errors[:20], "error_count": len(errors)}, ensure_ascii=False))
    return 1 if errors else 0

if __name__ == "__main__":
    sys.exit(run())
