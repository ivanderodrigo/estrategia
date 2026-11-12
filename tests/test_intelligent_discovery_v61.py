from __future__ import annotations

import unittest

from engine.research.intelligent_discovery import intelligent_discovery_queries
from engine.research.web_intelligence import _prioritize_research_queries
from engine.research.ted import notice_is_relevant
from engine.research.extractors import competitors_in_text


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
