
from __future__ import annotations

import copy
import unittest
from pathlib import Path

from engine.enrichment import normalize_fields
from engine.knowledge_provenance import typed_evidence_sufficient
from engine.preservation import snapshot


def foreign_ev(field: str) -> dict:
    return {
        "source": "ALSO",
        "source_catalog_name": "ALSO Spain Technology S.L.U.",
        "researched_entity": "V-Valley Advanced Solutions Portugal",
        "source_binding": "relationship-source",
        "title": "ALSO Cloud Marketplace",
        "url": "https://www.also.com/services/cloud",
        "date": "2026-10-11",
        "description": "ALSO ofrece soporte técnico y formación.",
        "official": True,
        "classification": "public",
        "source_type": "distributor-official",
        "method": "web-evidence:services",
        "field": field,
        "atomic": False,
    }


def good_ev(field: str, value: str) -> dict:
    return {
        "source": "v-valley.com",
        "source_catalog_name": "V-Valley Advanced Solutions Portugal",
        "researched_entity": "V-Valley Advanced Solutions Portugal",
        "source_binding": "atomic-item",
        "title": "Serviços | V-Valley",
        "url": "https://www.v-valley.com/pt/servicos/",
        "date": "2026-10-11",
        "description": "V-Valley presta suporte técnico especializado.",
        "official": True,
        "classification": "public",
        "source_type": "official-domain",
        "method": "web-evidence:services",
        "field": field,
        "item_value": value,
        "item_key": value.casefold(),
        "atomic": True,
    }


def data_with(field_id: str, evidences: list[dict]) -> dict:
    return {
        "schemas": {"distributors": [{"id": field_id}]},
        "manufacturers": [],
        "integrators": [],
        "clients_public": [],
        "clients_private": [],
        "trends": [],
        "architectures": [],
        "distributors": [{
            "id": "dist-vvalley-pt",
            "name": "V-Valley Advanced Solutions Portugal",
            "fields": {
                field_id: {
                    "value": ["Soporte"],
                    "items": [{
                        "value": "Soporte",
                        "evidence": copy.deepcopy(evidences),
                    }],
                    "evidence": copy.deepcopy(evidences),
                    "claim_type": "fact",
                }
            },
        }],
    }


class HF6R13R3FinalAtomicSanitation(unittest.TestCase):
    def test_foreign_fixture_is_typed_so_rejection_is_not_trivial(self):
        self.assertTrue(typed_evidence_sufficient(foreign_ev("services")))

    def test_good_fixture_is_typed_so_preservation_can_protect_it(self):
        self.assertTrue(typed_evidence_sufficient(good_ev("services", "Soporte")))

    def test_normalize_prunes_foreign_item_and_field_evidence(self):
        data = data_with(
            "services",
            [foreign_ev("services"), good_ev("services", "Soporte")],
        )
        normalize_fields(data)
        field = data["distributors"][0]["fields"]["services"]
        self.assertEqual(len(field["items"][0]["evidence"]), 1)
        self.assertEqual(field["items"][0]["evidence"][0]["source_binding"], "atomic-item")
        self.assertEqual(field["evidence"], field["items"][0]["evidence"])

    def test_only_foreign_evidence_is_removed_without_deleting_value(self):
        data = data_with("services", [foreign_ev("services")])
        normalize_fields(data)
        field = data["distributors"][0]["fields"]["services"]
        self.assertEqual(field["value"], ["Soporte"])
        self.assertEqual(field["items"][0]["evidence"], [])
        self.assertEqual(field["evidence"], [])

    def test_snapshot_does_not_protect_foreign_list_support(self):
        data = data_with("services", [foreign_ev("services")])
        snap = snapshot(data, {"relationships": []})
        self.assertEqual(snap["evidences"], [])

    def test_snapshot_keeps_exact_atomic_list_support(self):
        data = data_with("services", [good_ev("services", "Soporte")])
        snap = snapshot(data, {"relationships": []})
        self.assertEqual(len(snap["evidences"]), 1)

    def test_differential_capabilities_obeys_same_rule(self):
        data = data_with(
            "differential_capabilities",
            [
                foreign_ev("differential_capabilities"),
                good_ev("differential_capabilities", "Soporte"),
            ],
        )
        normalize_fields(data)
        field = data["distributors"][0]["fields"]["differential_capabilities"]
        self.assertEqual(len(field["evidence"]), 1)
        self.assertEqual(field["evidence"][0]["source_binding"], "atomic-item")

    def test_pipeline_has_final_normalize_after_westcon_apply(self):
        source = Path("engine/pipeline.py").read_text(encoding="utf-8")
        start = source.index("westcon_current_evidence = apply_westcon_current_evidence")
        final_norm = source.index("normalize_fields(data)", start)
        confidence = source.index("confidence_stats = apply_confidence_model(data)")
        self.assertLess(start, final_norm)
        self.assertLess(final_norm, confidence)


if __name__ == "__main__":
    unittest.main()
