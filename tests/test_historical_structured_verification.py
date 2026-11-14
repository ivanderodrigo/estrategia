import unittest
from unittest.mock import patch
from scripts.accredit_structured_historical import claims_inventory
from engine.historical_structured_verification import verify_explicit_alternative

URL = "https://www.gartner.com/reviews/product/attackiq-platform/alternatives"
HTML = """<h1>AttackIQ Platform Alternatives</h1><h5>1. Cymulate Platform</h5>
<h5>2. Picus Security Validation Platform</h5><p>LastPass is mentioned elsewhere</p>"""

class StructuredHistoricalAccreditationTests(unittest.TestCase):
    def test_archive_only_product_alternative_entering_global_inventory(self):
        # Do not depend on the small manufacturers historical sidecar.
        archive_claims = {URL: [
            {"section":"manufacturers", "entity":"AttackIQ",
             "field":"competitors", "value":"Cymulate",
             "inventory_origin":"git-archive-recovered"},
            {"section":"manufacturers", "entity":"EfficientIP",
             "field":"competitors", "value":"LastPass"},
            {"section":"integrators", "entity":"AttackIQ",
             "field":"vendor_relations", "value":"Cymulate"},
        ]}
        with patch("scripts.revalidate_historical_sources.candidate_inventory",
                   return_value=archive_claims):
            inventory=claims_inventory()
        self.assertEqual(list(inventory),[URL])
        self.assertEqual(len(inventory[URL]),1)
        self.assertEqual(inventory[URL][0]["value"],"Cymulate")

    def test_positive_explicit_alternative(self):
        self.assertTrue(verify_explicit_alternative(URL, HTML, "AttackIQ", "Cymulate")["verified"])
        self.assertTrue(verify_explicit_alternative(URL, HTML, "attackiq", "Picus Security")["verified"])

    def test_generic_mention_is_not_proof(self):
        self.assertFalse(verify_explicit_alternative(URL, HTML, "AttackIQ", "LastPass")["verified"])

    def test_wrong_entity_is_not_proof(self):
        self.assertFalse(verify_explicit_alternative(URL, HTML, "EfficientIP", "Cymulate")["verified"])

    def test_wrong_source_type_is_not_proof(self):
        self.assertFalse(verify_explicit_alternative("https://www.gartner.com/en/documents/111", HTML, "AttackIQ", "Cymulate")["verified"])

    def test_interstitial_is_not_proof(self):
        self.assertFalse(verify_explicit_alternative(URL, "<h1>Verification</h1><h5>1. Cymulate</h5>", "AttackIQ", "Cymulate")["verified"])

    def test_alias_must_be_exact_curated_mapping(self):
        html = "<h1>Avaya Aura UCaaS (Legacy) Alternatives</h1><h5>1. Webex Suite</h5>"
        url = "https://www.gartner.com/reviews/product/avaya-aura-ucaas/alternatives"
        self.assertTrue(verify_explicit_alternative(url, html, "Avaya", "Cisco Webex")["verified"])
        self.assertFalse(verify_explicit_alternative(url, html, "Avaya", "Cisco")["verified"])

if __name__ == "__main__":
    unittest.main()
