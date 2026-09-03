from __future__ import annotations

import unittest

from engine.research.planner import plan


class PlannerCompatibilityV420(unittest.TestCase):
    def _gap(self, gap_id: str, kind: str, *, section: str = "integrators", field: str = "vendor_relations"):
        return {
            "id": gap_id,
            "section": section,
            "entity": f"Entity {gap_id}",
            "entity_id": gap_id,
            "field": field,
            "gap_kind": kind,
            "priority": 1,
            "research_state": "Por investigar",
            "priority_score": 80,
            "priority_tier": "P0",
        }

    def test_include_gap_kinds_remains_supported(self):
        gaps = {"gaps": [self._gap("e", "evidence-support"), self._gap("s", "standard")]}
        tasks = plan(gaps, {"families": {}}, "daily", max_tasks=10, include_gap_kinds={"evidence-support"})
        self.assertTrue(tasks)
        self.assertTrue(all(set(task["gap_kinds"]) == {"evidence-support"} for task in tasks))

    def test_derivation_support_never_enters_web_plan(self):
        gaps = {"gaps": [self._gap("d", "derivation-support"), self._gap("s", "standard")]}
        tasks = plan(gaps, {"families": {}}, "daily", max_tasks=10)
        kinds = {kind for task in tasks for kind in task.get("gap_kinds") or []}
        self.assertNotIn("derivation-support", kinds)
        self.assertIn("standard", kinds)

    def test_historical_relationship_debt_remains_routable(self):
        historical = self._gap("h", "historical-relationship-revalidation")
        historical["revalidation_seeds"] = [{"url": "https://example.com/partner", "official": True}]
        gaps = {"gaps": [], "relationship_revalidation_debt": [historical]}
        tasks = plan(gaps, {"families": {}}, "daily", max_tasks=10)
        self.assertEqual(len(tasks), 1)
        self.assertIn("historical-relationship-revalidation", tasks[0]["gap_kinds"])
        self.assertEqual(tasks[0]["revalidation_seeds"][0]["url"], "https://example.com/partner")

    def test_legacy_and_v42_target_value_contracts_coexist(self):
        gap = self._gap("v", "public-validation")
        gap["target_values"] = ["Palo Alto Networks"]
        gap["source_family"] = "partners"
        gap["source_strategy"] = {"preferred_families": ["partners", "official"], "query_hints": ["Entity v Palo Alto"]}
        tasks = plan({"gaps": [gap]}, {"families": {}}, "daily", max_tasks=10)
        self.assertEqual(tasks[0]["target_values"]["vendor_relations"], ["Palo Alto Networks"])
        self.assertEqual(tasks[0]["target_values_by_field"]["vendor_relations"], ["Palo Alto Networks"])
        self.assertIn("partners", tasks[0]["source_families"])


if __name__ == "__main__":
    unittest.main()
