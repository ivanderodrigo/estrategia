#!/usr/bin/env python3
"""Report whether curated P0 evidence survives canonical build, without inventing closure."""
from __future__ import annotations
import json
from pathlib import Path
from engine.model import canonical

ROOT = Path(__file__).resolve().parents[1]
TARGETS = (("AWS", "IaaS/PaaS"), ("Cisco", "Observability"), ("F5", "ADC"))

def main():
    data = json.loads((ROOT / "data/current/intelligence.json").read_text(encoding="utf-8"))
    gaps = json.loads((ROOT / "data/current/research_gaps.json").read_text(encoding="utf-8"))
    remaining = {
        (canonical(g.get("entity") or ""), canonical(v))
        for g in gaps.get("gaps", []) if g.get("section") == "manufacturers"
        for v in (g.get("target_values") or [])
    }
    results = []
    for entity, value in TARGETS:
        match = next((r for r in data.get("manufacturers", []) if canonical(r.get("name") or "") == canonical(entity)), None)
        field = ((match or {}).get("fields") or {}).get("capabilities") or {}
        item = next((i for i in field.get("items", []) if canonical(i.get("value") or "") == canonical(value)), None)
        urls = [ev.get("url") for ev in (item or {}).get("evidence", []) if isinstance(ev, dict) and ev.get("url")]
        is_open = (canonical(entity), canonical(value)) in remaining
        results.append({"entity":entity, "value":value,"evidence_urls":urls,"gap_still_open":is_open})
    print(json.dumps({"targets":results, "total_gaps": gaps.get("total_gaps")},ensure_ascii=False,indent=2))
    if any(not x["evidence_urls"] or x["gap_still_open"] for x in results):
        raise SystemExit("P0 evidence not fully reconciled; no success reported")

if __name__ == "__main__":
    main()
