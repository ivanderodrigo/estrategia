#!/usr/bin/env python3
"""Guarantee Gartner's historical Ciena OSS alternatives reach colored badges.

The test uses the browser-facing public JSON, not merely the curated source
file or a historical link that happens to be reachable.
"""
from __future__ import annotations
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from engine.model import canonical

def run():
    source=json.loads((ROOT/"config/current/verified_historical_peer_20261114.json")
                      .read_text(encoding="utf-8"))
    dataset=json.loads((ROOT/"data/public/sections/manufacturers.json")
                       .read_text(encoding="utf-8"))
    rows={canonical(r.get("name")):r for r in dataset.get("rows") or []}
    evidence=dataset.get("evidence") or {}
    good=[];bad=[]
    for entry in source["existing_claim_sources"]:
        name=entry["entity"]
        field=((rows.get(canonical(name)) or {}).get("fields") or {}).get("competitors") or {}
        item=next((it for it in field.get("items") or []
                  if canonical(it.get("value"))==canonical(entry["value"])),None)
        if item:
            proof=list(item.get("evidence") or [])
            proof.extend(evidence.get(i) for i in item.get("evidence_ids") or [])
        else:
            proof=[]
        verified=any(isinstance(ev,dict)
            and ev.get("url")==entry["source"]["url"]
            and ev.get("atomic") is True
            and ev.get("field")=="competitors"
            and canonical(ev.get("item_value"))==canonical(entry["value"])
            and ev.get("provenance_origin")=="PUBLIC_ANALYST"
            and ev.get("verification_method")=="explicit-product-alternative"
            and ev.get("source_binding")=="claim-specific"
            for ev in proof)
        (good if verified else bad).append(entry["value"])
    report={"expected":len(source["existing_claim_sources"]),
            "verified_in_browser_json":len(good),
            "not_verified":bad}
    target=ROOT/"data/public/historical/current/peer_competitor_proof_audit.json"
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False))
    if bad:raise SystemExit(1)
    return report

if __name__=="__main__":
    run()
