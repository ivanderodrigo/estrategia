#!/usr/bin/env python3
"""Individually revalidate archived Gartner alternative claims.

Write accredited evidence only after reading explicit, structured alternative
entries on a product-specific page. All other historical claims remain pending.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict, Counter
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.historical_structured_verification import source_entity, verify_explicit_alternative
from engine.model import canonical
from engine.research.security import validate_public_url
from engine.storage import atomic_write_json, read_json

OUT = "config/current/historical_structured_verified.json"
AUDIT = "data/public/historical/current/structured_verification.json"
CURATED = "config/current/verified_research_20261113.json"

def apply_curated_reviews(attempts, registry):
    """Recover claim-by-claim human-reviewed proof even if live crawling is blocked.

    The registry only credits the exact historical entity, field, value AND
    original URL. It cannot turn an unrelated source into accreditation.
    """
    confirmed = set()
    for row in registry.get("existing_claim_sources") or []:
        source = row.get("source") or {}
        if (row.get("section"), row.get("field")) != ("manufacturers", "competitors"):
            continue
        if source.get("source_type") != "analyst-peer-review":
            continue
        confirmed.add((
            canonical(row.get("entity")), canonical(row.get("value")),
            str(source.get("url") or "")
        ))
    for item in attempts:
        key = (canonical(item.get("entity")), canonical(item.get("value")),
               str(item.get("source_url") or ""))
        if key not in confirmed or item.get("field") != "competitors" or item.get("section") != "manufacturers":
            continue
        if item["status"] != "VERIFIED_EXPLICIT_ALTERNATIVE":
            item["automated_fetch_status"] = item["status"]
            item["status"] = "VERIFIED_CURATED_DIRECT_SOURCE"
            item["review_method"] = "individual-direct-source-review"
    return attempts

def claims_inventory():
    payload = read_json("data/public/historical/current/manufacturers.json", {})
    target = defaultdict(list)
    for entity, fields in (payload.get("entities") or {}).items():
        for item in fields.get("competitors") or []:
            value = item.get("value")
            if not isinstance(value, str) or not value:
                continue
            for url in item.get("urls") or []:
                if source_entity(url) == entity:
                    target[url].append({"section": "manufacturers",
                                        "entity": entity, "field": "competitors",
                                        "value": value})
    return target

def run(limit=30, timeout=12):
    today = datetime.now(timezone.utc).isoformat()
    inventory = claims_inventory()
    previous = read_json(OUT, {})
    confirmed = {(c.get("section"), c.get("entity"), c.get("field"), c.get("value")): c
                 for c in previous.get("existing_claim_sources") or []}
    attempts = []
    counts = Counter()
    with requests.Session() as session:
        for url in sorted(inventory)[:limit]:
            claims = inventory[url]
            try:
                safe = validate_public_url(url)
                resp = session.get(safe, timeout=(4, timeout), allow_redirects=False,
                                   headers={"User-Agent":"WestconHistoricalEvidenceAudit/1.0"},
                                   stream=True)
                try:
                    if resp.status_code != 200:
                        raise ValueError("HTTP_" + str(resp.status_code))
                    if "text/html" not in resp.headers.get("Content-Type", "").lower():
                        raise ValueError("NOT_HTML")
                    content = bytearray()
                    for chunk in resp.iter_content(chunk_size=32768):
                        content.extend(chunk)
                        if len(content) > 2_000_000:
                            raise ValueError("DOCUMENT_TOO_LARGE")
                    html = content.decode(resp.encoding or "utf-8", errors="replace")
                finally:
                    resp.close()
                for claim in claims:
                    decision = verify_explicit_alternative(url, html, claim["entity"], claim["value"])
                    status = "VERIFIED_EXPLICIT_ALTERNATIVE" if decision["verified"] else decision["reason"]
                    counts[status] += 1
                    attempts.append({**claim, "source_url": url, "status": status,
                                     "matched_product": decision.get("matched_product"),
                                     "checked_at": today})
                    if not decision["verified"]:
                        continue
                    k = (claim["section"], claim["entity"], claim["field"], claim["value"])
                    confirmed[k] = {**claim, "source": {
                        "url": url,
                        "title": "Gartner Peer Insights - explicit product alternative",
                        "source": "Gartner Peer Insights",
                        "date": today[:10], "retrieved_at": today[:10],
                        "description": "Alternativa de producto explícita: "
                                       + str(decision["matched_product"]) + ". "
                                       "Comparación limitada al mercado del producto.",
                        "official": False, "source_type": "analyst-peer-review",
                        "provenance_origin": "PUBLIC_ANALYST",
                        "classification": "public", "scope": "GLOBAL",
                        "freshness_status": "current", "source_grade": "B",
                        "verification_method": "structured-product-alternative",
                        "matched_product": decision["matched_product"]
                    }}
            except (requests.RequestException, ValueError, OSError) as exc:
                counts["UNREACHABLE_OR_UNREADABLE"] += len(claims)
                for claim in claims:
                    attempts.append({**claim, "source_url": url, "status": "UNREACHABLE_OR_UNREADABLE",
                                     "error_type": type(exc).__name__, "checked_at": today})
    apply_curated_reviews(attempts, read_json(CURATED, {}))
    counts = Counter(item["status"] for item in attempts)
    output = {"version": 1, "verified_on": today,
              "policy": "Solo afirmaciones atómicas citadas en listados explícitos de alternativas de producto. Ninguna coincidencia de texto genérica acredita.",
              "existing_claim_sources": sorted(confirmed.values(), key=lambda c: (
                  c["section"], c["entity"], c["field"], c["value"]))}
    atomic_write_json(OUT, output)
    audit = {"generated_at": today, "urls_eligible": len(inventory),
             "claims_reviewed_this_run": len(attempts),
             "claims_confirmed_this_run": counts["VERIFIED_EXPLICIT_ALTERNATIVE"] + counts["VERIFIED_CURATED_DIRECT_SOURCE"],
             "claims_curated_source_review": counts["VERIFIED_CURATED_DIRECT_SOURCE"],
             "evidence_records_total": len(confirmed) + counts["VERIFIED_CURATED_DIRECT_SOURCE"],
             "statuses": dict(counts), "claims": attempts}
    atomic_write_json(AUDIT, audit)
    print(json.dumps({k:v for k,v in audit.items() if k != "claims"}, ensure_ascii=False))
    return audit

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--timeout", type=float, default=12)
    args = parser.parse_args()
    run(limit=args.limit, timeout=args.timeout)
