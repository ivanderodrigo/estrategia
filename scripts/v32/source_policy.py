from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping
from urllib.parse import urlparse


def load_json(path: str | Path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default if default is not None else {}


def registry_index(registry: Iterable[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {str(x.get("id")): dict(x) for x in registry if isinstance(x, Mapping) and x.get("id")}


def domain_index(registry: Iterable[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for src in registry:
        if not isinstance(src, Mapping):
            continue
        for domain in src.get("domains") or []:
            d = str(domain).lower().strip().lstrip("www.")
            if d:
                out[d] = dict(src)
    return out


def source_for_url(url: str, domains: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any] | None:
    try:
        host = (urlparse(url).hostname or "").lower().lstrip("www.")
    except Exception:
        return None
    if host in domains:
        return dict(domains[host])
    for domain, src in domains.items():
        if host.endswith("." + domain):
            return dict(src)
    return None


def source_tier(category: str, policy: Mapping[str, Any]) -> str:
    return str((policy.get("source_tiers") or {}).get(category, "D"))


def source_authority(source: Mapping[str, Any] | None, fallback: float = 0.58) -> float:
    if not source:
        return fallback
    try:
        return max(0.0, min(1.0, float(source.get("authority", fallback))))
    except Exception:
        return fallback


def seeded_entities(registry: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    seen = set()
    for src in registry:
        for ent in src.get("seed_entities") or []:
            if not isinstance(ent, Mapping) or not ent.get("name"):
                continue
            key = (str(ent.get("entity_type")), str(ent.get("country")), str(ent.get("name")).casefold())
            if key in seen:
                continue
            seen.add(key)
            out.append(dict(ent))
    return out
