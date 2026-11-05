import unittest
from pathlib import Path

class DeepCooldownRescueContract(unittest.TestCase):
    def test_bounded_deep_rescue_preserves_evidence_gate(self):
        text=(Path(__file__).resolve().parents[1]/"engine/research/web_intelligence.py").read_text(encoding="utf-8")
        self.assertIn('if profile == "deep" and len(targets) < 50:',text)
        self.assertIn("if rescue_targets >= 30:",text)
        self.assertIn("max_tasks=300, include_gap_kinds=include_gap_kinds",text)
        self.assertIn("rescue_targets_after_cooldown",text)
if __name__=="__main__": unittest.main()
