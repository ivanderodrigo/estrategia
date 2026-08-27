#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from v34.validate_v34 import validate


def main() -> int:
    errors = validate(ROOT)
    if errors:
        print("VALIDACIÓN v3.4.0 · FAIL")
        for error in errors:
            print(f"ERROR · {error}")
        return 1
    audit = json.loads((ROOT / "data/v34/recommendation_audit.json").read_text(encoding="utf-8"))
    quality = json.loads((ROOT / "data/v34/quality_report.json").read_text(encoding="utf-8"))
    metrics = json.loads((ROOT / "data/v34/metrics_before_after.json").read_text(encoding="utf-8"))
    after = metrics.get("after") or {}
    print(
        "VALIDACIÓN v3.4.0 · PASS · "
        f"recommendations {after.get('published_recommendations')} · "
        f"recommendation audit {audit.get('status')} · quality {quality.get('status')} · "
        f"quality errors {quality.get('summary', {}).get('errors', 0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
