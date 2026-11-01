import unittest
from engine.research.web_intelligence import _prioritize_research_queries

class QueryBudgetPriorityTests(unittest.TestCase):
    def test_daily_budget_includes_contextual_source_search(self):
        atomic=['"VASS" "Extreme"','"VASS" "Cisco"','"VASS" "Cloud"']
        planned=['"VASS" "Extreme"','"VASS" "Extreme" partner','"VASS" site:example.org']
        queries=_prioritize_research_queries(atomic,planned,3)
        self.assertEqual(len(queries),3)
        self.assertEqual(queries[0],atomic[0])
        self.assertIn('"VASS" "Extreme" partner',queries)

    def test_budget_and_dedup(self):
        self.assertEqual(_prioritize_research_queries(['A','A'],['B','C'],0),[])
        self.assertEqual(_prioritize_research_queries(['A','A'],['B','C'],5),['A','B','C'])
if __name__=='__main__':
    unittest.main()
