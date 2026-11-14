#!/usr/bin/env python3
"""Count every source attached to visible current claims, including archive misses.

This is the completeness audit for the source-verification inventory. It is
not a substitute for semantic verification of each claim.
"""
from __future__ import annotations
import sys,json
from pathlib import Path
from collections import Counter,defaultdict
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from engine.model import canonical
from scripts.revalidate_historical_sources import candidate_inventory

def main():
    inventory=candidate_inventory()
    by_section=defaultdict(Counter)
    pairs=set()
    history=set()
    current=set()
    for url,records in inventory.items():
        for record in records:
            section=record["section"]
            identity=(section,canonical(record.get("entity")),
                      record.get("field"),canonical(record.get("value")),url)
            pairs.add(identity)
            origin=record.get("inventory_origin") or "historical-sidecar"
            by_section[section][origin]+=1
            if origin=="current-visible-unaccredited":
                current.add(identity)
            else:
                history.add(identity)
    report={
        "policy":"Exact tuple (section, entity, field, value, URL) inspected across BOTH current visible rows and historical gap sidecars. Inventory is not accreditation.",
        "unique_urls":len(inventory),
        "unique_claim_url_pairs":len(pairs),
        "historical_claim_url_pairs":len(history),
        "visible_unaccredited_claim_url_pairs":len(current),
        "visible_pairs_missing_from_historical_sidecars":len(current-history),
        "by_section":{s:dict(c) for s,c in sorted(by_section.items())},
        "examples_outside_historical": [
            {"section":s,"entity":e,"field":f,"value":v,"url":url}
            for s,e,f,v,url in sorted(current-history)
        ][:30],
    }
    out=ROOT/"data/public/historical/current/full_source_inventory_coverage.json"
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="examples_outside_historical"},ensure_ascii=False))
    if not report["visible_unaccredited_claim_url_pairs"]:
        raise SystemExit("Current visible evidence inventory unexpectedly empty")
    return report

if __name__=="__main__":
    main()
