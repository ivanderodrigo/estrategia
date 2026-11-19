#!/usr/bin/env python3
"""Publish EVERY pending historical claim–URL pair with its individual reason.

The historical sidecars are research leads, not proof. A verified record must
match the exact (section, entity, field, value, source URL) tuple; approval of
one URL must never turn other URLs green. No invented source claims.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from engine.model import canonical

AREAS=("manufacturers","distributors","integrators","clients_public",
       "clients_private","trends","architectures")
def read(path):
    p=ROOT/path
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

def published_item_proofs(section, snapshot):
    proofs = set()
    for row in snapshot.get("rows") or []:
        for field, record in (row.get("fields") or {}).items():
            for item in record.get("items") or []:
                for ref in item.get("evidence_ids") or []:
                    source = (snapshot.get("evidence") or {}).get(ref) or {}
                    if (source.get("atomic") is True and source.get("field") == field
                            and source.get("source_binding") == "claim-specific"
                            and canonical(source.get("item_value")) == canonical(item.get("value"))
                            and source.get("url")):
                        proofs.add((section, canonical(row.get("name")), field,
                                    canonical(item.get("value")), source["url"]))
    return proofs


def pending_index(historical,registry,checks,published_proofs=()):
    verified={
        (c.get("section"),canonical(c.get("entity")),c.get("field"),
         canonical(c.get("value")),str((c.get("source") or {}).get("url") or ""))
        for c in registry.get("existing_claim_sources") or []
    }
    verified.update(published_proofs)
    pages=(checks.get("results") or {})
    results=[]
    counted=Counter()
    for area in AREAS:
        entities=(historical.get(area) or {}).get("entities") or {}
        for entity,fields in sorted(entities.items()):
            for field,values in sorted(fields.items()):
                for entry in values:
                    value=entry.get("value")
                    if not isinstance(value,str) or not value.strip():
                        continue
                    for url in sorted(set(entry.get("urls") or [])):
                        if not isinstance(url,str) or not url.startswith(("https://","http://")):
                            continue
                        key=(area,canonical(entity),field,canonical(value),url)
                        if key in verified:
                            counted["already_accredited_exact_url"]+=1
                            continue
                        page=pages.get(url) or {}
                        claims=page.get("claim_checks") or []
                        match=next((c for c in claims
                            if c.get("section")==area
                            and canonical(c.get("entity"))==canonical(entity)
                            and c.get("field")==field
                            and canonical(c.get("value"))==canonical(value)),None)
                        page_status=page.get("status") or "NOT_CHECKED"
                        reason=(match or {}).get("status") or page_status
                        # Text co-occurrence is a research lead, never proof.
                        priority=1 if reason=="VALUE_PRESENT_REQUIRES_CONTEXT" else (
                            2 if page_status=="REACHABLE_TEXT_MATCH" else
                            3 if page_status=="REACHABLE_NO_EXACT_TEXT" else 4
                        )
                        results.append({"section":area,"entity":entity,"field":field,
                            "value":value,"url":url,"priority":priority,
                            "source_status":page_status,"claim_status":reason,
                            "resolved_url":(match or {}).get("resolved_url") or url})
                        counted[area]+=1
                        counted["reason:"+reason]+=1
    results.sort(key=lambda c:(c["priority"],c["section"],c["entity"],c["field"],c["value"],c["url"]))
    return results,counted

def main():
    historical={area:read(f"data/public/historical/current/{area}.json") for area in AREAS}
    proofs=set()
    for area in AREAS:
        proofs.update(published_item_proofs(area, read(f"data/public/sections/{area}.json")))
    records,counters=pending_index(historical,
        read("config/current/historical_semantic_verified.json"),
        read("data/current/historical_source_checks.json"), proofs)
    snapshot=read("data/public/manifest.json").get("generated_at")
    payload={
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "snapshot_generated_at":snapshot,
        "policy":"Every unaccredited historical claim-and-source pair; link accessibility and textual overlap are NOT fact accreditation",
        "pending_claim_source_pairs":len(records),
        "by_section":{a:counters[a] for a in AREAS},
        "already_accredited_exact_url":counters["already_accredited_exact_url"],
        "by_reason":{k.removeprefix("reason:"):v for k,v in counters.items() if k.startswith("reason:")},
        "records":records,
    }
    target=ROOT/"data/public/historical/current/pending_review_queue.json"
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in payload.items() if k!="records"},ensure_ascii=False))
if __name__=="__main__":
    main()
