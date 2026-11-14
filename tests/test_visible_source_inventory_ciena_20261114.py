"""The audit must inspect UI-surviving evidence, not only expired gap trails."""
from __future__ import annotations
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts import revalidate_historical_sources as audit

class VisibleClaimAudit(unittest.TestCase):
    def test_finds_ciena_huawei_even_when_historical_sidecar_omits_it(self):
        data={"manufacturers":[{"name":"Ciena","fields":{"competitors":{
            "value":["Huawei","Nokia"],
            "items":[
                {"value":"Huawei","evidence":[{"url":"https://www.gartner.com/reviews/product/ciena-blue-planet-inventory-bpi/alternatives",
                                                 "provenance_origin":"LEGACY_UNRESOLVED"}]},
                {"value":"Nokia","evidence":[{"url":"https://www.example.org/nokia",
                                                "provenance_origin":"PUBLIC_PRIMARY",
                                                "source":"Official","title":"Nokia",
                                                "date":"2026-11-14","description":"exact source",
                                                "atomic":True,"field":"competitors","item_value":"Nokia"}]}
            ]
        }}}]}
        def fake_read(path,default=None):
            return data if path=="data/current/intelligence.json" else {}
        with patch.object(audit,"read_json",side_effect=fake_read):
            inventory=audit.candidate_inventory()
        self.assertIn("https://www.gartner.com/reviews/product/ciena-blue-planet-inventory-bpi/alternatives",inventory)
        found=inventory["https://www.gartner.com/reviews/product/ciena-blue-planet-inventory-bpi/alternatives"]
        self.assertTrue(any(x["entity"]=="Ciena" and x["value"]=="Huawei" for x in found))
        self.assertNotIn("https://www.example.org/nokia",inventory)

    def test_issuer_statement_names_huawei_exactly(self):
        root=Path(__file__).resolve().parents[1]
        doc=json.loads((root/"config/current/verified_issuer_competitors_20261114.json").read_text(encoding="utf-8"))
        claims=doc["existing_claim_sources"]
        self.assertGreaterEqual(len(claims),9)
        self.assertIn("Huawei",[x["value"] for x in claims])
        for x in claims:
            self.assertEqual(x["entity"],"ciena")
            self.assertEqual(x["field"],"competitors")
            self.assertEqual(x["source"]["verification_method"],"issuer-identified-direct-competitor")
            self.assertEqual(x["source"]["provenance_origin"],"PUBLIC_PRIMARY")
            self.assertIn("sec.gov/Archives/edgar/data/936395/",x["source"]["url"])

if __name__=="__main__":
    unittest.main()
