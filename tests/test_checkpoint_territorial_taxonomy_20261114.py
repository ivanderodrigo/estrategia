"""Check Point Portugal portfolio and its independently sourced cybersecurity facts."""
import unittest
from engine.model import canonical
from engine.storage import read_json
from engine.westcon_current_evidence import apply_westcon_current_evidence

class PortugalOnlyVendorTaxonomy(unittest.TestCase):
    def test_checkpoint_territory_and_technical_category_are_distinct(self):
        config = read_json("config/current/westcon_fy27_document_facts.json", {})
        data = {"manufacturers": [], "meta": {}}
        apply_westcon_current_evidence(data, config)
        rows = {canonical(r["name"]): r for r in data["manufacturers"]}
        self.assertIn("check point", rows)
        fields = rows["check point"]["fields"]
        self.assertIs(fields["westcon_spain"]["value"], False)
        self.assertIs(fields["westcon_portugal"]["value"], True)
        self.assertEqual(fields["scope"]["value"], "PT")
        domain = fields["domain"]
        self.assertEqual(canonical(domain["value"]), "cybersecurity")
        self.assertTrue(any(e.get("url")=="https://www.checkpoint.com/products/"
                            and e.get("atomic") is True
                            and e.get("field")=="domain"
                            and e.get("item_value")=="Cybersecurity"
                            and e.get("provenance_origin")=="PUBLIC_PRIMARY"
                            for e in domain["evidence"]))
        caps = fields["capabilities"]
        for capability in ("Network Security", "Cloud Security", "SASE",
                           "Endpoint Security", "AI Security"):
            item=next((i for i in caps["items"] if i["value"]==capability),None)
            self.assertIsNotNone(item)
            self.assertTrue(any(e.get("url")=="https://www.checkpoint.com/products/"
                                and e.get("item_value")==capability for e in item["evidence"]))

    def test_active_spain_vendors_also_in_portugal(self):
        cfg=read_json("config/current/westcon_fy27_document_facts.json", {})
        data={"manufacturers":[],"meta":{}}
        apply_westcon_current_evidence(data,cfg)
        for row in data["manufacturers"]:
            f=row["fields"]
            if f.get("westcon_spain",{}).get("value") is True:
                self.assertIs(f["westcon_portugal"]["value"],True,row["name"])

if __name__=="__main__":
    unittest.main()
