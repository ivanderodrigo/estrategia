from __future__ import annotations

import unittest

from engine.gaps import build_gaps, validate_gap_state_contract
from engine.knowledge_provenance import provenance_kind
from engine.preservation import (
    restore_research_seed_support,
    snapshot,
    sync_research_seed_registry,
)


def seed(title="Historical clue"):
    return {
        "source": "Internal memory",
        "title": title,
        "date": "baseline",
        "description": "research clue only",
        "source_type": "research-seed",
        "provenance_origin": "RESEARCH_SEED",
        "source_binding": "discovery-only",
        "classification": "research-seed",
        "accrediting": False,
    }


def public():
    return {
        "source": "Vendor",
        "title": "Official",
        "date": "2026-09-02",
        "description": "public proof",
        "url": "https://vendor.example/sase",
        "official": True,
        "source_grade": "A2",
        "source_type": "official-vendor-web",
        "provenance_origin": "PUBLIC_PRIMARY",
    }


class PublicEvidenceMemoryHF8(unittest.TestCase):
    def base_data(self, evidence=None):
        evidence = list(evidence or [])
        return {
            "schemas": {
                "manufacturers": [
                    {"id": "capabilities", "label": "Capabilities", "decision_required": True}
                ]
            },
            "manufacturers": [{
                "id": "vendor-a",
                "name": "Vendor A",
                "fields": {
                    "capabilities": {
                        "value": ["SASE"],
                        "items": [{"value": "SASE", "evidence": evidence}],
                    }
                },
            }],
        }

    def test_seed_registry_preserves_detached_clue_without_accrediting(self):
        before = self.base_data([seed()])
        sync_research_seed_registry(before)
        before_snap = snapshot(before, {"relationships": []})

        after = self.base_data([])
        stats = sync_research_seed_registry(after, before)
        after_snap = snapshot(after, {"relationships": []})

        self.assertGreaterEqual(stats["registry_claims"], 1)
        self.assertEqual(before_snap["research_seed_claims"], after_snap["research_seed_claims"])
        record = after["research_seed_registry"][0]
        self.assertFalse(record["accrediting"])
        self.assertEqual(record["classification"], "research-seed")

    def test_seed_is_reattached_to_same_surviving_value(self):
        before = self.base_data([seed()])
        after = self.base_data([])
        stats = restore_research_seed_support(after, before)
        ev = after["manufacturers"][0]["fields"]["capabilities"]["items"][0]["evidence"]
        self.assertGreaterEqual(stats["total_seed_rows_restored"], 1)
        self.assertTrue(any(provenance_kind(row) == "RESEARCH_SEED" for row in ev))

    def test_linecard_seed_survives_qualified_variant_merge(self):
        before = {
            "integrators": [{
                "id": "partner-a", "name": "Partner A",
                "fields": {
                    "vendor_relations": {
                        "value": ["Fortinet · Expert"],
                        "items": [{"value": "Fortinet · Expert", "evidence": [seed("Partner clue")]}],
                    }
                },
            }]
        }
        after = {
            "integrators": [{
                "id": "partner-a", "name": "Partner A",
                "fields": {
                    "vendor_relations": {
                        "value": ["Fortinet · Expert / Advanced"],
                        "items": [{"value": "Fortinet · Expert / Advanced", "evidence": []}],
                    }
                },
            }]
        }
        stats = restore_research_seed_support(after, before)
        ev = after["integrators"][0]["fields"]["vendor_relations"]["items"][0]["evidence"]
        self.assertGreaterEqual(stats["linecard_seed_rows_restored"], 1)
        self.assertTrue(any(provenance_kind(row) == "RESEARCH_SEED" for row in ev))

    def test_seed_does_not_recreate_deleted_value(self):
        before = self.base_data([seed()])
        after = self.base_data([])
        field = after["manufacturers"][0]["fields"]["capabilities"]
        field["value"] = []
        field["items"] = []
        stats = restore_research_seed_support(after, before)
        self.assertEqual(stats["total_seed_rows_restored"], 0)
        self.assertEqual(field["value"], [])

    def test_public_validation_has_distinct_state_and_contract(self):
        data = self.base_data([seed()])
        sync_research_seed_registry(data)
        report = build_gaps(data, "4.1.0", {})
        matches = [gap for gap in report["gaps"] if gap.get("gap_kind") == "public-validation"]
        self.assertTrue(matches)
        self.assertTrue(all(gap.get("research_state") == "Pendiente de validación pública" for gap in matches))
        self.assertEqual(validate_gap_state_contract(report), [])

    def test_public_evidence_closes_seed_validation_gap(self):
        data = self.base_data([seed(), public()])
        sync_research_seed_registry(data)
        report = build_gaps(data, "4.1.0", {})
        matches = [
            gap for gap in report["gaps"]
            if gap.get("entity") == "Vendor A" and gap.get("field") == "capabilities"
        ]
        self.assertFalse(matches)
        self.assertEqual(validate_gap_state_contract(report), [])

    def test_gap_state_contract_rejects_mismatched_public_state(self):
        report = {
            "public_validation_gaps": 1,
            "gaps": [{"id": "x", "gap_kind": "public-validation", "research_state": "Por investigar"}],
        }
        self.assertTrue(validate_gap_state_contract(report))


if __name__ == "__main__":
    unittest.main()
