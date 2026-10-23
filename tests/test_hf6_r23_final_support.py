"""Final normalization must surround reconciliation and revalidate restored evidence."""
import unittest
from pathlib import Path


class FinalAccreditedSupportOrdering(unittest.TestCase):
    def test_restoration_is_revalidated_before_quality(self):
        code = (Path(__file__).resolve().parents[1] / "engine/pipeline.py").read_text(encoding="utf-8")
        build = code[code.index("def run()"):]
        marker = "final_support_reconciliation = restore_accredited_support(data, preservation_source)"
        self.assertIn(marker, build)
        restoration = build.index(marker)
        normalization_before = build.rfind("    normalize_fields(data)", 0, restoration)
        normalization_after = build.find("    normalize_fields(data)", restoration)
        audit = build.index("    preservation_after = preservation_snapshot(data, graph)")
        self.assertGreaterEqual(normalization_before, 0)
        self.assertGreater(normalization_after, restoration)
        self.assertLess(normalization_after, audit)
        self.assertIn('"accredited_support_final": final_support_reconciliation', build)


if __name__ == "__main__":
    unittest.main()
