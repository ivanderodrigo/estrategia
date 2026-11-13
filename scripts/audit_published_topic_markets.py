#!/usr/bin/env python3
"""Gate publication of individually accredited Trends/Architectures market facts."""
from __future__ import annotations
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from engine.model import canonical

def main():
    doc=json.loads((ROOT/"config/current/verified_historical_topic_markets_20261114.json").read_text())
    sections={}
    for section in {"trends","architectures"}:
        sections[section]=json.loads((ROOT/f"data/public/sections/{section}.json").read_text())
    good=[];missing=[]
    for record in doc["existing_claim_sources"]:
        section=record["section"]
        public=sections[section]
        row=next((r for r in public.get("rows",[]) if canonical(r.get("name"))==canonical(record["entity"])),None)
        field=((row or {}).get("fields") or {}).get(record["field"]) or {}
        item=next((i for i in field.get("items",[]) if canonical(i.get("value"))==canonical(record["value"])),None)
        registry=public.get("evidence") or {}
        evidences=[registry.get(id) for id in (item or {}).get("evidence_ids") or []]
        evidences+=(item or {}).get("evidence") or []
        verified=any(isinstance(e,dict) and e.get("url")==record["source"]["url"]
                     and e.get("atomic") is True and e.get("topic_market_match") is True
                     and canonical(e.get("item_value"))==canonical(record["value"])
                     for e in evidences)
        (good if verified else missing).append({"section":section,"entity":record["entity"],
                  "field":record["field"],"value":record["value"],"url":record["source"]["url"]})
    report={"expected":len(doc["existing_claim_sources"]),"accredited_in_published_json":len(good),"missing":len(missing),
            "by_section":{section:sum(x["section"]==section for x in good) for section in sections},"failed":missing}
    path=ROOT/"data/public/historical/current/topic_market_proof_audit.json"
    path.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="failed"},ensure_ascii=False))
    if missing:
        for row in missing[:12]:print("MISSING",row)
        raise SystemExit(1)

if __name__=="__main__":
    main()
