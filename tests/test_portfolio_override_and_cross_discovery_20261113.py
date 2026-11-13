from __future__ import annotations

import unittest

from engine.research.intelligent_discovery import intelligent_discovery_queries
from engine.westcon_current_evidence import apply_westcon_current_evidence


class PortfolioAndCrossDiscoveryTests(unittest.TestCase):
    def test_recent_portfolio_rule_supersedes_old_deck(self):
        config = {
            "document": {"title": "FY27 original", "document_id": "old", "provenance_origin": "WESTCON_DOCUMENT_CURRENT"},
            "portugal_rule": {"title": "PT", "provenance_origin": "WESTCON_FIRST_PARTY_CURRENT"},
            "portfolio_spain": {
                "Juniper Networks": {"slides": [45], "domain": "Networking", "capabilities": ["Wi-Fi"]},
                "Ruckus Networks": {"slides": [47], "domain": "Networking", "capabilities": ["Wi-Fi"]},
            },
            "portfolio_override_2026_11": {
                "source": "Westcon Iberia", "title": "Update Nov 2026",
                "provenance_origin": "WESTCON_FIRST_PARTY_CURRENT",
                "excluded": ["Juniper Networks", "Ruckus Networks"],
                "included": {"Cloudflare": {}, "Sonar": {"aliases": ["SonarQube"]}},
            },
        }
        data = {"manufacturers": [], "meta": {}}
        apply_westcon_current_evidence(data, config)
        by_name = {row["name"]: row for row in data["manufacturers"]}
        for name in ("Juniper Networks", "Ruckus Networks"):
            self.assertIs(by_name[name]["fields"]["westcon_spain"]["value"], False)
            self.assertIs(by_name[name]["fields"]["westcon_portugal"]["value"], False)
            self.assertEqual(len(by_name[name]["fields"]["westcon_spain"]["evidence"]), 1)
        for name in ("Cloudflare", "Sonar"):
            self.assertIs(by_name[name]["fields"]["westcon_spain"]["value"], True)
            self.assertIs(by_name[name]["fields"]["westcon_portugal"]["value"], True)

    def test_same_category_vendor_cross_searches_do_not_claim_competition(self):
        market = [
            {"name": "Extreme Networks", "fields": {"domain": {"value": "Networking"}}},
            {"name": "Example Rival", "fields": {"domain": {"value": "Networking"}}},
            {"name": "Unrelated Vendor", "fields": {"domain": {"value": "Cybersecurity"}}},
        ]
        queries = intelligent_discovery_queries(
            market[0], ["competitors"], section="manufacturers",
            market_rows=market, rotation=0, limit=10,
        )
        self.assertTrue(any('"Example Rival"' in query and "comparison" in query for query in queries))
        self.assertFalse(any('"Unrelated Vendor"' in query for query in queries))

    def test_linecard_cross_searches_known_manufacturers(self):
        distributor = {"name": "Example Distribution", "fields": {"vendor_relations": {"value": []}}}
        market = [{"name": "Cloudflare", "fields": {}}, {"name": "Sonar", "fields": {}}]
        queries = intelligent_discovery_queries(
            distributor, ["vendor_relations"], section="distributors",
            market_rows=market, rotation=0, limit=12,
        )
        self.assertTrue(any('"Cloudflare"' in query for query in queries))
        self.assertTrue(any('"Sonar"' in query for query in queries))

    def test_trends_use_analyst_and_standard_sources(self):
        row = {"name": "AI Security", "fields": {"domain": {"value": "Cybersecurity"}}}
        queries = intelligent_discovery_queries(
            row, ["recent_signals"], section="trends", limit=15,
        )
        self.assertTrue(any("site:gartner.com" in query for query in queries))
        self.assertTrue(any("site:nist.gov" in query for query in queries))


if __name__ == "__main__":
    unittest.main()
