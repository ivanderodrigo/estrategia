"""The debt breakdown is exhaustive and never changes the canonical gap total."""
import unittest
from engine.gaps import build_gaps

class DebtBreakdownTests(unittest.TestCase):
    def test_empty_and_unsupported_claims_remain_distinct(self):
        dataset = {
            "schemas": {"integrators": [{"id": "services"}, {"id": "capabilities"}]},
            "integrators": [{"id": "example", "name": "Example Integrator", "fields": {
                "services": {"value": ["Managed Security"], "items": [
                    {"value": "Managed Security", "evidence": []}
                ]}
            }}],
        }
        report = build_gaps(dataset)
        breakdown = report["debt_breakdown"]
        self.assertEqual(sum(breakdown.values()), report["total_gaps"])
        self.assertGreaterEqual(breakdown["empty_schema_fields"], 1)
        self.assertGreaterEqual(breakdown["claims_awaiting_evidence"], 1)
        self.assertEqual(report["total_gaps"], len(report["gaps"]))
        self.assertEqual(report["actionable_by_section"]["integrators"]["unverified_claims"], breakdown["claims_awaiting_evidence"])
        self.assertEqual(report["actionable_by_section"]["integrators"]["empty_fields"], breakdown["empty_schema_fields"])

if __name__ == "__main__":
    unittest.main()
