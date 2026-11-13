import json
import unittest
from pathlib import Path

from engine.verified_research import apply_verified_research


ROOT = Path(__file__).resolve().parents[1]


class VerifiedResearchRelease(unittest.TestCase):
    def test_vendor_sources_and_competitors_are_atomic(self):
        data = {"manufacturers": [
            {"name": "Cloudflare", "fields": {}},
            {"name": "Sonar", "fields": {}},
        ], "trends": [], "architectures": []}
        stats = apply_verified_research(data)
        self.assertGreaterEqual(stats["manufacturer_values_added"], 25)
        for row in data["manufacturers"]:
            self.assertIn("capabilities", row["fields"])
            self.assertIn("competitors", row["fields"])
            for key in ("capabilities", "competitors"):
                f = row["fields"][key]
                self.assertTrue(f["items"])
                for item in f["items"]:
                    self.assertTrue(item["evidence"])
                    self.assertEqual(item["evidence"][0]["item_value"], item["value"])
                    self.assertEqual(item["evidence"][0]["field"], key)
                    self.assertTrue(item["evidence"][0]["url"].startswith("https://"))

    def test_no_generic_analyst_source_spills_to_other_topics(self):
        data = {"manufacturers": [], "trends": [
            {"name": "Zero Trust Architecture", "fields": {}},
            {"name": "Unrelated electricity market", "fields": {}},
        ], "architectures": [
            {"name": "SASE / SSE", "fields": {}},
            {"name": "Unrelated agriculture workflow", "fields": {}},
        ]}
        stats = apply_verified_research(data)
        self.assertGreaterEqual(stats["trend_values_added"], 1)
        self.assertGreaterEqual(stats["architecture_values_added"], 1)
        self.assertIn("sources", data["trends"][0]["fields"])
        self.assertNotIn("sources", data["trends"][1]["fields"])
        self.assertIn("analyst_basis", data["architectures"][0]["fields"])
        self.assertNotIn("analyst_basis", data["architectures"][1]["fields"])

    def test_existing_vendor_claim_must_be_present_before_source_is_attached(self):
        data = {"manufacturers": [], "trends": [
            {"name": "Agentic Automation", "fields": {"market_players": {
                "value": ["UiPath", "Unrelated Vendor"],
                "items": [{"value": "UiPath", "evidence": []},
                          {"value": "Unrelated Vendor", "evidence": []}],
                "evidence": [],
            }}},
        ], "architectures": [
            {"name": "Agentic Automation", "fields": {"vendors": {
                "value": ["UiPath"],
                "items": [{"value": "UiPath", "evidence": []}],
                "evidence": [],
            }}},
            {"name": "Modern SOC / SecOps", "fields": {"vendors": {
                "value": ["Unrelated Vendor"], "items": [
                    {"value": "Unrelated Vendor", "evidence": []}],
                "evidence": [],
            }}},
        ]}
        stats = apply_verified_research(data)
        self.assertGreaterEqual(stats["existing_claims_accredited"], 2)
        trend = data["trends"][0]["fields"]["market_players"]
        architecture = data["architectures"][0]["fields"]["vendors"]
        self.assertEqual(trend["value"], ["UiPath", "Unrelated Vendor"])
        self.assertTrue(next(x for x in trend["items"] if x["value"] == "UiPath")["evidence"])
        self.assertFalse(next(x for x in trend["items"] if x["value"] == "Unrelated Vendor")["evidence"])
        self.assertEqual(architecture["items"][0]["evidence"][0]["item_value"], "UiPath")
        self.assertEqual(data["architectures"][1]["fields"]["vendors"]["value"], ["Unrelated Vendor"])

    def test_default_frontend_name_sort_is_explicit(self):
        js = (ROOT / "assets/app/intelligence.js").read_text(encoding="utf-8")
        self.assertIn("view==='manufacturers'?[...rows].sort", js)


if __name__ == "__main__":
    unittest.main()
