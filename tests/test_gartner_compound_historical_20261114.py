"""Regression for Gartner peer-alternatives with qualified historical values."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts.revalidate_historical_sources import check_one
from scripts.accredit_semantic_historical_sources import classify

URL="https://www.gartner.com/reviews/product/ciena-blue-planet-inventory-bpi/alternatives"

class FakeResponse:
    status_code=200
    headers={"Content-Type":"text/html"}
    text="""<html><body><h1>Ciena Blue Planet Inventory (BPI) Alternatives</h1>
    <p>Operations Support Systems</p>
    <h2>Huawei SmartCare</h2><p>By Huawei</p>
    <a>Compare with Ciena Blue Planet Inventory (BPI)</a>
    <h2>Nokia NetAct</h2><p>By Nokia</p>
    <h2>Service Enablement Platform</h2><p>By Ericsson</p></body></html>"""

class Session:
    def get(self,*args,**kwargs):
        return FakeResponse()

class HistoricalCompoundAlternativeTests(unittest.TestCase):
    @patch("scripts.revalidate_historical_sources.validate_public_url",side_effect=lambda x:x)
    def test_gartner_product_page_verifies_three_compound_vendor_claims(self,_):
        claims=[{"section":"manufacturers","entity":"ciena","field":"competitors",
                 "value":f"{vendor} · Operations Support Systems peer"}
                for vendor in ("Huawei","Nokia","Ericsson","Unrelated")]
        result=check_one(URL,claims,session=Session())
        statuses={c["value"]:c for c in result["claim_checks"]}
        for vendor in ("Huawei","Nokia","Ericsson"):
            c=statuses[f"{vendor} · Operations Support Systems peer"]
            self.assertEqual(c["status"],"VERIFIED_EXPLICIT_ALTERNATIVE")
            self.assertTrue(c["accredited"])
            self.assertEqual(c["matched_vendor"],vendor.lower())
        self.assertFalse(statuses["Unrelated · Operations Support Systems peer"]["accredited"])
        self.assertEqual(result["semantically_verified"],3)

    @patch("scripts.revalidate_historical_sources.validate_public_url",side_effect=lambda x:x)
    def test_generic_vendor_mention_does_not_establish_alternative(self,_):
        class NotAlternatives(Session):
            def get(self,*args,**kwargs):
                res=FakeResponse()
                res.text="""<html><body><h1>Ciena News</h1><p>
                    Huawei appears in an unrelated quote.
                    Operations Support Systems peer means a market description.
                    </p></body></html>"""
                return res
        result=check_one(URL,[{"section":"manufacturers","entity":"ciena",
               "field":"competitors","value":"Huawei · Operations Support Systems peer"}],
               session=NotAlternatives())
        self.assertFalse(result["claim_checks"][0]["accredited"])

    def test_three_manually_checked_current_source_matches_exact_historical_labels(self):
        j=json.loads(Path("config/current/verified_historical_peer_20261114.json").read_text(encoding="utf-8"))
        self.assertEqual(len(j["existing_claim_sources"]),3)
        for entry in j["existing_claim_sources"]:
            self.assertEqual(entry["section"],"manufacturers")
            self.assertEqual(entry["field"],"competitors")
            self.assertEqual(entry["source"]["url"],URL)
            self.assertEqual(entry["source"]["verification_method"],"explicit-product-alternative")
            self.assertIn("Operations Support Systems peer",entry["value"])

if __name__=="__main__":
    unittest.main()
