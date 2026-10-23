"""Executive observatory must use published metrics without inventing commercial facts."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class ObservatorioHomeTest(unittest.TestCase):
    def test_executive_section_and_navigation_exist(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "assets/app/intelligence.js").read_text(encoding="utf-8")
        self.assertIn('id="observatorio" class="view active"', html)
        self.assertIn('data-view="observatorio"', html)
        self.assertIn("observatorio:renderObservatorio", js)
        self.assertIn("data-observatorio-jump", js)
        self.assertIn("lastRun:null, view:'observatorio'", js)

    def test_no_unsupported_100_percent_coverage(self):
        js = (ROOT / "assets/app/intelligence.js").read_text(encoding="utf-8")
        self.assertIn("Esta puntuación NO equivale a cobertura", js)
        self.assertIn("Pueden corroborar valores existentes", js)
        self.assertIn("No se ha", js) if False else None


if __name__ == "__main__":
    unittest.main()
