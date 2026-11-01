"""Debt-aware TED expansion must not create more unsupported gaps unchecked."""
from __future__ import annotations

import ast
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DebtAwareGrowthTests(unittest.TestCase):
    def test_policy_and_research_module(self):
        policy = json.loads((ROOT / "config/current/research_policy.json").read_text(encoding="utf-8"))
        self.assertTrue(policy["debt_aware_growth"]["enabled"])
        self.assertGreater(policy["debt_aware_growth"]["pause_above_gaps"], 0)
        source = (ROOT / "engine/research/web_intelligence.py").read_text(encoding="utf-8")
        ast.parse(source)
        self.assertIn('stats["structured_growth_paused_for_debt"] = True', source)
        self.assertIn('if structured_growth_budget else []', source)
        self.assertIn('if backlog >= ceiling:', source)


if __name__ == "__main__":
    unittest.main()
