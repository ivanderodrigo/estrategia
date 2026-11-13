import json
import unittest
from pathlib import Path

from engine.historical_claim_audit import audit_historical_claims
from engine.historical_source_alignment import source_alignment
from engine.storage import json_bytes

ROOT=Path(__file__).resolve().parents[1]


class HistoricalSourceIdentityTests(unittest.TestCase):
    def test_foreign_vendor_capability_urls_are_quarantined(self):
        ok, reason=source_alignment("manufacturers","1Password","capabilities",
                                    "https://www.levelblue.com/services")
        self.assertFalse(ok)
        self.assertEqual(reason,"other-vendor-source:levelblue")
        ok,_=source_alignment("manufacturers","1Password","capabilities",
                              "https://1password.com/products")
        self.assertTrue(ok)

    def test_cross_vendor_competitor_comparison_kept_as_research_lead(self):
        ok,_=source_alignment("manufacturers","1Password","competitors",
                              "https://www.lastpass.com/compare/lastpass-vs-1password")
        self.assertTrue(ok)

    def test_each_claim_has_its_own_review_and_only_current_atomic_support_counts(self):
        ev={"source":"1Password","title":"1Password vs LastPass",
            "date":"2026-11-13","description":"Official comparison",
            "url":"https://1password.com/compare/1password-vs-lastpass",
            "provenance_origin":"PUBLIC_PRIMARY","field":"competitors",
            "item_value":"LastPass","source_binding":"claim-specific"}
        data={"manufacturers":[{
            "name":"1Password",
            "fields":{"competitors":{"value":["LastPass","Keeper"],
              "items":[{"value":"LastPass","evidence":[ev]},
                       {"value":"Keeper","evidence":[]}]}}
        }]}
        hist={"data/public/historical/current/manufacturers.json":json_bytes({
            "entities":{"1password":{"competitors":[
                {"value":"LastPass","urls":["https://www.gartner.com/reviews"]},
                {"value":"Keeper","urls":["https://www.gartner.com/reviews"]}]}}})}
        output,summary=audit_historical_claims(data,hist,"2026-11-13T20:00:00Z")
        rows=json.loads(output)["claims"]
        self.assertEqual(summary["reviewed"],2)
        self.assertEqual(summary["accredited_existing"],1)
        self.assertEqual(summary["pending_revalidation"],1)
        self.assertEqual(rows[0]["status"],"ACREDITADO_CON_FUENTE_ACTUAL")
        self.assertEqual(rows[1]["status"],"PENDIENTE_DE_CONTRASTAR_AFIRMACION")

    def test_live_proof_must_match_field_value(self):
        ev={"source":"1Password","title":"Comparison",
            "date":"2026-11-13","description":"Official competitor source",
            "url":"https://1password.com/compare/password-manager",
            "provenance_origin":"PUBLIC_PRIMARY",
            "field":"competitors","item_value":"Bitwarden"}
        data={"manufacturers":[{"name":"1Password","fields":{"competitors":{
            "value":["LastPass"],"items":[{"value":"LastPass","evidence":[ev]}]}}}]}
        historical={"data/public/historical/current/manufacturers.json":json_bytes({
            "entities":{"1password":{"competitors":[{"value":"LastPass",
                                      "urls":["https://www.gartner.com/reviews"]}]}}})}
        _, summary=audit_historical_claims(data,historical,"2026-11-13T20:00:00Z")
        self.assertEqual(summary["accredited_existing"],0)


class StatusVisualTests(unittest.TestCase):
    def test_unresearched_differs_from_unaccredited(self):
        js=(ROOT/"assets/app/intelligence.js").read_text(encoding="utf-8")
        css=(ROOT/"assets/app/intelligence.css").read_text(encoding="utf-8")
        self.assertIn('confidence-tag not-researched',js)
        self.assertIn('confidence-tag unverified',js)
        self.assertIn('.confidence-tag.not-researched',css)

    def test_official_password_manager_comparisons_claim_specific(self):
        import json
        doc=json.loads((ROOT/"config/current/public_evidence_migrations.json").read_text(encoding="utf-8"))
        rows=[r for r in doc["claims"]
              if r.get("entity")=="1Password" and r.get("field")=="competitors"]
        self.assertGreaterEqual(len(rows),4)
        self.assertEqual({r["value"] for r in rows},
                         {"LastPass","Keeper","Dashlane","Bitwarden"})
        self.assertTrue(all(r["evidence"]["url"].startswith("https://1password.com/")
                            for r in rows))


if __name__=="__main__":
    unittest.main()
