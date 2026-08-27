import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "data/v35/intelligence.json").read_text(encoding="utf-8"))


class BusinessIntelligenceV350(unittest.TestCase):
    def test_five_domains_have_data(self):
        for key in ("manufacturers", "integrators", "distributors", "trends", "architectures"):
            self.assertTrue(DATA[key], key)

    def test_every_published_field_is_traceable(self):
        for key in ("manufacturers", "integrators", "distributors", "trends", "architectures"):
            for row in DATA[key]:
                for field_id, field in row.get("fields", {}).items():
                    self.assertNotIn(field.get("value"), (None, "", [], {}), (key, row.get("name"), field_id))
                    self.assertTrue(field.get("evidence"), (key, row.get("name"), field_id))

    def test_westcon_is_not_a_competitor_distributor(self):
        names = [str(row.get("name", "")).lower() for row in DATA["distributors"]]
        self.assertFalse(any("westcon" in name for name in names))

    def test_source_universe_is_broad(self):
        self.assertGreaterEqual(len(DATA["source_catalog"]), 180)
        ids = {row.get("id") for row in DATA["source_catalog"]}
        for required in ("gartner_public", "idc_public", "forrester_public", "linkedin_jobs_public", "infojobs_es", "placsp", "base_portugal"):
            self.assertIn(required, ids)

    def test_only_final_user_columns_are_in_schemas(self):
        banned = ("priority", "tier", "depth", "activation", "response", "decision", "action", "recommend")
        for section, schema in DATA["schemas"].items():
            for column in schema:
                field_id = str(column.get("id", "")).lower()
                self.assertFalse(any(x in field_id for x in banned), (section, field_id))
                if column.get("clarify"):
                    self.assertTrue(column.get("help"), (section, field_id))


if __name__ == "__main__":
    unittest.main()
