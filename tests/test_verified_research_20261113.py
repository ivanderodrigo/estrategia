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

    def test_default_frontend_name_sort_is_explicit(self):
        js = (ROOT / "assets/app/intelligence.js").read_text(encoding="utf-8")
        self.assertIn("view==='manufacturers'?[...rows].sort", js)


if __name__ == "__main__":
    unittest.main()
