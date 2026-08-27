#!/usr/bin/env python3
"""Deterministic tests for timezone-aware GitHub scheduling."""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import tempfile
from zoneinfo import ZoneInfo

from configure_updates import cron_candidates
import schedule_guard as guard


def main() -> None:
    daily = {"enabled": True, "time": "06:23"}
    deep = {"enabled": True, "weekday": 6, "time": "04:47"}
    monthly = {"enabled": True, "day": 1, "time": "03:17"}
    assert cron_candidates("daily", daily, "Europe/Madrid") == ["23 4 * * *", "23 5 * * *"]
    assert cron_candidates("deep", deep, "Europe/Madrid") == ["47 2 * * 0", "47 3 * * 0"]
    assert cron_candidates("exhaustive", monthly, "Europe/Madrid") == ["17 1 1 * *", "17 2 1 * *"]

    now = dt.datetime(2026, 7, 12, 2, 55, tzinfo=dt.timezone.utc)
    scheduled = guard.scheduled_moment(now, "47 2 * * 0", 180)
    assert scheduled and guard.cron_match(scheduled, "47 2 * * 0")
    local = scheduled.astimezone(ZoneInfo("Europe/Madrid"))
    assert guard.profile_due("deep", deep, local)
    wrong_now = dt.datetime(2026, 7, 12, 3, 55, tzinfo=dt.timezone.utc)
    wrong = guard.scheduled_moment(wrong_now, "47 3 * * 0", 180)
    assert wrong and not guard.profile_due("deep", deep, wrong.astimezone(ZoneInfo("Europe/Madrid")))

    winter = dt.datetime(2026, 1, 18, 3, 47, tzinfo=dt.timezone.utc).astimezone(ZoneInfo("Europe/Madrid"))
    assert guard.profile_due("deep", deep, winter)
    with tempfile.TemporaryDirectory() as tmp:
        guard.STATUS = pathlib.Path(tmp) / "status.json"
        guard.STATUS.write_text(json.dumps({"profile":"deep","outcome":"partial-recoverable","generatedAt":"2026-07-12T01:55:00Z"}),encoding="utf-8")
        assert guard.recent_success("deep", now, 120)
    print("OK · zona horaria · horario verano/invierno · guardia anti-duplicado")


if __name__ == "__main__":
    main()
