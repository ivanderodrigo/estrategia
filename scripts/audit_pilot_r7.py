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
        json.dumps(g.get("target_values") or [], ensure_ascii=False, sort_keys=True, default=str),
    )


def item_pairs(data, section, field):
    out = set()
    for row in data.get(section) or []:
        entity = str(row.get("name") or "")
        f = (row.get("fields") or {}).get(field) or {}
        for item in f.get("items") or []:
            if isinstance(item, dict) and item.get("value") not in (None, ""):
                out.add((
                    entity,
                    json.dumps(item.get("value"), ensure_ascii=False, sort_keys=True),
                ))
    return out


def evidence_for(data, section, entity, field, values):
    rows = [
        r for r in data.get(section) or []
        if str(r.get("name") or "") == str(entity)
    ]
    result = []
    for row in rows:
        f = (row.get("fields") or {}).get(field) or {}
        for item in f.get("items") or []:
            if not isinstance(item, dict):
                continue
            if item.get("value") not in values:
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
                    if isinstance(e, dict)
                ],
            })
    return result


def main() -> int:
    b_gaps = git_json("data/current/research_gaps.json")
    c_gaps = cur_json("data/current/research_gaps.json")
    b_intel = git_json("data/current/intelligence.json")
    c_intel = cur_json("data/current/intelligence.json")

    bm = {gkey(g): g for g in b_gaps.get("gaps") or []}
    cm = {gkey(g): g for g in c_gaps.get("gaps") or []}
    removed = [bm[k] for k in set(bm) - set(cm)]
    added = [cm[k] for k in set(cm) - set(bm)]

    closed = [g for g in removed if g.get("gap_kind") == "evidence-support"]
    new_external = [g for g in added if g.get("gap_kind") == "evidence-support"]

    bfit = item_pairs(b_intel, "clients_public", "westcon_fit")
    cfit = item_pairs(c_intel, "clients_public", "westcon_fit")

    closed_detail = []
    for g in closed:
        closed_detail.append({
            "section": g.get("section"),
            "entity": g.get("entity"),
            "field": g.get("field"),
            "target_values": g.get("target_values"),
            "current_evidence": evidence_for(
                c_intel,
                str(g.get("section") or ""),
                str(g.get("entity") or ""),
                str(g.get("field") or ""),
                set(g.get("target_values") or []),
            ),
        })

    result = {
        "clients_public_growth": (
            len(c_intel.get("clients_public") or [])
            - len(b_intel.get("clients_public") or [])
        ),
        "westcon_fit_added": len(cfit - bfit),
        "westcon_fit_removed": len(bfit - cfit),
        "evidence_support_closed": len(closed),
        "evidence_support_new": len(new_external),
        "derivation_support_before": sum(
            g.get("gap_kind") == "derivation-support"
            for g in b_gaps.get("gaps") or []
        ),
        "derivation_support_after": sum(
            g.get("gap_kind") == "derivation-support"
            for g in c_gaps.get("gaps") or []
        ),
        "closed_claims": closed_detail,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

    ok = (
        result["clients_public_growth"] == 0
        and result["westcon_fit_added"] == 0
        and result["westcon_fit_removed"] == 0
        and result["evidence_support_new"] == 0
        and result["derivation_support_before"] == result["derivation_support_after"]
    )
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
