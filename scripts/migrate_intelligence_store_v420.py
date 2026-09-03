#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from engine.intelligence_store import audit_store, migrate_legacy


def main() -> int:
    report = migrate_legacy(root=Path("."))
    audit = audit_store(root=Path("."))
    print("v4.2 intelligence-store migration:", audit["status"])
    print(" - migrated legacy monolith:", report.get("migrated"))
    print(" - compatibility stub bytes:", audit.get("stub_bytes"))
    print(" - shards:", audit.get("shards"))
    print(" - largest shard bytes:", audit.get("largest_shard_bytes"))
    print(" - logical dataset bytes:", audit.get("logical_bytes"))
    if audit.get("errors"):
        for error in audit["errors"]:
            print(" - ERROR:", error)
    Path("data/current/intelligence_storage_report.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0 if audit.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
