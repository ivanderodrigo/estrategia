#!/usr/bin/env python3
"""Recover explicit publication dates for news already visible in seven areas.

This is a presentation-only metadata index: it never accredits claims, changes
their sources, or turns the time of retrieval into a publication timestamp.
"""
from __future__ import annotations

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import requests

from engine.research.documents import parse_document

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'data/public/news_publication_dates.json'
FIELDS = {
    'manufacturers': ('recent_signals', 'analyst_signals'),
    'distributors': ('recent_signals', 'vendor_relations', 'acquisitions'),
    'integrators': ('recent_signals', 'public_cases', 'public_contracts', 'alliances'),
    'clients_public': ('recent_signals', 'investment_signals', 'public_projects', 'contracts', 'technology_signals', 'strategic_programs', 'request_or_need'),
    'clients_private': ('recent_signals', 'investment_signals', 'public_projects', 'contracts', 'technology_signals', 'strategic_programs', 'request_or_need'),
    'trends': ('recent_signals', 'sources', 'drivers', 'evolution', 'market_players', 'technology_signals', 'buyer_priorities'),
    'architectures': ('recent_signals', 'sources', 'use_cases', 'vendors', 'layers', 'technology_signals', 'market_drivers'),
}
ARTICLE = re.compile(r'/(?:news|noticias?|actualidad|novidades|press|prensa|releases?|announcements?|blog|insights|articles?|artigos?|research|reports?|estudios|publicaciones?|case.studies|newsroom)/[^/?#]{7,}', re.I)


def urls_by_section() -> dict[str, set[str]]:
    result = {}
    for section, fields in FIELDS.items():
        payload = json.loads((ROOT / f'data/public/sections/{section}.json').read_text(encoding='utf-8'))
        urls = set()
        for row in payload.get('rows', []):
            for name in fields:
                field = (row.get('fields') or {}).get(name) or {}
                ids = set(field.get('evidence_ids') or [])
                for item in field.get('items') or []:
                    ids.update(item.get('evidence_ids') or [])
                for eid in ids:
                    ev = (payload.get('evidence') or {}).get(eid) or {}
                    url = ev.get('url') or ''
                    if url.startswith('https://') and ARTICLE.search(urlsplit(url).path):
                        urls.add(url)
        result[section] = urls
    return result


def retrieve(url: str) -> tuple[str, dict | None]:
    try:
        # Article URLs are collected exclusively from the site's curated evidence
        # registry, never arbitrary external input or untrusted redirect targets.
        from engine.research.security import validate_public_url
        validate_public_url(url)
        response = requests.get(url, timeout=9, headers={'User-Agent': 'Westcon-Intelligence/1.0'}, allow_redirects=False)
        response.raise_for_status()
        validate_public_url(response.url)
        if 'html' not in response.headers.get('content-type', '').lower() or len(response.content) > 2_000_000:
            return url, None
        doc = parse_document(response.text, response.url, '')
        if not doc.published_at:
            return url, None
        return url, {'published_at': doc.published_at, 'method': 'explicit-article-metadata', 'source_url': url}
    except (requests.RequestException, ValueError, ImportError):
        return url, None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=180)
    args = parser.parse_args()
    groups = urls_by_section()
    previous = json.loads(DEST.read_text(encoding='utf-8')) if DEST.exists() else {}
    dates = previous.get('dates') or {}
    eligible = set().union(*groups.values())
    missing = sorted(eligible - dates.keys())[:max(0, args.limit)]
    recovered = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        for future in as_completed([pool.submit(retrieve, url) for url in missing]):
            url, item = future.result()
            if item:
                dates[url] = item
                recovered += 1
    result = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'scope': 'Explicit publication dates only; independent of claim accreditation',
        'eligible_urls': len(eligible),
        'checked_this_run': len(missing),
        'recovered_this_run': recovered,
        'by_section': {name: {'eligible': len(urls), 'dated': len(urls & dates.keys())} for name, urls in groups.items()},
        'dates': {url: dates[url] for url in sorted(dates) if url in eligible},
    }
    DEST.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'dates'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
