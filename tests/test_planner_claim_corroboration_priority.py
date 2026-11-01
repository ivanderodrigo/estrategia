"""Regression: prioritize verifiable existing claims over empty fields."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from engine.research.planner import plan


class ClaimPriorityTests(unittest.TestCase):
    @patch("engine.research.historical_leads.history_by_gap", return_value={})
    @patch("engine.research.historical_leads.historical_revalidation_seeds", return_value=[])
    def test_concrete_unsupported_claim_is_prioritized(self, *_):
        common = {"section": "integrators", "field": "services", "priority_score": 10,
                  "gap_kind": "evidence-support", "research_state": "Por investigar"}
        report = {"gaps": [
            {**common, "id": "blank", "entity": "Entity Empty"},
            {**common, "id": "claim", "entity": "Entity Claim", "target_values": ["Documented service"]},
        ]}
        tasks = plan(report, {}, "daily", max_tasks=2)
        self.assertEqual(tasks[0]["entity"], "Entity Claim")
        self.assertIn("Documented service", tasks[0]["target_values_by_field"]["services"])


if __name__ == "__main__":
    unittest.main()
