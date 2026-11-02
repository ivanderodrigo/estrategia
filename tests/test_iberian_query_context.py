"""Bilingual evidence discovery must survive the three-query daily budget."""
import unittest
from engine.research.planner import presentation_signal_queries
from engine.research.web_intelligence import _prioritize_research_queries

class IberianQueryTests(unittest.TestCase):
    def test_services_queries_include_iberian_vocabulary(self):
        hints = presentation_signal_queries("Integrador Ejemplo", {"services": ["SOC"]})
        self.assertTrue(any("servicios gestionados" in h for h in hints))
        self.assertTrue(any("serviços geridos" in h for h in hints))

    def test_multiple_fields_share_query_budget(self):
        queries = presentation_signal_queries(
            "Integrador Ejemplo",
            {"services": ["SOC"], "public_cases": ["Hospital Central"]},
            limit=4,
        )
        self.assertTrue(any("SOC" in query for query in queries))
        self.assertTrue(any("Hospital Central" in query for query in queries))

    def test_portuguese_context_is_not_cut_off(self):
        queries = presentation_signal_queries(
            "Integrador Ejemplo", {"services": ["SOC"]}, limit=8
        )
        self.assertTrue(any("serviços geridos" in query for query in queries))

    def test_contextual_iberian_query_uses_daily_budget(self):
        contextual = '"Integrador Ejemplo" "SOC" servicios gestionados'
        selected = _prioritize_research_queries(
            ['"Integrador Ejemplo" "SOC"'], [contextual], 3
        )
        self.assertIn(contextual, selected)

if __name__ == "__main__":
    unittest.main()
