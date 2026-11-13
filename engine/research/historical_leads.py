"""Use archived historical sources as targeted revalidation leads, never as facts.

A URL from a previous snapshot is only an entry point to a NEW crawl.
It receives no 'official' or accrediting status merely because it was archived.
"""
from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit
from collections import defaultdict

from ..model import canonical

from ..settings import ROOT

HISTORY_INDEX = ROOT / "data/public/historical/gap_matches.json"
ELIGIBLE = frozenset({"manufacturers", "distributors", "integrators", "clients_private", "trends", "architectures"})
MAX_SEEDS_PER_GAP = 5


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


def _exact_key(value: object) -> str:
    """Match the original JSON claim, not just a neighbouring entity/field."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


@lru_cache(maxsize=1)
def history_by_identity() -> dict[tuple[str, str, str, str], dict]:
    """Reuse archived evidence after a gap ID changes on a later rebuild.

    The archived 'gap_matches' index was keyed by ephemeral gap IDs from 2026-10.
    Current gaps have been reissued multiple times. Match exact claim identity
    instead: section + entity + field + JSON-serialized value.
    """
    try:
        report = json.loads(HISTORY_INDEX.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return {}
    return build_identity_index(report.get("matches") or [])


def build_identity_index(rows: list[dict]) -> dict[tuple[str, str, str, str], dict]:
    """Pure helper also used by regressions with synthetic historical rows."""
    lookup: dict[tuple[str, str, str, str], dict] = {}
    for record in rows:
        if not isinstance(record, dict):
            continue
        section = str(record.get("section") or "")
        if section not in ELIGIBLE or record.get("match_level") != "exact-value-history":
            continue
        if record.get("identity_scope") != "canonical-name":
            continue
        entity = canonical(record.get("entity"))
        field = str(record.get("field") or "")
        if not entity or not field:
            continue
        for historical in record.get("historical_samples") or []:
            raw = historical.get("value")
            if not isinstance(raw, str):
                continue
            try:
                value = json.loads(raw)
            except (ValueError, TypeError):
                # The public summary intentionally truncates some complex values.
                # Never match a partial JSON fragment and guess its provenance.
                continue
            # The record-level source_urls are a UNION across values of a
            # field; they can be unrelated to the exact historical assertion.
            # The sample-level URLs were recovered from the individual claim.
            specific_urls = [url for url in historical.get("source_urls") or []
                             if isinstance(url, str)]
            if not specific_urls:
                continue
            key = (section, entity, field, _exact_key(value))
            if key not in lookup:
                lookup[key] = {**record, "source_urls": list(specific_urls)}
            else:
                existing = lookup[key]["source_urls"]
                for url in specific_urls:
                    if url not in existing:
                        existing.append(url)
    return lookup


def historical_record_for_gap(
    gap: dict, index: dict[str, dict] | None = None,
    identity_index: dict[tuple[str, str, str, str], dict] | None = None,
) -> dict | None:
    section = str(gap.get("section") or "")
    entity = str(gap.get("entity") or "")
    field = str(gap.get("field") or "")
    if section not in ELIGIBLE or not entity or not field:
        return None
    candidates = index if index is not None else history_by_gap()
    by_id = candidates.get(str(gap.get("id") or ""))
    # Even an apparently matching ID must still match the exact assertion.
    target_values = gap.get("target_values") or []
    identity = identity_index if identity_index is not None else history_by_identity()
    if not target_values:
        return None
    hits = []
    for value in target_values:
        record = identity.get((section, canonical(entity), field, _exact_key(value)))
        if record:
            hits.append(record)
    if hits:
        combined = dict(hits[0])
        combined["source_urls"] = list(dict.fromkeys(
            url for hit in hits for url in (hit.get("source_urls") or [])
        ))
        return combined
    # Old index keyed by gap ID is not sufficient: it may refer to a renamed
    # or changed claim even if section/entity/field still look similar.
    if by_id and by_id.get("match_level") == "exact-value-history":
        key_values = {
            str(sample.get("value")) for sample in by_id.get("historical_samples") or []
            if isinstance(sample, dict)
        }
        if any(_exact_key(value) in key_values for value in target_values):
            specific = [
                url
                for sample in by_id.get("historical_samples") or []
                if isinstance(sample, dict) and sample.get("value") in
                {_exact_key(value) for value in target_values}
                for url in (sample.get("source_urls") or [])
            ]
            if specific:
                return {**by_id, "source_urls": list(dict.fromkeys(specific))}
    return None


def historical_revalidation_seeds(gap: dict, index: dict[str, dict] | None = None) -> list[dict]:
    if gap.get("gap_kind") == "derivation-support" or gap.get("research_mode") == "derive-from-supported-inputs":
        return []
    if str(gap.get("section") or "") not in ELIGIBLE:
        return []
    record = historical_record_for_gap(gap, index=index)
    if not record:
        return []
    if str(record.get("section")) != str(gap.get("section")):
        return []
    if str(record.get("field")) != str(gap.get("field")):
        return []
    if canonical(record.get("entity")) != canonical(gap.get("entity")):
        return []
    # Prefer independent hostnames before multiple pages from one domain.
    # A historical URL is only a rediscovery seed, not accredited evidence.
    candidates = []
    seen = set()
    for raw in record.get("source_urls") or []:
        url = str(raw).strip()
        if not usable_historical_url(url) or url in seen:
            continue
        seen.add(url)
        candidates.append(url)
    distinct_hosts = []
    repeated_hosts = []
    hosts = set()
    for url in candidates:
        host = (urlsplit(url).hostname or "").casefold().removeprefix("www.")
        if host not in hosts:
            distinct_hosts.append(url)
            hosts.add(host)
        else:
            repeated_hosts.append(url)
    urls = (distinct_hosts + repeated_hosts)[:MAX_SEEDS_PER_GAP]
    return [{
        "url": url,
        "official": False,
        "source_grade": "C",
        "source_name": "Referencia histórica: requiere lectura y corroboración actual",
        "historical_lead": True,
    } for url in urls]
