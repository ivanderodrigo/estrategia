"""Backfill exact technology demand from already-verified TED procedure titles.

No Internet request, AI inference or new buyer/vendor relationship is made.
The process is idempotent and preserves all historical claims and empty fields.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone

from engine.research.ted_title_signals import recover_verified_title_signals
from engine.storage import atomic_write_json, read_json


def backfill(data: dict, *, checked_date: str) -> dict:
    totals: Counter[str] = Counter()
    for row in data.get("clients_public") or []:
        if not isinstance(row, dict):
            continue
        accredited = recover_verified_title_signals(row, checked_date=checked_date)
        if accredited:
            totals["buyers_with_new_atomic_claims"] += 1
            totals.update(accredited)
    totals["new_atomic_claims"] = sum(
        totals.get(field_id, 0)
        for field_id in ("technology_signals", "technology_domains", "identified_vendors")
    )
    return dict(totals)


def main() -> None:
    prior = read_json("data/current/research_gaps.json", {})
    before = int(prior.get("total_gaps") or len(prior.get("gaps") or []))
    data = read_json("data/current/intelligence.json", {})
    checked_date = datetime.now(timezone.utc).date().isoformat()
    stats = backfill(data, checked_date=checked_date)
    if stats.get("new_atomic_claims"):
        atomic_write_json("data/current/intelligence.json", data)
        from engine.pipeline import run as rebuild
        rebuild()
    after_report = read_json("data/current/research_gaps.json", {})
    after = int(after_report.get("total_gaps") or len(after_report.get("gaps") or []))
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "offline, literal, item-bound extraction from independently verified TED API titles",
        "gaps_before": before,
        "gaps_after": after,
        "gaps_closed_net": before - after,
        "scope": "mentioned public-procurement demand, not installed technology or contracts won",
        **stats,
    }
    atomic_write_json("data/current/ted_title_backfill.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
