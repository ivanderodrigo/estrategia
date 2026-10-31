import unittest
from unittest.mock import Mock, patch

from scripts.review_sources_live import review_document


class LiveSourceReviewTests(unittest.TestCase):
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
    def test_redirect_not_followed(self, validate):
        response = Mock(status_code=301)
        session = Mock()
        session.get.return_value = response
        self.assertEqual(review_document(session, "https://example.org", "Integrator X", "Vendor A"),
                         "redirect_requires_review")


if __name__ == "__main__":
    unittest.main()
