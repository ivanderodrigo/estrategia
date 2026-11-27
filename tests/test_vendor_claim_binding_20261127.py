"""Official generic URLs are leads, not accredited channel relationships."""
import json
import unittest

from engine.publication import public_payloads
from engine.settings import SECTIONS
from engine.vendor_claims import exact_vendor_source


def ev(value, *, bound="atomic-item", field="vendor_relations", atomic=True):
    return {
        "source": "Distributor", "title": f"Official catalogue {value}",
        "url": "https://distributor.example/brands", "description": f"Lists {value}",
        "date": "2026-11-27", "source_type": "company-official", "source_grade": "A",
        "provenance_origin": "PUBLIC_PRIMARY", "official": True,
        "classification": "public", "field": field, "item_value": value,
        "source_binding": bound, "atomic": atomic,
    }


class VendorClaimBinding(unittest.TestCase):
    def test_atomic_item_and_claim_specific_are_both_valid(self):
        for mode in ("atomic-item", "claim-specific"):
            self.assertTrue(exact_vendor_source(ev("Check Point", bound=mode), "vendor_relations", "Check Point"))
        for altered in (
            ev("Check Point", bound="relationship-source"),
            ev("Check Point", field="services"),
            ev("CrowdStrike"),
            ev("Check Point", atomic=False),
        ):
            self.assertFalse(exact_vendor_source(altered, "vendor_relations", "Check Point"))

    def test_generic_official_link_downgrades_green_without_erasing_history(self):
        good, generic, wrong = ev("Check Point"), ev("BeyondTrust", bound="relationship-source"), ev("Cisco")
        items = []
        for value, proof in (("Check Point", good), ("BeyondTrust", generic), ("Zscaler", wrong)):
            items.append({"value": value, "evidence": [proof], "confidence": 0.9,
                          "evidence_color": "green", "confidence_band": "high", "assertion_status": "CONFIRMADO"})
        field = {"value": [x["value"] for x in items], "items": items,
                 "evidence": [good, generic, wrong], "confidence": 0.9,
                 "evidence_color": "green", "assertion_status": "CONFIRMADO"}
        data = {"meta": {}, "source_catalog": [], "schemas": {section: [] for section in SECTIONS},
                **{section: [] for section in SECTIONS}}
        data["distributors"] = [{"id": "distributor", "name": "Distributor",
                                 "fields": {"vendor_relations": field}}]
        files, manifest = public_payloads(data)
        public = json.loads(files["data/public/sections/distributors.json"])
        published_items = public["rows"][0]["fields"]["vendor_relations"]["items"]
        self.assertEqual([x["value"] for x in published_items], ["Check Point", "BeyondTrust", "Zscaler"])
        self.assertEqual([x["evidence_color"] for x in published_items], ["green", "red", "red"])
        self.assertTrue(published_items[0]["evidence_ids"])
        self.assertFalse(published_items[1]["evidence_ids"])
        self.assertFalse(published_items[2]["evidence_ids"])
        self.assertEqual(manifest["meta"]["vendor_relation_evidence_quarantine"]["downgraded_from_unproven"], 2)
        self.assertEqual(field["items"][1]["evidence_color"], "green")
        self.assertEqual(field["items"][1]["evidence"][0]["item_value"], "BeyondTrust")


if __name__ == "__main__":
    unittest.main()
