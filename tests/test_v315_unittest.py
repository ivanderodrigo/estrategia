import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from v31.discovery import _quality_filter, _profile_limits, make_query


def _task(name, country='ES', dim='hiring', entity_type='integrator'):
    return {'ent': {'name': name, 'country': country, 'entity_type': entity_type}, 'dim': dim}


def _row(title, source='Test', url='https://example.com/x', published='Wed, 26 Aug 2026 10:00:00 GMT'):
    return {'title': title, 'source': source, 'url': url, 'published_at': published}


class V315Tests(unittest.TestCase):
    def test_daily_profile_is_parallel_and_no_site_targets(self):
        lim = _profile_limits('daily')
        self.assertGreaterEqual(lim['workers'], 8)
        self.assertEqual(lim['target_sources'], 0)
        self.assertGreaterEqual(lim['freshness_days'], 90)

    def test_daily_query_has_absolute_recency_hint(self):
        q = make_query('Fortinet', 'distribution', country='GLOBAL', freshness_days=120)
        self.assertIn('after:', q)

    def test_secondary_move_is_rejected_for_target_entity(self):
        cleaned, reason = _quality_filter(
            _row('Christian Stein, nuevo CEO de Renault en España tras la marcha de Josep María Recasens a Indra'),
            _task('Indra', dim='hiring'),
            'daily',
        )
        self.assertIsNone(cleaned)
        self.assertEqual(reason, 'secondary_people_move')

    def test_direct_leadership_hire_is_kept(self):
        cleaned, reason = _quality_filter(
            _row('Indra nombra a Ana Pérez nueva directora de ciberseguridad'),
            _task('Indra', dim='hiring'),
            'daily',
        )
        self.assertIsNone(reason)
        self.assertEqual(cleaned['dimension'], 'hiring')


if __name__ == '__main__':
    unittest.main(verbosity=2)
