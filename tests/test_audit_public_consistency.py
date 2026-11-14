"""All audit dashboards must refer to one published snapshot and source contract."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts import audit_public_consistency as audit

SECTIONS=audit.SECTIONS

class PublicAuditConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        public=self.root/"data/public"
        (public/"sections").mkdir(parents=True)
        self.root_patch=patch.object(audit,"ROOT",self.root)
        self.public_patch=patch.object(audit,"PUBLIC",public)
        self.root_patch.start();self.public_patch.start()
        stamp="2026-11-14T15:00:00+00:00"
        self.manifest={"generated_at":stamp,"counts":{s:1 for s in SECTIONS},
                       "sections":{s:{"file":f"data/public/sections/{s}.json","evidence":1} for s in SECTIONS},
                       "meta":{"source_coverage":{s:{"claims":1,"sourced":1} for s in SECTIONS}}}
        self.debt={"generated_at":stamp,"total_open_gaps":7,
                   "debt_breakdown":{"empty_schema_fields":7,"claims_awaiting_evidence":0,"derived_support":0},
                   "by_section":{s:{"empty_schema_fields":1,"claims_awaiting_evidence":0,
                                    "derivation_support":0} for s in SECTIONS}}
        self.write("manifest.json",self.manifest)
        self.write("debt_overview.json",self.debt)
        self.write("last_run.json",{"generated_at":stamp})
        for s in SECTIONS:self.write(f"sections/{s}.json",{"rows":[{
            "name":s,"fields":{"sample":{"value":"Documentado","confidence":0.9,
            "evidence_ids":["ev"]}}}],
            "evidence":{"ev":{"source_role":"Fuente pública primaria",
                        "url":"https://example.org/example"}}})

    def tearDown(self):
        self.public_patch.stop();self.root_patch.stop();self.tmp.cleanup()

    def write(self,rel,value):
        p=audit.PUBLIC/rel
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(value),encoding="utf-8")

    def test_all_sections_concile(self):
        self.assertEqual(audit.evaluate()["status"],"PASS")

    def test_mixed_snapshot_dates_must_fail(self):
        self.debt["generated_at"]="2026-11-13T15:00:00+00:00"
        self.write("debt_overview.json",self.debt)
        self.assertEqual(audit.evaluate()["status"],"FAIL")

    def test_missing_source_role_must_fail(self):
        self.write("sections/architectures.json",{"rows":[{"name":"SASE"}],
                   "evidence":{"ev":{"url":"https://example.org"}}})
        result=audit.evaluate()
        self.assertEqual(result["status"],"FAIL")
        self.assertTrue(any("architectures" in x for x in result["errors"]))

    def test_missing_area_debt_must_fail(self):
        self.debt["by_section"].pop("trends")
        self.write("debt_overview.json",self.debt)
        self.assertEqual(audit.evaluate()["status"],"FAIL")

if __name__=="__main__":
    unittest.main()
