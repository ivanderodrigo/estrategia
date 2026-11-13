#!/usr/bin/env python3
"""Bounded, repeated live checking of historical source leads.

A successful HTTP response or phrase hit is NOT sufficient to accredit an
atomic claim. Output is an auditable research queue, never accrediting evidence.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore, Lock
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.model import canonical
from engine.research.security import UnsafeUrl, validate_public_url
from engine.storage import atomic_write_json, read_json


def candidate_inventory() -> dict[str, list[dict]]:
    targets: dict[str, list[dict]] = defaultdict(list)
    for section in ("manufacturers", "distributors", "integrators",
                    "trends", "architectures", "clients_private"):
        path = f"data/public/historical/current/{section}.json"
        store = read_json(path, {})
        for entity, fields in (store.get("entities") or {}).items():
            for field_id, claims in fields.items():
                for claim in claims:
                    value = claim.get("value")
                    if not isinstance(value, str):
                        continue  # Complex layer graphs need item-specific expert validation.
                    for url in claim.get("urls") or []:
                        if url.startswith("https://"):
                            targets[url].append({
                                "section": section, "entity": entity,
                                "field": field_id, "value": value,
                            })
    return targets


def check_one(url: str, claims: list[dict], timeout: float = 7.0,
              session: requests.Session | None = None) -> dict:
    checked = datetime.now(timezone.utc).isoformat()
    result = {"url": url, "checked_at": checked,
              "status": "UNAVAILABLE", "claim_hits": 0,
              "claims_tested": len(claims),
              "accreditation": "NOT_ACCREDITED"}
    try:
        safe = validate_public_url(url)
        get = session.get if session is not None else requests.get
        headers={"User-Agent": "Westcon-Intelligence-Historical-Revalidation/1.0"}
        redirects=[]
        # Redirects are not failed evidence: follow them only after validating
        # each next target against the public-URL security policy.
        for _ in range(4):
            response = get(safe, timeout=timeout, allow_redirects=False, headers=headers)
            if response.status_code not in (301,302,303,307,308):
                break
            from urllib.parse import urljoin
            location=response.headers.get("Location")
            if not location:
                break
            next_url=validate_public_url(urljoin(safe, location))
            redirects.append(next_url)
            safe=next_url
        result["http_status"] = response.status_code
        result["resolved_url"]=safe
        if redirects:
            result["redirect_chain"]=redirects
        if not (200 <= response.status_code < 300):
            result["status"] = "HTTP_UNAVAILABLE"
            return result
        content_type = str(response.headers.get("Content-Type") or "").lower()
        if content_type and not any(t in content_type for t in ("text/", "html", "json")):
            result["status"] = "NON_TEXT_SOURCE"
            return result
        text = canonical(unescape(re.sub(r"<[^>]+>", " ", response.text[:600_000])))
        if len(text) < 100:
            result["status"] = "INSUFFICIENT_SOURCE_CONTENT"
            return result
        # Every exact claim is evaluated separately. A text mention is a
        # RESEARCH FINDING, not accreditation: a vendor can occur in an index,
        # footnote, negative comparison or entirely unrelated page section.
        checks = []
        for claim in claims:
            value = canonical(claim["value"])
            tokens = value.split()
            informative = len(value) >= 6 and (
                len(tokens) >= 2 or
                claim.get("field") in ("competitors", "market_players", "vendors",
                                        "vendor_relations", "westcon_overlap")
            )
            occurs = bool(informative and re.search(
                r"(?<![a-z0-9])" + re.escape(value) + r"(?![a-z0-9])", text
            ))
            # Keep a bounded, reviewable excerpt for every positive match.
            # A mention is deliberately NOT evidence of a named relationship.
            context=""
            if occurs:
                match=re.search(r"(?<![a-z0-9])" + re.escape(value) + r"(?![a-z0-9])", text)
                if match:
                    context=text[max(0,match.start()-120):min(len(text),match.end()+120)]
            checks.append({
                "section": claim["section"], "entity": claim["entity"],
                "field": claim["field"], "value": claim["value"][:180],
                "status": "VALUE_PRESENT_REQUIRES_CONTEXT" if occurs
                          else "NO_SPECIFIC_VALUE_CONFIRMED",
                "source_context": context,
                "resolved_url": safe,
                "accredited": False,
            })
        hits = [c for c in checks if c["status"] == "VALUE_PRESENT_REQUIRES_CONTEXT"]
        result["claim_checks"] = checks
        result["claim_hits"] = len(hits)
        result["examples"] = hits[:5]
        result["status"] = "REACHABLE_TEXT_MATCH" if hits else "REACHABLE_NO_EXACT_TEXT"
        return result
    except (requests.RequestException, ValueError, OSError, UnsafeUrl) as exc:
        result["status"] = "FETCH_ERROR"
        result["error_kind"] = type(exc).__name__
        return result


def run(limit: int, timeout: float, workers: int = 1) -> dict:
    inventory = candidate_inventory()
    previous = read_json("data/current/historical_source_checks.json", {})
    state = dict(previous.get("results") or {})
    # Oldest checked first; never treat repeated search failure as lack of relevance.
    ordered = sorted(inventory, key=lambda url: (str(state.get(url, {}).get("checked_at") or ""),
                                                   url))
    chosen = ordered[:max(1, limit)]
    stats = Counter()
    if workers <= 1:
        with requests.Session() as session:
            for url in chosen:
                outcome = check_one(url, inventory[url], timeout, session)
                state[url] = outcome
                stats[outcome["status"]] += 1
    else:
        # Limit concurrent requests to any one hostname (external courtesy).
        semaphores: dict[str, BoundedSemaphore] = {}
        mutex = Lock()
        def assess(url: str) -> tuple[str, dict]:
            host = urlparse(url).hostname or ""
            with mutex:
                if host not in semaphores:
                    semaphores[host] = BoundedSemaphore(2)
                semaphore = semaphores[host]
            with semaphore:
                return url, check_one(url, inventory[url], timeout)
        with ThreadPoolExecutor(max_workers=min(12, max(1, workers))) as pool:
            for url, outcome in pool.map(assess, chosen):
                state[url] = outcome
                stats[outcome["status"]] += 1
    # Drop pages no longer referenced by any current historical assertion.
    state = {url: row for url, row in state.items() if url in inventory}
    completed = datetime.now(timezone.utc).isoformat()
    output = {
        "generated_at": completed,
        "status": "SOURCE_REACHABILITY_CHECK_NOT_ACCREDITATION",
        "urls_in_inventory": len(inventory),
        "urls_checked_this_run": len(chosen),
        "claims_checked_this_run": sum(int(state[url].get("claims_tested") or 0) for url in chosen),
        "urls_with_prior_checks": len(state),
        "claim_accuracy_note": "An HTTP success or phrase hit does not verify the specific fact; evidence promotion still needs content/relationship assessment.",
        "run_statuses": dict(stats),
        "results": state,
    }
    atomic_write_json("data/current/historical_source_checks.json", output)
    public = {k: value for k, value in output.items() if k != "results"}
    public["results"] = {url: {k: row.get(k) for k in (
        "checked_at", "status", "http_status", "claim_hits", "claims_tested", "accreditation")}
        for url, row in state.items()}
    atomic_write_json("data/public/historical/current/source_checks.json", public)
    print(json.dumps({k: v for k, v in output.items() if k != "results"},
                     ensure_ascii=False))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=24)
    parser.add_argument("--timeout", type=float, default=7.0)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    run(args.limit, args.timeout, args.workers)
