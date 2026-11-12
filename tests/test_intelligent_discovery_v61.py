from __future__ import annotations

import unittest

from engine.research.intelligent_discovery import intelligent_discovery_queries
from engine.research.web_intelligence import _prioritize_research_queries
from engine.research.ted import notice_is_relevant
from engine.research.extractors import competitors_in_text, extract_candidates, distributor_linecard_vendors
from engine.research.documents import Document, parse_document


class IntelligentDiscoveryV61Tests(unittest.TestCase):
    def test_category_aware_competitor_queries_from_known_vendor_technology(self):
        row = {
            "name": "Example Networks",
            "fields": {
                "domain": {"value": "Networking"},
                "subcategories": {"value": ["SD-WAN", "Network Fabric"]},
                "competitors": {"value": []},
            }
        }
        queries = intelligent_discovery_queries(row, ["competitors"], rotation=0, limit=8)
        self.assertGreaterEqual(len(queries), 3)
        self.assertTrue(any("competing vendors" in q for q in queries))
        self.assertTrue(any("competidores fabricantes" in q for q in queries))
        self.assertTrue(any("Networking" in q for q in queries))
        self.assertTrue(all('"Example Networks"' in q for q in queries))

    def test_competitor_query_reserved_under_daily_budget(self):
        planned = ['"Example Networks" "Networking" competing vendors alternatives',
                   '"Example Networks" security site:channelpartner.es',
                   '"Example Networks" partner announcement']
        selected = _prioritize_research_queries(['"Example Networks" "Legacy Vendor"'], planned, 3)
        self.assertEqual(len(selected), 3)
        self.assertTrue(any("competing vendors" in q for q in selected))
        self.assertTrue(any("site:channelpartner.es" in q for q in selected))

    def test_empty_fields_get_context_specific_searches(self):
        row = {"name": "Example Networks", "fields": {"domain": {"value": "Network Fabric"}}}
        queries = intelligent_discovery_queries(row, ["products_platforms", "services", "use_cases"], limit=12)
        self.assertTrue(any("datasheet" in q for q in queries))
        self.assertTrue(any("services" in q for q in queries))
        self.assertTrue(any("casos de uso" in q for q in queries))

    def test_competitor_extraction_requires_explicit_comparison(self):
        vendors = ["Cisco", "Juniper Networks", "Fortinet"]
        found, terms = competitors_in_text(
            "Extreme Networks competes with Cisco and Juniper Networks in campus networking.",
            "Extreme Networks", vendors
        )
        self.assertIn("Cisco", found)
        self.assertIn("Juniper Networks", terms)
        unrelated, _ = competitors_in_text(
            "Extreme Networks and Cisco announced an integration partnership.",
            "Extreme Networks", vendors
        )
        self.assertNotIn("Cisco", unrelated)

    def test_distributor_site_specific_linecard_queries(self):
        row = {
            "name": "Atlas Distribution",
            "evidence": [{"url": "https://atlas-distribution.example/fabricantes",
                          "official": True, "source_type": "official"}],
            "fields": {"vendor_relations": {"value": []},
                       "technology_domains": {"value": ["Networking"]}},
        }
        queries = intelligent_discovery_queries(
            row, ["vendor_relations"], section="distributors", limit=12)
        self.assertTrue(any("site:atlas-distribution.example" in q for q in queries))
        self.assertTrue(any("fabricantes" in q for q in queries))

    def test_official_distributor_linecard_extraction(self):
        page = Document(
            url="https://atlas-distribution.example/fabricantes",
            title="Nuestras marcas y fabricantes",
            text="Atlas Distribution. Fabricantes y marcas: Cisco, Fortinet y VMware.",
            links=(), content_digest="abc")
        found = extract_candidates(
            "distributors", "official", page, ["Cisco", "Fortinet", "VMware"],
            official=True, researched_entity="Atlas Distribution")
        self.assertIn("vendor_relations", found)
        self.assertIn("Cisco", found["vendor_relations"].values)
        unrelated = Document(
            url="https://atlas-distribution.example/contacto",
            title="Contacto",
            text="Nota de prensa con Cisco, Fortinet y VMware sin catálogo de marcas",
            links=(), content_digest="abc")
        self.assertEqual(distributor_linecard_vendors(unrelated, ["Cisco", "Fortinet"]), ([], []))

    def test_logo_only_distributor_page_provides_brand_labels(self):
        html = """<html><head><title>Atlas Distribution - Fabricantes</title></head>
            <body><h1>Nuestras marcas</h1>
            <a href="/vendor/cisco"><img alt="Cisco"></a>
            <a href="/vendor/fortinet"><img alt="Fortinet"></a></body></html>"""
        doc = parse_document(html, "https://atlas-distribution.example/fabricantes", "abc")
        extracted = distributor_linecard_vendors(doc, ["Cisco", "Fortinet"])
        self.assertEqual(set(extracted[0]), {"Cisco", "Fortinet"})
        outside = parse_document(
            '<html><body><img alt="Cisco"></body></html>',
            "https://atlas-distribution.example/noticias/articulo", "abc")
        self.assertNotIn("Cisco", outside.text)

    def test_integrator_and_customer_articles_extracted_with_evidence_specific_title(self):
        for section, name in (
            ("integrators", "Socio Integrador"),
            ("clients_private", "Cliente Empresa"),
            ("clients_public", "Ayuntamiento de Ejemplo"),
        ):
            page = Document(
                url="https://example.org/noticias/proyecto-red-segura-2026",
                title=f"{name} presenta una nueva red segura para sus sedes",
                text=f"{name} ha renovado su infraestructura y red de comunicaciones.",
                links=(), content_digest="abc")
            data = extract_candidates(
                section, "news", page, [], official=False, researched_entity=name)
            self.assertIn("recent_signals", data, section)
            self.assertTrue(data["recent_signals"].values)
        index = Document(
            url="https://example.org/noticias",
            title="Socio Integrador - Noticias",
            text="Socio Integrador actualidad corporativa",
            links=(), content_digest="abc")
        self.assertNotIn(
            "recent_signals",
            extract_candidates("integrators", "news", index, [], official=True,
                               researched_entity="Socio Integrador"),
        )

    def test_generic_telephone_cpv_rejected(self):
        self.assertFalse(notice_is_relevant({"classification-cpv": ["32500000"], "notice-title": {"spa": "Mantenimiento de teléfonos móviles"}}))

    def test_wifi_printer_commodity_rejected(self):
        self.assertFalse(notice_is_relevant({"classification-cpv": ["30200000"], "notice-title": {"spa": "Adquisición de impresoras Wi-Fi y tóner"}}))

    def test_non_portfolio_water_network_rejected(self):
        self.assertFalse(notice_is_relevant({"classification-cpv": ["32400000"], "notice-title": {"spa": "Renovación de redes de abastecimiento de agua"}}))

    def test_cyber_cloud_procurement_accepted(self):
        self.assertTrue(notice_is_relevant({"classification-cpv": ["72000000"], "notice-title": {"spa": "Servicios cloud de ciberseguridad, identidad y zero trust"}}))

    def test_lan_switch_procurement_accepted(self):
        self.assertTrue(notice_is_relevant({"classification-cpv": ["32420000"], "notice-title": {"spa": "Renovación de infraestructura LAN y switches"}}))


if __name__ == "__main__":
    unittest.main()
