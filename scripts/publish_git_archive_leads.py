#!/usr/bin/env python3
"""Publish compact, non-accrediting Git archive leads for observatory trace panels."""
from __future__ import annotations
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/public/historical/current"
SECTIONS = ("manufacturers", "distributors", "integrators", "clients_public",
            "clients_private", "trends", "architectures")

def norm(value):
    raw = unicodedata.normalize("NFD", str(value or "").lower())
    clean = "".join(ch for ch in raw if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", clean).strip()

def publish():
    source = BASE / "git_archive_additions.json"
    if not source.exists():
        raise SystemExit("Missing historical archive extraction: " + str(source))
    raw = json.loads(source.read_text(encoding="utf-8"))
    if raw.get("status") != "HISTORICAL_GIT_LEADS_NOT_ACCREDITED":
        raise SystemExit("Refusing unexpected or accrediting archive")
    grouped = {section: defaultdict(lambda: defaultdict(dict)) for section in SECTIONS}
    for claim in raw.get("claims") or []:
        if not isinstance(claim, dict):
            continue
        section = claim.get("section")
        if section not in grouped:
            continue
        entity, field, value = claim.get("entity"), claim.get("field"), claim.get("value")
        url = claim.get("url")
        if not all(isinstance(x, str) and x.strip() for x in (entity, field, value, url)):
            continue
        if not url.startswith("https://"):
            continue
        e, v = norm(entity), norm(value)
        if not e or not v:
            continue
        # Bind at exact entity + field + item value. Cap repeated
        # historical links, not the number of distinct provenances.
        target = grouped[section][e][field].setdefault(v, {"value": value, "urls": []})
        if url not in target["urls"] and len(target["urls"]) < 6:
            target["urls"].append(url)
    stats = {}
    for section in SECTIONS:
        entities = {}
        count = 0
        for entity, fields in grouped[section].items():
            entities[entity] = {}
            for field, values in fields.items():
                entities[entity][field] = list(values.values())
                count += len(values)
        result = {"status": "GIT_HISTORICAL_LEADS_NOT_ACCREDITED",
                  "section": section, "entities": entities,
                  "claim_count": count}
        (BASE / ("git_" + section + ".json")).write_text(
            json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8")
        stats[section] = count
    print(json.dumps({"visible_archived_claims": stats}, ensure_ascii=False))
    return stats

if __name__ == "__main__":
    publish()
