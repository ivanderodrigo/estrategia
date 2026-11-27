#!/usr/bin/env python3
"""Validate independently accredited historical facts in the actual public JSON."""
from __future__ import annotations
import sys,json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from engine.model import canonical
from engine.vendor_labels import non_vendor_reason
from engine.vendor_claims import VENDOR_RELATION_FIELDS


def historical_non_vendor_claim(claim):
    """A source-backed category is still not a manufacturer relationship."""
    return (claim.get("section") in {"distributors", "integrators"}
            and claim.get("field") in VENDOR_RELATION_FIELDS
            and non_vendor_reason(claim.get("value")))

def run():
    reg=json.loads((ROOT/"config/current/historical_semantic_verified.json").read_text(encoding="utf-8"))
    files={}
    confirmed=[];missing=[];excluded=[]
    for c in reg.get("existing_claim_sources") or []:
        if historical_non_vendor_claim(c):
            original_url=str((c.get("source") or {}).get("url") or "")
            if not original_url.startswith("https://"):
                missing.append({"section":c["section"],"entity":c["entity"],
                                "field":c["field"],"value":c["value"],
                                "reason":"historical_source_missing"})
                continue
            section=c["section"]
            if section not in files:
                files[section]=json.loads((ROOT/f"data/public/sections/{section}.json").read_text(encoding="utf-8"))
            public_row=next((r for r in files[section].get("rows") or []
                             if canonical(r.get("name"))==canonical(c["entity"])),None)
            visible=((public_row or {}).get("fields") or {}).get(c["field"]) or {}
            if any(canonical(v)==canonical(c["value"])
                   for v in visible.get("value") or []):
                missing.append({"section":section,"entity":c["entity"],
                                "field":c["field"],"value":c["value"],
                                "url":original_url,"reason":"false_vendor_still_public"})
                continue
            excluded.append({"section":c["section"],"entity":c["entity"],
                             "field":c["field"],"value":c["value"],
                             "url":original_url,"reason":non_vendor_reason(c["value"]),
                             "status":"HISTORICAL_SOURCE_PRESERVED_NOT_VENDOR"})
            continue
        section=c["section"]
        if section not in files:
            files[section]=json.loads((ROOT/f"data/public/sections/{section}.json").read_text(encoding="utf-8"))
        j=files[section]
        row=next((r for r in j.get("rows") or [] if canonical(r.get("name"))==canonical(c["entity"])),None)
        field=((row or {}).get("fields") or {}).get(c["field"]) or {}
        values=field.get("value") if isinstance(field.get("value"),list) else [field.get("value")]
        item=next((i for i in field.get("items") or [] if canonical(i.get("value"))==canonical(c["value"])),None)
        if isinstance(field.get("value"),list):
            ids=(item or {}).get("evidence_ids") or []
            ev=list((item or {}).get("evidence") or [])
        else:
            ids=field.get("evidence_ids") or []
            ev=list(field.get("evidence") or [])
        ev.extend(j.get("evidence",{}).get(i) for i in ids)
        proven=any(isinstance(e,dict)
                   and e.get("url")==c["source"]["url"]
                   and (
                       e.get("source_type") == "historical-verified-excerpt"
                       or (e.get("source_type") == "analyst-peer-review"
                           and e.get("verification_method") == "explicit-product-alternative"
                           and c.get("field") == "competitors"
                           and c.get("section") == "manufacturers"
                           and e.get("provenance_origin") == "PUBLIC_ANALYST")
                   )
                   and e.get("atomic") is True
                   and canonical(e.get("item_value"))==canonical(c["value"])
                   and e.get("field")==c["field"] for e in ev)
        entry={"section":section,"entity":c["entity"],"field":c["field"],
               "value":c["value"],"url":c["source"]["url"],
               "value_exists":any(canonical(v)==canonical(c["value"]) for v in values)}
        (confirmed if proven else missing).append(entry)
    result={"expected":len(reg.get("existing_claim_sources") or []),
            "confirmed_in_published_json":len(confirmed),"missing":len(missing),
            "excluded_misclassified_historical_sources":len(excluded),
            "historical_non_vendor_claims":excluded,
            "by_section":dict(Counter(x["section"] for x in confirmed)),
            "unaccredited_cases":missing}
    dst=ROOT/"data/public/historical/current/semantic_publication_audit.json"
    dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k not in {"unaccredited_cases","historical_non_vendor_claims"}},ensure_ascii=False))
    if missing:
        for x in missing[:15]:print("FAILED",x)
        raise SystemExit(1)
    return result

if __name__=="__main__":
    run()
