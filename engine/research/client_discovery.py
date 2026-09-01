"""Conservative official-site discovery for client entities.

Wikidata is used only as a directory to find P856. It is never published as evidence.
"""
from __future__ import annotations

import re
from typing import Any

import requests

from ..model import canonical
from .security import UnsafeUrl, validate_public_url
from .sources import SourceSeed

WIKIDATA_API = "https://www.wikidata.org/w/api.php"


def _tokens(value: str) -> set[str]:
    stop = {
        "sa", "s", "sl", "plc", "ltd", "limited", "group", "grupo", "holding",
        "sociedad", "companhia", "company", "corporation", "corp", "the", "de", "da", "do",
    }
    return {token for token in re.findall(r"[a-z0-9]+", canonical(value)) if len(token) >= 2 and token not in stop}


def _name_match_score(expected: str, candidate: str) -> float:
    left, right = _tokens(expected), _tokens(candidate)
    if not left or not right:
        return 0.0
    if canonical(expected) == canonical(candidate):
        return 1.0
    return len(left & right) / max(1, min(len(left), len(right)))


def _search_entities(session: requests.Session, entity: str, timeout_s: float) -> list[dict[str, Any]]:
    response = session.get(
        WIKIDATA_API,
        params={
            "action": "wbsearchentities", "search": entity, "language": "en", "uselang": "en",
            "format": "json", "limit": 5, "type": "item",
        },
        timeout=(min(4.0, timeout_s), timeout_s),
    )
    response.raise_for_status()
    return [item for item in response.json().get("search") or [] if isinstance(item, dict)]


def _official_url(session: requests.Session, qid: str, timeout_s: float) -> str | None:
    response = session.get(
        WIKIDATA_API,
        params={"action": "wbgetentities", "ids": qid, "props": "claims", "format": "json"},
        timeout=(min(4.0, timeout_s), timeout_s),
    )
    response.raise_for_status()
    entity = ((response.json().get("entities") or {}).get(qid) or {})
    for claim in ((entity.get("claims") or {}).get("P856") or []):
        try:
            value = claim["mainsnak"]["datavalue"]["value"]
        except (KeyError, TypeError):
            continue
        if not isinstance(value, str):
            continue
        try:
            return validate_public_url(value)
        except UnsafeUrl:
            continue
    return None


def discover_official_site(session: requests.Session, entity: str, timeout_s: float = 8.0) -> SourceSeed | None:
    try:
        candidates = _search_entities(session, entity, timeout_s)
        ranked = sorted(
            ((_name_match_score(entity, str(item.get("label") or "")), item) for item in candidates),
            key=lambda pair: pair[0], reverse=True,
        )
        for score, item in ranked:
            if score < 0.72:
                continue
            qid = str(item.get("id") or "")
            if not qid.startswith("Q"):
                continue
            url = _official_url(session, qid, timeout_s)
            if url:
                return SourceSeed(url, "official", True, "A", "official-domain-discovery", entity)
    except (requests.RequestException, ValueError, TypeError):
        return None
    return None
