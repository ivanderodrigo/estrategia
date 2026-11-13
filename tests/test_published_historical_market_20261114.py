import unittest
from pathlib import Path
import json
from scripts.audit_published_historical_market import check, OUTPUT

class PublishedHistoricalClaimTests(unittest.TestCase):
    def test_85_curated_competitors_have_item_bound_source_in_published_data(self):
        check()
        result=json.loads(OUTPUT.read_text(encoding="utf-8"))
        self.assertEqual(result["missing_in_public_json"],0)
        self.assertGreaterEqual(result["confirmed_in_public_json"],85)

if __name__=="__main__":
    unittest.main()
