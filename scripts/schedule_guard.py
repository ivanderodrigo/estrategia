#!/usr/bin/env python3
"""Decide whether a scheduled workflow is due in the configured local timezone."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/update_schedule.json"
STATUS = ROOT / "data/research_status.json"


def parse_iso(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


def cron_match(moment: dt.datetime, expression: str) -> bool:
    fields = expression.split()
    if len(fields) != 5:
        return False
    minute, hour, dom, _month, dow = fields
    github_dow = (moment.weekday() + 1) % 7
    return (
        (minute == "*" or int(minute) == moment.minute)
        and (hour == "*" or int(hour) == moment.hour)
        and (dom == "*" or int(dom) == moment.day)
        and (dow == "*" or int(dow) == github_dow)
    )


def scheduled_moment(now_utc: dt.datetime, expression: str, max_delay: int) -> dt.datetime | None:
    rounded = now_utc.astimezone(dt.timezone.utc).replace(second=0, microsecond=0)
    for minutes_ago in range(max_delay + 1):
        candidate = rounded - dt.timedelta(minutes=minutes_ago)
        if cron_match(candidate, expression):
            return candidate
    return None


def profile_due(profile: str, settings: dict, local_scheduled: dt.datetime) -> bool:
    expected_hour, expected_minute = map(int, settings["time"].split(":"))
    if (local_scheduled.hour, local_scheduled.minute) != (expected_hour, expected_minute):
        return False
    if profile == "deep" and local_scheduled.weekday() != int(settings["weekday"]):
        return False
    if profile == "exhaustive" and local_scheduled.day != int(settings["day"]):
        return False
    return True


def recent_success(profile: str, now_utc: dt.datetime, minimum_hours: int) -> bool:
    try:
        status = json.loads(STATUS.read_text(encoding="utf-8"))
        if status.get("profile") != profile or status.get("outcome") not in {"complete", "partial-recoverable"}:
            return False
        generated = parse_iso(status["generatedAt"]).astimezone(dt.timezone.utc)
        return dt.timedelta(0) <= now_utc - generated < dt.timedelta(hours=minimum_hours)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return False


def emit(run: bool, reason: str) -> None:
    line = f"run={'true' if run else 'false'}\nreason={reason}\n"
    output = os.getenv("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(line)
    print(line, end="")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, choices=["daily", "deep", "exhaustive"])
    parser.add_argument("--now", help="ISO timestamp used by deterministic tests")
    parser.add_argument("--schedule-expression", help="GitHub cron expression; normally supplied by the workflow")
    args = parser.parse_args()

    event = os.getenv("GITHUB_EVENT_NAME", "manual-local")
    if event in {"workflow_dispatch", "manual-local"} and not args.schedule_expression:
        emit(True, "manual")
        return

    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    settings = config["profiles"][args.profile]
    if not settings.get("enabled", True):
        emit(False, "disabled")
        return
    now_utc = parse_iso(args.now).astimezone(dt.timezone.utc) if args.now else dt.datetime.now(dt.timezone.utc)
    expression = args.schedule_expression or os.getenv("SCHEDULE_EXPRESSION", "")
    scheduled = scheduled_moment(now_utc, expression, int(config.get("maxScheduleDelayMinutes", 180)))
    if not scheduled:
        emit(False, "cron-not-found-in-delay-window")
        return
    local = scheduled.astimezone(ZoneInfo(config["timezone"]))
    if not profile_due(args.profile, settings, local):
        emit(False, "inactive-dst-candidate")
        return
    if recent_success(args.profile, now_utc, int(settings.get("minimumIntervalHours", 0))):
        emit(False, "already-updated")
        return
    emit(True, f"due-{local.isoformat()}")


if __name__ == "__main__":
    main()
