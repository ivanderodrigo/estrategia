"""Prevent historical source loss in nested architecture tabs and audits."""
import json
import unittest
from pathlib import Path

from scripts.audit_public_consistency import evaluate

ROOT = Path(__file__).resolve().parents[1]


class HistoricalVisibleLinkCoverage(unittest.TestCase):
    def test_all_architecture_and_trend_archive_claims_have_urls(self):
        for section in ('trends', 'architectures'):
            for prefix in ('', 'git_'):
                data = json.loads((ROOT / f'data/public/historical/current/{prefix}{section}.json').read_text(encoding='utf-8'))
                claims = [claim for fields in data.get('entities', {}).values()
                          for records in fields.values() for claim in records]
                self.assertGreater(len(claims), 0)
                self.assertTrue(all(any(u.startswith('https://') for u in c.get('urls', [])) for c in claims))

    def test_nested_architecture_vendor_has_historical_source(self):
        section = json.loads((ROOT / 'data/public/sections/architectures.json').read_text(encoding='utf-8'))
        history = json.loads((ROOT / 'data/public/historical/current/architectures.json').read_text(encoding='utf-8'))
        modern_soc = next(r for r in section['rows'] if r['name'] == 'Modern SOC / SecOps')
        nested_vendors = {v for layer in modern_soc['fields']['layers']['value'] for v in layer.get('vendors', [])}
        sources = history['entities']['modern soc secops']['vendors']
        self.assertIn('Anomali', nested_vendors)
        self.assertTrue(any(c['value'] == 'Anomali' and c['urls'] for c in sources))
        frontend = (ROOT / 'assets/app/intelligence.js').read_text(encoding='utf-8')
        self.assertIn('...(row._historical.vendors||[])', frontend)
        self.assertIn('_historical:field._historical||[]', frontend)

    def test_audit_explicitly_separates_urls_from_accreditation(self):
        result = evaluate()
        coverage = result['historical_link_coverage']
        self.assertTrue(result['historical_url_presence_is_not_claim_accreditation'])
        self.assertGreater(coverage['claims'], 1000)
        self.assertEqual(coverage['claims_without_urls'], 0)
        self.assertEqual(coverage['claims_with_invalid_urls'], 0)
        verification = result['historical_verification']
        self.assertTrue(verification['available'])
        self.assertTrue(verification['snapshot_matches'])
        self.assertLessEqual(verification['verified_claim_source_pairs'], verification['claim_source_pairs_reviewed'])


if __name__ == '__main__':
    unittest.main()
