import unittest

from engine.research.query_discovery import (
    _parse_bing_rss,
    _parse_duckduckgo_html,
    _safe_result_url,
)


class QueryDiscoveryTests(unittest.TestCase):
    def test_bing_rss_extracts_public_result_and_drops_search_host(self):
        xml = """<rss><channel>
        <item><title>A</title><link>https://example.com/partners/acme</link></item>
        <item><title>B</title><link>https://www.bing.com/search?q=acme</link></item>
        </channel></rss>"""
        self.assertEqual(_parse_bing_rss(xml), ["https://example.com/partners/acme"])

    def test_duckduckgo_wrapper_is_unwrapped(self):
        html = '<a href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.org%2Fcase-study">x</a>'
        self.assertEqual(_parse_duckduckgo_html(html), ["https://example.org/case-study"])

    def test_non_public_or_social_results_are_not_candidates(self):
        self.assertEqual(_safe_result_url("https://linkedin.com/company/acme"), "")
        self.assertEqual(_safe_result_url("javascript:alert(1)"), "")


if __name__ == "__main__":
    unittest.main()
