#!/usr/bin/env python3
"""Run the untouched legacy canonical validator against a temporary compatibility view.

HF8+ introduced a second legitimate open-gap state: ``Pendiente de validación pública``.
The v4.1.0 validator predates that distinction and only accepts ``Por investigar``.
This bridge NEVER changes the persisted canonical model: it projects public-validation
states to the legacy label only for the duration of scripts/validate.py, restores the
real file in ``finally``, and validates the richer HF8+ contract separately.
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
GAPS_PATH = ROOT / "data/current/research_gaps.json"


def compatibility_projection(report: Mapping[str, Any]) -> dict[str, Any]:
    projected = copy.deepcopy(dict(report))
    for gap in projected.get("gaps") or []:
        if not isinstance(gap, dict):
            continue
        if gap.get("gap_kind") == "public-validation" and gap.get("research_state") == "Pendiente de validación pública":
            gap["research_state"] = "Por investigar"
    states: dict[str, int] = {}
    for gap in projected.get("gaps") or []:
        if isinstance(gap, Mapping):
            state = str(gap.get("research_state") or "")
            states[state] = states.get(state, 0) + 1
    if isinstance(projected.get("research_states"), Mapping):
        projected["research_states"] = states
    return projected


def _load() -> dict[str, Any]:
    return json.loads(GAPS_PATH.read_text(encoding="utf-8"))


def _write(payload: Mapping[str, Any]) -> None:
    GAPS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run() -> int:
    if not GAPS_PATH.is_file():
        print(f"HF11 legacy validation bridge: FAIL - missing {GAPS_PATH}")
        return 1

    original_bytes = GAPS_PATH.read_bytes()
    report = json.loads(original_bytes.decode("utf-8"))

    # Validate the REAL richer model before giving the old validator a compatibility view.
    from engine.gaps import validate_gap_state_contract
    contract_errors = validate_gap_state_contract(report)
    if contract_errors:
        print("HF11 real gap-state contract: FAIL")
        for error in contract_errors:
            print(" -", error)
        return 1

    public_validation = sum(
        1 for gap in report.get("gaps") or []
        if isinstance(gap, Mapping) and gap.get("gap_kind") == "public-validation"
    )
    unknown = sum(
        1 for gap in report.get("gaps") or []
        if isinstance(gap, Mapping) and gap.get("research_state") == "Por investigar"
    )

    projected = compatibility_projection(report)
    try:
        _write(projected)
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts/validate.py")],
            cwd=str(ROOT),
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        rc = int(proc.returncode)
    finally:
        GAPS_PATH.write_bytes(original_bytes)

    # Prove byte-for-byte restoration and revalidate the real file after legacy validation.
    if GAPS_PATH.read_bytes() != original_bytes:
        print("HF11 legacy validation bridge: FAIL - canonical research_gaps.json was not restored byte-for-byte")
        return 1
    restored = _load()
    restored_errors = validate_gap_state_contract(restored)
    if restored_errors:
        print("HF11 restored gap-state contract: FAIL")
        for error in restored_errors:
            print(" -", error)
        return 1
    if rc != 0:
        print("HF11 legacy validation bridge: FAIL")
        return rc

    print("HF11 legacy validation bridge: PASS")
    print(f" - real public-validation gaps preserved: {public_validation}")
    print(f" - real unknown-research gaps preserved: {unknown}")
    print(" - compatibility projection persisted: no")
    print(" - canonical research_gaps.json restored byte-for-byte: yes")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
