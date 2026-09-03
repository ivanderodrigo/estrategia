from __future__ import annotations

import unittest

from scripts.legacy_validate_bridge_hf11 import compatibility_projection
from engine.gaps import validate_gap_state_contract


class ValidateBridgeHF11(unittest.TestCase):
    def test_projection_only_relabels_public_validation_for_legacy_validator(self):
        report = {
            "public_validation_gaps": 1,
            "research_states": {"Pendiente de validación pública": 1, "Por investigar": 1},
            "gaps": [
                {"id": "a", "gap_kind": "public-validation", "research_state": "Pendiente de validación pública", "marker": 1},
                {"id": "b", "gap_kind": "standard", "research_state": "Por investigar", "marker": 2},
            ],
        }
        projected = compatibility_projection(report)
        self.assertEqual(projected["gaps"][0]["research_state"], "Por investigar")
        self.assertEqual(projected["gaps"][1]["research_state"], "Por investigar")
        self.assertEqual(projected["gaps"][0]["marker"], 1)
        self.assertEqual(report["gaps"][0]["research_state"], "Pendiente de validación pública")

    def test_real_contract_still_rejects_invalid_state(self):
        report = {
            "public_validation_gaps": 0,
            "gaps": [{"id": "x", "gap_kind": "standard", "research_state": "Validado mágicamente"}],
        }
        self.assertTrue(validate_gap_state_contract(report))

    def test_real_contract_accepts_both_intended_states(self):
        report = {
            "public_validation_gaps": 1,
            "gaps": [
                {"id": "a", "gap_kind": "public-validation", "research_state": "Pendiente de validación pública"},
                {"id": "b", "gap_kind": "standard", "research_state": "Por investigar"},
            ],
        }
        self.assertEqual(validate_gap_state_contract(report), [])


if __name__ == "__main__":
    unittest.main()
