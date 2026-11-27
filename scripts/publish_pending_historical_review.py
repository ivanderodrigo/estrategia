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


def historical_inventory(historical):
    if historical is None:
        from scripts.revalidate_historical_sources import candidate_inventory
        return candidate_inventory()
    by_url = {}
    for area, archive in historical.items():
        for entity, fields in archive.get("entities", {}).items():
            for field, entries in fields.items():
                for entry in entries:
                    value = entry.get("value")
                    if isinstance(value,str) and value.strip():
                        for url in entry.get("urls") or []:
                            if isinstance(url,str) and url.startswith(("https://","http://")):
                                by_url.setdefault(url,[]).append(dict(section=area,entity=entity,field=field,value=value))
    return by_url


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
    seen=set()
    for url, claims_for_url in historical_inventory(historical).items():
        page = pages.get(url) or {}
        checks_by_claim = {
            (c["section"],canonical(c["entity"]),c["field"],canonical(c["value"])): c
            for c in page.get("claim_checks") or []
        }
        for claim in claims_for_url:
            area,entity,field,value = (claim[k] for k in ("section","entity","field","value"))
            identity = (area,canonical(entity),field,canonical(value))
            key = (*identity,url)
            if key in seen:
                continue
            seen.add(key)
            match = checks_by_claim.get(identity) or {}
            resolved = match.get("resolved_url") or url
            if key in verified or (*identity,resolved) in verified:
                counted["already_accredited_exact_url"] += 1
                continue
            page_status = page.get("status") or "NOT_CHECKED"
            reason = match.get("status") or "CLAIM_NOT_CHECKED"
            priority = 1 if reason=="VALUE_PRESENT_REQUIRES_CONTEXT" else (
                2 if page_status=="REACHABLE_TEXT_MATCH" else
                3 if page_status=="REACHABLE_NO_EXACT_TEXT" else 4
            )
            results.append({"section":area,"entity":entity,"field":field,
                "value":value,"url":url,"priority":priority,
                "source_status":page_status,"claim_status":reason,"resolved_url":resolved})
            counted[area]+=1
            counted["reason:"+reason]+=1
    results.sort(key=lambda c:(c["priority"],c["section"],c["entity"],c["field"],c["value"],c["url"]))
    return results,counted

def main():
    proofs=set()
    for area in AREAS:
        proofs.update(published_item_proofs(area, read(f"data/public/sections/{area}.json")))
    records,counters=pending_index(None,
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
