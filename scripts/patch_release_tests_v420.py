#!/usr/bin/env python3
"""Align only the two legitimate release assertions changed by v4.2.

The script deliberately does not touch routing/preservation assertions. Those must pass
through engine compatibility, not by weakening tests.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_contract(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one legacy assertion in {path}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> int:
    path = ROOT / "tests/test_release.py"
    replace_contract(
        path,
        'self.assertEqual(VERSION, "4.1.0")',
        'self.assertEqual(VERSION, "4.2.0")',
        "canonical version contract",
    )
    replace_contract(
        path,
        'self.assertEqual(self.gaps["engine"]["strategy_profile"], "adaptive-source-cascade")',
        'self.assertEqual(self.gaps["engine"]["strategy_profile"], "business-value-x-researchability")',
        "gap strategy contract",
    )
    print("v4.2 release-test contract alignment: PASS")
    print(" - VERSION: 4.1.0 -> 4.2.0")
    print(" - strategy_profile: adaptive-source-cascade -> business-value-x-researchability")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
