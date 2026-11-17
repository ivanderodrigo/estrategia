"""Regression: the FY27 deck is historical for manufacturers later removed."""
import inspect
import unittest
from pathlib import Path
from scripts import audit_v422


class SupersededManufacturerGate(unittest.TestCase):
    def test_release_gate_uses_november_exclusions_not_old_deck_membership(self):
        source=inspect.getsource(audit_v422.main)
        self.assertIn("portfolio_override_2026_11",source)
        self.assertIn("if canonical(name) in superseded",source)
        self.assertIn("field.get('value') is not False",source)
        self.assertIn("has_current(field,field=field_id,value=False)",source)
        config=__import__("json").loads(
            (Path(__file__).resolve().parents[1]/
             "config/current/westcon_fy27_document_facts.json").read_text(encoding="utf-8"))
        self.assertEqual(set(config["portfolio_override_2026_11"]["excluded"]),
                         {"Juniper Networks","Ruckus Networks"})


if __name__=="__main__":
    unittest.main()
