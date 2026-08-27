import sys,unittest,tempfile,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from v33.pipeline import _merge_targeted,_coverage_report,_research_plan,_verification_queue
from v33.ecosystem_engine import _entity_rows,_tiering
from v33.matrix_engine import build_relationship_matrix,build_distributor_matrix
from v33.targeted_research import _build_jobs

class T(unittest.TestCase):
 def test_cumulative_evidence_survives_short_run(self):
  old={'evidence':[{'name':'I','field':'vendors','title':'I partner Cisco','url':'u1','source':'Cisco','source_grade':'A','confidence':.9,'observed_at':'2026-08-01T00:00:00+00:00'}]}
  merged,new=_merge_targeted(old,[], 'daily')
  self.assertEqual(len(merged),1);self.assertEqual(new,0);self.assertIn('first_seen_at',merged[0])
 def test_repeat_evidence_increases_seen_not_count(self):
  old={'evidence':[{'name':'I','field':'vendors','title':'I partner Cisco','url':'u1','source':'Cisco','source_grade':'B','confidence':.7,'seen_count':1}]}
  cur=[{'name':'I','field':'vendors','title':'I partner Cisco','url':'u1','source':'Cisco','source_grade':'A','confidence':.9,'observed_at':'2026-08-27T00:00:00+00:00'}]
  merged,new=_merge_targeted(old,cur,'weekly')
  self.assertEqual(len(merged),1);self.assertEqual(new,0);self.assertEqual(merged[0]['seen_count'],2);self.assertEqual(merged[0]['source_grade'],'A')
 def test_exact_duplicate_entities_are_consolidated(self):
  d={'integrators':[{'name':'Ayesa','vendors':['Cisco'],'confidence':.6},{'name':'Ayesa','vendors':['AWS'],'confidence':.8}]}
  rows=_entity_rows(d)
  self.assertEqual(len(rows),1);self.assertEqual(set(rows[0]['vendors']),{'Cisco','AWS'});self.assertEqual(rows[0]['confidence'],.8)
 def test_t1_has_higher_coverage_target(self):
  _,tier,target,gap,attain,_=_tiering('integrator','ES',.95,90,0,90,0,.8,.9,50)
  self.assertEqual(tier,'T1');self.assertEqual(target,85);self.assertEqual(gap,35);self.assertLess(attain,100)
 def test_scheduler_prefers_t1_gap(self):
  ents=[{'name':'T1Co','entity_type':'integrator','country':'ES'},{'name':'T3Co','entity_type':'integrator','country':'ES'}]
  prev={'integrators':[{'name':'T1Co','entity_tier':'T1','coverage_target':85,'coverage_score':20,'westcon_relevance':90,'activation_priority':90},{'name':'T3Co','entity_tier':'T3','coverage_target':40,'coverage_score':30,'westcon_relevance':20,'activation_priority':20}]}
  cfg={'field_priorities':{},'minimum_integrator_share':1,'pair_verification_share':{'daily':0}}
  jobs=_build_jobs(ents,['Cisco'],prev,[],cfg,2)
  self.assertEqual(jobs[0]['name'],'T1Co')
 def test_relationship_intensity_is_separate_metric(self):
  p=[{'name':'I','entity_type':'integrator','vendors':['Cisco'],'confidence':.9,'westcon_relevance':90,'capability_score':80,'evidence':[{'title':'I Cisco certified partner','source':'Cisco','confidence':.95,'source_grade':'A','classification':'certification'},{'title':'I Cisco customer case','source':'BPS Channel Partner','confidence':.8,'source_grade':'B','classification':'customer_reference'}]}]
  row=build_relationship_matrix(p,['Cisco'],{'confirmed':.82,'probable':.64,'confirmed_min_evidence':2})['rows'][0]
  self.assertIn(row['status'],{'CONFIRMED_RELATION','PROBABLE_RELATION'});self.assertGreater(row['relationship_intensity'],50);self.assertEqual(row['official_evidence_count'],1)
 def test_distributor_intensity_exists(self):
  p=[{'name':'D','entity_type':'distributor','vendors':['Cisco'],'confidence':.9,'competitive_pressure':70,'competitive_response_priority':70,'westcon_relevance':80,'evidence':[{'title':'D distribuidor Cisco','source':'Cisco','confidence':.9,'source_grade':'A'}]}]
  row=build_distributor_matrix(p,['Cisco'])['rows'][0]
  self.assertGreater(row['relationship_intensity'],0);self.assertEqual(row['official_evidence_count'],1)
 def test_verification_queue_contains_probable(self):
  im={'rows':[{'integrator':'I','vendor':'Cisco','status':'PROBABLE_RELATION','priority_score':80,'relationship_intensity':60,'evidence_grade':'B','evidence_count':1,'next_research':'x'}]};dm={'rows':[]}
  q=_verification_queue(im,dm)['queue']
  self.assertEqual(len(q),1);self.assertEqual(q[0]['status'],'PROBABLE_RELATION')
 def test_coverage_report_has_tiers(self):
  ps=[{'entity_type':'integrator','entity_tier':'T1','coverage_score':50,'coverage_target':85,'coverage_gap':35,'evidence_grade':'B','vendors':['Cisco'],'technology_focus':['Cloud'],'certifications':[],'verticals':[],'customer_cases':[],'managed_services':[]}]
  d=_coverage_report(ps)
  self.assertEqual(d['by_tier']['T1']['entities'],1);self.assertEqual(d['summary']['average_target'],85)

if __name__=='__main__':unittest.main()
