"""Search discovery reports provider-level yield without promoting search hits to evidence."""
import unittest
from unittest.mock import Mock, patch
from engine.research.query_discovery import discover

class ProviderDiagnosticsTests(unittest.TestCase):
    def test_portuguese_query_uses_portuguese_locale(self):
        from engine.research.query_discovery import _search_provider
        response = Mock()
        response.text = "<html></html>"
        response.raise_for_status.return_value = None
        session = Mock()
        session.get.return_value = response
        _search_provider(session, "duckduckgo_html", '"Exemplo" serviços geridos',
                         timeout_s=4, result_limit=3)
        self.assertEqual(session.get.call_args.kwargs["params"]["kl"], "pt-pt")

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
