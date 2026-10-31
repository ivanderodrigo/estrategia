import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from engine.research.query_discovery import (
    _parse_bing_rss,
    _parse_duckduckgo_html,
    _safe_result_url,
    discover,
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

    @patch("engine.research.query_discovery._search_provider")
    def test_discovery_diversifies_hosts_and_retains_provenance(self, provider):
        provider.return_value = [
            "https://example.com/a", "https://example.com/b",
            "https://example.com/c", "https://another.example.org/d",
        ]
        seeds, stats = discover(Mock(), ['Example partnerships'],
            fallback_family="partners", providers=["bing_rss"],
            timeout_s=5, max_queries=1, results_per_query=8)
        self.assertEqual(len(seeds), 3)
        self.assertEqual(stats["host_saturation_skipped"], 1)
        self.assertTrue(all(not seed.official for seed in seeds))

    @patch("engine.research.query_discovery._search_provider")
    def test_alternative_engine_runs_when_first_only_duplicates(self, provider):
        provider.side_effect = [
            ["https://same.example.org/a"],
            ["https://same.example.org/a"],
            ["https://other.example.org/b"],
        ]
        leads, diagnostics = discover(Mock(), ["entity partners", "entity solutions"],
            fallback_family="partners", providers=["bing_rss", "duckduckgo_html"],
            timeout_s=5, max_queries=2, results_per_query=4)
        self.assertEqual(len(leads), 2)
        self.assertEqual(diagnostics["queries_attempted"], 3)
        self.assertGreaterEqual(diagnostics["duplicate_urls_skipped"], 1)

    def test_daily_cooldown_rescue_is_bounded_and_keeps_provenance_gates(self):
        source = (Path(__file__).resolve().parents[1] / "engine/research/web_intelligence.py").read_text(encoding="utf-8")
        self.assertIn('if profile == "daily" and not targets:', source)
        self.assertIn('targets = rotated[:12]', source)
        self.assertIn('"rescue_targets_after_cooldown": rescue_targets', source)


if __name__ == "__main__":
    unittest.main()
