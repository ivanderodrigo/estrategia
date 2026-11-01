"""Regression checks for actionable corroboration and diagnostic transparency."""
import unittest
from unittest.mock import patch
from pathlib import Path
from engine.research.planner import plan

class ResearchImprovementTests(unittest.TestCase):
    @patch("engine.research.historical_leads.history_by_gap")
    @patch("engine.research.historical_leads.historical_revalidation_seeds", return_value=[])
    def test_historical_claim_beats_equivalent_unsupported_claim(self, seeds, history):
        history.return_value = {"historic": {"status": "HISTORICAL_RESEARCH_LEAD_NOT_VERIFIED"}}
        base = {"section": "integrators", "field": "services", "gap_kind": "evidence-support",
                "priority_score": 10, "target_values": ["Cloud services"]}
        report = {"gaps": [
            {**base, "id": "ordinary", "entity": "Integrator Ordinary"},
            {**base, "id": "historic", "entity": "Integrator Historic"},
        ]}
        result = plan(report, {}, "daily", max_tasks=2)
        self.assertEqual(result[0]["entity"], "Integrator Historic")

    def test_supervisor_records_funnel_without_changing_evidence_rules(self):
        src = (Path(__file__).resolve().parents[1] / "scripts/research_supervisor.py").read_text(encoding="utf-8")
        for name in ("search_queries_attempted", "search_urls_discovered",
                     "candidate_values_seen", "candidate_values_rejected",
                     "candidate_fields_rejected", "structured_growth_paused_for_debt"):
            self.assertIn('"' + name + '": result.get(', src)

if __name__ == "__main__":
    unittest.main()
