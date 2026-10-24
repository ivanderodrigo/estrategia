import unittest
from copy import deepcopy
from engine.enrichment import normalize_fields
from engine.gaps import _support_rows

class ScalarSupport(unittest.TestCase):
    def fixture(self):
        ev=dict(source='Vendor',url='https://vendor.example/product',title='Vendor Security',date='2026-10-24',official=True,source_type='official-vendor-web',atomic=True,source_binding='claim-specific',researched_entity='Vendor',field='domain',item_value='Security')
        field=dict(value='Security',evidence=[ev],items=[dict(value='Security',evidence=[])])
        return {'manufacturers':[{'name':'Vendor','fields':{'domain':field}}]},field,ev
    def test_exact_scalar_wrapper_reuses_supported_claim(self):
        data,f,e=self.fixture();normalize_fields(data)
        self.assertEqual(len(f['items'][0]['evidence']),1);self.assertEqual(f['items'][0]['evidence'][0]['item_value'],'Security');self.assertTrue(_support_rows(f['items'][0]['evidence']))
        once=deepcopy(data);normalize_fields(data);self.assertEqual(data,once)
    def test_neighbour_scalar_does_not_inherit(self):
        data,f,e=self.fixture();f['items'][0]['value']='Networking';normalize_fields(data)
        self.assertEqual(f['items'][0]['evidence'],[])
    def test_wrong_owner_or_field_does_not_inherit(self):
        for key,value in [('researched_entity','Other'),('field','services'),('item_value','Networking')]:
            data,f,e=self.fixture();e[key]=value;e['title']='Unrelated';e['source']='Unrelated';normalize_fields(data)
            self.assertEqual(f['items'][0]['evidence'],[])

class PublicRecovery(unittest.TestCase):
    def test_recovery_preserves_internal_clues_and_new_public_entity(self):
        from engine.public_recovery import merge_snapshot
        data={'manufacturers':[{'id':'v','name':'Vendor','fields':{'capabilities':{'value':['Old'],'items':[{'value':'Old','evidence':[]}],'evidence':[]}}}]}
        public={'manufacturers':[{'id':'v','name':'Vendor','fields':{'capabilities':{'value':['New'],'items':[{'value':'New','evidence':[]}],'evidence':[]}}},{'id':'new','name':'New vendor','fields':{}}]}
        stats=merge_snapshot(data,public)
        self.assertEqual(stats['entities_restored'],1)
        self.assertEqual(data['manufacturers'][0]['fields']['capabilities']['value'],['Old','New'])
        self.assertEqual(merge_snapshot(data,public)['entities_restored'],0)
    def test_missing_evidence_reference_fails_closed(self):
        from engine.public_recovery import hydrate
        with self.assertRaises(KeyError):hydrate({'evidence_ids':['missing']},{})
    def test_scalar_supersession_retains_old_observation_separately(self):
        from engine.public_recovery import merge_snapshot
        d={'clients_public':[{'id':'a','fields':{'milestone_date':{'value':'2026-10-01','evidence':[]}}}]}
        p={'clients_public':[{'id':'a','fields':{'milestone_date':{'value':'2026-11-01','evidence':[]}}}]}
        merge_snapshot(d,p);f=d['clients_public'][0]['fields']['milestone_date']
        self.assertEqual(f['value'],'2026-11-01');self.assertEqual(f['prior_observations'][0]['value'],'2026-10-01')
    def test_publisher_includes_shard_directory_and_removals(self):
        from scripts.publish_research_update import ALLOWED
        from pathlib import Path
        self.assertIn('data/current/intelligence_store',ALLOWED)
        self.assertIn('"add", "-A"',Path('scripts/publish_research_update.py').read_text(encoding='utf-8'))
