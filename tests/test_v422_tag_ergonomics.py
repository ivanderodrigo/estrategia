import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class TagErgonomicsV422(unittest.TestCase):
    def test_atomic_tags_are_full_width_and_separated(self):
        css=(ROOT/'assets/app/intelligence.css').read_text(encoding='utf-8')
        self.assertIn('v4.2.2 · ergonomic atomic tags',css)
        self.assertIn('.tag-entry>.traceable{display:block!important;width:100%!important',css)
        self.assertIn('.tag-entry .confidence-tag{display:flex!important;width:100%!important',css)
        self.assertIn('.tag-entry .pending-verification{display:flex!important',css)

    def test_frontend_identity_is_current(self):
        html=(ROOT/'index.html').read_text(encoding='utf-8')
        js=(ROOT/'assets/app/intelligence.js').read_text(encoding='utf-8')
        self.assertIn('4.2.2',html)
        self.assertIn('4.2.2',js)


if __name__=='__main__':
    unittest.main()
