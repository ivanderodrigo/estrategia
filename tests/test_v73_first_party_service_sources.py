"""Official service source registry is routing only and never fabricates services."""
import unittest

from engine.research.sources import seeds_for
from engine.research.web_intelligence import _filter_entity_seeds
from engine.research.evidence_routing import prioritize_sources


class FirstPartyServiceResearch(unittest.TestCase):
    def test_claranet_receives_exact_service_portfolio_urls(self):
        row = {"name": "Claranet", "fields": {}}
        target = {"section": "integrators", "fields": ["services", "capabilities"]}
        seeds = seeds_for(row, target["fields"], target=target)
        urls = {seed.url: seed for seed in seeds}
        self.assertIn("https://www.claranet.com/es/servicios/", urls)
        self.assertIn("https://www.claranet.com/es/cybersecurity/", urls)
        self.assertTrue(urls["https://www.claranet.com/es/servicios/"].official)
        self.assertTrue(all(seed.source_type == "official-entity-source-lead" for seed in seeds))
        self.assertEqual(len(_filter_entity_seeds(seeds, "Claranet", "integrators")), 3)

    def test_orange_business_spain_maps_to_regional_official_urls(self):
        target = {"section": "integrators", "fields": ["services"]}
        seeds = seeds_for({"name": "Orange Business Spain", "fields": {}},
                          target["fields"], target=target)
        self.assertTrue(any("orange-business.com/es-es/soluciones/cloud" in s.url for s in seeds))
        self.assertTrue(all(s.official for s in seeds))

    def test_no_cross_entity_source_leak_or_marketing_claim_promotion(self):
        target = {"section": "integrators", "fields": ["services"]}
        no_leads = seeds_for({"name": "Unknown Group", "fields": {}},
                             target["fields"], target=target)
        self.assertFalse(any(s.source_type == "official-entity-source-lead" for s in no_leads))
        self.assertEqual(
            seeds_for({"name": "Claranet", "fields": {}}, ["job_profiles"],
                      target={"section": "integrators", "fields": ["job_profiles"]}),
            [],
        )

    def test_specific_official_service_sources_precede_guessed_homepage(self):
        target = {"section": "integrators", "fields": ["services"]}
        seeds = seeds_for({"name": "Axians", "fields": {}},
                          target["fields"], target=target)
        output = prioritize_sources(seeds, target)
        self.assertEqual(output[0].url,
                         "https://www.axians.es/mantenimiento-y-servicios-gestionados/")

if __name__ == "__main__":
    unittest.main()
