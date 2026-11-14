"""Bounded live source-review sampler.

The output is a review queue, never a definitive truth verdict. Source-page
accessibility and lexical matches cannot establish contextual or temporal truth.
No dataset files are modified.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import requests

from engine.research.security import UnsafeUrl, validate_public_url
from scripts.audit_claim_sources import SECTIONS, normal, text_mentions


class _VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in ("script", "style", "noscript"):
            self.hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in ("script", "style", "noscript") and self.hidden:
            self.hidden -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden and data.strip():
            self.parts.append(data)


def review_document(session: requests.Session, url: str, entity: str, value: str) -> str:
    """Do not follow redirects or request non-public hosts."""
    try:
        public = validate_public_url(url)
        response = session.get(public, timeout=(3, 7), allow_redirects=False,
                               stream=True, headers={"User-Agent": "Westcon-Research-Auditor/1.0"})
        try:
            if 300 <= response.status_code < 400:
                return "redirect_requires_review"
            # HTTP 202 Accepted can carry the complete readable document.
            # Do not reject all 2xx statuses before checking the actual body.
            # Conversely, a 202 with no usable content is NOT a verified page.
            if not 200 <= response.status_code < 300:
                return "http_" + str(response.status_code)
            content_type = response.headers.get("Content-Type", "").lower()
            if "text/html" not in content_type and "text/plain" not in content_type:
                return "document_format_requires_review"
            chunks = []
            total = 0
            for chunk in response.iter_content(chunk_size=16384):
                total += len(chunk)
                if total > 650000:
                    break
                chunks.append(chunk)
            raw = b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
        finally:
            response.close()
        parser = _VisibleText()
        if "text/html" in content_type:
            parser.feed(raw)
            text = " ".join(parser.parts)
        else:
            text = raw
        if len(text.strip()) < 20:
            return "http_" + str(response.status_code) + "_insufficient_content"
        if text_mentions(text, entity) and text_mentions(text, value):
            return "page_mentions_entity_and_value_needs_semantic_review"
        if text_mentions(text, value):
            return "page_mentions_value_only"
        return "page_does_not_mention_value"
    except (UnsafeUrl, requests.RequestException, UnicodeError, ValueError) as exc:
        return "fetch_error_" + type(exc).__name__


def collect_claims(root: Path) -> list[dict]:
    claims = []
    for section in SECTIONS:
        file = root / "sections" / (section + ".json")
        if not file.exists():
            continue
        payload = json.loads(file.read_text(encoding="utf-8"))
        registry = payload.get("evidence") or {}
        for row in payload.get("rows") or []:
            entity = str(row.get("name") or "")
            for field_name, field in (row.get("fields") or {}).items():
                if not isinstance(field, dict):
                    continue
                items = field.get("items") if isinstance(field.get("value"), list) else [field]
                for item in items if isinstance(items, list) else []:
                    if not isinstance(item, dict) or not isinstance(item.get("value"), str):
                        continue
                    for ref in item.get("evidence_ids") or []:
                        ev = registry.get(ref) or {}
                        url = str(ev.get("url") or "")
                        if not url.startswith(("https://", "http://")):
                            continue
                        claims.append({"section": section, "entity": entity, "field": field_name,
                                       "value": item["value"], "evidence_id": ref, "url": url})
    return sorted(claims, key=lambda x: (
        x["section"], normal(x["entity"]), x["field"], normal(x["value"]), x["url"]))


def run(root: Path, limit: int, day: int, session: requests.Session) -> dict:
    claims = collect_claims(root)
    total = len(claims)
    if not total:
        return {"total_references": 0, "sampled": 0, "items": []}
    # A contiguous slice can contain 200 references to the SAME host (TED,
    # for example), falsely reporting that *all* external sources failed.
    # Rotate across section+host strata first; rotate items inside each
    # stratum on successive days, retaining deterministic repeatability.
    from collections import defaultdict
    buckets = defaultdict(list)
    for claim in claims:
        host = (urlparse(claim["url"]).hostname or "").lower()
        buckets[(claim["section"],host)].append(claim)
    groups = sorted(buckets)
    rotation = day % len(groups)
    groups = groups[rotation:] + groups[:rotation]
    selection = []
    round_number = 0
    target = min(limit,total)
    while len(selection) < target:
        grew = False
        for key in groups:
            bucket = buckets[key]
            if round_number >= len(bucket):
                continue
            offset = day % len(bucket)
            selection.append(bucket[(offset + round_number) % len(bucket)])
            grew = True
            if len(selection) >= target:
                break
        if not grew:
            break
        round_number += 1
    start = rotation
    cache: dict[tuple[str, str, str], str] = {}
    for claim in selection:
        key = (claim["url"], claim["entity"], claim["value"])
        if key not in cache:
            cache[key] = review_document(session, *key)
        claim["review_status"] = cache[key]
    return {"total_references": total, "sampled": len(selection),
            "start_offset": start, "sampling_policy": "rotating-section-host-round-robin-v1",
            "unique_source_hosts_in_sample": len(set(
                (urlparse(item["url"]).hostname or "").lower() for item in selection
            )),
            "source_content_semantically_verified": False,
            "items": selection}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("data/public"))
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--day", type=int, default=date.today().toordinal())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with requests.Session() as session:
        report = run(args.root, max(1, min(args.limit, 300)), args.day, session)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts: dict[str, int] = {}
    for item in report["items"]:
        status = item["review_status"]
        counts[status] = counts.get(status, 0) + 1
    print(json.dumps({"total_references": report["total_references"],
                      "sampled": report["sampled"], "statuses": counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
