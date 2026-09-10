from __future__ import annotations

import json
import unittest
from pathlib import Path

from engine.enrichment import derive_overlap_fields
from engine.research.documents import Document
from engine.research.extractors import extract_candidates

ROOT = Path(__file__).resolve().parents[1]


def ev(title: str, value: str) -> dict:
    return {
        "source": "Example official",
        "title": title,
        "url": "https://example.com/evidence",
        "date": "2026-09-10",
        "description": title,
        "scope": "GLOBAL",
        "official": True,
        "source_grade": "A",
        "source_type": "official-domain",
        "item_value": value,
        "atomic": True,
    }


class BusinessColumnsHF3(unittest.TestCase):
    def test_schema_defaults_and_linecard_order(self) -> None:
        data = json.loads((ROOT / "config/current/business_intelligence_schema.json").read_text(encoding="utf-8"))
        manu = data["sections"]["manufacturers"]
        m = {x["id"]: x for x in manu}
        self.assertFalse(m["westcon_spain"]["default_visible"])
        self.assertFalse(m["westcon_portugal"]["default_visible"])
        self.assertEqual(m["revenue"]["type"], "list")
        self.assertTrue(m["revenue"]["default_visible"])

        dist = data["sections"]["distributors"]
        ids = [x["id"] for x in dist]
        pos = ids.index("westcon_overlap")
        self.assertEqual(ids[pos:pos + 3], ["westcon_overlap", "competitor_vendor_overlap", "vendor_relations"])
        d = {x["id"]: x for x in dist}
        self.assertEqual(d["revenue"]["type"], "list")
        self.assertTrue(d["vendor_relations"]["ui_remainder_of_linecard"])

    def test_revenue_extractor_for_manufacturer_and_distributor(self) -> None:
        doc = Document(
            url="https://example.com/investors/results",
            title="FY2025 results",
            text="Example Corp reported revenue of US$ 12.4 billion for fiscal year 2025.",
            links=(),
            content_digest="abc",
        )
        manufacturer = extract_candidates("manufacturers", "financial", doc, [], official=True)
        distributor = extract_candidates("distributors", "financial", doc, [], official=True)
        self.assertIn("revenue", manufacturer)
        self.assertIn("revenue", distributor)
        self.assertTrue(any("12.4 billion" in value for value in manufacturer["revenue"].values))

    def test_competitor_maps_to_specific_westcon_manufacturer(self) -> None:
        data = {
            "manufacturers": [{
                "name": "Fortinet",
                "fields": {"competitors": {
                    "value": ["Palo Alto Networks"],
                    "items": [{"value": "Palo Alto Networks", "evidence": [ev("Fortinet comparison", "Palo Alto Networks")]}],
                }},
            }],
            "distributors": [{
                "name": "Example Distributor",
                "fields": {"vendor_relations": {
                    "value": ["Fortinet", "Palo Alto Networks", "Dell Technologies"],
                    "confidence": 0.88,
                    "items": [
                        {"value": "Fortinet", "evidence": [ev("Line card", "Fortinet")]},
                        {"value": "Palo Alto Networks", "evidence": [ev("Line card", "Palo Alto Networks")]},
                        {"value": "Dell Technologies", "evidence": [ev("Line card", "Dell Technologies")]},
                    ],
                }},
            }],
            "integrators": [],
        }
        derive_overlap_fields(data)
        fields = data["distributors"][0]["fields"]
        self.assertEqual(fields["westcon_overlap"]["value"], ["Fortinet"])
        self.assertEqual(fields["competitor_vendor_overlap"]["value"], ["Palo Alto Networks"])
        item = fields["competitor_vendor_overlap"]["items"][0]
        self.assertEqual(item["competes_with_westcon"], ["Fortinet"])
        self.assertEqual(item["competition_mapping_status"], "EVIDENCIADO")
        self.assertNotIn("Dell Technologies", fields["competitor_vendor_overlap"]["value"])

    def test_frontend_has_remainder_mapping_and_pref_migration(self) -> None:
        js = (ROOT / "assets/app/intelligence.js").read_text(encoding="utf-8")
        self.assertIn("function linecardRemainderField(", js)
        self.assertIn("Fabricantes Westcon con los que compite", js)
        self.assertIn("westcon-table-pref-revision-v431-hf3", js)


if __name__ == "__main__":
    unittest.main()
