#!/usr/bin/env python3
"""Build/apply the v4.0.3 historical archive provenance registry."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.archive_provenance import (  # noqa: E402
    apply_archive_provenance,
    archive_registry_summary,
    build_archive_registry,
)
from engine.knowledge_provenance import provenance_summary  # noqa: E402
from engine.storage import atomic_write_json, read_json  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconstruye procedencia desde Westcon Iberia Business Intelligence históricos sin importar valores antiguos")
    parser.add_argument("--archives-dir", default=str(ROOT.parent), help="Directorio con ZIPs/PPTX históricos; solo se procesa la familia Westcon Iberia Business Intelligence")
    parser.add_argument("--min-archives", type=int, default=5, help="Mínimo razonable de ZIPs detectados")
    parser.add_argument("--no-reports", action="store_true", help="No usar PPTX como corroboración contextual")
    args = parser.parse_args()

    archives_dir = Path(args.archives_dir).resolve()
    data = read_json("data/current/intelligence.json")
    aliases = read_json("config/current/entity_aliases.json", {})
    before = provenance_summary(data)

    registry, lineage = build_archive_registry(
        data,
        archives_dir,
        alias_config=aliases,
        include_reports=not args.no_reports,
    )
    found = int((registry.get("stats") or {}).get("archives_found") or 0)
    if found < args.min_archives:
        raise SystemExit(
            f"ERROR: solo se detectaron {found} ZIPs históricos en {archives_dir}. "
            "Usa --archives-dir para señalar la carpeta donde guardaste las versiones antiguas."
        )

    apply_stats = apply_archive_provenance(data, registry)
    after = provenance_summary(data)
    report = {
        "version": "4.0.3",
        "archives_dir_name": archives_dir.name,
        "scan": registry.get("stats") or {},
        "archives": registry.get("archives") or [],
        "registry": archive_registry_summary(registry),
        "apply": apply_stats,
        "provenance_before": before,
        "provenance_after": after,
        "legacy_unresolved_delta": (
            int(after.get("legacy_unresolved_fields") or 0) + int(after.get("legacy_unresolved_items") or 0)
            - int(before.get("legacy_unresolved_fields") or 0) - int(before.get("legacy_unresolved_items") or 0)
        ),
    }

    atomic_write_json("config/current/archive_provenance_registry.json", registry)
    atomic_write_json("data/current/provenance_lineage.json", lineage)
    atomic_write_json("data/current/archive_provenance_report.json", report)
    atomic_write_json("data/current/intelligence.json", data, pretty=False)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
