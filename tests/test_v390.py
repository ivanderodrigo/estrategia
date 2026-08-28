from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / 'data/v39/intelligence.json').read_text(encoding='utf-8'))
LAST_RUN = json.loads((ROOT / 'data/v39/last_run.json').read_text(encoding='utf-8'))
INDEX = (ROOT / 'index.html').read_text(encoding='utf-8')
JS = (ROOT / 'assets/v390/intelligence.js').read_text(encoding='utf-8')
CSS = (ROOT / 'assets/v390/intelligence.css').read_text(encoding='utf-8')


class TestV390(unittest.TestCase):
    def test_version_file(self):
        self.assertEqual((ROOT / 'VERSION').read_text(encoding='utf-8').strip(), '3.9.0')

    def test_meta_version(self):
        self.assertEqual(DATA['meta']['version'], '3.9.0')
        self.assertGreaterEqual(DATA['meta']['source_count'], 235)

    def test_sections_present(self):
        for key in ['manufacturers', 'distributors', 'integrators', 'clients_public', 'clients_private', 'trends', 'architectures']:
            self.assertIn(key, DATA)

    def test_clients_minimum_volume(self):
        self.assertGreaterEqual(len(DATA['clients_public']), 8)
        self.assertGreaterEqual(len(DATA['clients_private']), 8)

    def test_clients_have_required_fields(self):
        required_public = {'scope', 'entity_type', 'request_or_need', 'opportunity_area', 'estimated_amount', 'milestone_date', 'procurement_stage', 'technology_signals', 'westcon_fit', 'opportunity_notes'}
        required_private = {'scope', 'segment', 'account_priority', 'technology_signals', 'hiring_signals', 'renewal_window', 'westcon_fit', 'opportunity_notes'}
        for row in DATA['clients_public']:
            self.assertTrue(required_public.issubset(row['fields']))
        for row in DATA['clients_private']:
            self.assertTrue(required_private.issubset(row['fields']))

    def test_client_fields_are_traceable(self):
        for row in DATA['clients_public'][:4] + DATA['clients_private'][:4]:
            self.assertTrue(row['evidence'])
            for field in row['fields'].values():
                self.assertTrue(field['evidence'])
                self.assertIn(field['confidence_band'], {'high', 'medium', 'low'})

    def test_source_catalog_includes_new_classes(self):
        names = {item['id'] for item in DATA['source_catalog']}
        for token in ['placsp_public_procurement', 'base_portugal_public_procurement', 'company_careers_es', 'company_careers_pt']:
            self.assertIn(token, names)

    def test_last_run_counts(self):
        self.assertEqual(LAST_RUN['version'], '3.9.0')
        self.assertEqual(LAST_RUN['clients_public'], len(DATA['clients_public']))
        self.assertEqual(LAST_RUN['clients_private'], len(DATA['clients_private']))
        self.assertEqual(LAST_RUN['clients'], len(DATA['clients_public']) + len(DATA['clients_private']))

    def test_index_uses_v390_assets(self):
        self.assertIn('assets/v390/intelligence.css?v=3.9.0', INDEX)
        self.assertIn('assets/v390/intelligence.js?v=3.9.0', INDEX)

    def test_tab_order_contains_clients(self):
        expected = ['data-view="fabricantes"', 'data-view="mayoristas"', 'data-view="integradores"', 'data-view="clientes"', 'data-view="tendencias"', 'data-view="arquitecturas"']
        pos = [INDEX.index(token) for token in expected]
        self.assertEqual(pos, sorted(pos))

    def test_index_contains_clients_sections(self):
        for token in ['publicClientSearch', 'publicClientTable', 'privateClientSearch', 'privateClientTable']:
            self.assertIn(token, INDEX)

    def test_js_loads_v39_data(self):
        self.assertIn("fetch('data/v39/intelligence.json'", JS)
        self.assertIn("fetch('data/v39/last_run.json'", JS)
        self.assertIn('renderClients()', JS)

    def test_js_exports_include_clients(self):
        for token in ['exportSections(modules)', 'clients_public', 'clients_private', 'Westcon_Iberia_Business_Intelligence_v3.9.0.pdf', 'Westcon_Iberia_Business_Intelligence_v3.9.0.pptx']:
            self.assertIn(token, JS)

    def test_js_footer_version(self):
        self.assertIn('App v3.9.0', JS)
        self.assertIn('Fabricantes · Mayoristas · Integradores · Clientes · Tendencias · Arquitecturas', JS)

    def test_css_contains_responsive_overrides(self):
        for token in ['client-blocks', 'subsection-head', 'appbar-actions', '@media(max-width:1380px)', '@media(max-width:720px)']:
            self.assertIn(token, CSS)


if __name__ == '__main__':
    unittest.main()
