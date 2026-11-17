#!/usr/bin/env python3
"""Compact, snapshot-bound dashboard telemetry for claim-by-claim historical proof.

Only the exact claim-source registry is called accredited. A discovered URL or
lexical hit remains purple until the semantic classifier has approved its claim.
This report must be generated AFTER rebuilding the public snapshot.
"""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
def read(relative):
    file=ROOT/relative
    return json.loads(file.read_text(encoding="utf-8")) if file.exists() else {}

def make_status(manifest, report, registry, history):
    audited=report.get("generated_at")
    claims=registry.get("existing_claim_sources") or []
    return {
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "snapshot_generated_at":manifest.get("generated_at"),
        "historical_check_generated_at":audited,
        "urls_scanned":int(report.get("urls_scanned") or 0),
        "claim_source_pairs_reviewed":int(report.get("claim_source_pairs_reviewed") or 0),
        "verified_claim_source_pairs":len(claims),
        "verified_new_this_check":int(report.get("verified_this_run") or 0),
        "retained_previous_verifications":int(report.get("retained_prior_verified") or 0),
        "quarantined_legacy":int(report.get("quarantined_generic_homepage_claims") or 0),
        "pending_review_examples_count":len(report.get("pending_recheck_examples") or []),
        "historical_leads_not_accredited":int(history.get("claims") or 0),
        "by_section":report.get("by_section") or {},
        "method":"Exact historical source URL + claim + field semantic verification",
        "disclaimer":"A source URL or text mention alone is not a confirmed fact. This is verified claim-source proof, not full-market coverage.",
    }

def main():
    status=make_status(read("data/public/manifest.json"),
        read("data/public/historical/current/semantic_claim_audit.json"),
        read("config/current/historical_semantic_verified.json"),
        read("data/public/historical/current/summary.json"))
    target=ROOT/"data/public/historical/current/verification_status.json"
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(status,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in status.items() if k!="by_section"},ensure_ascii=False))
if __name__=="__main__":
    main()
