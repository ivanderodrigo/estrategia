#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from v34.pipeline import run
from v34.validate_v34 import validate


PROFILE_MAP = {"daily": "daily", "weekly": "weekly", "deep": "weekly", "monthly": "monthly", "exhaustive": "monthly"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Westcon Iberia Decision Intelligence v3.4 supervisor")
    parser.add_argument("--profile", default="daily", choices=sorted(PROFILE_MAP))
    parser.add_argument("--max-runtime", type=int, default=720)
    parser.add_argument("--fallback-runtime", type=int, default=0)
    parser.add_argument("--skip-v33", action="store_true", help="Reutiliza datasets v3.1-v3.3 existentes y ejecuta solo la capa offline v3.4")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    canonical = PROFILE_MAP[args.profile]
    foundation_rc = 0
    if not args.skip_v33:
        v34_reserve = max(45, min(180, int(args.max_runtime * 0.16)))
        foundation_runtime = max(90, args.max_runtime - v34_reserve)
        print(f"v3.4 foundation · v3.3.3a {canonical} hasta {foundation_runtime}s", flush=True)
        try:
            process = subprocess.run(
                [sys.executable, str(ROOT / "scripts/research_supervisor_v33.py"), "--profile", canonical, "--max-runtime", str(foundation_runtime)],
                cwd=ROOT, timeout=foundation_runtime + 60,
            )
            foundation_rc = process.returncode
        except subprocess.TimeoutExpired:
            foundation_rc = 124
        if foundation_rc:
            print("v3.4 warning · la investigación foundation falló o agotó tiempo; se conserva el último dataset válido y continúa la capa de decisión", flush=True)
    print("v3.4 business + technology decision intelligence · hechos/interpretación/riesgo separados", flush=True)
    result = run(ROOT, canonical)
    errors = validate(ROOT)
    if errors:
        print("v3.4 validation failed · " + "; ".join(errors[:12]), file=sys.stderr, flush=True)
        return 1
    distribution = result.get("action_distribution") or {}
    print(
        f"v3.4.0 published · entities {result.get('entities')} · relationships {result.get('relationships')} · "
        f"recommendations {result.get('recommendations')} [ACTUAR {distribution.get('ACTUAR', 0)} / VALIDAR {distribution.get('PREPARAR / VALIDAR', 0)} / "
        f"INVESTIGAR {distribution.get('INVESTIGAR', 0)} / VIGILAR {distribution.get('VIGILAR', 0)}] · "
        f"architectures {result.get('architectures')} · quality {result.get('quality_status')} · recommendation audit {result.get('recommendation_audit_status')} · "
        f"foundation rc {foundation_rc}", flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
