"""Repeated searches reuse only short-lived, safe URL leads, never proof."""
from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from engine.research.query_discovery import discover
from engine.research.state import ResearchState
from engine.research.web_intelligence import _checkpoint
from scripts.publish_research_update import ALLOWED


class QueryDiscoveryCacheTests(unittest.TestCase):
    @patch("engine.research.web_intelligence.atomic_write_json")
    def test_cache_survives_checkpoint_and_is_allowed_in_canonical_publication(self, write):
        _checkpoint({}, {}, ResearchState({}), {},
                    {"results": [], "candidate_rejections": [], "families": {}},
                    set(), {"recent": {"ts": 1_800_000_000, "urls": ["https://example.org/"]}})
        paths = [call.args[0] for call in write.call_args_list]
        self.assertIn("data/current/query_discovery_cache.json", paths)
        self.assertIn("data/current/query_discovery_cache.json", ALLOWED)

    @patch("engine.research.security._public_dns", return_value=True)
    @patch("engine.research.query_discovery._search_provider")
    def test_same_query_reuses_leads_without_resubmitting_search(self, provider, _dns):
        provider.return_value = [
            "https://one.example.org/partners", "https://two.example.net/vendors",
        ]
        memory = {}
        args = dict(
            fallback_family="partners", providers=["bing_rss"],
            timeout_s=4, max_queries=1, results_per_query=6,
            query_cache=memory,
        )
        first, stats1 = discover(Mock(), ["Example vendors"], **args)
        second, stats2 = discover(Mock(), ["Example vendors"], **args)
        self.assertEqual(provider.call_count, 1)
        self.assertEqual(stats1["queries_attempted"], 1)
        self.assertEqual(stats2["queries_attempted"], 0)
        self.assertEqual(stats2["provider_cache_hits"], 1)
        self.assertEqual([seed.url for seed in first], [seed.url for seed in second])
        self.assertTrue(all(not seed.official and seed.source_grade == "C"
                            for seed in second))

    @patch("engine.research.security._public_dns", return_value=True)
    @patch("engine.research.query_discovery._search_provider")
    def test_expired_cache_requires_fresh_query(self, provider, _dns):
        provider.return_value = ["https://one.example.org/a"]
        memory = {}
        args = dict(fallback_family="official", providers=["bing_rss"],
                    timeout_s=4, max_queries=1, results_per_query=2,
                    query_cache=memory, cache_ttl_s=60)
        discover(Mock(), ["Example"], **args)
        self.assertEqual(len(memory), 1)
        for item in memory.values():
            item["ts"] -= 90
        _result, stats = discover(Mock(), ["Example"], **args)
        self.assertEqual(provider.call_count, 2)
        self.assertEqual(stats["provider_cache_hits"], 0)

    @patch("engine.research.query_discovery._search_provider")
    def test_poisoned_local_network_cache_is_rejected(self, provider):
        provider.return_value = ["https://safe.example.org/a"]
        memory = {}
        args = dict(fallback_family="official", providers=["bing_rss"],
                    timeout_s=4, max_queries=1, results_per_query=2,
                    query_cache=memory)
        discover(Mock(), ["Example"], **args)
        for item in memory.values():
            item["urls"] = ["http://127.0.0.1/private"]
        with patch("engine.research.security._public_dns", return_value=True):
            result, stats = discover(Mock(), ["Example"], **args)
        self.assertEqual(provider.call_count, 2)
        self.assertEqual(stats["provider_cache_hits"], 0)
        self.assertNotIn("http://127.0.0.1/private", [seed.url for seed in result])


if __name__ == "__main__":
    unittest.main()
