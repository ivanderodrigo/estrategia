"""v7.1: first-party vendor relations require explicit catalogue or named brand detail.

An incidental vendor mentioned by an official wholesaler is never sufficient to
accredit a contractual distributor/manufacturer relationship.
"""
import unittest

from engine.research.documents import parse_document
from engine.research.extractors import (
    _explicit_official_vendor_detail,
    extract_candidates,
    distributor_linecard_vendors,
)
from engine.research.sources import seeds_for


class FirstPartyVendorEvidenceV71(unittest.TestCase):
    def test_generic_official_partner_page_co_mentions_are_not_linecard(self):
        document = parse_document(
            '<title>Partners | Sample Wholesale</title>'
            '<body><h1>Partners de canal</h1>'
            '<p>Noticias: Cisco presenta soluciones y Fortinet participa en un evento.</p>'
            '<a href="/partners/contacto">Contacto</a></body>',
            'https://sample-wholesale.example/partners/', 'co-mentions',
        )
        self.assertNotIn('vendor_relations', extract_candidates(
            'distributors', 'partners', document, ['Cisco', 'Fortinet'],
            official=True, researched_entity='Sample Wholesale',
        ))

    def test_named_ajoomal_vendor_page_supports_only_named_brand(self):
        document = parse_document(
            '<title>GFI Software – Ajoomal Asociados</title>'
            '<body><h1>GFI Software</h1>'
            '<p>Soluciones de GFI Software: productos de seguridad.</p>'
            '<aside>También puede consultar noticias sobre Cisco.</aside></body>',
            'https://www.ajoomal.com/gfi/', 'gfi-brand',
        )
        candidates = extract_candidates(
            'distributors', 'partners', document, ['Cisco', 'GFI Software'],
            official=True, researched_entity='Ajoomal',
        )
        self.assertEqual(candidates['vendor_relations'].values, ('GFI Software',))
        self.assertNotIn('Cisco', candidates['vendor_relations'].values)

    def test_generic_vendor_slug_cannot_confirm_relationship(self):
        document = parse_document(
            '<title>Partners | Ajoomal</title><body>'
            '<h1>Partners</h1><p>Marcas Cisco and Fortinet discuss security.</p>'
            '</body>',
            'https://www.ajoomal.com/partners/', 'partner-news',
        )
        self.assertEqual(_explicit_official_vendor_detail(document), ([], []))

    def test_title_slug_mismatch_rejects_marketing_name_drops(self):
        document = parse_document(
            '<title>Cisco se suma al evento</title><body>'
            '<h1>Fabricantes</h1><p>Soluciones Cisco</p>'
            '</body>',
            'https://www.ajoomal.com/noticia-ciberseguridad/', 'marketing',
        )
        self.assertEqual(_explicit_official_vendor_detail(document), ([], []))

    def test_existing_explicit_catalogue_remains_supported(self):
        document = parse_document(
            '<title>Marcas Distribuidas | Sample Wholesale</title><body>'
            '<h1>Nuestras Marcas</h1><img alt="Logo Fortinet">'
            '<img alt="Logo Cisco"></body>',
            'https://sample-wholesale.example/marcas/', 'brands',
        )
        vendors, _terms = distributor_linecard_vendors(document, [])
        self.assertEqual(set(vendors), {'Fortinet', 'Cisco'})

    def test_ajoomal_vendor_detail_leads_preserve_subject_not_preconfirmed(self):
        seeds = seeds_for(
            {'name': 'Ajoomal', 'fields': {}},
            ['vendor_relations'],
            target={'section': 'distributors'},
        )
        self.assertTrue(any(
            seed.url == 'https://www.ajoomal.com/gfi/'
            and seed.official and seed.family == 'partners'
            for seed in seeds
        ))
        self.assertTrue(any(
            seed.url == 'https://www.ajoomal.com/engenius/'
            and seed.official and seed.family == 'partners'
            for seed in seeds
        ))
        self.assertTrue(all(seed.source_type != 'confirmed-relation'
                            for seed in seeds))

    def test_globomatik_uses_real_brand_directory_instead_of_homepage(self):
        seeds = seeds_for(
            {'name': 'Globomatik', 'fields': {}}, ['vendor_relations'],
            target={'section': 'distributors'},
        )
        self.assertTrue(any(
            seed.url == 'https://www.globomatik.com/marcas'
            and seed.official
            for seed in seeds
        ))


if __name__ == '__main__':
    unittest.main()
