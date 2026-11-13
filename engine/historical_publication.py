"""Publish exact archived source trails alongside current, accredited intelligence.

Historical URLs are leads for revalidation; they must NEVER be copied into
field.evidence, included in source coverage, or counted as credited facts.
The public sidecars link each existing pending claim to its exact old assertion.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from .model import canonical
from .historical_source_alignment import source_alignment
from .settings import SECTIONS
from .research.historical_leads import (
    historical_record_for_gap, history_by_gap, history_by_identity,
    usable_historical_url,
)
from .storage import json_bytes

MAX_URLS = 3
MAX_CLAIMS_PER_FIELD = 24


def publish_historical_trails(gap_report: dict[str, Any], generated_at: str) -> tuple[dict[str, bytes], dict[str, Any]]:
    previous_by_id = history_by_gap()
    previous_by_identity = history_by_identity()
    by_section: dict[str, dict[str, dict[str, list[dict]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )
    tally = Counter()
    unique_urls: set[str] = set()
    quarantine: list[dict[str, Any]] = []
    for gap in gap_report.get("gaps") or []:
        if not isinstance(gap, dict):
            continue
        if gap.get("gap_kind") == "derivation-support" or gap.get("research_mode") == "derive-from-supported-inputs":
            continue
        section = str(gap.get("section") or "")
        if section not in SECTIONS:
            continue
        record = historical_record_for_gap(
            gap, previous_by_id, previous_by_identity
        )
        if not record:
            continue
        entity = str(gap.get("entity") or "")
        field = str(gap.get("field") or "")
        if not entity or not field:
            continue
        targets = gap.get("target_values") or []
        if not isinstance(targets, list):
            targets = [targets]
        samples = record.get("historical_samples") or []
        for target in targets:
            import json
            key = json.dumps(target, ensure_ascii=False, sort_keys=True, default=str)
            sample = next((item for item in samples
                           if isinstance(item, dict) and item.get("value") == key), None)
            if sample is None:
                continue
            urls = []
            for url in dict.fromkeys(str(u) for u in sample.get("source_urls") or []):
                if not usable_historical_url(url):
                    continue
                aligned, reason = source_alignment(section, entity, field, url)
                if not aligned:
                    quarantine.append({"section": section, "entity": entity,
                                       "field": field, "value": target, "url": url,
                                       "reason": reason})
                    continue
                if len(urls) < MAX_URLS:
                    urls.append(url)
            if not urls:
                continue
            claims = by_section[section][canonical(entity)][field]
            if len(claims) >= MAX_CLAIMS_PER_FIELD:
                continue
            if any(item["value"] == target for item in claims):
                continue
            claims.append({
                "value": target,
                "urls": urls,
                "first_revision": sample.get("first_revision") or record.get("historical_samples", [{}])[0].get("first_revision") or "",
                "last_revision": sample.get("last_revision") or record.get("historical_samples", [{}])[0].get("last_revision") or "",
            })
            unique_urls.update(urls)
            tally["claims"] += 1
            tally["claims_" + section] += 1

    out: dict[str, bytes] = {}
    for section in SECTIONS:
        entities = by_section.get(section, {})
        result = {
            "generated_at": generated_at,
            "status": "HISTORICAL_LEADS_NOT_ACCREDITED",
            "section": section,
            "entities": entities,
            "claim_count": sum(len(claims) for fields in entities.values() for claims in fields.values()),
        }
        out[f"data/public/historical/current/{section}.json"] = json_bytes(result)
        tally["entities_" + section] = len(entities)
    summary = {
        "generated_at": generated_at,
        "status": "HISTORICAL_LEADS_NOT_ACCREDITED",
        "claims": tally["claims"],
        "unique_urls": len(unique_urls),
        "by_section": {section: {"claims": tally["claims_" + section],
                                "entities": tally["entities_" + section]} for section in SECTIONS},
        "policy": "Fuentes históricas localizadas, no acreditadas. Requieren lectura actual que respalde exactamente la afirmación. No reducen el contador de huecos sin validación.",
    }
    summary["quarantined_source_links"] = len(quarantine)
    out["data/public/historical/current/quarantined_links.json"] = json_bytes({
        "generated_at": generated_at, "records": quarantine,
        "policy": "URLs originales conservadas solo para auditoría: se refieren a otro fabricante."
    })
    out["data/public/historical/current/summary.json"] = json_bytes(summary)
    return out, summary
