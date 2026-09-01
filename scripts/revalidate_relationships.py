#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.relationship_revalidation import revalidate_registry


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Revalida relaciones H contra fuentes abiertas actuales."
    )
    parser.add_argument("--max-runtime", type=int, default=300)
    parser.add_argument("--max-items", type=int, default=None)
    args = parser.parse_args()

    result = revalidate_registry(args.max_runtime, args.max_items)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
