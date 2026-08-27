import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "data/v36/intelligence.json").read_text(encoding="utf-8"))
PORTFOLIO = json.loads((ROOT / "data/vendor_intelligence.json").read_text(encoding="utf-8"))["vendors"]


class BusinessIntelligenceV360(unittest.TestCase):
    def test_five_domains_have_data(self):
        minimums = {"manufacturers":36,"integrators":60,"distributors":8,"trends":15,"architectures":10}
        for key, minimum in minimums.items():
            self.assertGreaterEqual(len(DATA[key]), minimum, key)

    def test_manufacturer_rows_are_exactly_westcon_portfolio(self):
        expected = {x["name"] for x in PORTFOLIO}
        actual = {x["name"] for x in DATA["manufacturers"]}
        self.assertEqual(expected, actual)
        for row in DATA["manufacturers"]:
            self.assertNotIn("portfolio_role", row.get("fields", {}))
            self.assertNotIn("portfolio_compared", row.get("fields", {}))

    def test_every_published_field_is_traceable(self):
        for key in ("manufacturers", "integrators", "distributors", "trends", "architectures"):
            for row in DATA[key]:
                self.assertTrue(row.get("evidence"), (key, row.get("name"), "identity"))
                for field_id, field in row.get("fields", {}).items():
                    self.assertNotIn(field.get("value"), (None, "", [], {}), (key, row.get("name"), field_id))
                    self.assertTrue(field.get("evidence"), (key, row.get("name"), field_id))

    def test_integrator_relations_only_reference_westcon_vendors(self):
        vendors = {x["name"].lower() for x in PORTFOLIO}
        aliases = {"microsoft azure":"microsoft azure", "aws":"aws", "akamai / noname":"akamai / noname"}
        for row in DATA["integrators"]:
            rels = row.get("fields", {}).get("vendor_relations", {}).get("value", [])
            self.assertTrue(rels, row.get("name"))
            for rel in rels:
                vendor = str(rel).split(" · ", 1)[0].strip().lower()
                self.assertTrue(vendor in vendors or vendor in aliases, (row.get("name"), vendor))

    def test_trends_are_rich(self):
        required = {"observed","horizon","drivers","buyer_priorities","westcon_vendors","evolution","sources"}
        for row in DATA["trends"]:
            self.assertTrue(required.issubset(row.get("fields", {})), (row.get("name"), required - set(row.get("fields", {}))))
        self.assertGreaterEqual(sum("market_metrics" in x.get("fields", {}) for x in DATA["trends"]), 10)
        self.assertGreaterEqual(sum("market_players" in x.get("fields", {}) for x in DATA["trends"]), 10)

    def test_architecture_taxonomy_is_guarded(self):
        portfolio = {x["name"] for x in PORTFOLIO}
        for arch in DATA["architectures"]:
            for layer in arch.get("fields", {}).get("layers", {}).get("value", []):
                if "identity" in str(layer.get("layer", "")).lower():
                    self.assertNotIn("UiPath", layer.get("vendors", []), arch.get("name"))
            for vendor in arch.get("fields", {}).get("vendors", {}).get("value", []):
                self.assertIn(vendor, portfolio, (arch.get("name"), vendor))

    def test_westcon_is_not_competitor_distributor(self):
        self.assertFalse(any("westcon" in str(x.get("name", "")).lower() for x in DATA["distributors"]))

    def test_source_universe_is_broad(self):
        self.assertGreaterEqual(len(DATA["source_catalog"]), 200)
        ids = {row.get("id") for row in DATA["source_catalog"]}
        for required in ("gartner_public","idc_public","forrester_public","vendor_partner_locators_iberia","vendor_reseller_msp_directories","partner_jobs_linkedin","nist_zero_trust"):
            self.assertIn(required, ids)

    def test_frontend_has_accessible_text_scaling(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "assets/v360/intelligence.js").read_text(encoding="utf-8")
        for control in ("textSmaller","textReset","textLarger"):
            self.assertIn(f'id="{control}"', html)
        self.assertIn("--font-scale", (ROOT / "assets/v360/intelligence.css").read_text(encoding="utf-8"))
        self.assertIn("westcon-font-scale", js)

    def test_no_advice_vocabulary_in_active_product(self):
        pattern = re.compile(r"\brecomend(?:acion|ación|aciones|ar|ation|ations)\b", re.I)
        for rel in ("index.html", "assets/v360/intelligence.js", "data/v36/intelligence.json"):
            self.assertIsNone(pattern.search((ROOT / rel).read_text(encoding="utf-8")), rel)


if __name__ == "__main__":
    unittest.main()
