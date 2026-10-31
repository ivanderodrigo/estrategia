"""Discovery-only public web search for research targets.

Search engines are used only to discover candidate URLs. A search result never
accredits a claim: discovered pages still pass URL safety, entity/subject
binding, semantic extraction, typed provenance and atomic evidence promotion.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from typing import Iterable
from collections import Counter
from urllib.parse import parse_qs, unquote, urlparse

import requests

from .security import UnsafeUrl, validate_public_url
from .sources import SourceSeed, family_from_url

BING_RSS = "https://www.bing.com/search"
DUCKDUCKGO_HTML = "https://html.duckduckgo.com/html/"

SEARCH_HOSTS = {
    "bing.com", "www.bing.com",
    "duckduckgo.com", "www.duckduckgo.com", "html.duckduckgo.com",
}
IGNORED_RESULT_HOSTS = {
    "facebook.com", "www.facebook.com", "instagram.com", "www.instagram.com",
    "linkedin.com", "www.linkedin.com", "x.com", "www.x.com", "twitter.com",
    "www.twitter.com", "youtube.com", "www.youtube.com",
}


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "a":
            return
        href = next((value for key, value in attrs if key.casefold() == "href" and value), None)
        if href:
            self.hrefs.append(href)


def _unwrap_duckduckgo(raw: str) -> str:
    if raw.startswith("//"):
        raw = "https:" + raw
    parsed = urlparse(raw)
    if "duckduckgo.com" not in (parsed.hostname or "").casefold():
        return raw
    query = parse_qs(parsed.query)
    wrapped = (query.get("uddg") or [""])[0]
    return unquote(wrapped) if wrapped else ""


def _safe_result_url(raw: str) -> str:
    raw = _unwrap_duckduckgo(str(raw or "").strip())
    if not raw.startswith(("http://", "https://")):
        return ""
    try:
        url = validate_public_url(raw)
    except UnsafeUrl:
        return ""
    host = (urlparse(url).hostname or "").casefold()
    if not host or host in SEARCH_HOSTS or host in IGNORED_RESULT_HOSTS:
        return ""
    return url


def _parse_bing_rss(raw: str) -> list[str]:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []
    output: list[str] = []
    for item in root.findall(".//item"):
        link = item.findtext("link") or ""
        safe = _safe_result_url(link)
        if safe:
            output.append(safe)
    return output


def _parse_duckduckgo_html(raw: str) -> list[str]:
    parser = _LinkParser()
    try:
        parser.feed(raw)
    except Exception:
        return []
    output: list[str] = []
    for href in parser.hrefs:
        safe = _safe_result_url(href)
        if safe:
            output.append(safe)
    return output


def _unique(values: Iterable[str], limit: int) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.casefold().rstrip("/")
        if not value or key in seen:
            continue
        seen.add(key)
        output.append(value)
        if len(output) >= limit:
            break
    return output


def _search_provider(
    session: requests.Session,
    provider: str,
    query: str,
    *,
    timeout_s: float,
    result_limit: int,
) -> list[str]:
    timeout = (min(4.0, timeout_s), timeout_s)
    if provider == "bing_rss":
        response = session.get(
            BING_RSS,
            params={"q": query, "format": "rss", "count": result_limit},
            timeout=timeout,
        )
        response.raise_for_status()
        return _unique(_parse_bing_rss(response.text), result_limit)
    if provider == "duckduckgo_html":
        response = session.get(
            DUCKDUCKGO_HTML,
            params={"q": query, "kl": "es-es"},
            timeout=timeout,
        )
        response.raise_for_status()
        return _unique(_parse_duckduckgo_html(response.text), result_limit)
    return []


def discover(
    session: requests.Session,
    queries: Iterable[str],
    *,
    fallback_family: str,
    providers: Iterable[str],
    timeout_s: float,
    max_queries: int,
    results_per_query: int,
) -> tuple[list[SourceSeed], dict[str, int]]:
    """Return safe candidate URLs plus diagnostics.

    Results are deliberately grade C/discovery-only. The caller may upgrade a
    result to official only after proving that the result host belongs to the
    researched entity.
    """
    diagnostics = {
        "queries_attempted": 0,
        "queries_succeeded": 0,
        "provider_failures": 0,
        "urls_discovered": 0,
    }
    output: list[SourceSeed] = []
    seen: set[tuple[str, str]] = set()
    hosts_seen: Counter[str] = Counter()
    diagnostics["duplicate_urls_skipped"] = 0
    diagnostics["host_saturation_skipped"] = 0
    diagnostics["empty_result_queries"] = 0

    clean_queries = _unique((str(value).strip() for value in queries), max(0, max_queries))
    for query in clean_queries:
        if not query:
            continue
        for provider in providers:
            provider = str(provider or "").strip()
            if not provider:
                continue
            diagnostics["queries_attempted"] += 1
            try:
                urls = _search_provider(
                    session,
                    provider,
                    query,
                    timeout_s=max(2.0, timeout_s),
                    result_limit=max(1, results_per_query),
                )
                diagnostics["queries_succeeded"] += 1
            except (requests.RequestException, ValueError, UnicodeError):
                diagnostics["provider_failures"] += 1
                continue
            for url in urls:
                inferred_family = family_from_url(url, fallback=fallback_family)
                # Preserve the query intent for generic home/news URLs; explicit
                # partner/service/case/technology paths may still refine it.
                family = (
                    fallback_family
                    if inferred_family in {"official", "news", "signals"}
                    else inferred_family
                )
                key = (url.casefold().rstrip("/"), family)
                if key in seen:
                    diagnostics["duplicate_urls_skipped"] += 1
                    continue
                host = (urlparse(url).hostname or "").casefold()
                # Search ranking can otherwise flood each target with one
                # domain's generic pages and waste the bounded crawl budget.
                if hosts_seen[host] >= 2:
                    diagnostics["host_saturation_skipped"] += 1
                    continue
                seen.add(key)
                hosts_seen[host] += 1
                output.append(SourceSeed(
                    url=url,
                    family=family,
                    official=False,
                    source_grade="C",
                    source_type=f"search-discovery:{provider}",
                    source_name=f"Descubrimiento web · {provider}",
                ))
            # One provider with results is enough for this query; fall through to
            # the next provider only when the first one found nothing.
            if urls:
                break
        else:
            diagnostics["empty_result_queries"] += 1

    diagnostics["urls_discovered"] = len(output)
    return output, diagnostics
