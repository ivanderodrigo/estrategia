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


def _gaps(*rows):
    return {"gaps": list(rows), "total_gaps": len(rows)}


class HF6R18GapAwareQuality(unittest.TestCase):
    def test_supported_atomic_list_still_has_no_warning(self):
        data = _base_data()
        data["schemas"]["manufacturers"] = [{"id": "capabilities"}]
        data["manufacturers"] = [{
            "name": "Vendor",
            "fields": {
                "capabilities": {
                    "value": ["XDR"],
                    "items": [{"value": "XDR", "evidence": [_ev()]}],
                    "evidence": [],
                    "claim_type": "fact",
                }
            },
        }]
        result = audit(data, {"relationships": []}, _gaps())
        self.assertEqual([], result["warnings"])
        self.assertEqual(100, result["score"])

    def test_missing_atomic_item_with_exact_open_gap_is_coverage_debt_not_warning(self):
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
        gaps = _gaps({
            "section": "manufacturers",
            "entity": "Vendor",
            "field": "capabilities",
            "target_level": "item",
            "target_values": ["SASE"],
            "research_state": "Por investigar",
        })
        result = audit(data, {"relationships": []}, gaps)
        self.assertEqual([], result["warnings"])
        self.assertEqual(100, result["score"])

    def test_missing_atomic_item_without_matching_gap_remains_warning(self):
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
        result = audit(data, {"relationships": []}, _gaps())
        self.assertEqual(
            ["Dato factual sin evidencia directa: manufacturers/Vendor/capabilities/SASE"],
            result["warnings"],
        )
        self.assertEqual(99, result["score"])

    def test_wrong_item_gap_cannot_hide_missing_atomic_support(self):
        data = _base_data()
        data["schemas"]["manufacturers"] = [{"id": "capabilities"}]
        data["manufacturers"] = [{
            "name": "Vendor",
            "fields": {
                "capabilities": {
                    "value": ["SASE"],
                    "items": [{"value": "SASE", "evidence": []}],
                    "evidence": [],
                    "claim_type": "fact",
                }
            },
        }]
        gaps = _gaps({
            "section": "manufacturers",
            "entity": "Vendor",
            "field": "capabilities",
            "target_level": "item",
            "target_values": ["XDR"],
            "research_state": "Por investigar",
        })
        result = audit(data, {"relationships": []}, gaps)
        self.assertEqual(1, len(result["warnings"]))

    def test_missing_scalar_with_explicit_field_gap_is_not_warning(self):
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
        gaps = _gaps({
            "section": "manufacturers",
            "entity": "Vendor",
            "field": "market_position",
            "target_level": "field",
            "target_values": ["Leader"],
            "research_state": "Por investigar",
        })
        result = audit(data, {"relationships": []}, gaps)
        self.assertEqual([], result["warnings"])
        self.assertEqual(100, result["score"])

    def test_missing_scalar_without_gap_remains_warning(self):
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
        result = audit(data, {"relationships": []}, _gaps())
        self.assertEqual(
            ["Dato factual sin evidencia directa: manufacturers/Vendor/market_position"],
            result["warnings"],
        )
        self.assertEqual(99, result["score"])


if __name__ == "__main__":
    unittest.main()
