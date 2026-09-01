"""Persistent learning state for gaps and source health."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from ..settings import VERSION


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ResearchState:
    def __init__(self, raw: dict[str, Any] | None = None):
        self.raw = raw or {}
        self.raw["version"] = VERSION
        self.raw.setdefault("gaps", {})
        self.raw.setdefault("domains", {})

    def gap(self, gap_id: str) -> dict[str, Any]:
        return self.raw["gaps"].setdefault(
            gap_id,
            {"attempts": 0, "accepted": 0, "consecutive_no_yield": 0, "next_pass": 1},
        )

    def gap_due(self, gap_id: str, *, profile: str) -> bool:
        if profile == "exhaustive":
            return True
        due = str(self.gap(gap_id).get("next_due_at") or "")
        return not due or due <= now_iso()

    def record_gap(self, gap_id: str, *, accepted: int, error: str = "") -> None:
        item = self.gap(gap_id)
        item["attempts"] = int(item.get("attempts") or 0) + 1
        item["accepted"] = int(item.get("accepted") or 0) + max(0, accepted)
        item["last_attempt_at"] = now_iso()
        item["last_error"] = error[:240]
        if accepted:
            item["consecutive_no_yield"] = 0
            delay_days = 1
        else:
            misses = int(item.get("consecutive_no_yield") or 0) + 1
            item["consecutive_no_yield"] = misses
            delay_days = min(30, 2 ** min(4, misses))
        item["next_pass"] = 1 + (int(item.get("next_pass") or 1) % 48)
        item["next_due_at"] = (datetime.now(timezone.utc) + timedelta(days=delay_days)).isoformat()

    def domain_available(self, url: str) -> bool:
        host = urlparse(url).netloc.casefold()
        item = self.raw["domains"].get(host) or {}
        return str(item.get("circuit_until") or "") <= now_iso()

    def record_domain(self, url: str, *, ok: bool, relevant: bool = False, accepted: int = 0, status: int = 0) -> None:
        host = urlparse(url).netloc.casefold()
        if not host:
            return
        item = self.raw["domains"].setdefault(host, {"attempts": 0, "successes": 0, "failures": 0, "accepted": 0})
        item["attempts"] += 1
        item["last_status"] = status
        item["last_attempt_at"] = now_iso()
        if ok:
            item["successes"] += 1
            item["failures"] = 0
            item["last_success_at"] = now_iso()
            item["relevant_pages"] = int(item.get("relevant_pages") or 0) + int(relevant)
            item["accepted"] = int(item.get("accepted") or 0) + max(0, accepted)
            item.pop("circuit_until", None)
        else:
            failures = int(item.get("failures") or 0) + 1
            item["failures"] = failures
            if failures >= 5:
                hours = min(72, 2 ** min(6, failures - 4))
                item["circuit_until"] = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()

    def export(self, active_gap_ids: set[str] | None = None) -> dict[str, Any]:
        if active_gap_ids is not None:
            gaps = self.raw.get("gaps") or {}
            # Keep resolved history for 90 days only would need date parsing; a hard cap keeps the file bounded.
            if len(gaps) > 8_000:
                active = {key: value for key, value in gaps.items() if key in active_gap_ids}
                historical = sorted(
                    ((key, value) for key, value in gaps.items() if key not in active_gap_ids),
                    key=lambda item: str(item[1].get("last_attempt_at") or ""),
                    reverse=True,
                )[:2_000]
                self.raw["gaps"] = active | dict(historical)
        self.raw["version"] = VERSION
        self.raw["updated_at"] = now_iso()
        return self.raw
