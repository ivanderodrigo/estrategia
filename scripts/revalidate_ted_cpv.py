"""Revalidate existing CPV claims against the original official TED notice.

The claim to be checked is a precise (publication-number, CPV code) pair.
Search hits, the old value and general TED descriptions never count as proof.
Only a CPV code returned by the live public TED Search API for the same
publication number is given typed, atomic evidence.

No notice is created; no unsupported value is removed or silently accredited.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from engine.enrichment import merge_field
from engine.model import canonical
from engine.research.ted import TED_SEARCH_URL, _cpv_codes, _first
from engine.storage import atomic_write_json, read_json


_NUMBER = re.compile(r"^0*[0-9]{1,8}-20[0-9]{2}$")
_CPV = re.compile(r"^[0-9]{8}$")
ROOT = Path(__file__).resolve().parents[1]


def eligible_notices(data: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    indexed: dict[str, list[dict[str, Any]]] = {}
    for row in data.get("clients_public") or []:
        if not isinstance(row, dict):
            continue
        fields = row.get("fields") or {}
        notice = ((fields.get("notice_id") or {}).get("value"))
        numbers = notice if isinstance(notice, list) else [notice]
        cpvs = (fields.get("cpv_codes") or {}).get("value")
        cpvs = cpvs if isinstance(cpvs, list) else [cpvs]
        if not any(_CPV.fullmatch(str(code).strip()) for code in cpvs):
            continue
        for raw in numbers:
            num = str(raw or "").strip()
            if _NUMBER.fullmatch(num):
                indexed.setdefault(num, []).append(row)
    return indexed


def _api_payload(numbers: list[str]) -> dict[str, Any]:
    return {
        "query": f'publication-number IN ({" ".join(numbers)})',
        "fields": [
            "publication-number", "publication-date", "buyer-name",
            "notice-title", "title-proc", "classification-cpv",
        ],
        "limit": min(250, max(1, len(numbers) * 2)),
        "scope": "ALL",
        "checkQuerySyntax": False,
        "paginationMode": "PAGE_NUMBER",
        "page": 1,
        "onlyLatestVersions": False,
    }


def retrieve_batch(
    session: requests.Session,
    numbers: list[str],
    *,
    timeout: int = 20,
) -> tuple[list[dict[str, Any]], int]:
    """Return actual TED notices, or subdivide a rejected batch once needed."""
    if not numbers:
        return [], 0
    try:
        response = session.post(
            TED_SEARCH_URL, json=_api_payload(numbers),
            timeout=(min(6, timeout), timeout),
        )
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            return [], 1
        rows = body.get("notices") or []
        return [row for row in rows if isinstance(row, dict)], 0
    except (requests.RequestException, ValueError, TypeError):
        if len(numbers) <= 1:
            return [], 1
        middle = len(numbers) // 2
        first, failed1 = retrieve_batch(session, numbers[:middle], timeout=timeout)
        second, failed2 = retrieve_batch(session, numbers[middle:], timeout=timeout)
        return first + second, failed1 + failed2


def _buyer_bound(owner: str, published_buyer: str) -> bool:
    """Reject an unrelated buyer if the notice row was attached incorrectly."""
    left = set(canonical(owner).split()) - {"de", "del", "da", "do", "y", "e", "the"}
    right = set(canonical(published_buyer).split()) - {"de", "del", "da", "do", "y", "e", "the"}
    significant = {word for word in left if len(word) >= 5}
    if not published_buyer:
        return False
    return bool(significant & right) or canonical(owner) == canonical(published_buyer)


def reconcile_notice(
    row: dict[str, Any], notice: dict[str, Any], *,
    claimed_number: str,
    checked_date: str,
) -> int:
    """Promote only values explicitly present in THIS notice's CPV API field."""
    published_number = _first(notice.get("publication-number"))
    if published_number != claimed_number:
        return 0
    owner = str(row.get("name") or "").strip()
    buyer = _first(notice.get("buyer-name"))
    if not owner or not _buyer_bound(owner, buyer):
        return 0
    actual = {
        str(code).strip() for code in _cpv_codes(notice)
        if _CPV.fullmatch(str(code).strip())
    }
    fields = row.get("fields") or {}
    field = fields.get("cpv_codes") or {}
    original = field.get("value")
    values = original if isinstance(original, list) else [original]
    matched = [
        str(code).strip() for code in values
        if str(code).strip() in actual
    ]
    if not matched:
        return 0

    title = _first(notice.get("notice-title") or notice.get("title-proc"))
    published_at = _first(notice.get("publication-date")) or checked_date
    address = f"https://ted.europa.eu/en/notice/-/detail/{published_number}"
    items = []
    existing = {
        canonical(item.get("value")): item
        for item in field.get("items") or []
        if isinstance(item, dict)
    }
    accepted = 0
    for code in matched:
        old = existing.get(canonical(code)) or {}
        if any(ev.get("atomic") is True
               and ev.get("item_value") == code
               and ev.get("official") is True
               and ev.get("source_type") == "official-procurement-api"
               for ev in old.get("evidence") or [] if isinstance(ev, dict)):
            continue
        citation = {
            "source": "TED · Diario Oficial de la Unión Europea",
            "title": f"{published_number} · {title or 'Anuncio de contratación'}",
            "url": address,
            "date": published_at,
            "description": f"{buyer} · anuncio {published_number} · clasificación CPV: {code}",
            "scope": "GLOBAL",
            "source_grade": "A",
            "source_type": "official-procurement-api",
            "official": True,
            "classification": "public",
            "retrieved_at": checked_date,
            "freshness_status": "current",
            "method": "ted-search-api-v3-exact-cpv",
            "source_binding": "atomic-item",
            "researched_entity": owner,
            "item_value": code,
            "item_key": canonical(code),
            "field": "cpv_codes",
            "atomic": True,
            "accrediting": True,
            "matched_terms": [code],
        }
        items.append({"value": code, "evidence": [citation],
                      "confidence": 0.99, "claim_type": "fact",
                      "assertion_status": "CONFIRMADO"})
        accepted += 1
    if items:
        row.setdefault("fields", {})["cpv_codes"] = merge_field(
            field, {"value": [item["value"] for item in items],
                    "items": items, "confidence": 0.99,
                    "claim_type": "fact", "assertion_status": "CONFIRMADO"},
        )
    return accepted


def revalidate(
    data: dict[str, Any], session: requests.Session,
    *,
    max_runtime: int = 630,
    batch_size: int = 18,
    max_notices: int = 1000,
) -> dict[str, Any]:
    begun = time.monotonic()
    candidate_index = eligible_notices(data)
    numbers = list(candidate_index)[:max_notices]
    stats = Counter()
    stats["eligible_notices"] = len(candidate_index)
    stats["selected_notices"] = len(numbers)
    today = datetime.now(timezone.utc).date().isoformat()
    for offset in range(0, len(numbers), batch_size):
        if time.monotonic() - begun > max_runtime - 20:
            stats["stopped_by_deadline"] = 1
            break
        batch = numbers[offset: offset + batch_size]
        records, failures = retrieve_batch(session, batch)
        stats["api_batches"] += 1
        stats["api_failures"] += failures
        requested = set(batch)
        seen = set()
        for notice in records:
            number = _first(notice.get("publication-number"))
            if number not in requested:
                stats["unexpected_notice_rejected"] += 1
                continue
            if number in seen:
                continue
            seen.add(number)
            for row in candidate_index.get(number) or []:
                count = reconcile_notice(
                    row, notice, claimed_number=number, checked_date=today,
                )
                stats["cpv_values_accredited"] += count
                stats["notices_with_matches"] += bool(count)
        stats["matched_notices"] += len(seen)
        stats["notices_absent_in_response"] += len(requested - seen)
        if offset and offset % (batch_size * 5) == 0:
            print(f"TED exact verification: {offset} checked; "
                  f"{stats['cpv_values_accredited']} CPV codes independently corroborated",
                  flush=True)
    stats["elapsed_s"] = round(time.monotonic() - begun, 2)
    return dict(stats)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-runtime", type=int, default=630)
    parser.add_argument("--max-notices", type=int, default=1000)
    parser.add_argument("--batch-size", type=int, default=18)
    args = parser.parse_args()

    gaps_before = read_json("data/current/research_gaps.json", {})
    before = sum(1 for g in gaps_before.get("gaps") or []
                 if g.get("section") == "clients_public"
                 and g.get("field") == "cpv_codes")
    data = read_json("data/current/intelligence.json", {})
    with requests.Session() as session:
        session.headers.update({"User-Agent": "Westcon-Iberia-Observatory/7.2 (CPV independent verification)",
                                "Accept": "application/json"})
        stats = revalidate(data, session, max_runtime=args.max_runtime,
                           max_notices=args.max_notices,
                           batch_size=args.batch_size)

    if stats.get("cpv_values_accredited", 0):
        atomic_write_json("data/current/intelligence.json", data)
    from engine.pipeline import run as rebuild
    if stats.get("cpv_values_accredited", 0):
        rebuild()
    after_gaps = read_json("data/current/research_gaps.json", {})
    after = sum(1 for g in after_gaps.get("gaps") or []
                if g.get("section") == "clients_public"
                and g.get("field") == "cpv_codes")
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "independent live TED API CPV check; each code must match the exact publication number and buyer",
        "cpv_gaps_before": before,
        "cpv_gaps_after": after,
        "cpv_gaps_closed_net": before - after,
        **stats,
    }
    atomic_write_json("data/current/ted_cpv_revalidation.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
