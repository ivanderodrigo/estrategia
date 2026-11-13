#!/usr/bin/env python3
"""Fail the release if the advertised mass historical publication is absent."""
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sections=("manufacturers","distributors","integrators","clients_private","clients_public","trends","architectures")
summary=json.loads((ROOT/"data/public/historical/current/summary.json").read_text(encoding="utf-8"))
manifest=json.loads((ROOT/"data/public/manifest.json").read_text(encoding="utf-8"))
run=json.loads((ROOT/"data/public/last_run.json").read_text(encoding="utf-8"))
assert summary["generated_at"]==manifest["generated_at"]==run["generated_at"], "stale historical snapshot"
assert summary["status"]=="HISTORICAL_LEADS_NOT_ACCREDITED"
counts={}
for section in sections:
    data=json.loads((ROOT/f"data/public/historical/current/{section}.json").read_text(encoding="utf-8"))
    assert data["status"]=="HISTORICAL_LEADS_NOT_ACCREDITED"
    assert data["generated_at"]==manifest["generated_at"]
    n=sum(len(items) for fields in data["entities"].values() for items in fields.values())
    assert n==data["claim_count"]==summary["by_section"][section]["claims"]
    counts[section]=n
    for fields in data["entities"].values():
        for items in fields.values():
            for item in items:
                assert item["urls"] and all(url.startswith("https://") for url in item["urls"])
assert sum(counts.values())==summary["claims"]==run["historical_trails"]["claims"]
audit=json.loads((ROOT/"data/public/historical/current/claim_review.json").read_text(encoding="utf-8"))
quarantine=json.loads((ROOT/"data/public/historical/current/quarantined_links.json").read_text(encoding="utf-8"))
assert audit["generated_at"]==quarantine["generated_at"]==manifest["generated_at"]
assert audit["reviewed"]==summary["claims"], "one-by-one review does not cover all visible historical claims"
assert audit["accredited_existing"]+audit["pending_revalidation"]==audit["reviewed"]
assert len(audit["claims"])==audit["reviewed"]
assert len(quarantine["records"])==summary["quarantined_source_links"]
assert run["historical_trails"]["claim_review"]["reviewed"]==audit["reviewed"]

# Baselines from exact-history audit 2026-11-13, with margin for stale or derived gap removal.
assert summary["claims"]>=4000, "Mass historical recovery unexpectedly shrank"
assert counts["trends"]>=300, "Trends missing recovered history"
assert counts["architectures"]>=100, "Architecture history absent"
print(json.dumps({"published_historical_claims":summary["claims"],
                  "unique_urls":summary["unique_urls"],"by_section":counts,
                  "status":summary["status"],
                  "reviewed_one_by_one":audit["reviewed"],
                  "already_accredited":audit["accredited_existing"],
                  "still_pending_content_validation":audit["pending_revalidation"],
                  "quarantined_wrong_vendor_source_links":len(quarantine["records"])},ensure_ascii=False))
