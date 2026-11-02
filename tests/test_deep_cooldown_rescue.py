"""Deep research must not silently succeed with zero targets when debt exists."""
from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parents[1]

class DeepCooldownRescueTests(unittest.TestCase):
    def test_deep_and_daily_rescue_enabled(self):
        source = (ROOT / "engine/research/web_intelligence.py").read_text(encoding="utf-8")
        ast.parse(source)
        self.assertIn('if profile in {"daily", "deep"} and not targets:', source)
        self.assertIn('12 if profile == "daily" else 36', source)
        self.assertIn('rescue_targets_after_cooldown', source)

if __name__ == "__main__":
    unittest.main()
