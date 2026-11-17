#!/usr/bin/env python3
"""Rebuild non-accrediting historical link sidecars for the SAME public snapshot.

This does not modify current intelligence, claims, evidence or the manifest.
Exact already-published links for still-pending claims may never disappear.
"""
from __future__ import annotations
import json
import sys
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from engine.historical_publication import publish_historical_trails
from engine.settings import SECTIONS
from engine.storage import read_json


def identities(file: dict) -> dict:
    out={}
    for entity,fields in (file.get("entities") or {}).items():
        for field,items in fields.items():
            for item in items:
                if not isinstance(item,dict): continue
                key=(entity,field,json.dumps(item.get("value"),sort_keys=True,ensure_ascii=False))
                out[key]=set(item.get("urls") or [])
    return out


def main():
    manifest=read_json("data/public/manifest.json",{})
    gaps=read_json("data/current/research_gaps.json",{})
    stamp=manifest.get("generated_at")
    if not stamp or gaps.get("generated_at")!=stamp:
        raise SystemExit("Refusing to rebuild historical trails for mismatched manifest/gap snapshots")
    prior={}
    for section in SECTIONS:
        path=f"data/public/historical/current/{section}.json"
        prior[section]=identities(read_json(path,{}))
    published,summary=publish_historical_trails(gaps,stamp)
    total_old=total_new=0
    for section in SECTIONS:
        path=f"data/public/historical/current/{section}.json"
        new=identities(json.loads(published[path]))
        before=prior[section]
        for key,old_urls in before.items():
            # Only still-pending exact claims remain visible in the history.
            if key in new and not old_urls.issubset(new[key]):
                raise SystemExit(f"Historical source regression: {section}/{key[:2]} lost {len(old_urls-new[key])} URL(s)")
        total_old+=sum(len(v) for v in before.values())
        total_new+=sum(len(v) for v in new.values())
    for path,payload in published.items():
        dest=ROOT/path
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(payload)
    print(json.dumps({"status":"PASS","snapshot_generated_at":stamp,
        "old_historical_link_associations":total_old,
        "new_historical_link_associations":total_new,
        "historical_claims":summary["claims"],
        "unique_historical_urls":summary["unique_urls"],
        "accreditation_changed":False},ensure_ascii=False))


if __name__=="__main__":
    main()
