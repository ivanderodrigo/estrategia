from __future__ import annotations

import unittest

from engine.research.planner import plan


class EvidenceOnlyPilotRoutingV406(unittest.TestCase):
    def _gaps(self):
        return {
            "gaps": [
                {
                    "id": "external-1",
                    "section": "manufacturers",
                    "entity": "1Password",
                    "entity_id": "1password",
                    "field": "competitors",
                    "gap_kind": "evidence-support",
                    "priority": 1,
                    "target_values": ["Keeper"],
                    "revalidation_seeds": [],
                },
                {
                    "id": "standard-1",
                    "section": "manufacturers",
                    "entity": "Vendor X",
                    "entity_id": "vendor-x",
                    "field": "services",
                    "gap_kind": "standard",
                    "priority": 1,
                    "target_values": [],
                    "revalidation_seeds": [],
                },
                {
                    "id": "derived-1",
                    "section": "clients_public",
                    "entity": "Cliente X",
                    "entity_id": "cliente-x",
                    "field": "westcon_fit",
                    "gap_kind": "derivation-support",
                    "priority": 1,
                    "target_values": ["Networking"],
                    "revalidation_seeds": [],
                },
            ],
            "relationship_revalidation_debt": [
                {
                    "id": "rel-1",
                    "section": "clients_public",
                    "entity": "Cliente Y",
                    "entity_id": "cliente-y",
                    "field": "technology_signal",
                    "gap_kind": "historical-relationship-revalidation",
                    "priority": 1,
                    "target_values": ["Cloud"],
                    "revalidation_seeds": [{"url": "https://example.com"}],
                }
            ],
        }

    def test_default_plan_keeps_normal_research_but_blocks_derivation(self):
        tasks = plan(self._gaps(), {}, "daily", max_tasks=50)
        kinds = {kind for t in tasks for kind in (t.get("gap_kinds") or [])}
        self.assertIn("evidence-support", kinds)
        self.assertIn("standard", kinds)
        self.assertIn("historical-relationship-revalidation", kinds)
        self.assertNotIn("derivation-support", kinds)

    def test_include_gap_kinds_can_isolate_evidence_support(self):
        tasks = plan(
            self._gaps(),
            {},
            "daily",
            max_tasks=50,
            include_gap_kinds={"evidence-support"},
        )
        self.assertTrue(tasks)
        kinds = {kind for t in tasks for kind in (t.get("gap_kinds") or [])}
        self.assertEqual(kinds, {"evidence-support"})
        self.assertTrue(
            all(
                set(t.get("gap_kinds") or []) == {"evidence-support"}
                for t in tasks
            )
        )


if __name__ == "__main__":
    unittest.main()
