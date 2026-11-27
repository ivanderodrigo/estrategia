"""Official ES/PT source discoveries route research without accrediting claims."""
import json
import unittest
from pathlib import Path

from engine.research.sources import seeds_for
from engine.research.web_intelligence import _filter_entity_seeds
from engine.research.planner import _first_party_catalogue_boost


ROOT = Path(__file__).resolve().parents[1]


class IberianPrimarySourceRoutes(unittest.TestCase):
    def test_new_iberian_service_sources_reach_only_the_named_company(self):
        expected = {
            "Logicalis": "https://www.es.logicalis.com/es/soluciones-servicios/tecnologia/seguridad",
            "Integrity360": "https://www.integrity360.com/es/managed-cyber-services",
            "Nunsys": "https://www.nunsys.com/cybersoc/",
            "SEIDOR": "https://www.seidor.com/es-es/cloud/servicios-cloud",
            "Devoteam Portugal": "https://www.devoteam.com/pt/servicos/cybersecurity/",
            "T-Systems Spain": "https://www.t-systems.com/es/es/cloud-services/solutions/cloud-managed-services",
            "acens / Telefónica Tech": "https://telefonicatech.com/soluciones",
            "Evolutio": "https://www.evolutio.com/soluciones/ciberseguridad/",
            "Orange Cyberdefense": "https://www.orangecyberdefense.com/es/",
            "NTT Data Spain": "https://es.nttdata.com/services/cybersecurity",
            "Kyndryl": "https://www.kyndryl.com/es/es/services/network/managed",
        }
        target = {"section": "integrators", "fields": ["services", "capabilities"]}
        for entity, url in expected.items():
            with self.subTest(entity=entity):
                seeds = seeds_for({"name": entity, "fields": {}}, target["fields"], target=target)
                filtered = _filter_entity_seeds(seeds, entity, "integrators")
                self.assertIn(url, {source.url for source in filtered})
                self.assertTrue(all(source.official for source in filtered))
                self.assertTrue(all(source.source_type == "official-entity-source-lead" for source in filtered))
                self.assertFalse(any(source.url == url for source in seeds_for(
                    {"name": "Unrelated Integrator", "fields": {}}, target["fields"], target=target
                )))

    def test_new_distributor_linecards_are_exact_owner_leads(self):
        target = {"section": "distributors", "fields": ["vendor_relations"]}
        for entity, expected in {
            "Wifidom": {"https://www.wifidom.com/fabricantes/"},
            "Zaltor": {
                "https://zaltor.com/portfolio-soluciones-zaltor/",
                "https://zaltor.com/pt-pt/portefolio-de-solucoes/",
            },
        }.items():
            with self.subTest(entity=entity):
                seeds = seeds_for({"name": entity, "fields": {}}, target["fields"], target=target)
                self.assertTrue(expected <= {seed.url for seed in seeds})
                self.assertTrue(all(seed.official for seed in seeds))
                self.assertEqual(len(seeds), len(_filter_entity_seeds(seeds, entity, "distributors")))

    def test_registry_is_valid_and_contains_discovery_only_urls(self):
        registries = (
            "config/current/official_service_source_leads.json",
            "config/current/linecard_source_leads.json",
        )
        for registry in registries:
            with self.subTest(registry=registry):
                data = json.loads((ROOT / registry).read_text(encoding="utf-8"))
                leads = data["entries"]
                self.assertEqual(len(leads), len({
                    (lead["section"], lead["name"], lead["url"]) for lead in leads
                }))
                self.assertTrue(all(lead["url"].startswith("https://") for lead in leads))
                self.assertTrue(all(not any(key in lead for key in (
                    "verified", "accredited", "evidence", "item_value"
                )) for lead in leads))

    def test_official_catalogues_prioritize_verifiable_fields_not_derived_overlaps(self):
        self.assertEqual(_first_party_catalogue_boost("distributors", "Wifidom", "vendor_relations"), 2.0)
        self.assertEqual(_first_party_catalogue_boost("distributors", "Zaltor", "vendor_relations"), 2.0)
        self.assertEqual(_first_party_catalogue_boost("integrators", "Logicalis", "services"), 1.75)
        self.assertEqual(_first_party_catalogue_boost("integrators", "Devoteam Portugal", "capabilities"), 1.75)
        self.assertEqual(_first_party_catalogue_boost("distributors", "Wifidom", "services"), 1.75)
        self.assertEqual(_first_party_catalogue_boost("integrators", "Unknown", "services"), 1.0)
        self.assertEqual(_first_party_catalogue_boost("integrators", "Logicalis", "vendor_relations"), 1.0)
        self.assertEqual(_first_party_catalogue_boost("distributors", "Wifidom", "westcon_overlap"), 1.0)


if __name__ == "__main__":
    unittest.main()
