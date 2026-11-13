#!/usr/bin/env python3
"""Prove that individually accredited competitors actually reach public JSON.

This checks the final published evidence registry, not merely curated sources.
A deployment fails if an expected historical competitor remains without an
item-specific current source.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from engine.model import canonical
INPUT=ROOT/"config/current/verified_historical_market_20261114.json"
PUBLIC=ROOT/"data/public/sections/manufacturers.json"
OUTPUT=ROOT/"data/public/historical/current/market_proof_audit.json"

def check():
    evidence_config=json.loads(INPUT.read_text(encoding="utf-8"))
    public=json.loads(PUBLIC.read_text(encoding="utf-8"))
    registry=public.get("evidence") or {}
    rows={canonical(row.get("name")):row for row in public.get("rows") or []}
    confirmed,failures=[],[]
    for claim in evidence_config["existing_claim_sources"]:
        expected_url=claim["source"]["url"]
        row=rows.get(canonical(claim["entity"]))
        field=((row or {}).get("fields") or {}).get("competitors") or {}
        item=next((x for x in field.get("items") or []
                   if canonical(x.get("value"))==canonical(claim["value"])),None)
        evidence=[registry.get(eid) for eid in (item or {}).get("evidence_ids") or []]
        evidence.extend((item or {}).get("evidence") or [])
        proof=any(isinstance(ev,dict)
                  and ev.get("url")==expected_url
                  and ev.get("atomic") is True
                  and canonical(ev.get("item_value"))==canonical(claim["value"])
                  and ev.get("field")=="competitors"
                  and ev.get("accrediting") is not False
                  and ev.get("provenance_origin") in ("PUBLIC_PRIMARY","PUBLIC_ANALYST","PUBLIC_SECONDARY")
                  for ev in evidence)
        record={"entity":claim["entity"],"value":claim["value"],"url":expected_url,
                "row_present":bool(row),"item_present":bool(item),
                "item_has_exact_published_evidence":proof}
        (confirmed if proof else failures).append(record)
    report={"expected":len(evidence_config["existing_claim_sources"]),
            "confirmed_in_public_json":len(confirmed),
            "missing_in_public_json":len(failures),
            "confirmed":confirmed,"failures":failures,
            "method":"Published item-level evidence ID and exact source URL, value and field"}
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k not in ("confirmed","failures")},ensure_ascii=False))
    if failures:
        for f in failures[:15]:
            print("FAIL:", f)
        raise SystemExit(1)
if __name__=="__main__":
    check()
