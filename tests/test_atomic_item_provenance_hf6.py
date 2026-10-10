from __future__ import annotations

import unittest
from copy import deepcopy
from unittest.mock import patch

from engine.enrichment import merge_field, normalize_fields, project_graph_to_views
from engine.graph import build_graph
from engine.preservation import _relationship_is_hard_protected, restore_research_seed_support
from engine.provenance import (
    evidence_for_item,
    evidence_for_relationship,
    evidence_scopes,
    infer_scope_from_text,
)
from engine.quality import audit as quality_audit
from engine.research.documents import Document
from engine.research.extractors import Candidate
from engine.research.sources import SourceSeed
from engine.research.web_intelligence import _candidate_items


def exact_evidence(owner="Ignition Technology", value="Claroty", scope="GLOBAL"):
    return {
        "source": "ignition-technology.com",
        "title": f"{owner} · {value}",
        "description": f"{owner} distributes {value}.",
        "url": "https://www.ignition-technology.com/vendors/claroty",
        "scope": scope,
        "scope_provenance": "explicit-text" if scope != "GLOBAL" else "unspecified",
        "official": True,
    }


def wrong_evidence():
    return {
        "source": "Ignition Technology",
        "title": "Our Vendors",
        "description": "CrowdStrike expanded its partnership with Ignition Technology to Spain and Portugal in 2025.",
        "url": "https://www.ignition-technology.com/vendors/",
        "scope": "IBERIA",
        "official": True,
    }


class AtomicItemProvenanceHF6(unittest.TestCase):
    def test_claroty_cannot_inherit_crowdstrike_catalogue_evidence(self):
        self.assertEqual(
            evidence_for_relationship([wrong_evidence()], "Ignition Technology", "Claroty"),
            [],
        )

    def test_exact_relationship_is_accepted(self):
        ev = exact_evidence()
        self.assertEqual(
            evidence_for_relationship([ev], "Ignition Technology", "Claroty"),
            [ev],
        )

    def test_atomic_metadata_is_an_exact_binding(self):
        ev = {
            "source": "ignition-technology.com",
            "title": "Our Vendors",
            "description": "Selected cybersecurity vendors.",
            "url": "https://www.ignition-technology.com/vendors/",
            "researched_entity": "Ignition Technology",
            "item_value": "Claroty",
            "field": "vendor_relations",
            "atomic": True,
            "source_binding": "atomic-item",
        }
        self.assertEqual(
            evidence_for_item(
                [ev], "Ignition Technology", "Claroty", field_id="vendor_relations"
            ),
            [ev],
        )
        self.assertEqual(
            evidence_for_relationship([ev], "Ignition Technology", "CrowdStrike"),
            [],
        )

    def test_merge_field_does_not_fallback_for_explicit_empty_item(self):
        crowd = {
            **wrong_evidence(),
            "researched_entity": "Ignition Technology",
            "item_value": "CrowdStrike",
            "field": "vendor_relations",
            "atomic": True,
            "source_binding": "atomic-item",
        }
        field = merge_field(
            None,
            {
                "value": ["Claroty", "CrowdStrike"],
                "evidence": [crowd],
                "items": [
                    {"value": "Claroty", "evidence": []},
                    {"value": "CrowdStrike", "evidence": [crowd]},
                ],
                "confidence": 0.88,
                "claim_type": "fact",
                "assertion_status": "CONFIRMADO",
            },
        )
        items = {item["value"]: item for item in field["items"]}
        self.assertEqual(items["Claroty"]["evidence"], [])
        self.assertTrue(items["CrowdStrike"]["evidence"])

    def test_normalizer_removes_single_wrong_source_bypass(self):
        bad = wrong_evidence()
        data = {
            "distributors": [{
                "name": "Ignition Technology",
                "fields": {
                    "vendor_relations": {
                        "value": ["Claroty"],
                        "evidence": [bad],
                        "items": [{"value": "Claroty", "evidence": [bad]}],
                    }
                },
            }]
        }
        normalize_fields(data)
        item = data["distributors"][0]["fields"]["vendor_relations"]["items"][0]
        self.assertEqual(item["evidence"], [])

    def test_graph_refuses_wrong_edge(self):
        data = {
            "manufacturers": [{"name": "Claroty", "fields": {}}],
            "distributors": [{
                "name": "Ignition Technology",
                "fields": {
                    "vendor_relations": {
                        "value": ["Claroty"],
                        "items": [{"value": "Claroty", "evidence": [wrong_evidence()]}],
                    }
                },
            }],
            "integrators": [],
            "clients_public": [],
            "clients_private": [],
            "trends": [],
            "architectures": [],
        }
        with patch("engine.graph.read_json", return_value={"relationships": []}):
            graph = build_graph(data)
        self.assertFalse(any(rel.get("relation") == "distributes" for rel in graph["relationships"]))

    def test_preservation_does_not_hard_protect_wrong_edge(self):
        bad = {
            "entity_a": "Ignition Technology",
            "relation": "distributes",
            "entity_b": "Claroty",
            "status": "CONFIRMADO",
            "validity": "current",
            "confidence": 0.9,
            "evidence": [wrong_evidence()],
        }
        good = deepcopy(bad)
        good["evidence"] = [exact_evidence()]
        self.assertFalse(_relationship_is_hard_protected(bad))
        self.assertTrue(_relationship_is_hard_protected(good))

    def test_scope_comes_from_evidence_not_target_row(self):
        self.assertEqual(infer_scope_from_text("Available in Spain and Portugal"), "IBERIA")
        self.assertEqual(infer_scope_from_text("Global vendor programme"), "GLOBAL")
        ev = exact_evidence(scope="ES")
        ev["description"] = "Ignition Technology distributes Claroty in Spain."
        self.assertEqual(evidence_scopes([ev]), ["ES"])

    def test_global_edge_does_not_populate_manufacturer_iberia_column(self):
        data = {
            "manufacturers": [{
                "name": "Claroty",
                "fields": {
                    "distributors": {
                        "value": ["Stale Distributor"],
                        "items": [{"value": "Stale Distributor", "evidence": [exact_evidence()]}],
                    }
                },
            }],
            "distributors": [{"name": "Ignition Technology", "fields": {}}],
            "integrators": [],
        }
        graph = {
            "relationships": [{
                "entity_a": "Ignition Technology",
                "relation": "distributes",
                "entity_b": "Claroty",
                "status": "CONFIRMADO",
                "countries": ["GLOBAL"],
                "country": "GLOBAL",
                "confidence": 0.9,
                "evidence": [exact_evidence()],
            }]
        }
        project_graph_to_views(data, graph)
        self.assertNotIn("distributors", data["manufacturers"][0]["fields"])

    def test_iberia_edge_populates_manufacturer_column(self):
        ev = exact_evidence(scope="IBERIA")
        ev["description"] = "Ignition Technology distributes Claroty in Spain and Portugal."
        data = {
            "manufacturers": [{"name": "Claroty", "fields": {}}],
            "distributors": [{"name": "Ignition Technology", "fields": {}}],
            "integrators": [],
        }
        graph = {
            "relationships": [{
                "entity_a": "Ignition Technology",
                "relation": "distributes",
                "entity_b": "Claroty",
                "status": "CONFIRMADO",
                "countries": ["IBERIA"],
                "country": "IBERIA",
                "confidence": 0.9,
                "evidence": [ev],
            }]
        }
        project_graph_to_views(data, graph)
        self.assertEqual(
            data["manufacturers"][0]["fields"]["distributors"]["value"],
            ["Ignition Technology"],
        )

    def test_candidate_values_receive_separate_evidence(self):
        filler = " unrelated filler " * 40
        document = Document(
            url="https://www.ignition-technology.com/vendors/",
            title="Ignition Technology Our Vendors",
            text=(
                "Ignition Technology lists Claroty as a cybersecurity vendor."
                + filler
                + "CrowdStrike expanded with Ignition Technology in Spain and Portugal."
            ),
            links=(),
            content_digest="hf6",
        )
        candidate = Candidate(
            ("Claroty", "CrowdStrike"),
            "fact",
            0.9,
            "shared snippet must not be reused",
            ("Claroty", "CrowdStrike"),
        )
        seed = SourceSeed(
            document.url, "partners", True, "A", "official-domain", "Ignition Technology"
        )
        items = _candidate_items(
            seed, document, "vendor_relations", candidate, "Ignition Technology", "IBERIA"
        )
        claroty_ev = items[0]["evidence"][0]
        crowd_ev = items[1]["evidence"][0]
        self.assertEqual(claroty_ev["item_value"], "Claroty")
        self.assertEqual(crowd_ev["item_value"], "CrowdStrike")
        self.assertIn("claroty", claroty_ev["description"].casefold())
        self.assertNotIn("crowdstrike", claroty_ev["description"].casefold())
        self.assertEqual(claroty_ev["scope"], "GLOBAL")
        self.assertEqual(crowd_ev["scope"], "IBERIA")

    def test_atomic_westcon_document_lineage_survives_normalization(self):
        document = {
            "source": "Westcon Comstor España",
            "title": "FY27 · slide 29",
            "url": "",
            "date": "FY2027",
            "description": "Documento corporativo Westcon.",
            "scope": "ES",
            "source_grade": "A-WESTCON",
            "source_type": "westcon-document",
            "document_id": "westcon-corporate-fy27",
            "document": "Westcon_Comstor_Espana_FY27_completa.pptx",
            "slide": 29,
            "field": "capabilities",
            "item_value": "Password Management",
            "atomic": True,
            "provenance_origin": "WESTCON_DOCUMENT",
        }
        data = {
            "manufacturers": [{
                "name": "1Password",
                "fields": {
                    "capabilities": {
                        "value": ["Password Management"],
                        "items": [{"value": "Password Management", "evidence": [document]}],
                        "evidence": [],
                    }
                },
            }]
        }
        normalize_fields(data)
        item = data["manufacturers"][0]["fields"]["capabilities"]["items"][0]
        self.assertTrue(item["evidence"])
        kept = item["evidence"][0]
        # Normalization is allowed to enrich the evidence with freshness/retrieval
        # metadata. The invariant is that the same typed Westcon documentary
        # lineage survives on the same exact item.
        for key in (
            "source_type", "document_id", "document", "slide",
            "field", "item_value", "provenance_origin",
        ):
            self.assertEqual(kept.get(key), document.get(key))
        self.assertEqual(kept.get("url") or "", "")

    def test_research_seed_survives_qualified_linecard_variant(self):
        seed = {
            "source": "Internal memory",
            "title": "Partner clue",
            "date": "baseline",
            "description": "research clue only",
            "source_type": "research-seed",
            "provenance_origin": "RESEARCH_SEED",
            "source_binding": "discovery-only",
            "classification": "research-seed",
            "accrediting": False,
        }
        before = {
            "integrators": [{
                "id": "partner-a",
                "name": "Partner A",
                "fields": {
                    "vendor_relations": {
                        "value": ["Fortinet · Expert"],
                        "items": [{"value": "Fortinet · Expert", "evidence": [seed]}],
                    }
                },
            }]
        }
        after = {
            "integrators": [{
                "id": "partner-a",
                "name": "Partner A",
                "fields": {
                    "vendor_relations": {
                        "value": ["Fortinet · Expert / Advanced"],
                        "items": [{"value": "Fortinet · Expert / Advanced", "evidence": []}],
                    }
                },
            }]
        }
        stats = restore_research_seed_support(after, before)
        evidence = after["integrators"][0]["fields"]["vendor_relations"]["items"][0]["evidence"]
        self.assertGreaterEqual(stats["linecard_seed_rows_restored"], 1)
        self.assertTrue(any(ev.get("provenance_origin") == "RESEARCH_SEED" for ev in evidence))

    def test_quality_gate_detects_cross_item_evidence(self):
        data = {
            "schemas": {"distributors": [{"id": "vendor_relations"}]},
            "manufacturers": [{"name": "Claroty", "fields": {}}],
            "distributors": [{
                "name": "Ignition Technology",
                "fields": {
                    "vendor_relations": {
                        "value": ["Claroty"],
                        "items": [{"value": "Claroty", "evidence": [wrong_evidence()]}],
                        "evidence": [wrong_evidence()],
                        "claim_type": "fact",
                    }
                },
            }],
            "integrators": [],
            "clients_public": [],
            "clients_private": [],
            "trends": [],
            "architectures": [],
        }
        graph = {
            "relationships": [{
                "id": "bad-edge",
                "entity_a_id": "ignition",
                "entity_a": "Ignition Technology",
                "relation": "distributes",
                "entity_b_id": "claroty",
                "entity_b": "Claroty",
                "evidence": [wrong_evidence()],
            }]
        }
        report = quality_audit(data, graph, {"gaps": [], "total_gaps": 0})
        blob = "\n".join(report["errors"])
        self.assertIn("Evidencia atómica mal asociada", blob)
        self.assertIn("Relación con evidencia mal asociada", blob)


if __name__ == "__main__":
    unittest.main()
