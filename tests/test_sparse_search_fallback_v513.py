import unittest
from unittest.mock import patch
import requests
from engine.research.query_discovery import discover
from engine.research.sources import SourceSeed


class IndependentDiscoveryTests(unittest.TestCase):
    @patch("engine.research.query_discovery._search_provider")
    def test_sparse_first_provider_triggers_independent_search(self, search):
        search.side_effect=[["https://one.example.org/partners"],["https://two.example.net/vendors"]]
        seeds, stats=discover(requests.Session(),["Example Vendor"],fallback_family="partners",
            providers=["bing_rss","duckduckgo_html"],timeout_s=4,
            max_queries=1,results_per_query=4)
        self.assertEqual(search.call_count,2)
        self.assertEqual(stats["urls_discovered"],2)
        self.assertTrue(all(not x.official and x.source_grade=="C" for x in seeds))

    @patch("engine.research.query_discovery._search_provider")
    def test_two_distinct_domains_end_query(self, search):
        search.return_value=["https://one.example.org/a","https://two.example.net/b"]
        seeds, stats=discover(requests.Session(),["Example Vendor"],fallback_family="partners",
            providers=["bing_rss","duckduckgo_html"],timeout_s=4,
            max_queries=1,results_per_query=4)
        self.assertEqual(search.call_count,1)
        self.assertEqual(len(seeds),2)

if __name__=="__main__":
    unittest.main()
