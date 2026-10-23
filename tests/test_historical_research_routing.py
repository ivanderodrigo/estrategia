import unittest
from engine.research.historical_leads import historical_revalidation_seeds, usable_historical_url
from engine.research.planner import plan

GAP={"id":"gap-1","section":"integrators","entity":"Test Integrator","field":"services",
     "gap_kind":"public-validation","priority":1}
RECORD={"gap_id":"gap-1","section":"integrators","entity":"Test Integrator","field":"services",
 "match_level":"exact-value-history","identity_scope":"canonical-name",
 "source_urls":["https://example.com/services","https://example.net/partners","https://example.org/about"]}

class HistoricalResearchRoutingTest(unittest.TestCase):
    def test_exact_evidence_urls_are_bounded_and_untrusted(self):
        urls=historical_revalidation_seeds(GAP,{"gap-1":RECORD})
        self.assertEqual(len(urls),2)
        self.assertTrue(all(row["official"] is False and row["source_grade"]=="C" for row in urls))
        self.assertTrue(all(row["historical_lead"] is True for row in urls))

    def test_unrelated_field_or_public_buyer_is_not_promoted(self):
        wrong={**RECORD,"field":"revenue"}
        self.assertEqual(historical_revalidation_seeds(GAP,{"gap-1":wrong}),[])
        public={**GAP,"section":"clients_public"}
        self.assertEqual(historical_revalidation_seeds(public,{"gap-1":RECORD}),[])
        derived={**GAP,"gap_kind":"derivation-support"}
        self.assertEqual(historical_revalidation_seeds(derived,{"gap-1":RECORD}),[])

    def test_ssrf_style_links_are_excluded(self):
        self.assertFalse(usable_historical_url("http://example.org/path"))
        self.assertFalse(usable_historical_url("https://localhost/path"))
        self.assertFalse(usable_historical_url("https://user:secret@example.com/path"))
        self.assertTrue(usable_historical_url("https://example.org/partners"))

if __name__=="__main__":
    unittest.main()
