"""Prevent ranking starvation of research sections in bounded Daily runs."""
import unittest
from engine.research.sources import SourceSeed
from engine.research.web_intelligence import (
    _fair_target_order, _query_limit_for_target,
)


class ResearchLaneFairness(unittest.TestCase):
    def test_distributors_are_seen_before_public_clients_exhaust_deadline(self):
        targets = (
            [{'section': 'clients_public', 'entity': f'Public {i}'} for i in range(70)]
            + [{'section': 'distributors', 'entity': f'Dist {i}'} for i in range(16)]
            + [{'section': 'integrators', 'entity': f'Integrator {i}'} for i in range(10)]
            + [{'section': 'manufacturers', 'entity': f'Vendor {i}'} for i in range(8)]
            + [{'section': 'trends', 'entity': f'Trend {i}'} for i in range(5)]
            + [{'section': 'architectures', 'entity': f'Architecture {i}'} for i in range(5)]
        )
        ordered = _fair_target_order(targets)
        self.assertEqual(len(ordered), len(targets))
        self.assertEqual(ordered[0]['entity'], 'Dist 0')
        self.assertEqual(ordered[1]['entity'], 'Integrator 0')
        self.assertEqual(ordered[2]['entity'], 'Dist 1')
        self.assertTrue({'distributors', 'integrators', 'manufacturers', 'trends',
                         'architectures', 'clients_public'}.issubset(
            {row['section'] for row in ordered[:10]}))
        self.assertEqual(
            [row['entity'] for row in ordered if row['section'] == 'clients_public'],
            [f'Public {i}' for i in range(70)],
        )
        self.assertEqual(
            [row['entity'] for row in ordered if row['section'] == 'distributors'],
            [f'Dist {i}' for i in range(16)],
        )

    def test_empty_and_unrecognised_sections_preserve_all_targets(self):
        self.assertEqual(_fair_target_order([]), [])
        sample = [{'section': 'special', 'entity': 'A'},
                  {'section': 'special', 'entity': 'B'}]
        self.assertEqual(_fair_target_order(sample), sample)

    def test_official_catalogue_first_reduces_only_daily_distributor_queries(self):
        official_catalogue = SourceSeed(
            'https://www.depau.es/marcas-disponibles',
            'partners', True, 'A', 'official-catalogue', 'Depau',
        )
        unofficial = SourceSeed(
            'https://example.org/article', 'news', False, 'C',
            'search-discovery', 'Example',
        )
        target = {'section': 'distributors', 'fields': ['vendor_relations']}
        self.assertEqual(_query_limit_for_target('daily', target, [official_catalogue], 6), 1)
        self.assertEqual(_query_limit_for_target('deep', target, [official_catalogue], 14), 14)
        self.assertEqual(_query_limit_for_target('daily', target, [unofficial], 6), 6)
        self.assertEqual(_query_limit_for_target(
            'daily', {'section': 'distributors', 'fields': ['revenue']},
            [official_catalogue], 6), 6)
        self.assertEqual(_query_limit_for_target(
            'daily', {'section': 'clients_public', 'fields': ['vendor_relations']},
            [official_catalogue], 6), 6)


if __name__ == '__main__':
    unittest.main()
