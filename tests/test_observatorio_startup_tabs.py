"""Regression: initial page navigation must bind a list of tab nodes."""
from pathlib import Path
import unittest


class ObservatoryStartupTest(unittest.TestCase):
    def test_tab_binding_uses_query_selector_all(self):
        code = (Path(__file__).resolve().parents[1] / "assets/app/intelligence.js").read_text(encoding="utf-8")
        self.assertIn("$$('#tabs [data-view]').forEach(", code)
        self.assertNotIn("\n    $(\'#tabs [data-view]\').forEach(", code)


if __name__ == "__main__":
    unittest.main()
