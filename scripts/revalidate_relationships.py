#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from engine.relationship_revalidation import revalidate_registry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-runtime", type=int, default=300)
    parser.add_argument("--max-items", type=int, default=None)
    args = parser.parse_args()
    result = revalidate_registry(args.max_runtime, args.max_items)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
