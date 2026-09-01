from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RelationshipRevalidationV405(unittest.TestCase):
    def _registry(self):
        return json.loads(
            (ROOT / "config/current/relationship_revalidation_registry.json").read_text(encoding="utf-8")
        )

    def test_relationship_registry_exists_and_is_nonempty(self) -> None:
        data = self._registry()
        self.assertGreater(data.get("candidates_total", 0), 0)

    def test_registry_counters_are_explicit_from_creation(self) -> None:
        data = self._registry()
        self.assertIn("supported_current_open", data)
        self.assertIn("search_required", data)
        self.assertEqual(
            data.get("candidates_total"),
            int(data.get("supported_current_open") or 0) + int(data.get("search_required") or 0),
        )

    def test_every_candidate_has_url_seed(self) -> None:
        data = self._registry()
        for row in data.get("candidates") or []:
            self.assertTrue(row.get("revalidation_seeds"))
            self.assertTrue(
                any(
                    str(seed.get("url") or "").startswith(("http://", "https://"))
                    for seed in row.get("revalidation_seeds") or []
                )
            )

    def test_relationship_debt_is_separate_from_main_gap_kpi(self) -> None:
        gaps = json.loads(
            (ROOT / "data/current/research_gaps.json").read_text(encoding="utf-8")
        )
        debt = gaps.get("relationship_revalidation_debt") or []
        self.assertGreater(len(debt), 0)
        self.assertEqual(
            len(debt),
            gaps.get("relationship_revalidation_debt_total"),
        )
        self.assertTrue(
            all(
                row.get("gap_kind") == "historical-relationship-revalidation"
                for row in debt
            )
        )

    def test_current_graph_does_not_count_pending_h_relationships(self) -> None:
        registry = self._registry()
        graph = json.loads(
            (ROOT / "data/current/relationship_graph.json").read_text(encoding="utf-8")
        )
        visible = {
            (
                str(r.get("entity_a") or "").casefold(),
                str(r.get("relation") or "").casefold(),
                str(r.get("entity_b") or "").casefold(),
            )
            for r in graph.get("relationships") or []
        }
        for row in registry.get("candidates") or []:
            if row.get("revalidation_status") == "supported-by-current-open-source":
                continue
            key = (
                str(row.get("entity") or "").casefold(),
                str(row.get("relation") or "").casefold(),
                str(row.get("entity_b") or "").casefold(),
            )
            self.assertNotIn(key, visible)


if __name__ == "__main__":
    unittest.main()
