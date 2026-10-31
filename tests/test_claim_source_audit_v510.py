import unittest
from scripts.audit_claim_sources import audit_section, check_reference

class ClaimSourceAuditTests(unittest.TestCase):
    def test_exact_value_and_entity(self):
        ev = {"url":"https://example.org/partners","researched_entity":"Integrator X",
              "field":"vendor_relations","item_value":"Vendor A",
              "description":"Integrator X partners with Vendor A."}
        self.assertEqual(check_reference(ev,entity="Integrator X",field_name="vendor_relations",item_value="Vendor A"),"metadata_text_support")
        self.assertEqual(check_reference(ev,entity="Integrator X",field_name="vendor_relations",item_value="Vendor B"),"item_mismatch")
        self.assertEqual(check_reference(ev,entity="Other",field_name="vendor_relations",item_value="Vendor A"),"entity_mismatch")

    def test_generic_reference_is_not_verified(self):
        data = {"rows":[{"name":"Integrator X","fields":{"vendor_relations":{
            "value":["Vendor A"],"items":[{"value":"Vendor A","evidence_ids":["e1"]}]}}}],
            "evidence":{"e1":{"url":"https://example.org","title":"Partners"}}}
        report = audit_section(data)
        self.assertEqual(report["counts"]["generic_not_atomic"],1)
        self.assertFalse(report["source_page_content_verified"])

if __name__ == "__main__":
    unittest.main()
