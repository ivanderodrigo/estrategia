#!/usr/bin/env python3
"""Verify issuer-identified competitors survive all canonical transforms."""
from __future__ import annotations
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from engine.model import canonical

def run():
    cfg=json.loads((ROOT/"config/current/verified_issuer_competitors_20261114.json").read_text(encoding="utf-8"))
    doc=json.loads((ROOT/"data/public/sections/manufacturers.json").read_text(encoding="utf-8"))
    row=next((x for x in doc["rows"] if canonical(x["name"])=="ciena"),None)
    if row is None:
        raise AssertionError("Ciena missing")
    field=row["fields"]["competitors"]
    registry=doc.get("evidence") or {}
    passed=[];failed=[]
    for source in cfg["existing_claim_sources"]:
        item=next((x for x in field.get("items") or []
                   if canonical(x.get("value"))==canonical(source["value"])),None)
        ev=list((item or {}).get("evidence") or [])
        ev.extend(registry.get(k) for k in (item or {}).get("evidence_ids") or [])
        match=any(isinstance(x,dict)
                  and x.get("url")==source["source"]["url"]
                  and x.get("atomic") is True
                  and canonical(x.get("item_value"))==canonical(source["value"])
                  and x.get("provenance_origin")=="PUBLIC_PRIMARY"
                  and x.get("verification_method")=="issuer-identified-direct-competitor"
                  for x in ev)
        (passed if match else failed).append(source["value"])
    report={"expected":len(cfg["existing_claim_sources"]),"accredited":len(passed),
            "missing":failed,"values":passed}
    out=ROOT/"data/public/historical/current/ciena_issuer_competitors_audit.json"
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(report)
    if failed:
        raise SystemExit("Missing exact first-party issuer evidence")
    return report

if __name__=="__main__":
    run()
