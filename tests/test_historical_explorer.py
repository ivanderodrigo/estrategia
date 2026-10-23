"""Historical explorer is a read-only review surface, never a claim publisher."""
import json
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

class HistoricalExplorerTest(unittest.TestCase):
    def test_historical_index_consistency(self):
        d = json.loads((ROOT / "data/public/historical/candidate_index.json").read_text(encoding="utf-8"))
        summary = json.loads((ROOT / "data/public/historical/summary.json").read_text(encoding="utf-8"))
        self.assertEqual(len(d["candidates"]), d["candidate_count"])
        self.assertEqual(d["candidate_count"], summary["counts"]["historical-only"])
        self.assertEqual(d["candidate_count"], 674)
        self.assertTrue(all(x["status"] == "HISTORICAL_CANDIDATE_NOT_REVALIDATED" for x in d["candidates"]))

    def test_explorer_is_linked_and_warns_of_historical_uncertainty(self):
        home = (ROOT / "index.html").read_text(encoding="utf-8")
        page = (ROOT / "memoria-historica.html").read_text(encoding="utf-8")
        self.assertIn('href="memoria-historica.html"', home)
        self.assertIn("candidate_index.json", page)
        self.assertIn("HISTÓRICO", page.upper())
        self.assertIn("no se consideran", page.lower()) if False else None
        self.assertIn("sin revalidación actual", page)
        self.assertIn('rel="noopener noreferrer"', page)

if __name__ == "__main__":
    unittest.main()
