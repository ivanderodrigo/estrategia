from __future__ import annotations

import json
import unittest
from pathlib import Path

from engine.research.documents import Document, Link
from engine.research.extractors import extract_candidates
from engine.research.planner import plan
from engine.research.sources import SourceSeed
from engine.research.web_intelligence import (
    _financial_entry_seed,
    _financial_link_is_relevant,
    _trusted_external_financial_link,
)

ROOT = Path(__file__).resolve().parents[1]


class ManufacturerRevenueHF4(unittest.TestCase):
    def test_revenue_columns_stay_visible_when_empty(self) -> None:
        schema = json.loads(
            (ROOT / 'config/current/business_intelligence_schema.json').read_text(encoding='utf-8')
        )
        for section in ('manufacturers', 'distributors'):
            revenue = next(
                col for col in schema['sections'][section] if col.get('id') == 'revenue'
            )
            self.assertTrue(revenue.get('default_visible'))
            self.assertTrue(revenue.get('show_when_empty'))

    def test_official_manufacturer_page_can_yield_revenue(self) -> None:
        doc = Document(
            url='https://example.com/about',
            title='Example Corp',
            text='Example Corp reported annual revenue of US$ 12.4 billion in fiscal year 2025.',
            links=(),
            content_digest='hf4',
        )
        result = extract_candidates('manufacturers', 'official', doc, [], official=True)
        self.assertIn('revenue', result)
        self.assertTrue(any('12.4 billion' in value for value in result['revenue'].values))

    def test_daily_planner_reserves_manufacturer_revenue_capacity(self) -> None:
        gaps = {'gaps': []}
        for i in range(30):
            gaps['gaps'].append({
                'id': f'i-{i}',
                'section': 'integrators',
                'entity': f'Integrator {i}',
                'entity_id': f'integrator-{i}',
                'field': 'vendor_relations',
                'priority': 1,
                'priority_score': 99,
                'gap_kind': 'standard',
            })
        for i in range(12):
            gaps['gaps'].append({
                'id': f'm-{i}',
                'section': 'manufacturers',
                'entity': f'Manufacturer {i}',
                'entity_id': f'manufacturer-{i}',
                'field': 'revenue',
                'priority': 2,
                'priority_score': 20,
                'gap_kind': 'standard',
            })
        tasks = plan(gaps, {'families': {}}, 'daily', max_tasks=10)
        revenue_tasks = [
            task for task in tasks
            if task.get('section') == 'manufacturers' and 'revenue' in task.get('fields', [])
        ]
        self.assertGreaterEqual(len(revenue_tasks), 8)

    def test_financial_link_discovery_uses_label_and_official_linked_host(self) -> None:
        link = Link(
            'https://investors.example-ir.com/results',
            'Investor Relations - Financial Results',
        )
        self.assertTrue(_financial_link_is_relevant(link))
        source = SourceSeed(
            'https://example.com/',
            'financial',
            True,
            'A',
            'official-financial-entry',
            'Example',
        )
        document = Document(
            'https://example.com/',
            'Example',
            'Example company',
            (link,),
            'hf4',
        )
        self.assertTrue(
            _trusted_external_financial_link(
                link, document, entity='Example', seed=source
            )
        )

    def test_financial_entry_comes_from_entity_owned_official_host(self) -> None:
        seeds = [
            SourceSeed(
                'https://example.com/security',
                'services',
                True,
                'A',
                'official-domain',
                'Example',
            )
        ]
        entry = _financial_entry_seed(seeds, 'Example')
        self.assertIsNotNone(entry)
        self.assertEqual(entry.family, 'financial')
        self.assertEqual(entry.url, 'https://example.com/')

    def test_frontend_keeps_show_when_empty_column_available(self) -> None:
        js = (ROOT / 'assets/app/intelligence.js').read_text(encoding='utf-8')
        self.assertIn('col.show_when_empty===true', js)
        self.assertIn('col?.show_when_empty===true', js)

    def test_runtime_has_revenue_coverage_metrics(self) -> None:
        code = (ROOT / 'engine/research/web_intelligence.py').read_text(encoding='utf-8')
        self.assertIn('"manufacturer_revenue_rows_before"', code)
        self.assertIn('"manufacturer_revenue_rows_after"', code)
        self.assertIn('"manufacturer_revenue_rows_added"', code)
        self.assertIn('"financial_links_discovered"', code)


if __name__ == '__main__':
    unittest.main()
