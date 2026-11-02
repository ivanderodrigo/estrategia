"""Ensure the v5 landing is a real navigation layer backed by verified dataset files."""
from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]

class CommandCenterTests(unittest.TestCase):
    def test_home_and_every_existing_domain_remain_accessible(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="commandCenter"', html)
        self.assertIn('id="homeNav"', html)
        for domain in ("fabricantes","mayoristas","integradores","clientes","tendencias","arquitecturas"):
            self.assertIn('data-cc-go="'+domain+'"', html)
            self.assertIn('data-view="'+domain+'"', html)
            self.assertIn('id="'+domain+'"', html)

    def test_new_dashboard_is_data_driven(self):
        js=(ROOT / "assets/app/command-center.js").read_text(encoding="utf-8")
        self.assertIn("data/public/manifest.json", js)
        self.assertIn("data/public/debt_overview.json", js)
        self.assertIn("document.body.classList.remove('cc-home')", js)

    def test_public_audit_reconciles_without_claiming_blank_fields_are_evidence(self):
        data=json.loads((ROOT / "data/public/debt_overview.json").read_text(encoding="utf-8"))
        self.assertEqual(data["total_open_gaps"],sum(data["debt_breakdown"].values()))
        self.assertGreater(data["debt_breakdown"]["empty_schema_fields"],0)

if __name__ == "__main__":
    unittest.main()
