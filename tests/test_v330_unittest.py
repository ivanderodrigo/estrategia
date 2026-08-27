import sys,unittest,tempfile,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from v33.matrix_engine import build_relationship_matrix,build_vendor_pairs
from v33.architecture_engine import build_architectures
from v33.validate_v33 import validate

class T(unittest.TestCase):
 def test_relationship_does_not_assert_absence(self):
  p=[{'name':'Integrator X','entity_type':'integrator','vendors':[],'technology_focus':['Cybersecurity'],'confidence':.7,'westcon_relevance':80,'whitespace_candidates':[{'vendor':'Vendor A','research_priority_score':.8}]}]
  d=build_relationship_matrix(p,['Vendor A'],{'confirmed':.82,'probable':.64,'whitespace_shortlist':.68})
  self.assertEqual(d['rows'][0]['status'],'WHITESPACE_RESEARCH_PRIORITY');self.assertIn('Ausencia',d['rows'][0]['caution'])
 def test_confirmed_relation(self):
  ev=[{'title':'Integrator X certified partner Vendor A','source':'Vendor A','url':'u'} for _ in range(4)]
  p=[{'name':'Integrator X','entity_type':'integrator','vendors':['Vendor A'],'technology_focus':['Cybersecurity'],'confidence':.9,'westcon_relevance':90,'evidence':ev,'whitespace_candidates':[]}]
  d=build_relationship_matrix(p,['Vendor A'],{'confirmed':.82,'probable':.64,'whitespace_shortlist':.68})
  self.assertEqual(d['rows'][0]['status'],'CONFIRMED_RELATION')
 def test_vendor_pair_has_caution(self):
  d=build_vendor_pairs({'vendors':[{'vendor':'A','top_technologies':['Cybersecurity'],'avg_materiality':.8},{'vendor':'B','top_technologies':['Identity'],'avg_materiality':.8}]},['A','B'])
  self.assertEqual(len(d['pairs']),1);self.assertIn('no implica',d['pairs'][0]['caution'])
 def test_architectures_original_style(self):
  d=build_architectures({'vendors':[]},[]);self.assertGreaterEqual(len(d['architectures']),5);self.assertIn('no proprietary',d['meta']['style'])
 def test_validator_requires_provenance(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);(r/'data/v33').mkdir(parents=True)
   for n in ['integrator_vendor_matrix.json','distributor_vendor_matrix.json','vendor_pair_intelligence.json','architectures.json','last_run.json']:(r/'data/v33'/n).write_text('{}',encoding='utf-8')
   (r/'data/v33/ecosystem_profiles.json').write_text(json.dumps({'integrators':[{'name':'X'}],'distributors':[]}),encoding='utf-8')
   self.assertTrue(any('provenance' in x for x in validate(r)))
if __name__=='__main__':unittest.main()
