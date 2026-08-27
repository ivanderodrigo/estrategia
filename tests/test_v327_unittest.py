import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class TestV327(unittest.TestCase):
    def test_assets_exist(self):
        self.assertTrue((ROOT/'assets/v327/ecosystem-tables.js').exists())
        self.assertTrue((ROOT/'assets/v327/ecosystem-tables.css').exists())
    def test_index_injected(self):
        t=(ROOT/'index.html').read_text(encoding='utf-8')
        self.assertIn('assets/v327/ecosystem-tables.css',t)
        self.assertIn('assets/v327/ecosystem-tables.js',t)
    def test_tables_cover_both_entity_types(self):
        t=(ROOT/'assets/v327/ecosystem-tables.js').read_text(encoding='utf-8')
        self.assertIn("distributors:{",t)
        self.assertIn("integrators:{",t)
        self.assertIn("competitive_pressure.json",t)
        self.assertIn("whitespace_candidates.json",t)
    def test_no_claimed_whitespace(self):
        t=(ROOT/'assets/v327/ecosystem-tables.js').read_text(encoding='utf-8')
        self.assertIn('no afirmado',t.lower())

if __name__=='__main__':
    unittest.main()
