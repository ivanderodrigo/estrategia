from __future__ import annotations

import unittest

from engine.research.intelligent_discovery import intelligent_discovery_queries
from engine.westcon_current_evidence import apply_westcon_current_evidence
from engine.enrichment import _active_westcon_manufacturer_map, derive_overlap_fields


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

    def test_old_vendors_do_not_count_as_westcon_overlap(self):
        data = {
            "manufacturers": [
                {"name": "Juniper Networks", "fields": {}},
                {"name": "Ruckus Networks", "fields": {}},
                {"name": "Cloudflare", "fields": {}},
                {"name": "Sonar", "fields": {}},
            ],
            "distributors": [{
                "name": "Distributor Example",
                "fields": {"vendor_relations": {
                    "value": ["Juniper Networks", "Ruckus Networks", "Cloudflare", "Sonar"],
                    "items": [{"value": name, "evidence": []} for name in
                              ("Juniper Networks", "Ruckus Networks", "Cloudflare", "Sonar")],
                }},
            }],
            "integrators": [],
        }
        active = _active_westcon_manufacturer_map(data)
        self.assertNotIn("juniper networks", active)
        self.assertNotIn("ruckus networks", active)
        self.assertIn("cloudflare", active)
        self.assertIn("sonar", active)
        derive_overlap_fields(data)
        overlaps = data["distributors"][0]["fields"]["westcon_overlap"]["value"]
        self.assertEqual(set(overlaps), {"Cloudflare", "Sonar"})

    def test_competing_active_westcon_peers_are_not_external_channel_competitors(self):
        # The product portfolios can compete technologically without making
        # either active Westcon manufacturer an external competitor.
        proof = {
            "url": "https://example.org/partners/cisco",
            "source": "Test primary",
            "provenance_origin": "PUBLIC_PRIMARY",
            "source_type": "official-web",
            "atomic": True,
        }
        def relation(values):
            return {
                "value": values,
                "items": [
                    {"value": value, "evidence": [dict(proof)]}
                    for value in values
                ],
                "evidence": [dict(proof)],
            }
        data = {
            "manufacturers": [
                {"name": "Extreme Networks", "fields": {
                    "competitors": relation(["Cisco", "Arista Networks"])}},
                {"name": "Cisco", "fields": {
                    "competitors": relation(["Extreme Networks"])}},
                {"name": "Arista Networks", "fields": {}},
            ],
            "distributors": [
                {"name": "Channel Example", "fields": {
                    "vendor_relations": relation(["Cisco", "Arista Networks"])}},
            ],
            "integrators": [],
        }
        derive_overlap_fields(data)
        fields = data["distributors"][0]["fields"]
        self.assertIn("Cisco", fields["westcon_overlap"]["value"])
        competitors = fields.get("competitor_vendor_overlap", {}).get("value", [])
        self.assertNotIn("Cisco", competitors)
        self.assertNotIn("Extreme Networks", competitors)
        # An external manufacturer remains eligible if both explicit claims
        # have individual source binding.
        self.assertIn("Arista Networks", competitors)

    def test_trends_use_analyst_and_standard_sources(self):
        row = {"name": "AI Security", "fields": {"domain": {"value": "Cybersecurity"}}}
        queries = intelligent_discovery_queries(
            row, ["recent_signals"], section="trends", limit=15,
        )
        self.assertTrue(any("site:gartner.com" in query for query in queries))
        self.assertTrue(any("site:nist.gov" in query for query in queries))


if __name__ == "__main__":
    unittest.main()
