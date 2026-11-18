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
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

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
MONTHS = {name: month for month, names in enumerate((
    ('january', 'enero', 'janeiro'), ('february', 'febrero', 'fevereiro'),
    ('march', 'marzo', 'março', 'marco'), ('april', 'abril'),
    ('may', 'mayo', 'maio'), ('june', 'junio', 'junho'),
    ('july', 'julio', 'julho'), ('august', 'agosto'),
    ('september', 'septiembre', 'setembro'), ('october', 'octubre', 'outubro'),
    ('november', 'noviembre', 'novembro'), ('december', 'diciembre', 'dezembro'),
), 1) for name in names}


def visible_publication_date(raw: str, text: str) -> str:
    """Use a labelled article byline or press-release dateline, never generic dates."""
    candidates = []
    # <time> in article headers has a strong relation to the article itself.
    for match in re.finditer(r'<time\b([^>]{0,450})>', raw[:80_000], re.I):
        attributes = match.group(1)
        if not re.search(r'(?:published|pubdate|fecha|publicad|post.date)', attributes, re.I):
            continue
        stamp = re.search(r'datetime\s*=\s*["\'](\d{4}-\d{2}-\d{2})', attributes, re.I)
        if stamp:
            candidates.append(stamp.group(1))
    # The leading article text may explicitly identify when it was published.
    # Avoid unrelated dates in recommendations, footers and body paragraphs.
    opening = text[:1500]
    label = r'(?:published\s*(?:on|:)?|publicad[oa]\s*(?:el|em|:)?|fecha\s+de\s+publicaci[oó]n\s*:?)'
    numeric = r'\d{4}-\d{2}-\d{2}'
    for match in re.finditer(label + r'\s*(' + numeric + r')', opening, re.I):
        candidates.append(match.group(1))
    months = '|'.join(re.escape(m) for m in MONTHS)
    human = re.compile(r'(\d{1,2})\s*(?:de\s+)?(' + months + r')\s*(?:de\s+|,?\s*)(20\d{2})', re.I)
    for match in human.finditer(opening):
        before = opening[max(0, match.start()-85):match.start()]
        # Press-release datelines have city/country followed by an em dash;
        # other dates need an explicit publishing label close to the date.
        if not (re.search(label, before, re.I) or re.search(r'[A-Z][A-Za-z .,-]{3,35}[–—-]\s*$', before)):
            continue
        try:
            parsed = date(int(match.group(3)), MONTHS[match.group(2).casefold()], int(match.group(1)))
            candidates.append(parsed.isoformat())
        except ValueError:
            continue
    valid = set()
    for candidate in candidates:
        try:
            parsed = date.fromisoformat(candidate)
        except ValueError:
            continue
        if date(1990, 1, 1) <= parsed <= date.today() + timedelta(days=1):
            valid.add(parsed.isoformat())
    return next(iter(valid)) if len(valid) == 1 else ''


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


def retrieve(url: str) -> tuple[str, dict | None, str]:
    try:
        # Article URLs are collected exclusively from the site's curated evidence
        # registry, never arbitrary external input or untrusted redirect targets.
        from engine.research.security import validate_public_url
        validate_public_url(url)
        current = url
        for _ in range(4):
            response = requests.get(current, timeout=9, headers={'User-Agent': 'Westcon-Intelligence/1.0'}, allow_redirects=False)
            if response.status_code not in (301, 302, 303, 307, 308):
                break
            location = response.headers.get('location')
            if not location:
                return url, None, 'REDIRECT_WITHOUT_LOCATION'
            current = validate_public_url(urljoin(current, location))
        else:
            return url, None, 'REDIRECT_LIMIT'
        response.raise_for_status()
        validate_public_url(response.url)
        if 'html' not in response.headers.get('content-type', '').lower() or len(response.content) > 2_000_000:
            return url, None, 'NOT_HTML'
        doc = parse_document(response.text, response.url, '')
        publication = doc.published_at or visible_publication_date(response.text, doc.text)
        if not publication:
            return url, None, 'NO_EXPLICIT_PUBLICATION_DATE'
        method = 'explicit-article-metadata' if doc.published_at else 'explicit-article-byline'
        return url, {'published_at': publication, 'method': method, 'source_url': url}, 'VERIFIED'
    except requests.HTTPError as exc:
        return url, None, 'HTTP_' + str(exc.response.status_code if exc.response is not None else 'ERROR')
    except (requests.RequestException, ValueError, ImportError) as exc:
        return url, None, type(exc).__name__.upper()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=180)
    args = parser.parse_args()
    groups = urls_by_section()
    previous = json.loads(DEST.read_text(encoding='utf-8')) if DEST.exists() else {}
    dates = previous.get('dates') or {}
    reviews = previous.get('reviews') or {}
    eligible = set().union(*groups.values())
    missing = sorted(eligible - dates.keys())[:max(0, args.limit)]
    recovered = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        for future in as_completed([pool.submit(retrieve, url) for url in missing]):
            url, item, status = future.result()
            reviews[url] = {'status': status, 'checked_at': datetime.now(timezone.utc).isoformat()}
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
        'reviews': {url: reviews.get(url, {'status': 'NOT_YET_REVIEWED'}) for url in sorted(eligible)},
    }
    DEST.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'dates'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
