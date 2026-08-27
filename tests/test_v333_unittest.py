import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from v33.ecosystem_engine import _entity_rows,_assign_relative_tiers
from v33.pipeline import _coverage_report,_relationship_movement
from v33.targeted_research import _profile_map

class T(unittest.TestCase):
 def test_consolidation_is_auditable_and_preserves_country_operations(self):
  d={'integrators':[{'name':'Example SI','country':'ES','vendors':['Cisco']},{'name':'Example SI','country':'PT','vendors':['AWS']} ]}
  rows,report=_entity_rows(d,with_report=True)
  self.assertEqual(len(rows),1)
  self.assertEqual(rows[0]['scope'],'IBERIA')
  self.assertEqual(set(rows[0]['scope_variants']),{'ES','PT'})
  self.assertEqual(rows[0]['operation_count'],2)
  self.assertEqual(report['summary']['consolidated_source_variants'],1)
  self.assertEqual(report['summary']['ambiguous_merges'],0)
  self.assertEqual(len(report['groups']),1)
 def test_exact_name_only_not_fuzzy(self):
  d={'integrators':[{'name':'NTT DATA Spain','country':'ES'},{'name':'NTT DATA Portugal','country':'PT'}]}
  rows,report=_entity_rows(d,with_report=True)
  self.assertEqual(len(rows),2);self.assertEqual(report['summary']['consolidated_source_variants'],0)
 def test_relative_tiers_are_not_driven_by_confidence(self):
  rows=[]
  for i in range(20):
   rows.append({'name':f'I{i}','entity_type':'integrator','strategic_importance_score':100-i,'westcon_relevance':50,'activation_priority':50,'coverage_score':20,'confidence':0.05 if i==0 else .95,'evidence':[],'provenance':{}})
  _assign_relative_tiers(rows)
  counts={k:sum(1 for x in rows if x['entity_tier']==k) for k in ('T1','T2','T3')}
  self.assertEqual(counts,{'T1':3,'T2':7,'T3':10})
  self.assertEqual(rows[0]['entity_tier'],'T1')
 def test_coverage_separates_mean_delta_from_knowledge_debt(self):
  ps=[
   {'entity_type':'integrator','entity_tier':'T3','coverage_score':100,'coverage_target':40,'coverage_gap':0,'evidence_grade':'B','vendors':['Cisco'],'certifications':['x'],'technology_focus':['Cloud'],'verticals':['Public'],'customer_cases':['A'],'managed_services':['SOC']},
   {'entity_type':'integrator','entity_tier':'T1','coverage_score':0,'coverage_target':80,'coverage_gap':80,'evidence_grade':'D','vendors':[],'certifications':[],'technology_focus':[],'verticals':[],'customer_cases':[],'managed_services':[]}
  ]
  s=_coverage_report(ps)['summary']
  self.assertEqual(s['average_coverage'],50.0);self.assertEqual(s['average_target'],60.0)
  self.assertEqual(s['difference_between_averages'],10.0);self.assertEqual(s['average_knowledge_debt'],40.0)
 def test_relationship_movement_tracks_transition(self):
  old={'rows':[{'integrator':'I','vendor':'Cisco','status':'PROBABLE_RELATION','priority_score':80}]}
  new={'rows':[{'integrator':'I','vendor':'Cisco','status':'CONFIRMED_RELATION','priority_score':90,'relationship_intensity':85}]}
  m=_relationship_movement(old,new,'integrator')
  self.assertEqual(m['changed_pairs'],1);self.assertEqual(m['uncertainty_resolved'],1)
  self.assertEqual(m['transitions']['PROBABLE_RELATION→CONFIRMED_RELATION'],1)
 def test_profile_map_uses_canonical_flat_collection_once(self):
  d={'profiles':[{'name':'A','coverage_score':10},{'name':'B','coverage_score':20}], 'integrators':[{'name':'A','coverage_score':99}], 'distributors':[{'name':'B','coverage_score':99}]}
  m=_profile_map(d)
  self.assertEqual(len(m),2);self.assertEqual(m['a']['coverage_score'],10);self.assertEqual(m['b']['coverage_score'],20)

if __name__=='__main__':unittest.main()
