"""Historical evidence must be judged from the strongest actual claim passage."""
import unittest
from scripts.revalidate_historical_sources import best_claim_excerpt
from scripts.accredit_semantic_historical_sources import classify

class HistoricalBestEvidenceWindowTests(unittest.TestCase):
    def test_distribution_announcement_not_masked_by_navigation(self):
        page = ("products | ingram micro | partner navigation | resources " * 25 +
                "today 1password announces a distribution agreement with ingram micro "
                "to make its products available to resellers")
        present, context = best_claim_excerpt(page, "ingram micro", "distributors")
        self.assertTrue(present)
        self.assertIn("distribution agreement", context)
        c={"section":"manufacturers", "entity":"1Password",
           "field":"distributors", "value":"Ingram Micro",
           "source_context":context}
        self.assertEqual("VERIFIED_EXPLICIT_DISTRIBUTION_AGREEMENT",
                         classify(c,"https://1password.com/blog/partnership"))

    def test_menu_mention_does_not_accredit_distribution(self):
        present, context=best_claim_excerpt(
            "1password | ingram micro | products and news",
            "ingram micro","distributors")
        self.assertTrue(present)
        c={"section":"manufacturers","entity":"1Password",
           "field":"distributors","value":"Ingram Micro","source_context":context}
        self.assertEqual("DISTRIBUTION_RELATIONSHIP_NOT_SHOWN",
                         classify(c,"https://1password.com/partners"))

    def test_absent_value_never_claimed(self):
        self.assertEqual((False,""),best_claim_excerpt("other brands","cisco","distributors"))

if __name__=="__main__":
    unittest.main()
