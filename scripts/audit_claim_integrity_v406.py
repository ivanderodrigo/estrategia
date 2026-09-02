#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "d91c11a"


def git_json(path: str):
    raw = subprocess.check_output(
        ["git", "show", f"{BASE}:{path}"],
        cwd=ROOT,
    )
    return json.loads(raw.decode("utf-8-sig"))


def cur_json(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8-sig"))


def item_pairs(data, section, field):
    out = set()
    for row in data.get(section) or []:
        name = str(row.get("name") or "")
        f = (row.get("fields") or {}).get(field) or {}
        for item in f.get("items") or []:
            if isinstance(item, dict) and item.get("value") not in (None, ""):
                out.add((
                    name,
                    json.dumps(item.get("value"), ensure_ascii=False, sort_keys=True),
                ))
    return out


def main() -> int:
    base_intel = git_json("data/current/intelligence.json")
    cur_intel = cur_json("data/current/intelligence.json")
    base_gaps = git_json("data/current/research_gaps.json")
    cur_gaps = cur_json("data/current/research_gaps.json")

    base_fit = item_pairs(base_intel, "clients_public", "westcon_fit")
    cur_fit = item_pairs(cur_intel, "clients_public", "westcon_fit")

    result = {
        "clients_public_baseline": len(base_intel.get("clients_public") or []),
        "clients_public_current": len(cur_intel.get("clients_public") or []),
        "clients_public_delta": len(cur_intel.get("clients_public") or []) - len(base_intel.get("clients_public") or []),
        "westcon_fit_baseline_pairs": len(base_fit),
        "westcon_fit_current_pairs": len(cur_fit),
        "westcon_fit_added_pairs": len(cur_fit - base_fit),
        "westcon_fit_removed_pairs": len(base_fit - cur_fit),
        "evidence_support_baseline": sum(g.get("gap_kind") == "evidence-support" for g in base_gaps.get("gaps") or []),
        "evidence_support_current": sum(g.get("gap_kind") == "evidence-support" for g in cur_gaps.get("gaps") or []),
        "derivation_support_baseline": sum(g.get("gap_kind") == "derivation-support" for g in base_gaps.get("gaps") or []),
        "derivation_support_current": sum(g.get("gap_kind") == "derivation-support" for g in cur_gaps.get("gaps") or []),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    ok = (
        result["clients_public_delta"] == 0
        and result["westcon_fit_added_pairs"] == 0
        and result["westcon_fit_removed_pairs"] == 0
    )
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
