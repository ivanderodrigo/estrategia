"""A navigation menu must never become an accredited distributor linecard."""
import json
import unittest

from engine.publication import public_payloads
from engine.research.extractors import vendors_in_text
from engine.research.web_intelligence import _vendor_names
from engine.settings import SECTIONS
from engine.vendor_labels import non_vendor_reason, plausible_vendor_name


def evidence(value):
    return {
        "url": f"https://distributor.example/catalog/{value.replace(' ', '-').lower()}",
        "source": "Distributor", "title": f"Catalog {value}",
        "description": f"Distributor lists {value} in its official manufacturer linecard.",
        "date": "2026-11-27", "retrieved_at": "2026-11-27",
        "provenance_origin": "PUBLIC_PRIMARY", "source_type": "official-domain",
        "source_grade": "A", "official": True, "classification": "public",
        "source_binding": "claim-specific", "researched_entity": "Distributor",
        "field": "vendor_relations", "item_value": value, "atomic": True,
    }


class VendorLabelHygiene(unittest.TestCase):
    def test_navigation_assets_and_categories_are_not_vendors(self):
        invalid = [
            "Marketing", "Recursos", "NOVEDADES", "Redes", "MSSP",
            "Case Studies", "proofpoint.svg", "x-od.png",
            "woman talking on phone", "Discos Duros", "Spain", "Privacy Policy",
            "Partner Portal", "Infinigate Group", "Poland", "Pan-EMEA",
            "Arrow Capital Solutions", "RUCKUS Networks Endorsed",
            "Google Cloud Partner", "Parceria Sharp e Multimac",
            "Placas Base Intel", "Portátiles Acer", "Pasta Térmica",
        ]
        for label in invalid:
            with self.subTest(label=label):
                self.assertIsNotNone(non_vendor_reason(label))
        for label in ("Check Point", "Proofpoint", "Rackmount.IT", "Zscaler", "Cloudflare"):
            with self.subTest(real_vendor=label):
                self.assertTrue(plausible_vendor_name(label))

    def test_research_cannot_resurrect_legacy_nav_entries(self):
        values, _ = vendors_in_text(
            "Marketing, Recursos, Redes, Check Point, Proofpoint, proofpoint.svg",
            ["Marketing", "Recursos", "Redes", "Check Point", "Proofpoint", "proofpoint.svg"],
        )
        self.assertEqual(values, ["Check Point", "Proofpoint"])
        data = {
            "distributors": [{"name": "Distributor", "fields": {
                "vendor_relations": {"value": ["Marketing", "proofpoint.svg", "Check Point"]}
            }}],
        }
        vocabulary = _vendor_names(data)
        self.assertNotIn("Marketing", vocabulary)
        self.assertNotIn("proofpoint.svg", vocabulary)
        self.assertIn("Check Point", vocabulary)

    def test_publication_quarantines_false_green_without_touching_archive(self):
        values = ("Marketing", "proofpoint.svg", "Discos Duros", "Check Point")
        field = {
            "value": list(values), "confidence": 0.90,
            "confidence_band": "high", "evidence_color": "green",
            "assertion_status": "CONFIRMADO",
            "items": [{
                "value": value, "confidence": 0.90,
                "confidence_band": "high", "evidence_color": "green",
                "assertion_status": "CONFIRMADO", "evidence": [evidence(value)],
            } for value in values],
            "evidence": [evidence(value) for value in values],
        }
        data = {
            "meta": {}, "source_catalog": [], "schemas": {section: [] for section in SECTIONS},
            **{section: [] for section in SECTIONS},
        }
        data["distributors"] = [{
            "id": "dist", "name": "Distributor", "fields": {"vendor_relations": field},
        }]
        files, manifest = public_payloads(data)
        public = json.loads(files["data/public/sections/distributors.json"])
        field_public = public["rows"][0]["fields"]["vendor_relations"]
        self.assertEqual(field_public["value"], ["Check Point"])
        self.assertEqual([item["value"] for item in field_public["items"]], ["Check Point"])
        self.assertEqual(field_public["items"][0]["evidence_color"], "green")
        self.assertFalse(any(
            "Marketing" in str(item) or "proofpoint.svg" in str(item)
            for item in public["evidence"].values()
        ))
        self.assertEqual(
            manifest["meta"]["vendor_label_quarantine"]["removed_from_public_views"], 3
        )
        self.assertEqual(field["value"], list(values))  # historical/canonical unchanged


if __name__ == "__main__":
    unittest.main()
