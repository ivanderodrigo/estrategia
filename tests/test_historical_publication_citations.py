"""Claim-specific citation accreditation from recovered historical analyst links."""
import unittest
from scripts.revalidate_historical_sources import publication_title_match
from scripts.accredit_semantic_historical_sources import classify

URL = "https://www.gartner.com/en/newsroom/press-releases/2026-top-cybersecurity-trends"
VALUE = "Gartner: Top Cybersecurity Trends for 2026"
TEXT = ("gartner identifies the top cybersecurity trends for 2026 "
        "including agent security and identity threat defense.")

class HistoricalPublicationTests(unittest.TestCase):
    def test_same_publisher_substantial_title_overlap(self):
        matched, context = publication_title_match(VALUE, TEXT, URL, "trends", "sources")
        self.assertTrue(matched)
        claim = {"section":"trends", "field":"sources", "entity":"AI Security",
                 "value":VALUE, "source_context":context,
                 "match_method":"PUBLISHER_TITLE_OVERLAP"}
        self.assertEqual(classify(claim,URL),"VERIFIED_CITED_ANALYST_DOCUMENT")

    def test_wrong_publisher_not_credited(self):
        url = "https://www.forrester.com/blogs/top-cybersecurity-trends/"
        self.assertFalse(publication_title_match(VALUE, TEXT, url, "trends", "sources")[0])

    def test_no_accreditation_for_vendor_participation(self):
        self.assertFalse(publication_title_match(
            VALUE,TEXT,URL,"trends","market_players")[0])

    def test_insufficient_and_generic_terms_not_credited(self):
        value="Gartner: Market Report 2026"
        self.assertFalse(publication_title_match(
            value,TEXT,URL,"architectures","analyst_basis")[0])

    def test_classifier_requires_matching_publisher_and_role(self):
        claim={"section":"architectures","field":"analyst_basis","entity":"Zero Trust",
               "value":"Forrester: Top Cybersecurity Trends for 2026",
               "source_context":TEXT,"match_method":"PUBLISHER_TITLE_OVERLAP"}
        self.assertNotEqual(classify(claim, URL),"VERIFIED_CITED_ANALYST_DOCUMENT")

if __name__=="__main__":
    unittest.main()
