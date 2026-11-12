"""v6.6 regression coverage: independent first-party catalogue leads, no invented linecards."""
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from engine.research.documents import parse_document
from engine.research.extractors import distributor_linecard_vendors, extract_candidates
from engine.research.query_discovery import _disambiguate_technical_query, discover
from engine.research.sources import seeds_for


ROOT = Path(__file__).resolve().parents[1]


class PreciseLinecardsAndSearchV66(unittest.TestCase):
    def test_spanish_esprinet_catalogue_retains_brand_logos(self):
        html = ('<title>Todos los fabricantes - Esprinet</title><body>'
                + ''.join(f'<img alt="Manufacturer {i} logo">' for i in range(150))
                + '</body>')
        doc = parse_document(
            html,
            'https://www.esprinet.com/es/oferta/fabricantes-y-socios/todos-los-fabricantes/',
            'esprinet-test',
        )
        names, _ = distributor_linecard_vendors(doc, [])
        self.assertEqual(len(names), 150)
        self.assertIn('Manufacturer 149', names)

    def test_arrow_portfolio_on_generic_products_path_is_a_catalogue(self):
        doc = parse_document(
            '<title>Portfolio de Fabricantes | Arrow ECS</title><body>'
            '<img alt="Cohesity Logo"><img alt="Fortinet logo"></body>',
            'https://www.arrow.com/globalecs/es/productos/', 'arrow-test',
        )
        names, _ = distributor_linecard_vendors(doc, [])
        self.assertEqual(set(names), {'Cohesity', 'Fortinet'})

    def test_vvalley_only_uses_logos_inside_manufacturer_section(self):
        doc = parse_document(
            '<title>Ciberseguridad V-Valley</title><body>'
            '<img alt="Decoración de seguridad">'
            '<h2>NUESTROS FABRICANTES QUE OFRECEN SOLUCIONES DE CIBERSEGURIDAD</h2>'
            '<img alt="logo Iberlayer"><img alt="logo-Ironchip">'
            '<h2>NUESTROS SERVICIOS COMPLEMENTARIOS</h2>'
            '<img alt="Tarjeta de consultoría"></body>',
            'https://www.v-valley.com/es/soluciones/ciberseguridad/', 'vvalley-test',
        )
        names, _ = distributor_linecard_vendors(doc, [])
        self.assertEqual(set(names), {'Iberlayer', 'Ironchip'})
        self.assertNotIn('Tarjeta de consultoría', names)
        self.assertNotIn('Decoración de seguridad', names)

    def test_ingram_catalogue_uses_explicit_vendor_index_links(self):
        doc = parse_document(
            '<title>Fabricantes</title><body><h1>Lista de Fabricantes</h1>'
            '<a href="/site/vendor/details?id=1">Acronis (11)</a>'
            '<a href="/site/vendor/details?id=2">Allied Telesis (1875)</a>'
            '<a href="/noticias">Noticias (250)</a></body>',
            'https://es-new.ingrammicro.com/site/vendor/index', 'ingram-test',
        )
        names, _ = distributor_linecard_vendors(doc, [])
        self.assertEqual(set(names), {'Acronis', 'Allied Telesis'})

    def test_generic_article_logos_do_not_become_brands(self):
        doc = parse_document(
            '<title>Noticias de ciberseguridad</title><body>'
            '<img alt="Fortinet Logo"><img alt="Check Point Logo">'
            '<h2>Los fabricantes invierten</h2></body>',
            'https://example.com/noticias/post', 'news-test',
        )
        self.assertEqual(distributor_linecard_vendors(doc, []), ([], []))

    def test_official_regional_leads_are_not_predeclared_relations(self):
        cases = {
            'Esprinet': '/es/oferta/fabricantes-y-socios/todos-los-fabricantes/',
            'Arrow ECS': '/globalecs/es/productos/',
            'Ingram Micro': '/site/vendor/index',
            'ALSO': '/2610/es_es/fabricantes/index.jsp',
            'V-Valley': '/es/soluciones/ciberseguridad/',
        }
        for name, suffix in cases.items():
            with self.subTest(name=name):
                seeds = seeds_for(
                    {'name': name, 'fields': {}}, ['vendor_relations'],
                    target={'section': 'distributors'},
                )
                self.assertTrue(any(s.official and suffix in s.url for s in seeds))
                self.assertTrue(all(s.source_grade == 'A' for s in seeds))

    def test_depau_brand_inventory_reads_only_explicit_brand_section(self):
        doc = parse_document(
            '<title>Nuestras Marcas | Depau</title><body>'
            '<h1>Estas son las marcas que forman parte de nuestro catálogo:</h1>'
            '<span>A</span><span>ADATA</span><span>BROTHER</span>'
            '<span>D-LINK</span><span>MIKROTIK</span><span>TP-LINK</span>'
            '<h2>Volver</h2><span>MARCA DECORATIVA</span></body>',
            'https://www.depau.es/marcas-disponibles', 'depau-test',
        )
        names, _ = distributor_linecard_vendors(doc, [])
        self.assertEqual(set(names), {'ADATA', 'BROTHER', 'D-LINK', 'MIKROTIK', 'TP-LINK'})
        self.assertNotIn('MARCA DECORATIVA', names)

    def test_infortisa_explicit_brands_paragraph_not_site_wide_news(self):
        doc = parse_document(
            '<title>Nuestros productos - Infortisa</title><body>'
            '<p>Somos proveedores y distribuidores oficiales.</p>'
            '<p>Los mejores fabricantes del sector: MSI, ASUS, Intel,'
            ' Gigabyte, Synology, Ubiquiti y Zyxel, entre otros.</p>'
            '<div>Noticias: Cisco firma una alianza distinta</div></body>',
            'https://www.infortisa.com/productos/', 'infortisa-test',
        )
        names, _ = distributor_linecard_vendors(doc, ['Cisco'])
        self.assertEqual(
            set(names),
            {'MSI', 'ASUS', 'Intel', 'Gigabyte', 'Synology', 'Ubiquiti', 'Zyxel'}
        )
        self.assertNotIn('Cisco', names)

    def test_new_brandless_distributors_have_official_targeted_sources(self):
        entries = {
            'MCR': '/marcas/',
            'Depau': '/marcas-disponibles',
            'Megasur': '/list-brand',
            'Infortisa': '/productos/',
            'Niposom': 'niposom.pt',
            'Globomatik': 'globomatik.com',
            'Valorista': 'valorista.com',
            'Visiotech Security': 'visiotechsecurity.com',
        }
        for name, suffix in entries.items():
            with self.subTest(name=name):
                seeds = seeds_for(
                    {'name': name, 'fields': {}},
                    ['vendor_relations'],
                    target={'section': 'distributors'},
                )
                self.assertTrue(any(s.official and suffix in s.url for s in seeds))

    def test_search_disambiguation_prevents_entertainment_queries(self):
        original = '"OT / CPS Security" latest architecture'
        new = _disambiguate_technical_query(original)
        self.assertIn('"operational technology"', new)
        self.assertIn('"industrial control systems"', new)
        self.assertNotIn('OT / CPS Security', new)
        self.assertEqual(_disambiguate_technical_query('"Palo Alto" Zero Trust'),
                         '"Palo Alto" Zero Trust')

    @patch('engine.research.query_discovery._search_provider')
    def test_search_provider_receives_disambiguated_query(self, provider):
        provider.return_value = []
        discover(
            Mock(), ['"OT / CPS Security" partners'],
            fallback_family='analyst', providers=['bing_rss'],
            timeout_s=5, max_queries=1, results_per_query=2,
        )
        query = provider.call_args.args[2]
        self.assertIn('operational technology', query)
        self.assertNotIn('OT / CPS Security', query)


if __name__ == '__main__':
    unittest.main()
