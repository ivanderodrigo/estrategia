import unittest
from engine.research.planner import historical_exact_queries


class HistoricalExactDiscoveryTests(unittest.TestCase):
    def test_exact_entity_value_and_original_domain_first(self):
        result = historical_exact_queries(
            "Acme Iberia", {"vendor_relations": ["Extreme Networks"]},
            [{"url": "https://www.example.com/partners/acme"}])
        self.assertIn('"Acme Iberia" "Extreme Networks"', result)
        self.assertIn('"Acme Iberia" site:www.example.com', result)
        self.assertLess(result.index('"Acme Iberia" "Extreme Networks"'), result.index('"Acme Iberia" site:www.example.com'))

    def test_repeat_and_long_values_are_bounded(self):
        result = historical_exact_queries(
            "Acme", {"vendor_relations": ["Vendor X", "Vendor X", "X" * 250]},
            [{"url": "https://localhost/invalid"}, {"url": "https://partner.example.org/entry"}],
            limit=4)
        self.assertEqual(len(result), len(set(result)))
        self.assertLessEqual(len(result), 4)
        self.assertFalse(any("localhost" in q for q in result))


if __name__ == "__main__":
    unittest.main()
