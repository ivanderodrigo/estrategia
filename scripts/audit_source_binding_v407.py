#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.research.web_intelligence import _seed_binding


def main() -> int:
    data = json.loads(
        (ROOT / "data/current/intelligence.json").read_text(
            encoding="utf-8-sig"
        )
    )
    counts = Counter()
    suspicious = []

    for row in data.get("source_catalog") or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "")
        url = str(row.get("url") or "")
        source_type = str(row.get("class") or row.get("source_type") or "")
        if not url.startswith(("http://", "https://")):
            continue

        binding = _seed_binding(
            url,
            name,
            source_type=source_type,
            source_name=name,
        )
        counts[binding] += 1

        if binding == "discovery-only" and name:
            suspicious.append({
                "name": name,
                "host": urlparse(url).netloc,
                "class": source_type,
                "url": url,
            })

    result = {
        "catalog_rows": sum(counts.values()),
        "binding_counts_if_name_were_subject": dict(counts),
        "discovery_only_examples": suspicious[:25],
        "policy": (
            "Catalog is preserved. Runtime research only promotes entity-owned "
            "or relationship-source seeds for entity claims; discovery-only "
            "entries cannot directly close evidence-support."
        ),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
