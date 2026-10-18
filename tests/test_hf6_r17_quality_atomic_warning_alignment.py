from __future__ import annotations

import unittest

from engine.quality import audit
from engine.settings import SECTIONS


def _base_data():
    data = {"schemas": {section: [] for section in SECTIONS}}
    for section in SECTIONS:
        data[section] = []
    return data


def _ev():
    return {
        "source": "Example",
        "title": "Exact support",
        "url": "https://example.com/evidence",
        "official": True,
    }


class HF6R17QualityAtomicWarningAlignment(unittest.TestCase):
    def test_supported_list_items_do_not_require_redundant_field_evidence(self):
        data = _base_data()
        data["schemas"]["manufacturers"] = [{"id": "capabilities"}]
        data["manufacturers"] = [{
            "name": "Vendor",
            "fields": {
                "capabilities": {
                    "value": ["XDR", "SASE"],
                    "items": [
                        {"value": "XDR", "evidence": [_ev()]},
                        {"value": "SASE", "evidence": [_ev()]},
                    ],
                    "evidence": [],
                    "claim_type": "fact",
                }
            },
        }]
        result = audit(data, {"relationships": []}, {"gaps": [], "total_gaps": 0})
        self.assertEqual([], result["errors"])
        self.assertEqual([], result["warnings"])
        self.assertEqual(100, result["score"])

    def test_unsupported_list_item_remains_visible_as_warning(self):
        data = _base_data()
        data["schemas"]["manufacturers"] = [{"id": "capabilities"}]
        data["manufacturers"] = [{
            "name": "Vendor",
            "fields": {
                "capabilities": {
                    "value": ["XDR", "SASE"],
                    "items": [
                        {"value": "XDR", "evidence": [_ev()]},
                        {"value": "SASE", "evidence": []},
                    ],
                    "evidence": [],
                    "claim_type": "fact",
                }
            },
        }]
        result = audit(data, {"relationships": []}, {"gaps": [], "total_gaps": 0})
        self.assertEqual([], result["errors"])
        self.assertEqual(
            ["Dato factual sin evidencia directa: manufacturers/Vendor/capabilities/SASE"],
            result["warnings"],
        )
        self.assertEqual(99, result["score"])

    def test_scalar_fact_without_evidence_is_still_warned(self):
        data = _base_data()
        data["schemas"]["manufacturers"] = [{"id": "market_position"}]
        data["manufacturers"] = [{
            "name": "Vendor",
            "fields": {
                "market_position": {
                    "value": "Leader",
                    "evidence": [],
                    "claim_type": "fact",
                }
            },
        }]
        result = audit(data, {"relationships": []}, {"gaps": [], "total_gaps": 0})
        self.assertEqual([], result["errors"])
        self.assertEqual(
            ["Dato factual sin evidencia directa: manufacturers/Vendor/market_position"],
            result["warnings"],
        )
        self.assertEqual(99, result["score"])


if __name__ == "__main__":
    unittest.main()
