"""Contract: a compact, inspectable diagnostic accompanies the complete gap audit."""
from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parents[1]

class DebtDiagnosticPublicationTests(unittest.TestCase):
    def test_pipeline_publishes_diagnostic_without_replacing_full_gap_report(self):
        code = (ROOT / "engine/pipeline.py").read_text(encoding="utf-8")
        ast.parse(code)
        self.assertIn('"data/current/debt_diagnostic.json"', code)
        self.assertIn('"data/current/research_gaps.json"', code)
        for field in ("total_open_gaps", "debt_breakdown", "actionable_by_section", "missing_by_field"):
            self.assertIn(f'"{field}"', code)

if __name__ == "__main__":
    unittest.main()
