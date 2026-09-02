from __future__ import annotations

import unittest
from pathlib import Path

from engine.research.planner import plan

ROOT = Path(__file__).resolve().parents[1]


class ResearchRoutingV406(unittest.TestCase):
    def test_derivation_support_never_enters_web_plan(self) -> None:
        gaps = {
            "gaps": [
                {
                    "id": "external-1",
                    "section": "manufacturers",
                    "entity": "1Password",
                    "entity_id": "1password",
                    "field": "competitors",
                    "gap_kind": "evidence-support",
                    "priority": 1,
                    "target_values": ["Keeper"],
                    "revalidation_seeds": [],
                },
                {
                    "id": "derived-1",
                    "section": "clients_public",
                    "entity": "Cliente X",
                    "entity_id": "cliente-x",
                    "field": "westcon_fit",
                    "gap_kind": "derivation-support",
                    "priority": 1,
                    "target_values": ["Networking"],
                    "revalidation_seeds": [],
                },
            ]
        }
        tasks = plan(gaps, {}, "daily", max_tasks=50)
        self.assertTrue(tasks)
        self.assertTrue(
            any("evidence-support" in set(t.get("gap_kinds") or []) for t in tasks)
        )
        self.assertFalse(
            any("derivation-support" in set(t.get("gap_kinds") or []) for t in tasks)
        )
        self.assertFalse(
            any("westcon_fit" in set(t.get("fields") or []) for t in tasks)
        )

    def test_web_engine_has_defensive_derivation_guard(self) -> None:
        text = (ROOT / "engine/research/web_intelligence.py").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn(
            '"derivation-support" in set(target.get("gap_kinds") or [])',
            text,
        )
        self.assertIn("continue", text)


if __name__ == "__main__":
    unittest.main()
