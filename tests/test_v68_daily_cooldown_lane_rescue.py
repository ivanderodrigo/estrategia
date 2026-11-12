"""v6.8: prevent all-public-client research when strategic areas are in cooldown."""
import unittest
from unittest.mock import patch

from engine.research.web_intelligence import _rescue_missing_research_sections, _fair_target_order


def target(section, number, fields=None):
    return {
        "section": section, "entity": f"{section}-{number}",
        "task_entity_key": f"{section}-{number}",
        "fields": fields or ["vendor_relations"],
        "priority": 100 - number,
        "gap_ids": [f"gap-{section}-{number}"],
        "gap_kinds": ["evidence-support"],
    }


class ResearchCooldownLaneCoverage(unittest.TestCase):
    @patch("engine.research.web_intelligence.read_json")
    @patch("engine.research.web_intelligence.plan")
    def test_missing_sections_receive_capped_daily_research(self, planner, json_reader):
        json_reader.return_value = {"entries": [
            {"name": "distributors-1", "url": "https://example.org/vendors"}
        ]}
        due = [target("clients_public", i, ["technology_signals"]) for i in range(160)]
        pool = (
            [target("clients_public", i, ["technology_signals"]) for i in range(200)]
            + [target("distributors", i) for i in range(18)]
            + [target("integrators", i) for i in range(10)]
            + [target("manufacturers", i) for i in range(8)]
            + [target("clients_private", i) for i in range(5)]
            + [target("trends", i) for i in range(5)]
            + [target("architectures", i) for i in range(5)]
        )
        planner.return_value = pool
        chosen, rescue = _rescue_missing_research_sections(
            due, {}, {}, "daily"
        )
        self.assertEqual(len(chosen), 160)
        self.assertEqual(rescue["distributors"], 12)
        self.assertEqual(rescue["integrators"], 5)
        self.assertEqual(rescue["manufacturers"], 4)
        self.assertEqual(rescue["clients_private"], 3)
        self.assertEqual(rescue["trends"], 3)
        self.assertEqual(rescue["architectures"], 3)
        self.assertEqual(chosen[0]["entity"], "distributors-1")
        self.assertEqual(len({(x["section"], x["entity"]) for x in chosen}), 160)
        self.assertEqual(
            {x["section"] for x in _fair_target_order(chosen[:15])},
            {"distributors", "integrators"},
        )
        planner.assert_called_once()

    @patch("engine.research.web_intelligence.plan")
    def test_no_cooldown_override_when_all_lanes_are_due(self, planner):
        sections = [
            "distributors", "integrators", "manufacturers",
            "clients_private", "trends", "architectures"
        ]
        due = [target(section, 1) for section in sections]
        chosen, rescue = _rescue_missing_research_sections(due, {}, {}, "daily")
        self.assertEqual(chosen, due)
        self.assertEqual(rescue, {})
        planner.assert_not_called()

    @patch("engine.research.web_intelligence.plan")
    def test_deep_and_targeted_revalidation_unchanged(self, planner):
        due = [target("clients_public", 0)]
        for profile, kwargs in [
            ("deep", {}), ("daily", {"include_gap_kinds": {"public-validation"}}),
        ]:
            with self.subTest(profile=profile):
                chosen, rescue = _rescue_missing_research_sections(
                    due, {}, {}, profile, **kwargs
                )
                self.assertEqual(chosen, due)
                self.assertEqual(rescue, {})
        planner.assert_not_called()

    @patch("engine.research.web_intelligence.read_json")
    @patch("engine.research.web_intelligence.plan")
    def test_non_linecard_distributor_tasks_do_not_count_as_linecard_research(self, planner, json_reader):
        json_reader.return_value = {"entries": []}
        planner.return_value = [
            target("distributors", 0, ["revenue"]),
            target("distributors", 1, ["vendor_relations"]),
            target("clients_private", 2, ["recent_signals"]),
        ]
        chosen, rescue = _rescue_missing_research_sections(
            [target("clients_public", i) for i in range(25)], {}, {}, "daily",
            max_tasks=25,
        )
        self.assertEqual(rescue.get("distributors"), 1)
        self.assertTrue(any(x["entity"] == "distributors-1" for x in chosen))
        self.assertFalse(any(x["entity"] == "distributors-0" for x in chosen))


if __name__ == "__main__":
    unittest.main()
