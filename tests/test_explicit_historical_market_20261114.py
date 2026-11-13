"""Historical competitor accreditation is exact and market-scoped.

A Gartner list supports vendors competing in the same studied market;
it does not prove a specific partnership, distribution agreement or ranking.
"""
import unittest
from pathlib import Path
import json
from engine.model import canonical
from engine.verified_research import apply_verified_research

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"config/current/verified_historical_market_20261114.json"

class ExplicitHistoricalMarketClaims(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry=json.loads(SOURCE.read_text(encoding="utf-8"))

    def test_all_market_claims_have_both_vendors_in_exact_market_roster(self):
        entries=self.registry["existing_claim_sources"]
        self.assertGreaterEqual(len(entries),80)
        for claim in entries:
            with self.subTest(owner=claim["entity"],value=claim["value"]):
                ev=claim["source"]
                self.assertEqual(claim["section"],"manufacturers")
                self.assertEqual(claim["field"],"competitors")
                self.assertTrue(ev.get("url"))
                if ev.get("verification_method")=="same-market-explicit-vendor-list":
                    code=ev["url"].rstrip("/").split("/")[-1]
                    roster=self.registry["market_rosters"][code]
                    self.assertIn(canonical(claim["entity"]),[canonical(x) for x in roster["owner_keys"]])
                    self.assertIn(canonical(claim["value"]),[canonical(x) for x in roster["verified_vendor_roster"]])

    def test_missing_competitor_recovers_with_exact_atomic_evidence(self):
        data={"manufacturers":[{"name":"AudioCodes","fields":{"competitors":{
            "value":["Unrelated"],"items":[{"value":"Unrelated","evidence":[]}]}}},
            {"name":"Ivanti","fields":{"competitors":{"value":[]}}},
            {"name":"Cisco","fields":{"competitors":{"value":[]}}}]}
        stats=apply_verified_research(data)
        by_name={r["name"]:r for r in data["manufacturers"]}
        for owner,value in (("AudioCodes","Cisco"),("AudioCodes","Oracle"),
                            ("AudioCodes","Ribbon Communications"),
                            ("Ivanti","Jamf"),("Cisco","Armis")):
            field=by_name[owner]["fields"]["competitors"]
            matching=[item for item in field["items"] if canonical(item["value"])==canonical(value)]
            self.assertEqual(len(matching),1)
            evidence=matching[0].get("evidence") or []
            self.assertTrue(any(e.get("atomic") and e.get("field")=="competitors"
                                and canonical(e.get("item_value"))==canonical(value)
                                and str(e.get("url") or "").startswith("https://")
                                for e in evidence))
        self.assertFalse(by_name["AudioCodes"]["fields"]["competitors"]["items"][0].get("evidence"))
        self.assertGreater(stats["existing_claims_accredited"],5)

    def test_does_not_turn_wrong_market_source_into_competitor(self):
        rejected=self.registry["rejected_historical_claims"]
        self.assertGreaterEqual(len(rejected),20)
        accepted={(canonical(x["entity"]),canonical(x["value"]),x["source"]["url"])
                  for x in self.registry["existing_claim_sources"]}
        for item in rejected:
            self.assertNotIn((canonical(item["entity"]),canonical(item["value"]),item["url"]),accepted)

    def test_ui_marks_matching_historical_link_verified(self):
        js=(ROOT/"assets/app/intelligence.js").read_text(encoding="utf-8")
        self.assertIn("acreditado: fuente vinculada al dato exacto",js)
        self.assertIn("historicalKey(ev.item_value)===historicalKey(h.value)",js)

if __name__=="__main__":
    unittest.main()
