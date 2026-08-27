import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from v33.targeted_research import _build_jobs
from v33.matrix_engine import build_distributor_matrix,build_vendor_pairs,build_relationship_matrix
from v33.architecture_engine import build_architectures

class T(unittest.TestCase):
 def test_fair_share_reaches_integrators(self):
  ents=[{'name':f'D{i}','entity_type':'distributor','country':'ES'} for i in range(24)]+[{'name':f'I{i}','entity_type':'integrator','country':'ES'} for i in range(137)]
  cfg={'field_priorities':{},'minimum_integrator_share':.68,'pair_verification_share':{'daily':0}}
  jobs=_build_jobs(ents,['Cisco'],{},[],cfg,84)
  types=[x['entity_type'] for x in jobs]
  self.assertGreaterEqual(types.count('integrator'),55)
  self.assertGreater(len({x['name'] for x in jobs}),60)
 def test_gap_priority_prefers_missing(self):
  ents=[{'name':'I1','entity_type':'integrator','country':'ES'}]
  prev={'integrators':[{'name':'I1','vendors':['Cisco'],'coverage_score':20,'evidence_count':1}]}
  cfg={'field_priorities':{'certifications':1,'vendors':1},'minimum_integrator_share':1,'pair_verification_share':{'daily':0}}
  jobs=_build_jobs(ents,['Cisco'],prev,[],cfg,3)
  self.assertNotEqual(jobs[0]['field'],'vendors')
 def test_relation_with_whitespace_does_not_crash(self):
  p=[{'name':'I','entity_type':'integrator','vendors':['Cisco'],'confidence':.8,'westcon_relevance':80,'capability_score':70,'evidence':[{'title':'I Cisco partner','source':'Cisco','confidence':.9,'source_grade':'A'}],'whitespace_candidates':[{'vendor':'Cisco','research_priority_score':.8}]}]
  d=build_relationship_matrix(p,['Cisco'],{'confirmed':.82,'probable':.64,'whitespace_shortlist':.68})['rows'][0]
  self.assertIn(d['status'],{'PROBABLE_RELATION','CONFIRMED_RELATION'});self.assertGreaterEqual(d['whitespace_score'],0)
 def test_distributor_matrix_has_status(self):
  p=[{'name':'D','entity_type':'distributor','vendors':['Cisco'],'confidence':.9,'competitive_pressure':70,'competitive_response_priority':70,'westcon_relevance':80,'evidence':[{'title':'D distribuidor Cisco','source':'Cisco','confidence':.9,'source_grade':'A'}]}]
  d=build_distributor_matrix(p,['Cisco'])['rows'][0]
  self.assertEqual(d['status'],'CONFIRMED_DISTRIBUTION');self.assertIsInstance(d['priority_score'],int)
 def test_relation_priority_normalized(self):
  p=[{'name':'I','entity_type':'integrator','vendors':[],'confidence':.7,'westcon_relevance':80,'capability_score':70,'evidence':[],'whitespace_candidates':[{'vendor':'Cisco','research_priority_score':.8}]}]
  d=build_relationship_matrix(p,['Cisco'],{'confirmed':.82,'probable':.64,'whitespace_shortlist':.68})['rows'][0]
  self.assertEqual(d['status'],'WHITESPACE_RESEARCH_PRIORITY');self.assertLessEqual(d['priority_score'],100)
 def test_vendor_pair_exposes_overlap_and_readiness(self):
  port={'vendors':[{'vendor':'A','top_technologies':['Cybersecurity'],'avg_materiality':.8,'evidence_events':4},{'vendor':'B','top_technologies':['Identity'],'avg_materiality':.7,'evidence_events':3}]}
  d=build_vendor_pairs(port,['A','B'],[])["pairs"][0]
  self.assertIn('overlap_score',d);self.assertIn('commercial_play_readiness',d)
 def test_architecture_strength_not_hardcoded(self):
  port={'vendors':[{'vendor':'A','top_technologies':['Cybersecurity'],'avg_materiality':.4,'evidence_events':1}]}
  d=build_architectures(port,['A'],[])['architectures']
  vals={x['evidence_strength'] for x in d}
  self.assertGreater(len(vals),1)
if __name__=='__main__':unittest.main()
