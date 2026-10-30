"""Executive observatory must use published metrics without inventing commercial facts."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class ObservatorioHomeTest(unittest.TestCase):
    def test_six_domain_observatory_is_primary_navigation(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "assets/app/intelligence.js").read_text(encoding="utf-8")
        self.assertNotIn('data-view="observatorio"', html)
        self.assertIn('data-view="fabricantes"', html)
        self.assertIn('data-view="mayoristas"', html)
        self.assertIn('data-view="integradores"', html)
        self.assertIn('data-view="clientes"', html)
        self.assertIn('data-view="tendencias"', html)
        self.assertIn('data-view="arquitecturas"', html)
        self.assertIn("lastRun:null, view:'fabricantes'", js)
        self.assertNotIn("observatorio:renderObservatorio", js)

    def test_no_unsupported_100_percent_coverage(self):
        js = (ROOT / "assets/app/intelligence.js").read_text(encoding="utf-8")
        self.assertIn("Esta puntuación NO equivale a cobertura", js)
        self.assertIn("Pueden corroborar valores existentes", js)


if __name__ == "__main__":
    unittest.main()
