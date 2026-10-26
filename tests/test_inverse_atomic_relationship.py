import unittest
from engine.provenance import evidence_for_relationship, evidence_for_item
from engine.enrichment import normalize_fields

class InverseAtomicRelationship(unittest.TestCase):
    def evidence(self):
        return dict(source='acens',title='Security services',url='https://acens.example/security',date='2026-10-25',official=True,atomic=True,source_binding='atomic-item',researched_entity='acens / Telefónica Tech',field='vendor_relations',item_value='Zscaler')
    def test_inverse_exact_binding_survives_normalization(self):
        ev=self.evidence()
        self.assertEqual(len(evidence_for_relationship([ev],'Zscaler','acens / Telefónica Tech')),1)
        f={'value':['acens / Telefónica Tech'],'items':[{'value':'acens / Telefónica Tech','evidence':[ev]}],'evidence':[ev]}
        normalize_fields({'manufacturers':[{'name':'Zscaler','fields':{'integrators':f}}]})
        self.assertEqual(len(f['items'][0]['evidence']),1)
    def test_neighbour_and_discovery_do_not_gain_support(self):
        ev=self.evidence()
        self.assertEqual(evidence_for_relationship([ev],'Okta','acens / Telefónica Tech'),[])
        self.assertEqual(evidence_for_relationship([ev],'Zscaler','Other partner'),[])
        ev['source_binding']='discovery-only'
        self.assertEqual(evidence_for_relationship([ev],'Zscaler','acens / Telefónica Tech'),[])
    def test_nonrelational_item_policy_stays_directional(self):
        self.assertEqual(evidence_for_item([self.evidence()],'Zscaler','acens / Telefónica Tech',field_id='services'),[])
