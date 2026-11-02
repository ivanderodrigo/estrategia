"""Regression guards for truthful research run outcomes and gap movement."""
from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SupervisorOutcomeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "scripts/research_supervisor.py").read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_research_failure_changes_exit_code(self):
        self.assertIn('if result.get("status") != "ok":', self.source)
        self.assertIn('exit_code = 1', self.source)
        self.assertIn('"research": result.get("status")', self.source)

    def test_idle_research_with_backlog_is_not_success(self):
        self.assertIn('result["status"] = "no-research-work"', self.source)
        self.assertIn('int(previous_gap_count or 0) > 0', self.source)
        self.assertIn('int(result.get("fetch_attempts") or 0) == 0', self.source)
        self.assertIn('int(result.get("search_queries_attempted") or 0) == 0', self.source)

    def test_gap_delta_uses_immediately_previous_quality_report(self):
        self.assertIn('previous_quality = read_json("data/current/quality_report.json", {})', self.source)
        self.assertIn('"gaps_delta_vs_previous_run"', self.source)
        self.assertIn('"gaps_closed_vs_previous_run"', self.source)
        self.assertIn('previous_gap_count - after["gaps_total"]', self.source)


if __name__ == "__main__":
    unittest.main()
