"""Regression: historical analyst pages can support exact competitor claims only."""
import unittest
from engine.verified_research import apply_verified_research


class HistoricalCompetitorAccreditationTest(unittest.TestCase):
    def test_exact_competitor_gets_claim_specific_evidence(self):
        data = {"manufacturers": [
            {"name": "AttackIQ", "fields": {"competitors": {
                "value": ["Cymulate", "Picus Security", "Unrelated Vendor"],
                "items": [{"value": x, "evidence": []} for x in
                          ["Cymulate", "Picus Security", "Unrelated Vendor"]],
                "evidence": []}}},
            {"name": "EfficientIP", "fields": {"competitors": {
                "value": ["BlueCat", "Micetro"],
                "items": [{"value": x, "evidence": []} for x in ["BlueCat", "Micetro"]],
                "evidence": []}}}
        ]}
        apply_verified_research(data)
        attack = data["manufacturers"][0]["fields"]["competitors"]
        vals = {item["value"]: item for item in attack["items"]}
        self.assertTrue(vals["Cymulate"].get("evidence"))
        self.assertTrue(vals["Picus Security"].get("evidence"))
        self.assertFalse(vals["Unrelated Vendor"].get("evidence"))
        efficient = data["manufacturers"][1]["fields"]["competitors"]
        vals = {item["value"]: item for item in efficient["items"]}
        self.assertTrue(vals["BlueCat"].get("evidence"))
        self.assertTrue(vals["Micetro"].get("evidence"))


if __name__ == "__main__":
    unittest.main()
