#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from v36.pipeline import run
from v36.validate_v36 import validate

PROFILE_MAP = {"daily": "daily", "weekly": "weekly", "deep": "weekly", "monthly": "monthly", "exhaustive": "monthly"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Westcon Iberia Business Intelligence v3.6 supervisor")
    parser.add_argument("--profile", default="daily", choices=sorted(PROFILE_MAP))
    parser.add_argument("--max-runtime", type=int, default=720)
    parser.add_argument("--fallback-runtime", type=int, default=0)
    parser.add_argument("--skip-v33", action="store_true", help="Reutiliza la última investigación base y reconstruye solo la capa descriptiva v3.6")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    canonical = PROFILE_MAP[args.profile]
    foundation_rc = 0
    if not args.skip_v33:
        reserve = max(60, min(210, int(args.max_runtime * 0.20)))
        foundation_runtime = max(90, args.max_runtime - reserve)
        print(f"v3.6 foundation · investigación {canonical} hasta {foundation_runtime}s", flush=True)
        try:
            process = subprocess.run(
                [sys.executable, str(ROOT / "scripts/research_supervisor_v33.py"), "--profile", canonical, "--max-runtime", str(foundation_runtime)],
                cwd=ROOT,
                timeout=foundation_runtime + 60,
            )
            foundation_rc = process.returncode
        except subprocess.TimeoutExpired:
            foundation_rc = 124
        if foundation_rc:
            print("v3.6 warning · la investigación base no terminó correctamente; se conserva la última evidencia válida y continúa la publicación descriptiva", flush=True)

    print("v3.6 · reconstruyendo inteligencia trazable de fabricantes, integradores, mayoristas, tendencias y arquitecturas", flush=True)
    result = run(ROOT, canonical, foundation_rc=foundation_rc)
    errors = validate(ROOT)
    if errors:
        print("v3.6 validation failed · " + "; ".join(errors[:16]), file=sys.stderr, flush=True)
        return 1
    print(
        f"v3.6.0 published · fabricantes {result['manufacturers']} · integradores {result['integrators']} · "
        f"mayoristas {result['distributors']} · tendencias {result['trends']} · arquitecturas {result['architectures']} · "
        f"fuentes {result['source_count']} · campos trazables {result['traceable_fields']} · foundation rc {foundation_rc}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
