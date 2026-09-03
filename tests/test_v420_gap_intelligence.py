from __future__ import annotations

import unittest

from engine.gap_intelligence import annotate_gap, enrich_gap_report
from engine.research.planner import plan


class GapIntelligenceV420(unittest.TestCase):
    def setUp(self):
        self.public = {
            "schemas": {
                "integrators": [
                    {"id": "vendor_relations", "decision_required": True},
                    {"id": "services", "decision_required": True},
                ],
                "clients_public": [
                    {"id": "entity_type"},
                    {"id": "technology_signals", "decision_required": True},
                ],
            },
            "integrators": [{"id": "i1", "name": "Integrator 1"}],
            "clients_public": [{"id": "p1", "name": "Public 1"}],
        }

    def test_channel_relation_outranks_low_value_public_completeness(self):
        high = {
            "id": "h", "section": "integrators", "entity": "Integrator 1", "entity_id": "i1",
            "field": "vendor_relations", "priority": 1, "research_state": "Por investigar",
            "gap_kind": "standard", "consecutive_no_yield": 0,
        }
        low = {
            "id": "l", "section": "clients_public", "entity": "Public 1", "entity_id": "p1",
            "field": "entity_type", "priority": 2, "research_state": "Por investigar",
            "gap_kind": "standard", "consecutive_no_yield": 0,
        }
        annotate_gap(high, self.public)
        annotate_gap(low, self.public)
        self.assertGreater(high["priority_score"], low["priority_score"])
        self.assertIn(high["priority_tier"], {"P0", "P1"})
        self.assertIn(low["priority_tier"], {"P2", "P3"})

    def test_public_validation_gets_exact_source_playbook(self):
        gap = {
            "id": "pv", "section": "integrators", "entity": "Integrator 1", "entity_id": "i1",
            "field": "vendor_relations", "priority": 1, "research_state": "Pendiente de validación pública",
            "gap_kind": "public-validation", "target_values": ["Palo Alto Networks"],
            "historical_lineage_present": True,
            "revalidation_seeds": [{"url": "https://example.com/partners", "official": True}],
        }
        annotate_gap(gap, self.public)
        self.assertEqual(gap["source_family"], "partners")
        self.assertTrue(gap["source_strategy"]["query_hints"])
        self.assertGreater(gap["researchability_score"], 80)

    def test_report_has_business_weighted_coverage_and_tiers(self):
        gaps = [{
            "id": "h", "section": "integrators", "entity": "Integrator 1", "entity_id": "i1",
            "field": "vendor_relations", "priority": 1, "research_state": "Por investigar", "gap_kind": "standard",
        }]
        summary = enrich_gap_report(gaps, self.public)
        self.assertIn("business_weighted_coverage_pct", summary)
        self.assertEqual(sum(summary["tiers"].values()), 1)

    def test_planner_prevents_public_clients_from_monopolising_bounded_run(self):
        gaps = []
        for i in range(40):
            gap = {
                "id": f"p{i}", "section": "clients_public", "entity": f"Public {i}", "entity_id": f"p{i}",
                "field": "technology_signals", "priority": 1, "research_state": "Por investigar", "gap_kind": "standard",
            }
            annotate_gap(gap, self.public)
            gaps.append(gap)
        for i in range(12):
            gap = {
                "id": f"i{i}", "section": "integrators", "entity": f"Integrator {i}", "entity_id": f"i{i}",
                "field": "vendor_relations", "priority": 1, "research_state": "Por investigar", "gap_kind": "standard",
            }
            annotate_gap(gap, self.public)
            gaps.append(gap)
        tasks = plan({"gaps": gaps}, {"families": {}}, "daily", max_tasks=20)
        public_count = sum(1 for task in tasks if task["section"] == "clients_public")
        integrator_count = sum(1 for task in tasks if task["section"] == "integrators")
        self.assertGreater(integrator_count, 0)
        self.assertLess(public_count, 20)


if __name__ == "__main__":
    unittest.main()
