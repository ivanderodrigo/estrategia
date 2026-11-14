import unittest
from unittest.mock import patch
from scripts.accredit_semantic_historical_sources import classify, owner_site
from engine.verified_research import apply_verified_research


class PragmaticHistoricalAccreditation(unittest.TestCase):
    def test_proven_historical_relation_is_restored_as_atomic_base_fact(self):
        entry = dict(section='integrators', entity='Example', field='vendor_relations', value='Cisco',
                     source=dict(source_type='historical-verified-excerpt',
                                 verification_method='VERIFIED_EXPLICIT_PARTNER_CONTEXT',
                                 description='Extracto de evidencia: Example Cisco partners',
                                 url='https://example.com/partners'))
        def read(path, default):
            return {'existing_claim_sources': [entry]} if 'historical_semantic_verified' in path else {}
        data = {'integrators': [{'name': 'Example', 'fields': {}}]}
        with patch('engine.verified_research.read_json', side_effect=read):
            apply_verified_research(data)
        field = data['integrators'][0]['fields']['vendor_relations']
        self.assertEqual(field['value'], ['Cisco'])
        self.assertTrue(field['items'][0]['evidence'][0]['atomic'])

    def assess(self, section, entity, field, value, context, url):
        return classify(dict(section=section, entity=entity, field=field,
                             value=value, source_context=context), url)

    def test_short_named_distributor_is_not_discarded(self):
        self.assertTrue(self.assess('manufacturers', 'Cisco', 'distributors', 'ALSO',
            'Cisco distribution agreement with ALSO', 'https://www.cisco.com/news/').startswith('VERIFIED_'))

    def test_overlap_uses_actual_partnership(self):
        self.assertTrue(self.assess('distributors', 'Ingram Micro', 'westcon_overlap', '1Password',
            '1Password partners with Ingram Micro to distribute extended access management',
            'https://1password.com/blog/partnership').startswith('VERIFIED_'))

    def test_other_distributor_cannot_borrow_same_partnership(self):
        self.assertFalse(self.assess('distributors', 'Ignition Technology', 'westcon_overlap', '1Password',
            '1Password partners with Ingram Micro to distribute extended access management',
            'https://1password.com/blog/partnership').startswith('VERIFIED_'))

    def test_catalogue_brand_is_a_valid_relation(self):
        self.assertTrue(self.assess('distributors', 'Aseminfor', 'vendor_relations', 'ASUS',
            'ASUS Kingston Intel', 'https://aseminfor.es/catalogo/').startswith('VERIFIED_'))

    def test_short_capability_on_own_product_page(self):
        self.assertTrue(self.assess('manufacturers', 'Check Point', 'capabilities', 'SASE',
            'SASE solutions', 'https://checkpoint.com/products/').startswith('VERIFIED_'))

    def test_numeric_capacity_needs_no_competitor_comparison(self):
        self.assertTrue(self.assess('distributors', 'Aseminfor', 'differential_capabilities',
            '14.000+ clientes activos', 'mas de 14 000 clientes activos',
            'https://aseminfor.es/').startswith('VERIFIED_'))

    def test_superlative_still_requires_comparison(self):
        self.assertEqual(self.assess('distributors', 'Aseminfor', 'differential_capabilities',
            'mejor servicio de soporte', 'mejor servicio de soporte',
            'https://aseminfor.es/'), 'DIFFERENTIAL_REQUIRES_COMPARISON')

    def test_short_company_host_label_not_partial_substring(self):
        self.assertTrue(owner_site('AWS', 'https://aws.amazon.com/'))
        self.assertFalse(owner_site('SIA', 'https://asia.example.com/'))

    def test_primary_news_title_and_unrelated_source(self):
        title='Amazon Cognito adds admin API operation'
        self.assertTrue(self.assess('manufacturers', 'AWS', 'recent_signals', title,
            title, 'https://aws.amazon.com/about-aws/whats-new/').startswith('VERIFIED_'))
        self.assertFalse(self.assess('manufacturers', 'Cisco', 'recent_signals', title,
            title, 'https://aws.amazon.com/about-aws/whats-new/').startswith('VERIFIED_'))
