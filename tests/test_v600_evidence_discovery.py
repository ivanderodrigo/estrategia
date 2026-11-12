from __future__ import annotations

import json
import unittest
from pathlib import Path

from engine.research.planner import systematic_discovery_queries
from engine.research.ted import notice_is_relevant


ROOT = Path(__file__).resolve().parents[1]


class V600EvidenceDiscoveryTests(unittest.TestCase):
    def test_systematic_discovery_samples_independent_domains(self):
        queries = systematic_discovery_queries(
            "integrators",
            "Example Integrator",
            ["vendor_relations", "services", "capabilities"],
            profile="daily",
        )
        self.assertGreaterEqual(len(queries), 3)
        self.assertLessEqual(len(queries), 3)
        self.assertTrue(any("site:channelpartner.es" in query for query in queries))
        self.assertTrue(any("site:itreseller.es" in query for query in queries))
        self.assertEqual(len(queries), len(set(queries)))

    def test_public_procurement_uses_procurement_lane(self):
        queries = systematic_discovery_queries(
            "clients_public",
            "Ayuntamiento de Ejemplo",
            ["request_or_need", "technology_signals"],
            profile="deep",
        )
        self.assertTrue(any("site:contrataciondelestado.es" in query for query in queries))
        self.assertTrue(any("site:base.gov.pt" in query for query in queries))
        self.assertTrue(any("site:ted.europa.eu" in query for query in queries))

    def test_generic_commodity_it_notice_is_rejected(self):
        notice = {
            "classification-cpv": ["30200000"],
            "notice-title": {"spa": "Suministro de ordenadores personales y portátiles"},
        }
        self.assertFalse(notice_is_relevant(notice))

    def test_cloud_security_notice_is_kept(self):
        notice = {
            "classification-cpv": ["72000000"],
            "notice-title": {"spa": "Servicios cloud de ciberseguridad, identidad y zero trust"},
        }
        self.assertTrue(notice_is_relevant(notice))

    def test_networking_cpv_is_kept(self):
        notice = {
            "classification-cpv": ["32420000"],
            "notice-title": {"spa": "Renovación de infraestructura LAN"},
        }
        self.assertTrue(notice_is_relevant(notice))

    def test_debt_policy_preserves_small_high_fit_growth_floor(self):
        policy = json.loads((ROOT / "config/current/research_policy.json").read_text(encoding="utf-8"))
        floors = policy["debt_aware_growth"]["minimum_growth_under_debt"]
        self.assertGreater(floors["daily"], 0)
        self.assertGreater(floors["deep"], floors["daily"])
        self.assertIn("portfolio_procurement_relevance_gate", policy["source_cascade"])


if __name__ == "__main__":
    unittest.main()
