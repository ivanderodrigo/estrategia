import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "data/v37/intelligence.json").read_text(encoding="utf-8"))
PORTFOLIO = json.loads((ROOT / "data/vendor_intelligence.json").read_text(encoding="utf-8"))["vendors"]


class BusinessIntelligenceV370(unittest.TestCase):
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
        required = {"domain","observed","trend_market_metrics","adjacent_market_metrics","horizon","drivers","buyer_priorities","market_players","westcon_vendors","evolution","iberia_context","sources"}
        for row in DATA["trends"]:
            self.assertTrue(required.issubset(row.get("fields", {})), (row.get("name"), required - set(row.get("fields", {}))))
        self.assertGreaterEqual(sum("trend_market_metrics" in x.get("fields", {}) for x in DATA["trends"]), 10)
        self.assertGreaterEqual(sum("market_players" in x.get("fields", {}) for x in DATA["trends"]), 10)


    def test_atomic_tags_have_own_traceability_and_confidence(self):
        bands={"high","medium","low"}
        seen=0
        for section in ("manufacturers","integrators","distributors","trends","architectures"):
            for row in DATA[section]:
                for field in row.get("fields",{}).values():
                    for item in field.get("items",[]) or []:
                        seen+=1
                        self.assertTrue(item.get("evidence"),(section,row.get("name"),item.get("value")))
                        self.assertIn(item.get("confidence_band"),bands)
                        self.assertGreaterEqual(float(item.get("confidence",0)),.35)
        self.assertGreater(seen,1500)

    def test_portugal_portfolio_rule(self):
        scopes={r["name"]:r["fields"]["scope"]["value"] for r in DATA["manufacturers"]}
        self.assertEqual(scopes["Proofpoint"],"PT")
        self.assertEqual(scopes["Check Point"],"PT")
        self.assertTrue(all(v=="ES + PT" for k,v in scopes.items() if k not in {"Proofpoint","Check Point"}))

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
        js = (ROOT / "assets/v370/intelligence.js").read_text(encoding="utf-8")
        for control in ("textSmaller","textReset","textLarger"):
            self.assertIn(f'id="{control}"', html)
        self.assertIn("--font-scale", (ROOT / "assets/v370/intelligence.css").read_text(encoding="utf-8"))
        self.assertIn("westcon-font-scale", js)
        for token in ("confidence-tag", "data-more-tags", "toggleSort", "reorderColumn", "renderTrendAnalytics"):
            self.assertIn(token, js)

    def test_no_advice_vocabulary_in_active_product(self):
        pattern = re.compile(r"\brecomend(?:acion|ación|aciones|ar|ation|ations)\b", re.I)
        for rel in ("index.html", "assets/v370/intelligence.js", "data/v37/intelligence.json"):
            self.assertIsNone(pattern.search((ROOT / rel).read_text(encoding="utf-8")), rel)

    def test_exports_follow_web_visual_system(self):
        js = (ROOT / "assets/v370/intelligence.js").read_text(encoding="utf-8")
        css = (ROOT / "assets/v370/intelligence.css").read_text(encoding="utf-8")
        for token in ("pptAddEntityCard", "pptAddDetailCard", "pptAddDomainDivider", "pptAddSources", "reportCover", "reportCardPage"):
            self.assertIn(token, js)
        for token in (".r-brand", ".r-intel-card", ".r-table", ".r-source-grid", ".report-sheet.rendering"):
            self.assertIn(token, css)
        self.assertIn("Westcon_Iberia_Business_Intelligence_v3.7.0.pptx", js)
        self.assertIn("Westcon_Iberia_Business_Intelligence_v3.7.0.pdf", js)

    def test_research_gap_feedback_loop_is_active(self):
        gaps = json.loads((ROOT / "data/v37/research_gaps.json").read_text(encoding="utf-8"))
        self.assertGreater(gaps.get("total_gaps", 0), 0)
        self.assertGreater(gaps.get("high_priority_gaps", 0), 0)
        sample = gaps.get("gaps", [])[:40]
        self.assertTrue(sample)
        self.assertTrue(all(x.get("query_hints") for x in sample))
        research = (ROOT / "scripts/research.py").read_text(encoding="utf-8")
        self.assertIn("v37_gap_tasks", research)
        self.assertIn("V37_GAPS_OUT", research)

    def test_evidence_has_freshness_and_revalidation_metadata(self):
        seen = 0
        fresh = 0
        for section in ("manufacturers", "integrators", "distributors", "trends", "architectures"):
            for row in DATA[section]:
                for field in row.get("fields", {}).values():
                    for ev in field.get("evidence", []) or []:
                        seen += 1
                        if ev.get("freshness_status") and ev.get("revalidation"):
                            fresh += 1
        self.assertGreater(seen, 100)
        self.assertGreater(fresh, 100)

    def test_automatic_workflows_validate_v37_and_publish_without_rebase(self):
        publisher = (ROOT / "scripts/publish_research_update.py").read_text(encoding="utf-8")
        self.assertIn("run(\"git\",\"reset\",\"--hard\",\"origin/main\")", publisher.replace(" ", ""))
        self.assertIn("--attempts", publisher)
        for name in ("research-daily.yml", "research-weekly.yml", "research-monthly.yml"):
            text = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
            self.assertIn("tests/test_v370.py", text, name)
            self.assertIn("tests/ui_smoke_v370.js", text, name)
            self.assertIn("publish_research_update.py", text, name)
            self.assertNotIn("git pull --rebase origin main", text, name)


if __name__ == "__main__":
    unittest.main()
