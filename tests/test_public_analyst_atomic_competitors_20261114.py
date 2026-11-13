import unittest
from engine.knowledge_provenance import accrediting_evidence

def sample(**changes):
    ev={"source":"Gartner","title":"Gartner Magic Quadrant for Endpoint Protection",
        "date":"2026-11-14","retrieved_at":"2026-11-14",
        "description":"Both vendors explicitly listed in the same evaluated market",
        "url":"https://www.gartner.com/en/documents/7913209",
        "provenance_origin":"PUBLIC_ANALYST","source_type":"analyst-market-comparison",
        "atomic":True,"source_binding":"claim-specific",
        "field":"competitors","item_value":"Sophos",
        "verification_method":"same-market-explicit-vendor-list"}
    ev.update(changes)
    return ev

class AnalystCompetitorProvenanceTests(unittest.TestCase):
    def test_market_roster_exact_competitor_is_accrediting(self):
        self.assertTrue(accrediting_evidence(sample()))

    def test_general_analyst_mention_is_not_accrediting(self):
        for change in ({"atomic":False},{"source_binding":"discovery-only"},
                       {"field":"revenue"},{"item_value":""},
                       {"verification_method":""},{"url":"https://www.gartner.com/en/documents/111",
                                                    "verification_method":"unspecified"},
                       {"url":"https://example.com/reports/7913209"}):
            with self.subTest(change=change):
                self.assertFalse(accrediting_evidence(sample(**change)))

    def test_previous_gartner_product_alternatives_are_accrediting(self):
        self.assertTrue(accrediting_evidence(sample(
            url="https://www.gartner.com/reviews/product/attackiq-platform/alternatives",
            source_type="analyst-peer-review", verification_method="",item_value="Cymulate")))

    def test_unbound_peer_insights_source_is_not_accrediting(self):
        self.assertFalse(accrediting_evidence(sample(
            url="https://www.gartner.com/reviews/product/attackiq-platform/alternatives",
            source_type="analyst-peer-review", verification_method="",atomic=False)))

if __name__=="__main__":
    unittest.main()
