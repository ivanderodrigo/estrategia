"""Regression tests for evidence-first document navigation and source priority."""
from __future__ import annotations

import unittest

from engine.research.documents import parse_document
from engine.research.evidence_routing import (
    precise_claim_queries,
    precise_navigation,
    prioritize_sources,
)
from engine.research.sources import SourceSeed
from engine.research.web_intelligence import _prioritize_research_queries


def seed(url: str, family: str = "official", official: bool = True,
         source_type: str = "official-domain") -> SourceSeed:
    return SourceSeed(url, family, official, "A" if official else "C",
                      source_type, "Sample Distributor")


class EvidenceFirstRoutingV70(unittest.TestCase):
    def test_first_party_homepage_navigates_to_explicit_brand_directory(self):
        document = parse_document(
            '<title>Sample Distributor</title><body><h1>Inicio</h1>'
            '<a href="/fabricantes/">Fabricantes</a>'
            '<a href="/casos-exito/">Casos de éxito</a>'
            '<a href="/noticias">Noticias</a>'
            '<a href="https://outsider.example/vendors/">Marcas externas</a>'
            '</body>',
            "https://sample.example/", "home-digest",
        )
        result = precise_navigation(
            document, seed("https://sample.example/"),
            ["vendor_relations"], limit=4,
        )
        self.assertEqual([item.url for item in result],
                         ["https://sample.example/fabricantes"])
        self.assertTrue(result[0].official)
        self.assertEqual(result[0].family, "partners")

    def test_discovery_only_homepage_does_not_inherit_official_authority(self):
        document = parse_document(
            '<a href="/fabricantes/">Fabricantes</a>',
            "https://random.example/", "digest",
        )
        result = precise_navigation(
            document,
            seed("https://random.example/", "partners", False, "search-discovery:bing_rss"),
            ["vendor_relations"],
        )
        self.assertEqual(result, [])

    def test_targets_limit_to_relevant_intelligence_family(self):
        document = parse_document(
            '<a href="/fabricantes/">Fabricantes</a>'
            '<a href="/servicios/gestionados">Servicios gestionados</a>'
            '<a href="/trabaja-con-nosotros">Empleo</a>'
            '<a href="/contacto">Contacto</a>',
            "https://sample.example/", "digest",
        )
        result = precise_navigation(
            document, seed("https://sample.example/"),
            ["services"], limit=4,
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].url, "https://sample.example/servicios/gestionados")

    def test_prioritizes_explicit_linecard_and_archived_claim_over_generic_routes(self):
        catalogue = seed("https://distributor.example/marcas", "partners", True,
                         "official-linecard-discovery-lead")
        historical = seed("https://partner.example/certified/distributor",
                          "partners", False, "public-web-revalidated")
        homepage = seed("https://distributor.example/")
        sitemap = seed("https://distributor.example/sitemap.xml", "partners")
        data = [homepage, sitemap, historical, catalogue, homepage]
        result = prioritize_sources(data, {"fields": ["vendor_relations"]})
        self.assertEqual(result[:2], [catalogue, historical])
        self.assertEqual(len(result), 4)
        self.assertEqual(result[-1], sitemap)

    def test_exact_claim_searches_are_site_restricted_and_do_not_create_facts(self):
        target = {
            "entity": "Sample Distributor",
            "target_values_by_field": {
                "vendor_relations": ["Fortinet", "Cisco"],
                "services": ["Por investigar"],
            },
        }
        result = precise_claim_queries(
            target, [seed("https://www.sample.example/fabricantes", "partners")],
            rotation=0, limit=2,
        )
        self.assertEqual(result, [
            '"Sample Distributor" "Fortinet" site:sample.example',
            '"Sample Distributor" "Cisco" site:sample.example',
        ])
        self.assertEqual(precise_claim_queries(
            {"entity": "Sample Distributor", "target_values_by_field": {}},
            [seed("https://sample.example")],
        ), [])

    def test_linecard_query_precedes_generic_press_when_budget_one(self):
        result = _prioritize_research_queries(
            ['"Dist" "Fortinet"'],
            ['"Dist" networking site:channelpartner.es',
             '"Dist" fabricantes marcas linecard',
             '"Dist" services'],
            budget=1, section="distributors",
        )
        self.assertEqual(result, ['"Dist" fabricantes marcas linecard'])

    def test_navigation_never_promotes_a_citation_by_itself(self):
        doc = parse_document(
            '<a href="/fabricantes">Nuestros fabricantes</a>',
            "https://distributor.example/", "digest",
        )
        seeds = precise_navigation(
            doc, seed("https://distributor.example/"), ["vendor_relations"]
        )
        self.assertEqual(len(seeds), 1)
        self.assertNotIn("Fortinet", str(seeds))


if __name__ == "__main__":
    unittest.main()
