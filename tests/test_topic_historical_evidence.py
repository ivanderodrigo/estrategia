import unittest
from unittest.mock import patch
from engine.topic_evidence import topic_excerpt, classify_topic
from scripts.revalidate_historical_sources import historical_topic_text, candidate_inventory
from engine.verified_research import apply_verified_research

class TopicHistoryTests(unittest.TestCase):
    def claim(self, field, value, text='', entity='Observability / Digital Experience'):
        return dict(section='architectures',entity=entity,field=field,value=value,source_context=text)

    def test_publisher_prefix_does_not_block_exact_report_title(self):
        c=self.claim('analyst_basis','Gartner · Magic Quadrant for Observability Platforms',
                     'Magic Quadrant for Observability Platforms published in 2026')
        self.assertEqual(classify_topic(c,'https://www.gartner.com/en/documents/8114397'), 'VERIFIED_CITED_TOPIC_DOCUMENT')

    def test_wrong_publisher_cannot_credit_title(self):
        c=self.claim('analyst_basis','Forrester · Magic Quadrant for Observability Platforms',
                     'Magic Quadrant for Observability Platforms')
        self.assertEqual(classify_topic(c,'https://www.gartner.com/en/documents/8114397'), '')

    def test_report_edition_and_numbers_must_match(self):
        c=self.claim('sources','Gartner: Observability Platforms 2026','Observability Platforms 2025')
        self.assertEqual(topic_excerpt(c,'https://www.gartner.com/en/documents/1',c['source_context']), '')

    def test_name_is_grounded_in_documented_component(self):
        c=self.claim('name','Observability / Digital Experience','Magic Quadrant for Observability Platforms')
        self.assertEqual(classify_topic(c,'https://www.gartner.com/en/documents/8114397'), 'VERIFIED_TOPIC_COMPONENT')
        self.assertEqual(classify_topic(c,'https://unrelated.example/'), '')

    def test_menu_is_not_topic_identity_evidence(self):
        text=historical_topic_text('<nav>Observability</nav><title>Unrelated article</title><h1>Networking</h1>')
        self.assertNotIn('observability',text)

    def test_inventory_includes_topic_names_from_field_sources(self):
        data={'architectures':[{'name':'Zero Trust','fields':{'context':{'value':'Some context',
              'evidence':[{'url':'https://csrc.nist.gov/publications/detail/sp/800-207/final'}]}}}]}
        with patch('scripts.revalidate_historical_sources.read_json',side_effect=lambda p,d: data if p=='data/current/intelligence.json' else {}):
            inv=candidate_inventory()
        self.assertTrue(any(c['field']=='name' and c['value']=='Zero Trust' for cs in inv.values() for c in cs))

    def test_name_proof_publishes_as_scalar_not_whole_card_accreditation(self):
        entry={'section':'architectures','entity':'Zero Trust','field':'name','value':'Zero Trust',
               'source':{'source_type':'historical-verified-excerpt','verification_method':'VERIFIED_TOPIC_COMPONENT',
                         'description':'Extracto de evidencia: Zero Trust Architecture','url':'https://csrc.nist.gov/'}}
        data={'architectures':[{'name':'Zero Trust','fields':{'limits':{'value':'Unproven limit','evidence':[]}}}]}
        with patch('engine.verified_research.read_json',side_effect=lambda p,d: {'existing_claim_sources':[entry]} if 'historical_semantic_verified' in p else {}):
            apply_verified_research(data)
        self.assertEqual(data['architectures'][0]['fields']['name']['value'],'Zero Trust')
        self.assertEqual(data['architectures'][0]['fields']['limits']['evidence'],[])
