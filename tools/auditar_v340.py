#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from v34.pipeline import run
from v34.validate_v34 import validate


def main() -> int:
    result = run(ROOT, "audit")
    errors = validate(ROOT)
    recommendation = json.loads((ROOT / "data/v34/recommendation_audit.json").read_text(encoding="utf-8"))
    quality = json.loads((ROOT / "data/v34/quality_report.json").read_text(encoding="utf-8"))
    print("AUDITORÍA WESTCON IBERIA v3.4.0")
    print(f"Resultado pipeline: {result.get('status')}")
    print(f"Recomendaciones: {recommendation.get('summary', {}).get('published_recommendations')} · errores {recommendation.get('summary', {}).get('errors')} · warnings {recommendation.get('summary', {}).get('warnings')}")
    print(f"Calidad: {quality.get('status')} · checks {quality.get('summary', {}).get('checks')} · errores {quality.get('summary', {}).get('errors')} · warnings {quality.get('summary', {}).get('warnings')}")
    for warning in quality.get("warnings", []):
        print(f"AVISO · {warning.get('check')} · {warning.get('detail')}")
    for error in errors:
        print(f"ERROR · {error}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
