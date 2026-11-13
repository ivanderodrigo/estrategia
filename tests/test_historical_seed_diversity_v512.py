import unittest
from engine.research.historical_leads import historical_revalidation_seeds, MAX_SEEDS_PER_GAP

class HistoricSeedDiversityTests(unittest.TestCase):
    def test_independent_hosts_precede_duplicate_host_pages(self):
        gap={"id":"g1","section":"integrators","entity":"A","field":"vendor_relations","target_values":["Extreme Networks"]}
        records={"g1":{"section":"integrators","entity":"A","field":"vendor_relations","match_level":"exact-value-history",
         "historical_samples":[{"value":'"Extreme Networks"'}],"source_urls":[
            "https://one.example.com/a","https://one.example.com/b",
            "https://two.example.org/a","https://three.example.net/a",
            "https://one.example.com/a","http://invalid.example/b",
        ]}}
        seeds=historical_revalidation_seeds(gap,records)
        self.assertEqual([s["url"] for s in seeds][:3],[
            "https://one.example.com/a","https://two.example.org/a","https://three.example.net/a"])
        self.assertTrue(all(s["official"] is False and s["historical_lead"] for s in seeds))
        self.assertLessEqual(len(seeds),MAX_SEEDS_PER_GAP)

    def test_does_not_use_derived_gaps(self):
        gap={"id":"g1","section":"integrators","entity":"A","field":"vendor_relations",
             "gap_kind":"derivation-support"}
        self.assertEqual(historical_revalidation_seeds(gap,{"g1":{"section":"integrators","entity":"A","field":"vendor_relations","source_urls":["https://example.org"]}}),[])
if __name__=="__main__":
    unittest.main()
