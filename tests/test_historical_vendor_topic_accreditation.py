import unittest

from scripts.accredit_semantic_historical_sources import classify


class HistoricalVendorTopicAccreditation(unittest.TestCase):
    def claim(self, section, field, entity, value, context):
        return {
            "section": section, "field": field, "entity": entity,
            "value": value, "source_context": context,
        }

    def test_own_official_product_page_proves_topic(self):
        claim = self.claim(
            "trends", "market_players", "Observability / Digital Experience",
            "Datadog", "Datadog offers observability for applications and infrastructure.",
        )
        self.assertEqual(
            "VERIFIED_FIRST_PARTY_TECHNOLOGY_PARTICIPATION",
            classify(claim, "https://www.datadoghq.com/product/"),
        )

    def test_unrelated_vendor_page_is_not_proof(self):
        claim = self.claim(
            "architectures", "vendors", "Zero Trust", "Cisco",
            "Our article mentions Cisco and zero trust among other vendors.",
        )
        self.assertEqual(
            "TECHNOLOGY_PARTICIPATION_NOT_FIRST_PARTY",
            classify(claim, "https://www.example.org/vendors"),
        )

    def test_official_generic_mention_is_not_proof(self):
        claim = self.claim(
            "trends", "market_players", "Observability / Digital Experience",
            "Datadog", "Datadog careers, legal notices and contact details.",
        )
        self.assertEqual(
            "TECHNOLOGY_CONTEXT_NOT_SHOWN",
            classify(claim, "https://www.datadoghq.com"),
        )

    def test_explicit_versus_detected_without_comparison_keyword(self):
        claim = self.claim(
            "manufacturers", "competitors", "Ciena", "Huawei",
            "Ciena versus Huawei in optical infrastructure.",
        )
        self.assertEqual(
            "VERIFIED_EXPLICIT_COMPETITOR_CONTEXT",
            classify(claim, "https://www.ciena.com/products"),
        )


if __name__ == "__main__":
    unittest.main()
