"""Link open research tasks to dated historical leads, without asserting current validity."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping
from .model import canonical
from .settings import ROOT

INDEX = ROOT / "data/public/historical/candidate_index.json"

def enrich_from_history(gaps: list[dict[str, Any]], index_path: Path = INDEX) -> dict[str, int]:
    if not index_path.is_file():
        return {"index_available": 0, "matched_gaps": 0, "historical_leads": 0}
    data = json.loads(index_path.read_text(encoding="utf-8"))
    entries = data.get("candidates") or []
    if len(entries) != int(data.get("candidate_count", -1)):
        raise ValueError("Historical candidate index truncated")
    lookup: dict[tuple[str,str,str],list[Mapping[str,Any]]] = defaultdict(list)
    for item in entries:
        if not isinstance(item,Mapping) or item.get("status") != "HISTORICAL_CANDIDATE_NOT_REVALIDATED":
            continue
        key = (str(item.get("section") or ""),canonical(item.get("entity") or ""),str(item.get("field") or ""))
        if not all(key):continue
        lookup[key].append(item)
    matched = 0;total = 0
    for gap in gaps:
        key = (str(gap.get("section") or ""), canonical(gap.get("entity") or ""),str(gap.get("field") or ""))
        possible = lookup.get(key, [])
        if not possible:continue
        matched += 1
        leads=[]
        for item in possible[:8]:
            leads.append({
                "historical_value":str(item.get("value") or "")[:500],
                "first_revision":str(item.get("first_revision") or ""),
                "last_revision":str(item.get("last_revision") or ""),
                "source_urls":[u for u in item.get("urls") or [] if isinstance(u,str) and u.startswith(("https://","http://"))][:3],
                "review_status":"HISTORICAL_ONLY_NOT_CURRENTLY_ACCREDITED",
            })
        total += len(leads)
        gap["historical_research_leads"] = leads
        gap["historical_lookup_status"] = "prior-evidence-to-review"
        # Research state, scoring, accepted values and quality gates remain untouched.
    return {"index_available":1,"matched_gaps":matched,"historical_leads":total}
