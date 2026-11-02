"""Search discovery reports provider-level yield without promoting search hits to evidence."""
import unittest
from unittest.mock import Mock, patch
from engine.research.query_discovery import discover

class ProviderDiagnosticsTests(unittest.TestCase):
    @patch("engine.research.query_discovery._search_provider")
    def test_provider_yield_is_visible(self, search):
        search.return_value = ["https://example.org/cases/example"]
        seeds, stats = discover(
            Mock(), ['"Example" case study'], fallback_family="cases",
            providers=["bing_rss"], timeout_s=4, max_queries=1,
            results_per_query=3
        )
        self.assertEqual(stats["provider_attempts"]["bing_rss"], 1)
        self.assertEqual(stats["provider_urls"]["bing_rss"], 1)
        self.assertEqual(len(seeds), 1)
        self.assertFalse(seeds[0].official)

if __name__ == "__main__":
    unittest.main()
