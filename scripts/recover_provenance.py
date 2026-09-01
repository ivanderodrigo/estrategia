#!/usr/bin/env python3
"""Recover lost provenance before rebuilding the public projection."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.knowledge_provenance import (  # noqa: E402
    apply_westcon_document_provenance,
    load_knowledge_baseline,
    mark_legacy_unresolved,
    provenance_summary,
    recover_historical_provenance,
    restore_protected_knowledge,
)
from engine.storage import atomic_write_json, read_json  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-commits", type=int, default=100)
    args = parser.parse_args()

    data = read_json("data/current/intelligence.json")
    baseline = load_knowledge_baseline()
    guard = restore_protected_knowledge(data, baseline)
    history = recover_historical_provenance(data, ROOT, max_commits=args.max_commits)
    documents = apply_westcon_document_provenance(data)
    legacy = mark_legacy_unresolved(data)
    report = {
        "version": "4.0.2",
        "guard": guard,
        "history": history,
        "documents": documents,
        "legacy": legacy,
        "summary": provenance_summary(data),
    }
    atomic_write_json("data/current/intelligence.json", data, pretty=False)
    atomic_write_json("data/current/provenance_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
