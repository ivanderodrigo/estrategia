import unittest
from engine.research.planner import presentation_signal_queries

class PresentationSignalResearchTests(unittest.TestCase):
    def test_relationship_signals_use_partner_context(self):
        q=presentation_signal_queries("VASS",{"vendor_relations":["Extreme Networks"]})
        self.assertIn('"VASS" "Extreme Networks" partner',q)
        self.assertIn('"VASS" "Extreme Networks" technology alliance',q)

    def test_capability_signals_use_product_context(self):
        q=presentation_signal_queries("Claroty",{"capabilities":["OT security"]})
        self.assertIn('"Claroty" "OT security" solution',q)

    def test_marketing_metrics_not_automatically_evidence(self):
        self.assertEqual(presentation_signal_queries("Vendor",{"revenue":["99%"]}),[])
        self.assertEqual(presentation_signal_queries("Vendor",{"vendor_relations":["por investigar"]}),[])

if __name__=="__main__":
    unittest.main()
