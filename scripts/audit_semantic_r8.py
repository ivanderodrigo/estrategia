#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "d91c11a"


def git_json(path: str):
    raw = subprocess.check_output(["git", "show", f"{BASE}:{path}"], cwd=ROOT)
    return json.loads(raw.decode("utf-8-sig"))


def cur_json(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8-sig"))


def gkey(g):
    return (
        str(g.get("gap_kind") or ""),
        str(g.get("section") or ""),
        str(g.get("entity_id") or ""),
        str(g.get("entity") or ""),
        str(g.get("field") or ""),
        str(g.get("target_level") or ""),
        json.dumps(
            g.get("target_values") or [],
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        ),
    )


def evidence_for(data, section, entity, field, values):
    result = []
    for row in data.get(section) or []:
        if str(row.get("name") or "") != str(entity):
            continue
        f = (row.get("fields") or {}).get(field) or {}
        for item in f.get("items") or []:
            if not isinstance(item, dict) or item.get("value") not in values:
                continue
            result.append({
                "value": item.get("value"),
                "evidence": [
                    {
                        "source": e.get("source"),
                        "url": e.get("url"),
                        "source_binding": e.get("source_binding"),
                        "description": e.get("description"),
                    }
                    for e in item.get("evidence") or []
                    if isinstance(e, dict) and e.get("url")
                ],
            })
    return result


def main() -> int:
    bg = git_json("data/current/research_gaps.json")
    cg = cur_json("data/current/research_gaps.json")
    ci = cur_json("data/current/intelligence.json")

    bm = {gkey(g): g for g in bg.get("gaps") or []}
    cm = {gkey(g): g for g in cg.get("gaps") or []}
    removed = [bm[k] for k in set(bm) - set(cm)]
    closed = [g for g in removed if g.get("gap_kind") == "evidence-support"]

    details = []
    for g in closed:
        details.append({
            "section": g.get("section"),
            "entity": g.get("entity"),
            "field": g.get("field"),
            "target_values": g.get("target_values"),
            "current_evidence": evidence_for(
                ci,
                str(g.get("section") or ""),
                str(g.get("entity") or ""),
                str(g.get("field") or ""),
                set(g.get("target_values") or []),
            ),
        })

    result = {
        "evidence_support_before": sum(
            g.get("gap_kind") == "evidence-support"
            for g in bg.get("gaps") or []
        ),
        "evidence_support_after": sum(
            g.get("gap_kind") == "evidence-support"
            for g in cg.get("gaps") or []
        ),
        "derivation_support_before": sum(
            g.get("gap_kind") == "derivation-support"
            for g in bg.get("gaps") or []
        ),
        "derivation_support_after": sum(
            g.get("gap_kind") == "derivation-support"
            for g in cg.get("gaps") or []
        ),
        "closed_claims": details,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
