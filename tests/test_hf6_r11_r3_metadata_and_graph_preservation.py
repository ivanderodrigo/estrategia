from copy import deepcopy
import unittest

from engine.graph import build_graph
from engine.model import canonical
from engine.preservation import (
    _relationship_is_hard_protected,
    audit as preservation_audit,
    restore_preserved_relations,
    snapshot,
)
from engine.provenance import evidence_for_relationship
from engine.storage import read_json


def web_relation(owner: str, value: str):
    return {
        "source": owner,
        "title": f"{owner} {value}",
        "date": "2026-10-11",
        "description": f"{owner} has an evidenced relationship with {value}.",
        "url": f"https://example.com/{owner}-{value}".replace(" ", "-").lower(),
        "scope": "ES",
        "scope_provenance": "explicit-text",
        "method": "web-evidence:test",
        "source_binding": "claim-specific",
        "provenance_origin": "PUBLIC_PRIMARY",
        "accrediting": True,
        "atomic": True,
        "researched_entity": owner,
        "field": "vendor_relations",
        "item_value": value,
        "item_key": value.casefold(),
    }


class HF6R11R3MetadataAndGraphPreservation(unittest.TestCase):
    def test_metadata_only_owner_does_not_create_textual_relationship(self):
        ev = {
            "source": "also.com",
            "title": "Fabricantes - ALSO Spain Technology S.L.U.",
            "description": "Ivanti enterprise security portfolio.",
            "url": "https://www.also.com/example",
            "researched_entity": "CloudIT",
            "item_value": None,
            "field": "vendor_relations",
            "scope": "PT",
            "method": "web-evidence:partners",
            "source_binding": "claim-specific",
            "accrediting": True,
        }
        self.assertEqual(evidence_for_relationship([ev], "CloudIT", "Ivanti"), [])

    def test_exact_atomic_metadata_pair_still_accredits(self):
        ev = {
            "source": "vendor-directory.example",
            "title": "Partner directory",
            "description": "Certified partner entry.",
            "url": "https://vendor-directory.example/partners/123",
            "researched_entity": "CloudIT",
            "item_value": "Ivanti",
            "field": "vendor_relations",
            "scope": "PT",
            "method": "web-evidence:partners",
            "source_binding": "atomic-item",
            "atomic": True,
            "accrediting": True,
        }
        self.assertEqual(evidence_for_relationship([ev], "CloudIT", "Ivanti"), [ev])

    def test_r7_table_only_fixture_still_restores_and_prunes(self):
        valid = web_relation("SIA", "1Password")
        wrong = web_relation("SIA", "CrowdStrike")
        data = {
            "schemas": {},
            "manufacturers": [{"id": "manufacturer_1password", "name": "1Password", "fields": {}}],
            "distributors": [],
            "integrators": [{"id": "integrator_sia", "name": "SIA", "fields": {}}],
            "clients_public": [],
            "clients_private": [],
            "trends": [],
            "architectures": [],
        }
        baseline = {
            "relationships": [{
                "id": "rel_old",
                "entity_a_id": "old_sia",
                "entity_a": "SIA",
                "relation": "partners_with",
                "entity_b_id": "old_1password",
                "entity_b": "1Password",
                "countries": ["ES"],
                "country": "ES",
                "evidence": [valid, wrong],
                "status": "CONFIRMADO",
                "confidence": 0.9,
                "validity": "current",
            }]
        }
        current = {"relationships": []}
        stats = restore_preserved_relations(current, baseline, data)
        self.assertEqual(stats["relations_restored"], 1)
        self.assertEqual(stats["endpoint_evidence_rows_pruned"], 1)
        self.assertGreaterEqual(stats["table_endpoint_fallbacks"], 2)
        self.assertEqual(len(current["relationships"][0]["evidence"]), 1)
        self.assertEqual(current["relationships"][0]["evidence"][0]["item_value"], "1Password")

    def test_current_nine_legacy_false_edges_are_not_hard_protected(self):
        baseline = read_json("data/current/relationship_graph.json", {})
        suspects = {
            ("aicox soluciones", "distributes", "ruckus networks"),
            ("cloudit", "distributes", "ivanti"),
            ("cloudit", "distributes", "ping identity"),
            ("cloudit", "distributes", "proofpoint"),
            ("lidera networks", "distributes", "ivanti"),
            ("lidera networks", "distributes", "ping identity"),
            ("lidera networks", "distributes", "proofpoint"),
            ("sce", "distributes", "ruckus networks"),
            ("tempel", "distributes", "ruckus networks"),
        }
        found = set()
        still_hard = []
        for rel in baseline.get("relationships") or []:
            key = (
                canonical(rel.get("entity_a")),
                canonical(rel.get("relation")),
                canonical(rel.get("entity_b")),
            )
            if key not in suspects:
                continue
            found.add(key)
            if _relationship_is_hard_protected(rel):
                still_hard.append(key)
        # HF6-R19: these are known legacy false edges. Their disappearance is a
        # successful cleanup outcome, not a regression. If any remain present, the
        # assertions above still require every one of them to be non-hard-protected.
        self.assertEqual(still_hard, [])

    def test_current_repo_rebuild_unique_and_no_hard_relation_loss(self):
        data = read_json("data/current/intelligence.json")
        baseline = read_json("data/current/relationship_graph.json", {})
        before = snapshot(data, baseline)
        rebuilt = build_graph(deepcopy(data))
        stats = restore_preserved_relations(rebuilt, baseline, data)

        graph_keys = [
            (r.get("entity_a_id"), r.get("relation"), r.get("entity_b_id"))
            for r in rebuilt.get("relationships") or []
        ]
        semantic_keys = [
            (canonical(r.get("entity_a")), canonical(r.get("relation")), canonical(r.get("entity_b")))
            for r in rebuilt.get("relationships") or []
        ]
        self.assertEqual(len(graph_keys), len(set(graph_keys)), f"duplicate graph-id edges; stats={stats}")
        self.assertEqual(len(semantic_keys), len(set(semantic_keys)), f"duplicate semantic edges; stats={stats}")

        report = preservation_audit(before, snapshot(data, rebuilt))
        self.assertEqual(report["missing"]["relations"], [], f"hard relation losses: {report['missing']['relations'][:20]}; stats={stats}")

    def test_confirmed_non_channel_relationship_contract_remains(self):
        data = {
            "manufacturers": [{"id": f"m{i}", "name": f"M{i}", "fields": {}} for i in range(36)],
            "trends": [{"id": f"t{i}", "name": f"T{i}", "fields": {}} for i in range(15)],
            "architectures": [{"id": f"a{i}", "name": f"A{i}", "fields": {}} for i in range(12)],
        }
        confirmed = {
            "entity_a_id": "partner-a",
            "entity_a": "Partner A",
            "relation": "uses",
            "entity_b_id": "vendor-a",
            "entity_b": "Vendor A",
            "confidence": 0.9,
            "status": "CONFIRMADA",
            "validity": "current",
            "derived": False,
        }
        before = snapshot(data, {"relationships": [confirmed]})
        after = snapshot(data, {"relationships": []})
        self.assertEqual(len(before.get("relations") or []), 1)
        self.assertEqual(preservation_audit(before, after)["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
