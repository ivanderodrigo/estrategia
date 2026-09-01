"""Keyless official TED procurement connector for Spain and Portugal."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from ..enrichment import merge_field
from ..model import canonical, stable_id


TED_SEARCH_URL = "https://api.ted.europa.eu/v3/notices/search"
IT_CPV_PREFIXES = ("302", "324", "325", "48", "72")


def _first(value: Any) -> str:
    if isinstance(value, dict):
        for language in ("spa", "por", "eng"):
            candidate = value.get(language)
            if candidate:
                return _first(candidate)
        return _first(next(iter(value.values()), ""))
    if isinstance(value, list):
        return _first(value[0]) if value else ""
    return str(value or "").strip()


def _cpv_codes(notice: dict[str, Any]) -> list[str]:
    raw = notice.get("classification-cpv") or []
    values = raw if isinstance(raw, list) else [raw]
    return list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


def notice_is_relevant(notice: dict[str, Any]) -> bool:
    """Limit automatic growth to computing, networking, telecom, software and IT services."""

    return any(code.startswith(IT_CPV_PREFIXES) for code in _cpv_codes(notice))


def parse_notice(notice: dict[str, Any]) -> dict[str, Any] | None:
    if not notice_is_relevant(notice):
        return None
    number = _first(notice.get("publication-number"))
    title = _first(notice.get("notice-title") or notice.get("title-proc"))
    buyer = _first(notice.get("buyer-name"))
    country = _first(notice.get("buyer-country") or notice.get("organisation-country-buyer"))
    scope = "ES" if country in {"ESP", "ES", "Spain", "España"} else "PT" if country in {"PRT", "PT", "Portugal"} else "IBERIA"
    if not number or not title or not buyer:
        return None
    url = f"https://ted.europa.eu/en/notice/-/detail/{number}"
    publication_date = _first(notice.get("publication-date"))
    deadline = _first(notice.get("deadline-receipt-tender-date-lot") or notice.get("deadline"))
    amount = _first(notice.get("estimated-value-proc") or notice.get("total-value"))
    currency = _first(notice.get("estimated-value-cur-proc") or notice.get("total-value-cur"))
    cpv_codes = _cpv_codes(notice)
    evidence = [{
        "source": "TED · Tenders Electronic Daily",
        "title": f"{number} · {title}",
        "url": url,
        "date": publication_date or datetime.now(timezone.utc).date().isoformat(),
        "description": title,
        "scope": scope,
        "source_grade": "A",
        "source_type": "official-procurement-api",
        "official": True,
        "classification": "public",
        "retrieved_at": datetime.now(timezone.utc).date().isoformat(),
        "freshness_status": "current",
        "method": "ted-search-api-v3",
    }]
    return {
        "id": stable_id("client", f"{buyer}|{number}"),
        "name": buyer,
        "evidence": evidence,
        "fields": {
            "scope": merge_field(None, {"value": scope, "evidence": evidence, "confidence": 0.96, "claim_type": "fact"}),
            "entity_type": merge_field(None, {"value": "Administración / entidad pública", "evidence": evidence, "confidence": 0.92, "claim_type": "fact"}),
            "notice_id": merge_field(None, {"value": number, "evidence": evidence, "confidence": 0.99, "claim_type": "fact"}),
            "request_or_need": merge_field(None, {"value": title, "evidence": evidence, "confidence": 0.96, "claim_type": "fact"}),
            "milestone_date": merge_field(None, {"value": deadline or publication_date, "evidence": evidence, "confidence": 0.90, "claim_type": "fact"}),
            "procurement_stage": merge_field(None, {"value": "Anuncio publicado", "evidence": evidence, "confidence": 0.92, "claim_type": "fact"}),
            "source_portal": merge_field(None, {"value": "TED", "evidence": evidence, "confidence": 0.99, "claim_type": "fact"}),
            # Internal lifecycle marker. It is intentionally outside the public schema.
            "cpv_codes": merge_field(None, {"value": cpv_codes, "evidence": evidence, "confidence": 0.99, "claim_type": "fact"}),
        },
    } | ({"_amount": f"{amount} {currency}".strip()} if amount else {})


def upsert_notices(data: dict[str, Any], notices: list[dict[str, Any]]) -> int:
    rows = data.setdefault("clients_public", [])
    # v4.0.0 migration: the first TED implementation did not retain CPV and used a
    # broader root query. Remove only those managed imports; manually curated rows stay.
    rows[:] = [
        row for row in rows
        if not (
            (((row.get("fields") or {}).get("source_portal") or {}).get("value") == "TED")
            and not ((row.get("fields") or {}).get("cpv_codes") or {}).get("value")
        )
    ]
    index = {
        canonical(((row.get("fields") or {}).get("notice_id") or {}).get("value")): row
        for row in rows
    }
    added = 0
    for raw_notice in notices:
        parsed = parse_notice(raw_notice)
        if not parsed:
            continue
        number = canonical(parsed["fields"]["notice_id"]["value"])
        amount = parsed.pop("_amount", "")
        if amount:
            parsed["fields"]["estimated_amount"] = merge_field(None, {
                "value": amount,
                "evidence": parsed["evidence"],
                "confidence": 0.90,
                "claim_type": "fact",
            })
        existing = index.get(number)
        if existing:
            existing["name"] = parsed["name"]
            existing["evidence"] = parsed["evidence"]
            for field_id, field in parsed["fields"].items():
                existing.setdefault("fields", {})[field_id] = merge_field(existing.get("fields", {}).get(field_id), field)
        else:
            rows.append(parsed)
            index[number] = parsed
            added += 1
    rows.sort(key=lambda row: str((((row.get("fields") or {}).get("milestone_date") or {}).get("value")) or ""), reverse=True)
    return added


def fetch_notices(session: requests.Session, *, lookback_days: int, timeout_s: int, limit: int = 100) -> list[dict[str, Any]]:
    since = (datetime.now(timezone.utc).date() - timedelta(days=max(1, lookback_days))).strftime("%Y%m%d")
    payload = {
        "query": (
            f"publication-date >= {since} AND organisation-country-buyer IN (ESP PRT) "
            "AND classification-cpv = (30200000 OR 32400000 OR 32500000 OR 48000000 OR 72000000) "
            "SORT BY publication-date DESC"
        ),
        "fields": [
            "publication-number", "publication-date", "notice-title", "title-proc", "buyer-name",
            "organisation-country-buyer", "classification-cpv", "estimated-value-proc",
            "estimated-value-cur-proc", "total-value", "total-value-cur",
            "deadline-receipt-tender-date-lot",
        ],
        "limit": min(250, max(1, limit)),
        "scope": "ACTIVE",
        "checkQuerySyntax": False,
        "paginationMode": "PAGE_NUMBER",
        "page": 1,
        "onlyLatestVersions": True,
    }
    response = session.post(TED_SEARCH_URL, json=payload, timeout=timeout_s)
    response.raise_for_status()
    body = response.json()
    notices = body.get("notices") or []
    return [
        notice for notice in notices
        if isinstance(notice, dict) and notice_is_relevant(notice)
    ]
