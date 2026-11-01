"""Regression: discovery budget must exist before processing any research target."""
from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ResearchBudgetInitializationTests(unittest.TestCase):
    def test_query_budget_is_initialized_before_target_iteration(self):
        source = (ROOT / "engine/research/web_intelligence.py").read_text(encoding="utf-8")
        module = ast.parse(source)
        run = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "run")
        target_loop = next(
            node for node in run.body
            if isinstance(node, ast.For) and isinstance(node.target, ast.Name)
            and node.target.id == "target" and isinstance(node.iter, ast.Name)
            and node.iter.id == "targets"
        )
        prior = [
            node for node in run.body if isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "query_budget" for t in node.targets)
            and node.lineno < target_loop.lineno
        ]
        self.assertTrue(prior, "query_budget must be set before looping over research targets")


if __name__ == "__main__":
    unittest.main()
