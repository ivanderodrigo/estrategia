from __future__ import annotations
import json
from pathlib import Path
from typing import List

REQUIRED=["events.json","knowledge_graph.json","decisions.json","briefing.json","source_health.json","research_priorities.json","source_coverage.json","source_learning.json"]


def validate(root:str|Path)->List[str]:
    root=Path(root);d=root/"data/v32";errors=[]
    for name in REQUIRED:
        p=d/name
        if not p.exists():errors.append(f"missing data/v32/{name}");continue
        try:json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:errors.append(f"invalid {name}: {exc}")
    p=d/"events.json"
    if p.exists():
        try:
            events=json.loads(p.read_text(encoding="utf-8")).get("events",[])
            for e in events:
                if e.get("event_type")=="ma_acquisition" and any(x in str(e.get("title") or "").casefold() for x in ["recomendación de compra","recommendation de compra","buy rating","price target"]):errors.append("stock buy-rating misclassified as M&A")
                if e.get("event_type")=="procurement_award" and e.get("market_scope")=="OTHER_REGION" and float(e.get("westcon_relevance") or 0)>.5:errors.append("other-region procurement has excessive Westcon relevance")
        except Exception as exc:errors.append(f"event validation failed: {exc}")
    return errors
