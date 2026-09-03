from __future__ import annotations

import unittest

from engine.confidence import profile
from engine.gap_intelligence import annotate_gap
from engine.research.planner import plan
from engine.research.sources import relevant_families


class OpportunityAwarePriorityV421(unittest.TestCase):
    def _public(self):
        return {
            "schemas": {
                "clients_public": [
                    {"id": "technology_signals", "decision_required": True},
                    {"id": "request_or_need", "decision_required": True},
                    {"id": "estimated_amount"},
                    {"id": "procurement_stage", "decision_required": True},
                    {"id": "milestone_date"},
                ]
            },
            "clients_public": [
                {
                    "id": "notice-a",
                    "name": "Entidad Pública",
                    "fields": {
                        "notice_id": {"value": "EXP-2026-001"},
                        "source_portal": {"value": "https://contratacion.example/EXP-2026-001"},
                        "request_or_need": {"value": "Renovación de ciberseguridad y red"},
                        "technology_signals": {"value": ["SASE", "NGFW"]},
                        "estimated_amount": {"value": 1500000},
                        "procurement_stage": {"value": "Abierto"},
                        "milestone_date": {"value": "2099-12-31"},
                    },
                },
                {
                    "id": "notice-b",
                    "name": "Entidad Pública",
                    "fields": {
                        "notice_id": {"value": "EXP-2026-002"},
                    },
                },
            ],
        }

    def test_actionable_public_tender_can_reach_p0_p1_without_section_quota(self):
        public = self._public()
        gap = {
            "id": "g1", "section": "clients_public", "entity": "Entidad Pública", "entity_id": "notice-a",
            "field": "technology_signals", "priority": 1, "research_state": "Por investigar", "gap_kind": "standard",
        }
        annotate_gap(gap, public)
        self.assertIn(gap["priority_tier"], {"P0", "P1"})
        self.assertGreater(gap["opportunity_context_multiplier"], 1.20)
        self.assertEqual(gap["source_family"], "procurement")

    def test_low_context_public_gap_is_not_promoted_artificially(self):
        public = self._public()
        gap = {
            "id": "g2", "section": "clients_public", "entity": "Entidad Pública", "entity_id": "notice-b",
            "field": "technology_signals", "priority": 1, "research_state": "Por investigar", "gap_kind": "standard",
        }
        annotate_gap(gap, public)
        self.assertIn(gap["priority_tier"], {"P2", "P3"})
        self.assertLessEqual(gap["opportunity_context_multiplier"], 1.10)

    def test_public_procurement_technology_routes_to_procurement_sources(self):
        self.assertIn("procurement", relevant_families(["technology_signals"], section="clients_public"))
        self.assertNotIn("procurement", relevant_families(["technology_signals"], section="clients_private"))

    def test_same_buyer_name_with_two_notice_ids_stays_two_research_tasks(self):
        public = self._public()
        gaps = []
        for suffix in ("a", "b"):
            gap = {
                "id": f"g-{suffix}", "section": "clients_public", "entity": "Entidad Pública", "entity_id": f"notice-{suffix}",
                "field": "technology_signals", "priority": 1, "research_state": "Por investigar", "gap_kind": "standard",
            }
            annotate_gap(gap, public)
            gaps.append(gap)
        tasks = plan({"gaps": gaps}, {"families": {}}, "daily", max_tasks=10)
        public_tasks = [task for task in tasks if task["section"] == "clients_public"]
        self.assertEqual(len(public_tasks), 2)
        self.assertEqual({task["entity_id"] for task in public_tasks}, {"notice-a", "notice-b"})

    def test_missing_confidence_requires_public_evidence_only(self):
        result = profile([])
        message = result["details"]["missing_for_upgrade"]
        self.assertIn("fuente pública", message)
        self.assertNotIn("Westcon", message)
        self.assertNotIn("documentación", message.casefold())


if __name__ == "__main__":
    unittest.main()
