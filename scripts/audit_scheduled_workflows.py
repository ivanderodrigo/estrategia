#!/usr/bin/env python3
"""Publish factual GitHub Actions schedule health, independent of data integrity.

Success means a completed scheduled run actually succeeded. A manual retry,
successful website deployment or freshly generated dataset cannot conceal a
failed scheduled run. An API error is UNKNOWN, never a fabricated success.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/public/scheduled_workflow_health.json"
REPO = "ivanderodrigo/estrategia"
SCHEDULES = {
    "research-daily.yml": ("Investigación diaria", 80),
    "research-weekly.yml": ("Investigación profunda", 120),
    "research-monthly.yml": ("Investigación mensual", 960),
    "historical-source-diligence.yml": ("Contraste de fuentes históricas", 72),
    "source-verification.yml": ("Verificación de fuentes", 72),
    "audit-live-integrity.yml": ("Integridad de publicación", 24),
    "news-publication-date-backfill.yml": ("Fechas de noticias", 240),
    "ted-cpv-revalidate.yml": ("CPV de TED", 240),
}


def classify(runs, now, maximum_age_hours, observer_run_id=None):
    scheduled = next((r for r in runs if r.get("event") == "schedule"
                      and str(r.get("id")) != observer_run_id), None)
    latest = runs[0] if runs else None
    result = {
        "status": "UNKNOWN",
        "reason": "Sin ejecuciones programadas observables",
        "scheduled_run": None,
        "latest_run": run_summary(latest),
    }
    if not scheduled:
        return result
    result["scheduled_run"] = run_summary(scheduled)
    if scheduled.get("status") != "completed":
        result.update(status="RUNNING", reason="La última ejecución programada no ha terminado")
        return result
    if scheduled.get("conclusion") != "success":
        result.update(status="FAIL", reason="Falló la última ejecución programada")
        return result
    try:
        timestamp = datetime.fromisoformat(scheduled["created_at"].replace("Z", "+00:00"))
        age_hours = (now - timestamp).total_seconds() / 3600
    except (ValueError, TypeError, KeyError):
        result.update(status="UNKNOWN", reason="Fecha de ejecución no verificable")
        return result
    if age_hours < -1:
        result.update(status="UNKNOWN", reason="Fecha de ejecución futura")
    elif age_hours > maximum_age_hours:
        result.update(status="STALE", reason="Último éxito programado demasiado antiguo")
    else:
        result.update(status="PASS", reason="Última ejecución programada satisfactoria")
    return result


def run_summary(run):
    if not run:
        return None
    return {
        "run_id": run.get("id"),
        "event": run.get("event"),
        "status": run.get("status"),
        "conclusion": run.get("conclusion"),
        "created_at": run.get("created_at"),
        "url": run.get("html_url"),
    }


def fetch_runs(workflow, token):
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{workflow}/runs?per_page=100"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "westcon-scheduled-health-audit"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    with urlopen(request, timeout=25) as response:
        return json.load(response).get("workflow_runs", [])


def evaluate(fetcher=fetch_runs, now=None, token=None):
    now = now or datetime.now(timezone.utc)
    token = token if token is not None else os.getenv("GH_TOKEN", "")

    def examine(item):
        workflow, (label, max_age) = item
        try:
            observer = os.getenv("GITHUB_RUN_ID") if workflow == "audit-live-integrity.yml" else None
            result = classify(fetcher(workflow, token), now, max_age, observer)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError) as exc:
            result = {
                "status": "UNKNOWN",
                "reason": f"No se pudo consultar GitHub Actions ({type(exc).__name__})",
                "scheduled_run": None,
                "latest_run": None,
            }
        return workflow, {"name": label, "max_age_hours": max_age, **result}

    with ThreadPoolExecutor(max_workers=4) as pool:
        entries = dict(pool.map(examine, SCHEDULES.items()))
    statuses = [v["status"] for v in entries.values()]
    overall = "FAIL" if "FAIL" in statuses else (
        "UNKNOWN" if any(s in ("UNKNOWN", "STALE", "RUNNING") for s in statuses)
        else "PASS"
    )
    return {
        "generated_at": now.isoformat(),
        "status": overall,
        "scope": "Última ejecución programada por tarea. El monitor muestra su ejecución anterior al muestreo.",
        "workflows": entries,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    result = evaluate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "workflows": {
        name: entry["status"] for name, entry in result["workflows"].items()
    }}, ensure_ascii=False))


if __name__ == "__main__":
    main()
