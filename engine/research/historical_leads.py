"""Use archived historical sources as targeted revalidation leads, never as facts.

A URL from a previous snapshot is only an entry point to a NEW crawl.
It receives no 'official' or accrediting status merely because it was archived.
"""
from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from ..settings import ROOT

HISTORY_INDEX = ROOT / "data/public/historical/gap_matches.json"
ELIGIBLE = frozenset({"manufacturers", "distributors", "integrators", "clients_private", "trends"})
MAX_SEEDS_PER_GAP = 2


def usable_historical_url(url: str) -> bool:
    try:
        parsed = urlsplit(str(url).strip())
        host = parsed.hostname or ""
        return (
            parsed.scheme == "https"
            and bool(host and "." in host)
            and not parsed.username
            and not parsed.password
            and not host.casefold().endswith((".local", ".internal"))
            and not host.casefold() in {"localhost", "127.0.0.1"}
        )
    except ValueError:
        return False


@lru_cache(maxsize=1)
def history_by_gap() -> dict[str, dict]:
    try:
        report = json.loads(HISTORY_INDEX.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return {}
    rows = report.get("matches")
    if not isinstance(rows, list):
        return {}
    out = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("status") != "HISTORICAL_RESEARCH_LEAD_NOT_VERIFIED":
            continue
        if row.get("match_level") != "exact-value-history" or row.get("section") not in ELIGIBLE:
            continue
        identifier = str(row.get("gap_id") or "")
        if not identifier or row.get("identity_scope") != "canonical-name":
            continue
        out[identifier] = row
    return out


def historical_revalidation_seeds(gap: dict, index: dict[str, dict] | None = None) -> list[dict]:
    if gap.get("gap_kind") == "derivation-support" or gap.get("research_mode") == "derive-from-supported-inputs":
        return []
    if str(gap.get("section") or "") not in ELIGIBLE:
        return []
    record = (index if index is not None else history_by_gap()).get(str(gap.get("id") or ""))
    if not record:
        return []
    if str(record.get("section")) != str(gap.get("section")):
        return []
    if str(record.get("field")) != str(gap.get("field")):
        return []
    if str(record.get("entity")) != str(gap.get("entity")):
        return []
    urls = []
    for url in record.get("source_urls") or []:
        if not usable_historical_url(url) or url in urls:
            continue
        urls.append(url)
        if len(urls) == MAX_SEEDS_PER_GAP:
            break
    return [{
        "url": url,
        "official": False,
        "source_grade": "C",
        "source_name": "Referencia histórica: requiere lectura y corroboración actual",
        "historical_lead": True,
    } for url in urls]
