#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from engine.pipeline import run as build
from engine.research.web_intelligence import run as research
from engine.storage import read_json
from engine.relationship_revalidation import revalidate_registry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("daily", "deep", "exhaustive"), default="deep")
    parser.add_argument("--max-runtime", type=int, default=900)
    parser.add_argument("--max-tasks", type=int, default=None)
    args = parser.parse_args()

    print("1/3 build: generando gaps H de revalidación")
    build()
    before = read_json("data/current/source_rationalization_v405.json", {})
    print(json.dumps({
        "historical_total": before.get("historical_total"),
        "historical_search_required": before.get("historical_search_required"),
    }, ensure_ascii=False))

    print("2/3 research: búsqueda abierta dirigida")
    result = research(args.profile, args.max_runtime, args.max_tasks)
    print(json.dumps(result, ensure_ascii=False))

    print("2b/3 relations: revalidando relaciones H derivadas")
    relationship_revalidation = revalidate_registry(max(60, args.max_runtime // 3), args.max_tasks)
    print(json.dumps(relationship_revalidation, ensure_ascii=False))

    print("3/3 build: recalculando procedencia")
    build()
    after = read_json("data/current/source_rationalization_v405.json", {})
    print(json.dumps({
        "historical_total": after.get("historical_total"),
        "historical_supported_current_open": after.get("historical_supported_current_open"),
        "historical_search_required": after.get("historical_search_required"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
