from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List


def load_registry(path: str | Path) -> List[Dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("sources", [])
    return [x for x in data if isinstance(x, dict) and x.get("id")]


def select_sources(registry: Iterable[Dict[str, Any]], *, country: str | None = None, entity_type: str | None = None, dimension: str | None = None):
    out = []
    for src in registry:
        countries = set(src.get("countries") or ["GLOBAL"])
        entity_types = set(src.get("entity_types") or ["all"])
        dimensions = set(src.get("dimensions") or ["all"])
        if country and country not in countries and "GLOBAL" not in countries and "IBERIA" not in countries:
            continue
        if entity_type and entity_type not in entity_types and "all" not in entity_types:
            continue
        if dimension and dimension not in dimensions and "all" not in dimensions:
            continue
        out.append(src)
    return out
