from __future__ import annotations

import unittest

from engine.gaps import build_gaps


class PublicEvidenceContractHF9(unittest.TestCase):
    def test_populated_external_fact_without_public_support_stays_actionable(self) -> None:
        public = {
            "schemas": {
                "manufacturers": [
                    {"id": "capabilities", "label": "Capacidades", "decision_required": True}
                ]
            },
            "manufacturers": [
                {
                    "id": "vendor-test",
                    "name": "Vendor Test",
                    "fields": {"capabilities": {"value": "SASE", "evidence": []}},
                }
            ],
        }
        report = build_gaps(public, research_state={})
        found = [
            gap for gap in report["gaps"]
            if gap.get("section") == "manufacturers"
            and gap.get("entity") == "Vendor Test"
            and gap.get("field") == "capabilities"
            and gap.get("target_values") == ["SASE"]
        ]
        self.assertEqual(len(found), 1)
        gap = found[0]
        self.assertEqual(gap.get("gap_kind"), "evidence-support")
        self.assertEqual(gap.get("research_state"), "Por investigar")
        self.assertEqual(gap.get("support_requirement"), "CURRENT_PUBLIC_ONLY")
        self.assertTrue(gap.get("preserve_value"))

    def test_populated_fields_outside_schema_are_not_invisible(self) -> None:
        public = {
            "schemas": {"distributors": []},
            "distributors": [
                {
                    "id": "dist-test",
                    "name": "Distributor Test",
                    "fields": {
                        "orphan_one": {"value": "Value A", "evidence": []},
                        "orphan_two": {"value": "Value B", "evidence": []},
                    },
                }
            ],
        }
        report = build_gaps(public, research_state={})
        found = [
            gap for gap in report["gaps"]
            if gap.get("section") == "distributors"
            and gap.get("entity") == "Distributor Test"
            and gap.get("field") in {"orphan_one", "orphan_two"}
        ]
        self.assertEqual(len(found), 2)
        self.assertEqual({gap.get("field") for gap in found}, {"orphan_one", "orphan_two"})
        self.assertTrue(all(gap.get("gap_kind") == "evidence-support" for gap in found))
        self.assertTrue(all(gap.get("research_state") == "Por investigar" for gap in found))


if __name__ == "__main__":
    unittest.main()
