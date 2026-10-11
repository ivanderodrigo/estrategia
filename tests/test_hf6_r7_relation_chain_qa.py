from __future__ import annotations

from copy import deepcopy
import unittest

from engine.graph import build_graph
from engine.preservation import restore_preserved_relations
from engine.provenance import evidence_for_relationship
from engine.quality import audit
from engine.storage import read_json


def web_relation(owner: str, value: str, field: str = "vendor_relations", *, title: str = ""):
    return {
        "source": owner,
        "title": title or f"{owner} {value}",
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
        "field": field,
        "item_value": value,
        "item_key": value.casefold(),
    }


def base_data():
    return {
        "schemas": {},
        "manufacturers": [],
        "distributors": [],
        "integrators": [],
        "clients_public": [],
        "clients_private": [],
        "trends": [],
        "architectures": [],
    }


class HF6R7RelationChainQA(unittest.TestCase):
    def test_restore_preserved_relation_prunes_wrong_endpoint_evidence(self):
        valid = web_relation("SIA", "1Password")
        wrong = web_relation("SIA", "CrowdStrike")
        data = base_data()
        data["manufacturers"] = [{"id": "manufacturer_1password", "name": "1Password", "fields": {}}]
        data["integrators"] = [{"id": "integrator_sia", "name": "SIA", "fields": {}}]
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
        rel = current["relationships"][0]
        self.assertEqual(len(rel["evidence"]), 1)
        self.assertTrue(evidence_for_relationship(
            rel["evidence"], rel["entity_a"], rel["entity_b"]
        ))
        self.assertEqual(rel["evidence"][0]["item_value"], "1Password")

    def test_direct_relation_with_extra_wrong_web_row_still_fails_quality(self):
        valid = web_relation("SIA", "1Password")
        wrong = web_relation("SIA", "CrowdStrike")
        data = base_data()
        data["manufacturers"] = [{
            "name": "1Password",
            "fields": {
                "integrators": {
                    "value": ["SIA"],
                    "items": [{"value": "SIA", "evidence": [valid, wrong]}],
                    "evidence": [valid, wrong],
                }
            },
        }]
        result = audit(data, {"relationships": []}, {"gaps": []})
        self.assertTrue(
            any("Evidencia web mal asociada" in e for e in result["errors"]),
            result["errors"],
        )

    def test_distributor_competitor_overlap_accepts_two_leg_evidence_chain(self):
        linecard = web_relation("Arrow ECS", "Microsoft")
        competitive = web_relation("Check Point", "Microsoft", field="competitors")
        data = base_data()
        data["distributors"] = [{
            "name": "Arrow ECS",
            "fields": {
                "competitor_vendor_overlap": {
                    "value": ["Microsoft"],
                    "items": [{
                        "value": "Microsoft",
                        "evidence": [linecard, competitive],
                        "competes_with_westcon": ["Check Point"],
                        "competition_mapping_status": "EVIDENCIADO",
                    }],
                    "evidence": [linecard, competitive],
                }
            },
        }]
        result = audit(data, {"relationships": []}, {"gaps": []})
        bad = [
            e for e in result["errors"]
            if "competitor_vendor_overlap/Microsoft" in e
            and ("mal asociada" in e or "Metadata atómica cruzada" in e)
        ]
        self.assertFalse(bad, result["errors"])

    def test_distributor_competitor_overlap_rejects_unrelated_third_leg(self):
        linecard = web_relation("Arrow ECS", "Microsoft")
        competitive = web_relation("Check Point", "Microsoft", field="competitors")
        unrelated = web_relation("SIA", "CrowdStrike")
        data = base_data()
        data["distributors"] = [{
            "name": "Arrow ECS",
            "fields": {
                "competitor_vendor_overlap": {
                    "value": ["Microsoft"],
                    "items": [{
                        "value": "Microsoft",
                        "evidence": [linecard, competitive, unrelated],
                        "competes_with_westcon": ["Check Point"],
                    }],
                    "evidence": [linecard, competitive, unrelated],
                }
            },
        }]
        result = audit(data, {"relationships": []}, {"gaps": []})
        self.assertTrue(
            any("Evidencia web mal asociada" in e for e in result["errors"]),
            result["errors"],
        )

    def test_current_graph_reconciliation_has_only_endpoint_specific_channel_rows(self):
        data = read_json("data/current/intelligence.json")
        baseline = read_json("data/current/relationship_graph.json", {})
        rebuilt = build_graph(deepcopy(data))
        stats = restore_preserved_relations(rebuilt, baseline, data)
        bad = []
        for rel in rebuilt.get("relationships") or []:
            if rel.get("relation") not in {"distributes", "partners_with"}:
                continue
            for ev in rel.get("evidence") or []:
                if not evidence_for_relationship(
                    [ev], rel.get("entity_a"), rel.get("entity_b")
                ):
                    bad.append((
                        rel.get("entity_a"),
                        rel.get("relation"),
                        rel.get("entity_b"),
                        ev.get("title") or ev.get("source"),
                    ))
        self.assertFalse(bad[:20], f"bad endpoint evidence rows: {bad[:20]}; stats={stats}")


if __name__ == "__main__":
    unittest.main()
