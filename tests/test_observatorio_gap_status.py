"""Research-debt classifications remain transparent and non-destructive."""
import unittest
from engine.gap_status import classify_gap, annotate_public_states


class GapStatusTest(unittest.TestCase):
    def test_unsearched_and_searched_are_distinct(self):
        self.assertEqual(classify_gap({"gap_kind": "standard"})[0], "not-researched")
        self.assertEqual(classify_gap({"gap_kind": "standard", "attempts_completed": 3})[0], "not-found")
        self.assertEqual(classify_gap({"gap_kind": "standard", "attempts_completed": 3, "accepted_evidences": 1})[0], "insufficient-support")

    def test_historical_and_derived_are_not_web_unknowns(self):
        self.assertEqual(classify_gap({"gap_kind": "public-validation"})[0], "historical-validation")
        self.assertEqual(classify_gap({"gap_kind": "derivation-support"})[0], "derivation-pending")

    def test_classification_does_not_change_research_state_or_priority(self):
        gaps = [
            {"section": "manufacturers", "research_state": "Por investigar", "priority": 1},
            {"section": "manufacturers", "research_state": "Pendiente de validación pública", "gap_kind": "public-validation", "priority": 2},
        ]
        summary = annotate_public_states(gaps)
        self.assertEqual(summary["total"], 2)
        self.assertEqual(sum(summary["by_status"].values()), 2)
        self.assertEqual([gap["priority"] for gap in gaps], [1, 2])
        self.assertEqual(gaps[0]["research_state"], "Por investigar")
        self.assertEqual(gaps[1]["research_state"], "Pendiente de validación pública")


if __name__ == "__main__":
    unittest.main()
