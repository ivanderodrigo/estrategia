"""Bilingual evidence discovery must survive the three-query daily budget."""
import unittest
from engine.research.planner import presentation_signal_queries
from engine.research.web_intelligence import _prioritize_research_queries

class IberianQueryTests(unittest.TestCase):
    def test_services_queries_include_iberian_vocabulary(self):
        hints = presentation_signal_queries("Integrador Ejemplo", {"services": ["SOC"]})
        self.assertTrue(any("servicios gestionados" in h for h in hints))
        self.assertTrue(any("serviços geridos" in h for h in hints))

    def test_contextual_iberian_query_uses_daily_budget(self):
        contextual = '"Integrador Ejemplo" "SOC" servicios gestionados'
        selected = _prioritize_research_queries(
            ['"Integrador Ejemplo" "SOC"'], [contextual], 3
        )
        self.assertIn(contextual, selected)

if __name__ == "__main__":
    unittest.main()
