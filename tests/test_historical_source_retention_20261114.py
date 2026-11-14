"""Regression: don't lose an individually checked claim after a temporary 403."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import accredit_semantic_historical_sources as audit

class HistoricalProvenanceRetention(unittest.TestCase):
    def test_previously_accredited_individual_claim_survives_source_error(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            checks=root/"checks.json"
            registry=root/"proofs.json"
            report=root/"audit.json"
            checks.write_text(json.dumps({"generated_at":"2026-11-14T12:00:00+00:00",
                "results":{"https://www.cpcdi.pt/": {
                  "status":"HTTP_UNAVAILABLE","claim_checks":[]}}}),encoding="utf-8")
            proof={"section":"distributors","entity":"cpcdi","field":"services",
                   "value":"Departamentos técnicos","source":{
                     "url":"https://www.cpcdi.pt/","date":"2026-11-13",
                     "retrieved_at":"2026-11-13","source_type":"historical-verified-excerpt",
                     "verification_method":"VERIFIED_FIRST_PARTY_CATALOG_VALUE"}}
            registry.write_text(json.dumps({"existing_claim_sources":[proof]}),encoding="utf-8")
            with (patch.object(audit,"CHECKS",checks),patch.object(audit,"REGISTRY",registry),
                  patch.object(audit,"REPORT",report)):
                saved=audit.main()
            self.assertEqual(len(saved),1)
            self.assertTrue(saved[0]["source"]["verification_reused"])
            summary=json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(summary["retained_prior_verified"],1)
            self.assertEqual(summary["verified_this_run"],0)
            self.assertEqual(summary["verified_claim_source_pairs"],1)

    def test_old_unsupported_claim_does_not_remain_accredited_forever(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            checks=root/"checks.json"
            registry=root/"proofs.json"
            report=root/"audit.json"
            checks.write_text(json.dumps({"generated_at":"2026-11-14T12:00:00+00:00",
                                          "results":{}}),encoding="utf-8")
            registry.write_text(json.dumps({"existing_claim_sources":[{
                 "section":"distributors","entity":"cpcdi","field":"services",
                 "value":"Departamento técnico","source":{
                     "url":"https://cpcdi.pt/","date":"2025-01-01"}}]}),encoding="utf-8")
            with (patch.object(audit,"CHECKS",checks),patch.object(audit,"REGISTRY",registry),
                  patch.object(audit,"REPORT",report)):
                saved=audit.main()
            self.assertEqual(saved,[])
            self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["expired_prior_verified"],1)

if __name__=="__main__":
    unittest.main()
