#!/usr/bin/env python3
"""Configure local update times and regenerate GitHub Actions UTC schedules.

Examples
--------
python scripts/configure_updates.py --show
python scripts/configure_updates.py --timezone Europe/Madrid --daily 06:23 \
  --weekly SUN@04:47 --monthly 1@03:17
python scripts/configure_updates.py --weekly off
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/update_schedule.json"
WORKFLOWS = {
    "daily": ROOT / ".github/workflows/research-daily.yml",
    "deep": ROOT / ".github/workflows/research-weekly.yml",
    "exhaustive": ROOT / ".github/workflows/research-monthly.yml",
}
WEEKDAYS = {"MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4, "SAT": 5, "SUN": 6}
WEEKDAY_NAMES = {value: key for key, value in WEEKDAYS.items()}
BEGIN = "    # BEGIN CONFIGURABLE_SCHEDULE"
END = "    # END CONFIGURABLE_SCHEDULE"


def parse_time(value: str) -> str:
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value or ""):
        raise ValueError(f"Hora inválida: {value!r}; use HH:MM")
    return value


def local_datetime(year: int, month: int, day: int, time_value: str, zone: ZoneInfo) -> dt.datetime:
    hour, minute = map(int, parse_time(time_value).split(":"))
    return dt.datetime(year, month, day, hour, minute, tzinfo=zone)


def matching_weekday(year: int, month: int, weekday: int) -> int:
    day = 8
    while dt.date(year, month, day).weekday() != weekday:
        day += 1
    return day


def cron_candidates(profile: str, settings: dict, timezone_name: str) -> list[str]:
    if not settings.get("enabled", True):
        return []
    zone = ZoneInfo(timezone_name)
    refs: list[dt.datetime] = []
    if profile == "daily":
        refs = [local_datetime(2026, month, 15, settings["time"], zone) for month in (1, 7)]
    elif profile == "deep":
        weekday = int(settings["weekday"])
        refs = [local_datetime(2026, month, matching_weekday(2026, month, weekday), settings["time"], zone) for month in (1, 7)]
    else:
        day = int(settings["day"])
        refs = [local_datetime(2026, month, day, settings["time"], zone) for month in (1, 7)]

    crons = set()
    for local in refs:
        utc = local.astimezone(dt.timezone.utc)
        if profile == "daily":
            cron = f"{utc.minute} {utc.hour} * * *"
        elif profile == "deep":
            github_weekday = (utc.weekday() + 1) % 7
            cron = f"{utc.minute} {utc.hour} * * {github_weekday}"
        else:
            if utc.day != local.day:
                raise ValueError(
                    "La hora mensual cruza de día al convertirla a UTC. "
                    "Elija otra hora local para evitar ejecuciones ambiguas."
                )
            cron = f"{utc.minute} {utc.hour} {utc.day} * *"
        crons.add(cron)
    return sorted(crons, key=lambda value: tuple(int(x) if x.isdigit() else 99 for x in value.split()))


def rewrite_workflow(path: pathlib.Path, crons: list[str]) -> str:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.S)
    if not pattern.search(text):
        raise ValueError(f"Faltan marcadores de calendario en {path.relative_to(ROOT)}")
    lines = [BEGIN]
    if crons:
        lines.extend(f'    - cron: "{cron}"' for cron in crons)
    else:
        lines.append('    # Perfil desactivado: schedule_guard impide su ejecución programada.')
        lines.append('    - cron: "17 4 1 1 *"')
    lines.append(END)
    return pattern.sub("\n".join(lines), text)


def describe(config: dict) -> str:
    p = config["profiles"]
    daily = "off" if not p["daily"].get("enabled") else p["daily"]["time"]
    weekly = "off" if not p["deep"].get("enabled") else f'{WEEKDAY_NAMES[int(p["deep"]["weekday"])]}@{p["deep"]["time"]}'
    monthly = "off" if not p["exhaustive"].get("enabled") else f'{p["exhaustive"]["day"]}@{p["exhaustive"]["time"]}'
    return f"Zona: {config['timezone']} · diaria: {daily} · semanal: {weekly} · mensual: {monthly}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Configura actualizaciones automáticas sin editar YAML a mano.")
    parser.add_argument("--timezone", help="Zona IANA, por ejemplo Europe/Madrid o Europe/Lisbon")
    parser.add_argument("--daily", help="HH:MM u off")
    parser.add_argument("--weekly", help="MON@HH:MM ... SUN@HH:MM, u off")
    parser.add_argument("--monthly", help="DIA@HH:MM (1-28), u off")
    parser.add_argument("--max-delay", type=int, help="Retraso máximo aceptado de GitHub Actions, 30-720 minutos")
    parser.add_argument("--show", action="store_true", help="Muestra la configuración efectiva sin cambiar archivos")
    args = parser.parse_args()

    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    if args.timezone:
        try:
            ZoneInfo(args.timezone)
        except ZoneInfoNotFoundError as exc:
            raise SystemExit(f"Zona horaria IANA desconocida: {args.timezone}") from exc
        config["timezone"] = args.timezone
    if args.max_delay is not None:
        if not 30 <= args.max_delay <= 720:
            raise SystemExit("--max-delay debe estar entre 30 y 720 minutos")
        config["maxScheduleDelayMinutes"] = args.max_delay

    if args.daily:
        config["profiles"]["daily"]["enabled"] = args.daily.lower() != "off"
        if args.daily.lower() != "off":
            config["profiles"]["daily"]["time"] = parse_time(args.daily)
    if args.weekly:
        config["profiles"]["deep"]["enabled"] = args.weekly.lower() != "off"
        if args.weekly.lower() != "off":
            match = re.fullmatch(r"(MON|TUE|WED|THU|FRI|SAT|SUN)@(.+)", args.weekly.upper())
            if not match:
                raise SystemExit("--weekly debe ser DAY@HH:MM, por ejemplo SUN@04:47")
            config["profiles"]["deep"]["weekday"] = WEEKDAYS[match.group(1)]
            config["profiles"]["deep"]["time"] = parse_time(match.group(2))
    if args.monthly:
        config["profiles"]["exhaustive"]["enabled"] = args.monthly.lower() != "off"
        if args.monthly.lower() != "off":
            match = re.fullmatch(r"(\d{1,2})@(.+)", args.monthly)
            if not match or not 1 <= int(match.group(1)) <= 28:
                raise SystemExit("--monthly debe ser DIA@HH:MM con día 1-28")
            config["profiles"]["exhaustive"]["day"] = int(match.group(1))
            config["profiles"]["exhaustive"]["time"] = parse_time(match.group(2))

    rendered = {
        profile: rewrite_workflow(WORKFLOWS[profile], cron_candidates(profile, settings, config["timezone"]))
        for profile, settings in config["profiles"].items()
    }
    if args.show:
        print(describe(config))
        for profile, settings in config["profiles"].items():
            print(f"{profile}: {', '.join(cron_candidates(profile, settings, config['timezone'])) or 'off'}")
        return

    CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for profile, text in rendered.items():
        WORKFLOWS[profile].write_text(text, encoding="utf-8")
    print("OK · " + describe(config))


if __name__ == "__main__":
    main()
