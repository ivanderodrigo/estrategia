"""Bounded gap detail report to prioritize research, without weakening evidence policy."""
from __future__ import annotations

import json
from collections import Counter, defaultdict

from engine.storage import read_json

def main() -> None:
    data = read_json("data/current/research_gaps.json", {})
    rows = data.get("gaps") or []
    for section in ("trends", "architectures"):
        selected = [g for g in rows if g.get("section") == section]
        by_name: dict[str, list[dict]] = defaultdict(list)
        for gap in selected:
            by_name[str(gap.get("entity") or "")].append(gap)
        print("RESEARCH TARGETS", section, "total", len(selected), "rows", len(by_name))
        for entity, gaps in sorted(by_name.items(), key=lambda x: (-len(x[1]), x[0]))[:32]:
            counter = Counter(str(g.get("field") or "") for g in gaps)
            unsourced = [g for g in gaps if g.get("gap_kind") not in ("derivation-support",)]
            detail = {
                "name":entity,"gaps":len(gaps),
                "fields":counter.most_common(12),
                "examples":[{
                    "field":str(g.get("field") or ""),
                    "gap_kind":str(g.get("gap_kind") or ""),
                    "status":str(g.get("research_state") or ""),
                    "target":str(g.get("target_values") or g.get("reason") or "")[:160]
                } for g in unsourced[:4]]
            }
            print(json.dumps(detail,ensure_ascii=False))
if __name__ == "__main__":
    main()
