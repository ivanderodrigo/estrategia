#!/usr/bin/env python3
"""Validate the seven published audit areas against ONE canonical snapshot.

No new evidence is generated here. A failed invariant blocks publication;
a stale publication date is reported rather than silently relabelled 'actual'.
"""
from __future__ import annotations

import argparse
import json
import sys
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from engine.publication import _source_coverage
from engine.model import canonical
PUBLIC=ROOT/"data/public"
SECTIONS=("manufacturers","distributors","integrators","clients_public",
          "clients_private","trends","architectures")
HISTORICAL=PUBLIC/"historical/current"
ROLES={"Fuente pública primaria","Fuente pública secundaria / analista",
       "Fuente documental Westcon vigente","Fuente Westcon vigente"}


def read(name):
    return json.loads((PUBLIC/name).read_text(encoding="utf-8"))


def evaluate():
    manifest=read("manifest.json")
    debt=read("debt_overview.json")
    run=read("last_run.json")
    errors=[]
    stamped=manifest.get("generated_at")
    for name,obj in (("debt_overview",debt),("last_run",run)):
        if not stamped or obj.get("generated_at")!=stamped:
            errors.append(f"{name} snapshot timestamp mismatch")
    breakdown=debt.get("debt_breakdown") or {}
    total=int(debt.get("total_open_gaps") or 0)
    subtotal=sum(int(x or 0) for x in breakdown.values())
    if subtotal!=total:
        errors.append(f"debt breakdown != total: {subtotal} != {total}")
    section_debt=debt.get("by_section") or {}
    section_total=0
    section_metrics={}
    historic_totals={"claims":0,"claims_without_urls":0,"claims_with_invalid_urls":0,"unmatched_entities":0}
    for section in SECTIONS:
        info=(manifest.get("sections") or {}).get(section) or {}
        path=info.get("file")
        if not isinstance(path,str) or not path.startswith("data/public/sections/"):
            errors.append(f"{section}: bad section file")
            continue
        payload=json.loads((ROOT/path).read_text(encoding="utf-8"))
        rows=payload.get("rows") or []
        declared=(manifest.get("counts") or {}).get(section)
        if declared is None or int(declared)!=len(rows):
            errors.append(f"{section}: entity count mismatch {declared} != {len(rows)}")
        # Never substitute quality_score for coverage; it is an integrity grade.
        coverage=((manifest.get("meta") or {}).get("source_coverage") or {}).get(section) or {}
        claims=int(coverage.get("claims") or 0)
        sourced=int(coverage.get("sourced") or 0)
        if claims<=0 or sourced<0 or sourced>claims:
            errors.append(f"{section}: invalid published source coverage")
        source_registry=payload.get("evidence") or {}
        actual=_source_coverage(rows,source_registry)
        for metric in ("claims","sourced","unsourced","broken_references"):
            declared=int(coverage.get(metric) or 0)
            if declared!=actual[metric]:
                errors.append(f"{section}: {metric} manifest={declared} actual={actual[metric]}")
        if actual["broken_references"]:
            errors.append(f"{section}: dangling evidence_id references: {actual['broken_references']}")
        info_evidence=int(info.get("evidence") or 0)
        if info_evidence!=len(source_registry):
            errors.append(f"{section}: source registry metadata={info_evidence} actual={len(source_registry)}")
        wrong_role=[eid for eid,ev in source_registry.items()
                    if not isinstance(ev,dict) or ev.get("source_role") not in ROLES]
        if wrong_role:
            errors.append(f"{section}: {len(wrong_role)} source references missing valid role")
        by=section_debt.get(section)
        if not isinstance(by,dict):
            errors.append(f"{section}: missing debt counters")
            by={}
        this_debt=sum(int(by.get(k) or 0) for k in
                      ("claims_awaiting_evidence","derivation_support","empty_schema_fields"))
        section_total+=this_debt
        section_metrics[section]={"entities":len(rows),"claims":claims,
            "sourced":sourced,"research_debt":this_debt,
            "source_registry_entries":len(source_registry)}
        published_names={canonical(str(row.get('name') or '')) for row in rows}
        section_historic={"claims":0,"claims_without_urls":0,
                          "claims_with_invalid_urls":0,"unmatched_entities":0}
        for layer in (section, 'git_'+section):
            path=HISTORICAL/(layer+'.json')
            if not path.exists():
                errors.append(f"{section}: missing historical source layer {layer}")
                continue
            archive=json.loads(path.read_text(encoding='utf-8'))
            for entity, fields in (archive.get('entities') or {}).items():
                if canonical(entity) not in published_names:
                    section_historic['unmatched_entities']+=1
                for records in fields.values():
                    if not isinstance(records,list):
                        continue
                    for claim in records:
                        section_historic['claims']+=1
                        urls=claim.get('urls') or []
                        if not urls:
                            section_historic['claims_without_urls']+=1
                        elif not any(isinstance(url,str) and re.match(r'^https://[^\s"\'<>]+$',url)
                                     for url in urls):
                            section_historic['claims_with_invalid_urls']+=1
        for metric, count in section_historic.items():
            historic_totals[metric]+=count
        section_metrics[section]['historical_links']=section_historic
    if historic_totals['claims_without_urls'] or historic_totals['claims_with_invalid_urls']:
        errors.append('Historical source records without a usable exact URL')
    # Git archives deliberately retain deleted/renamed historical entities.
    # Report these orphans separately without asserting the current dataset is broken.
    historical_verification={"available":False,"snapshot_matches":False}
    verification_path=HISTORICAL/'verification_status.json'
    if verification_path.exists():
        verification=json.loads(verification_path.read_text(encoding='utf-8'))
        matching=verification.get('snapshot_generated_at')==stamped
        if not matching:
            errors.append("Historical verification snapshot timestamp mismatch")
        historical_verification={
            "available":True,
            "snapshot_matches":matching,
            "checked_at":verification.get('historical_check_generated_at'),
            "report_generated_at":verification.get('generated_at'),
            "urls_scanned":int(verification.get('urls_scanned') or 0),
            "claim_source_pairs_reviewed":int(verification.get('claim_source_pairs_reviewed') or 0),
            "verified_claim_source_pairs":int(verification.get('verified_claim_source_pairs') or 0),
            "historical_leads_not_accredited":int(verification.get('historical_leads_not_accredited') or 0),
        }
        if historical_verification['verified_claim_source_pairs']>historical_verification['claim_source_pairs_reviewed']:
            errors.append('Historical accreditation count exceeds reviewed source/claim pairs')
    else:
        errors.append("Missing historical verification status")
    if section_total!=total:
        errors.append(f"area debt total mismatch: {section_total} != {total}")
    if not stamped:
        errors.append("missing publication timestamp")
    return {"snapshot_generated_at":stamped,
            "audited_at":datetime.now(timezone.utc).isoformat(),
            "status":"PASS" if not errors else "FAIL",
            "source_coverage_is_not_verification":True,
            "integrity_score_is_not_evidence_coverage":True,
            "historical_url_presence_is_not_claim_accreditation":True,
            "historical_link_coverage":historic_totals,
            "historical_verification":historical_verification,
            "total_open_gaps":total,"areas":section_metrics,"errors":errors}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",default="data/public/audit_integrity.json")
    args=p.parse_args()
    result=evaluate()
    output=ROOT/args.output
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="areas"},ensure_ascii=False))
    return 0 if result["status"]=="PASS" else 1


if __name__=="__main__":
    sys.exit(main())
