#!/usr/bin/env python3
"""Bind official product-capability sources to atomic SASE/SSE architecture vendors.

Run AFTER pipeline regeneration; only source-supported vendor/layer pairs are
promoted. Sources assert capability alignment, not vendor interoperability.
"""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from engine.publication import _source_coverage
from engine.storage import json_bytes
REGISTRY=ROOT/"config/current/sase_layer_vendor_sources.json"
PUBLISHED=ROOT/"data/public/sections/architectures.json"


def apply():
    spec=json.loads(REGISTRY.read_text(encoding="utf-8"))
    payload=json.loads(PUBLISHED.read_text(encoding="utf-8"))
    rows=[row for row in payload.get("rows",[]) if row.get("name")=="SASE / SSE"]
    if len(rows)!=1:
        raise AssertionError(f"Expected one SASE / SSE architecture: {len(rows)}")
    field=rows[0]["fields"]["layers"]
    layers=field.get("value") or []
    if not layers or not all(isinstance(v,dict) for v in layers):
        raise AssertionError("SASE/SSE layers missing")
    registry=payload.setdefault("evidence",{})
    counts={"vendor_layer_pairs":0,"source_records":0}
    touched=set()
    for spec_item in spec.get("sources") or []:
        layer_name=spec_item["layer"]; vendor=spec_item["vendor"]
        url=spec_item["url"]
        if spec_item.get("status")!="VERIFIED_VENDOR_CAPABILITY":
            continue
        if not url.startswith("https://"):
            raise AssertionError("Official source must be HTTPS")
        targets=[]
        for lay in layers:
            if lay.get("layer")!=layer_name:
                continue
            names=lay.get("vendors") or []
            if vendor not in names:
                continue
            item=next((v for v in lay.get("vendor_items") or []
                       if v.get("value")==vendor),None)
            if item is None:
                raise AssertionError(f"Missing specific vendor item {vendor} in {layer_name}")
            targets.append(item)
        if not targets:
            raise AssertionError(f"Source does not match an architecture vendor: {layer_name} / {vendor}")
        digest=hashlib.sha256((layer_name+"|"+vendor+"|"+url).encode()).hexdigest()[:16]
        eid="ev_sase_capability_"+digest
        registry[eid]={
            "source":vendor,"title":spec_item["title"],"url":url,
            "description":spec_item["description"],
            "date":spec_item["reviewed_at"],
            "retrieved_at":spec_item["reviewed_at"],
            "provenance_origin":"PUBLIC_PRIMARY",
            "source_type":"manufacturer-product-documentation",
            "source_grade":"A","official":True,
            "source_role":"Fuente pública primaria",
            "scope":"GLOBAL","classification":"public",
            "atomic":True,"field":"layers","item_value":vendor,
            "architecture":"SASE / SSE","layer":layer_name,
            "source_binding":"claim-specific","freshness_status":"current",
            "claim_type":"fact",
            "qualifier":"Encaje funcional documentado; no implica interoperabilidad certificada entre fabricantes."
        }
        for item in targets:
            ids=item.setdefault("evidence_ids",[])
            if eid not in ids:
                ids.insert(0,eid)
            # Displayed confidence is based on this exact vendor capability,
            # not on unrelated generic SASE market publications.
            item["confidence"]=max(float(item.get("confidence") or 0),.86)
            item["confidence_band"]="high"
            item["confidence_reason"]="Capacidad acreditada mediante documentación oficial específica del fabricante."
            item["assertion_status"]="CONFIRMADO"
            touched.add((layer_name,vendor))
        counts["source_records"]+=1
    # Source schema is also copied into field.items for some renderers and
    # exports; keep both copies in sync so hydration never loses the URL.
    keyed={(v["layer"],v["vendor"]):v for v in spec.get("sources") or []
           if v.get("status")=="VERIFIED_VENDOR_CAPABILITY"}
    for layer_item in field.get("items") or []:
        if not isinstance(layer_item.get("value"),dict):
            continue
        lay=layer_item["value"]
        for vendor_item in lay.get("vendor_items") or []:
            key=(lay.get("layer"),vendor_item.get("value"))
            if key not in keyed:
                continue
            doc=keyed[key]
            digest=hashlib.sha256((key[0]+"|"+key[1]+"|"+doc["url"]).encode()).hexdigest()[:16]
            eid="ev_sase_capability_"+digest
            evidences=vendor_item.setdefault("evidence_ids",[])
            if eid not in evidences:
                evidences.insert(0,eid)
            vendor_item["confidence"]=max(float(vendor_item.get("confidence") or 0),.86)
            vendor_item["confidence_band"]="high"
            vendor_item["confidence_reason"]="Capacidad acreditada mediante documentación oficial específica del fabricante."
    counts["vendor_layer_pairs"]=len(touched)
    expected={(x["layer"],x["vendor"]) for x in spec["sources"]}
    if touched != expected:
        raise AssertionError(f"Unmatched sources: {sorted(expected-touched)}")
    if counts["vendor_layer_pairs"] < 12:
        raise AssertionError("Unexpectedly few SASE/SSE sources")
    encoded=json_bytes(payload,pretty=False)
    PUBLISHED.write_bytes(encoded)
    # The pipeline calculated manifest coverage BEFORE this source binding.
    # Reconcile the public manifest with the final actual JSON, not with an
    # intermediate projection; otherwise green tabs and audit coverage differ.
    manifest_file=ROOT/"data/public/manifest.json"
    manifest=json.loads(manifest_file.read_text(encoding="utf-8"))
    manifest.setdefault("meta",{}).setdefault("source_coverage",{})["architectures"]=(
        _source_coverage(payload["rows"],registry)
    )
    info=manifest.setdefault("sections",{}).get("architectures")
    if not isinstance(info,dict):
        raise AssertionError("Missing architecture section metadata in manifest")
    info["evidence"]=len(registry)
    info["bytes"]=len(encoded)
    manifest_file.write_bytes(json_bytes(manifest,pretty=False))
    print(json.dumps(counts))
    return counts


if __name__=="__main__":
    apply()
