"""Failed page fetches must never consume an entire research cycle."""
from __future__ import annotations

import unittest

from engine.research.web_intelligence import _source_attempt_limits
from engine.settings import RESEARCH_POLICY


class ResearchAttemptBudgets(unittest.TestCase):
    def test_deep_has_independent_transport_and_financial_limits(self):
        total, financial = _source_attempt_limits("deep", 16)
        self.assertEqual(total, 32)
        self.assertEqual(financial, 4)
        self.assertLess(financial, total)

    def test_daily_and_exhaustive_retain_bounded_financial_research(self):
        self.assertEqual(_source_attempt_limits("daily", 5), (10, 2))
        self.assertEqual(_source_attempt_limits("exhaustive", 32), (64, 6))

    def test_attempt_budget_is_positive_even_for_empty_page_configuration(self):
        total, financial = _source_attempt_limits("deep", 0)
        self.assertGreater(total, financial)
        self.assertGreater(financial, 0)

    def test_deep_and_exhaustive_discovery_have_bounded_search_fanout(self):
        budgets = RESEARCH_POLICY["query_discovery"]["budgets"]
        self.assertLessEqual(budgets["deep"]["queries_per_entity"], 8)
        self.assertLessEqual(budgets["exhaustive"]["queries_per_entity"], 12)
        self.assertGreater(budgets["deep"]["queries_per_entity"],
                           budgets["daily"]["queries_per_entity"])


if __name__ == "__main__":
    unittest.main()
