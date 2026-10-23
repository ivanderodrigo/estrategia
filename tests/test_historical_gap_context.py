"""Historical lead matching never promotes old evidence to current truth."""
import json
import tempfile
import unittest
from pathlib import Path
from engine.historical_gap_context import enrich_from_history

class HistoricalGapBridge(unittest.TestCase):
    def test_matches_exact_entity_field_only_and_preserves_state(self):
        data={"candidate_count":2,"candidates":[
            {"section":"integrators","entity":"Example Partner","field":"services","value":"{\"value\": \"Support\"}","urls":["https://example.org/archive"],"first_revision":"abc","last_revision":"def","status":"HISTORICAL_CANDIDATE_NOT_REVALIDATED"},
            {"section":"integrators","entity":"Other Partner","field":"services","value":"{\"value\": \"Other\"}","urls":[],"status":"HISTORICAL_CANDIDATE_NOT_REVALIDATED"},
        ]}
        gaps=[{"section":"integrators","entity":"Example Partner","field":"services","research_state":"Por investigar","priority":1,"revalidation_seeds":[]},
              {"section":"integrators","entity":"Example Partner","field":"specializations","research_state":"Por investigar"}]
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"index.json"
            path.write_text(json.dumps(data),encoding="utf-8")
            metrics=enrich_from_history(gaps,path)
        self.assertEqual(metrics["matched_gaps"],1)
        self.assertEqual(len(gaps[0]["historical_research_leads"]),1)
        self.assertEqual(gaps[0]["research_state"],"Por investigar")
        self.assertEqual(gaps[0]["priority"],1)
        self.assertEqual(gaps[0]["revalidation_seeds"][0]["url"],"https://example.org/archive")
        self.assertFalse(gaps[0]["revalidation_seeds"][0]["official"])
        self.assertNotIn("historical_research_leads",gaps[1])
        self.assertEqual(gaps[0]["historical_research_leads"][0]["review_status"],"HISTORICAL_ONLY_NOT_CURRENTLY_ACCREDITED")

    def test_fails_closed_on_incomplete_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"index.json"
            path.write_text('{"candidate_count":3,"candidates":[]}',encoding="utf-8")
            with self.assertRaises(ValueError):
                enrich_from_history([],path)

if __name__=="__main__":
    unittest.main()
