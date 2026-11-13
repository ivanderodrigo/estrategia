import json
import unittest
from pathlib import Path
from unittest.mock import patch

from engine.historical_publication import publish_historical_trails
from engine.research.historical_leads import build_identity_index

ROOT = Path(__file__).resolve().parents[1]


class HistoricalPublicationTests(unittest.TestCase):
    def _data(self):
        old = [{
            "gap_id": "old-id", "section": "architectures",
            "entity": "Zero Trust", "field": "vendors",
            "match_level": "exact-value-history",
            "identity_scope": "canonical-name",
            "source_urls": ["https://unrelated.example.org/other"],
            "historical_samples": [{
                "value": json.dumps("Okta"),
                "first_revision": "oldsha",
                "last_revision": "newsha",
                "source_urls": ["https://www.okta.com/products/"]
            }]
        }]
        gaps = {"gaps": [{
            "id": "changed-id", "section": "architectures",
            "entity": "Zero Trust", "field": "vendors",
            "target_values": ["Okta"], "gap_kind": "evidence-support",
        }, {
            "id": "unrelated-id", "section": "architectures",
            "entity": "Zero Trust", "field": "principles",
            "target_values": ["Okta"], "gap_kind": "evidence-support",
        }]}
        return old, gaps

    def test_exports_exact_historical_url_but_not_unrelated_url(self):
        old, gaps = self._data()
        with patch("engine.historical_publication.history_by_gap", return_value={}):
            with patch("engine.historical_publication.history_by_identity",
                       return_value=build_identity_index(old)):
                files, summary = publish_historical_trails(gaps, "2026-11-13T16:00:00Z")
        arch = json.loads(files["data/public/historical/current/architectures.json"])
        self.assertEqual(arch["status"], "HISTORICAL_LEADS_NOT_ACCREDITED")
        self.assertEqual(summary["claims"], 1)
        self.assertEqual(summary["unique_urls"], 1)
        claims = arch["entities"]["zero trust"]["vendors"]
        self.assertEqual(claims[0]["value"], "Okta")
        self.assertEqual(claims[0]["urls"], ["https://www.okta.com/products/"])
        self.assertNotIn("principles", arch["entities"]["zero trust"])
        self.assertNotIn("https://unrelated.example.org/other", str(arch))
        self.assertEqual(len(files), 8)

    def test_does_not_export_derived_claim_or_source_for_wrong_value(self):
        old, gaps = self._data()
        gaps["gaps"][0]["target_values"] = ["Zscaler"]
        gaps["gaps"][1]["gap_kind"] = "derivation-support"
        with patch("engine.historical_publication.history_by_gap", return_value={}):
            with patch("engine.historical_publication.history_by_identity",
                       return_value=build_identity_index(old)):
                files, summary = publish_historical_trails(gaps, "2026-11-13T16:00:00Z")
        self.assertEqual(summary["claims"], 0)
        self.assertEqual(summary["unique_urls"], 0)
        self.assertEqual(json.loads(files["data/public/historical/current/architectures.json"])["entities"], {})

    def test_frontend_displays_explicit_not_accredited_history_label(self):
        js=(ROOT / "assets/app/intelligence.js").read_text(encoding="utf-8")
        self.assertIn("historicalTrail(view,row,col.id)", js)
        self.assertIn("No acreditado hoy.", js)
        self.assertIn("HISTORICAL_LEADS_NOT_ACCREDITED", js)
        self.assertIn("historicalTrail(context===\'trend\'?\'trends\':\'architectures\',row,c.id)", js)


if __name__ == "__main__":
    unittest.main()
