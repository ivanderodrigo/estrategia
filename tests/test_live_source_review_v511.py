import unittest
from unittest.mock import Mock, patch

from scripts.review_sources_live import review_document, run


class LiveSourceReviewTests(unittest.TestCase):
    def test_complete_review_checks_each_reference_with_one_download_per_url(self):
        from scripts.review_sources_live import full_review
        claims = [dict(entity="Example Buyer", value=v, url="https://example.org/detail")
                  for v in ["correct value", "another value"]]
        with patch("scripts.review_sources_live.collect_claims",return_value=claims), \
             patch("scripts.review_sources_live.fetch_document",
                   return_value=("", " example buyer correct value ")) as fetch:
            result = full_review(None)
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(result["sampled"], 2)
        self.assertEqual(claims[0]["review_status"],"page_mentions_entity_and_value_needs_semantic_review")
        self.assertEqual(claims[1]["review_status"],"page_does_not_mention_value")

    @patch("scripts.review_sources_live.validate_public_url", side_effect=lambda x: x)
    def test_page_word_match_is_not_semantic_verification(self, validate):
        response = Mock()
        response.status_code = 200
        response.headers = {"Content-Type": "text/html"}
        response.encoding = "utf-8"
        response.iter_content.return_value = [b"<html><body>Integrator X works with Vendor A.</body></html>"]
        session = Mock()
        session.get.return_value = response
        status = review_document(session, "https://example.org", "Integrator X", "Vendor A")
        self.assertEqual(status, "page_mentions_entity_and_value_needs_semantic_review")
        self.assertFalse(session.get.call_args.kwargs["allow_redirects"])

    @patch("scripts.review_sources_live.validate_public_url", side_effect=lambda x: x)
    def test_http_202_with_real_html_content_can_be_reviewed(self, validate):
        response=Mock()
        response.status_code=202
        response.headers={"Content-Type":"text/html"}
        response.encoding="utf-8"
        response.iter_content.return_value=[
            b"<html><body>Integrator X offers Vendor A enterprise networking platforms.</body></html>"
        ]
        session=Mock()
        session.get.return_value=response
        self.assertEqual(
            review_document(session,"https://example.org","Integrator X","Vendor A"),
            "page_mentions_entity_and_value_needs_semantic_review"
        )

    @patch("scripts.review_sources_live.validate_public_url", side_effect=lambda x: x)
    def test_http_202_without_document_does_not_count_as_verified(self, validate):
        response=Mock()
        response.status_code=202
        response.headers={"Content-Type":"text/html"}
        response.encoding="utf-8"
        response.iter_content.return_value=[b"<html></html>"]
        session=Mock()
        session.get.return_value=response
        self.assertEqual(
            review_document(session,"https://example.org","Integrator X","Vendor A"),
            "http_202_insufficient_content"
        )

    def test_rotating_sample_spreads_across_hosts_and_sections(self):
        claims=[
            {"section":"clients_public","entity":"Buyer","field":"notice_id",
             "value":str(i),"url":f"https://ted.europa.eu/notice/{i}"}
            for i in range(100)
        ]+[
            {"section":"manufacturers","entity":"Vendor","field":"competitors",
             "value":str(i),"url":f"https://manufacturer{i%4}.example.org/compare/{i}"}
            for i in range(20)
        ]+[
            {"section":"integrators","entity":"Partner","field":"vendor_relations",
             "value":str(i),"url":f"https://partner{i%3}.example.org/vendors/{i}"}
            for i in range(20)
        ]
        with patch("scripts.review_sources_live.collect_claims",return_value=claims), \
             patch("scripts.review_sources_live.review_document",return_value="page_mentions_value_only"):
            result=run(None,limit=14,day=740000,session=Mock())
        self.assertEqual(result["sampled"],14)
        self.assertEqual(result["total_references"],140)
        self.assertGreaterEqual(result["unique_source_hosts_in_sample"],6)
        self.assertGreaterEqual(len({x["section"] for x in result["items"]}),3)
        self.assertEqual(result["sampling_policy"],"rotating-section-host-round-robin-v1")

    @patch("scripts.review_sources_live.validate_public_url", side_effect=lambda x: x)
    def test_redirect_not_followed(self, validate):
        response = Mock(status_code=301)
        session = Mock()
        session.get.return_value = response
        self.assertEqual(review_document(session, "https://example.org", "Integrator X", "Vendor A"),
                         "redirect_requires_review")


if __name__ == "__main__":
    unittest.main()
