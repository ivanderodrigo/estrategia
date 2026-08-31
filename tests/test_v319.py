
import json,re,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class T(unittest.TestCase):
 def setUp(self): self.d=json.loads((ROOT/'data/current/intelligence.json').read_text(encoding='utf-8'));self.g=json.loads((ROOT/'data/current/research_gaps.json').read_text(encoding='utf-8'));self.r=json.loads((ROOT/'data/current/relationship_graph.json').read_text(encoding='utf-8'))
 def test_version(self): self.assertEqual(self.d['meta']['version'],'3.19.0')
 def test_no_embedded_baselines(self): self.assertFalse(any(k.startswith('_baseline_') for k in self.d))
 def test_comstor(self): self.assertNotIn('Comstor',[r['name'] for r in self.d['distributors']])
 def test_forescout(self): self.assertNotIn('Forescout',[r['name'] for r in self.d['manufacturers']])
 def test_no_vendor_as_distributor(self): self.assertFalse(set(r['name'] for r in self.d['distributors']) & set(r['name'] for r in self.d['manufacturers']))
 def test_alias_merges(self): self.assertNotIn('Arrow Electronics',[r['name'] for r in self.d['distributors']]);self.assertNotIn('Digicomp',[r['name'] for r in self.d['distributors']])
 def test_relationship_evidence(self): self.assertTrue(self.r['relationships']);self.assertTrue(all(x.get('evidence') and all(e.get('url') for e in x['evidence']) for x in self.r['relationships']))
 def test_gaps_strict(self): self.assertTrue(all(g['research_state']=='Por investigar' for g in self.g['gaps']))
 def test_distributor_gap_reduction(self): self.assertLess(self.g['by_section']['distributors'],355)
 def test_total_gap_reduction(self): self.assertLess(self.g['total_gaps'],1615)
 def test_graph_truth(self): self.assertTrue(self.r['model']['bidirectional_projection'])
 def test_current_only(self):
  for d in ['assets','data','config','scripts']: self.assertFalse(list((ROOT/d).glob('v[0-9]*')))
 def test_table_common_component(self):
  js=(ROOT/'assets/app/intelligence.js').read_text(encoding='utf-8');
  for v in ['manufacturers','integrators','distributors','clients_public','clients_private']: self.assertIn(v,js)
  for token in ['reorderColumn','setColumnVisible','currentColumnWidth','columnChooser']: self.assertIn(token,js)

 def test_relationship_unique_canonical_edge(self):
  keys=[(x.get('entity_a_id'),x.get('relation'),x.get('entity_b_id')) for x in self.r['relationships']];self.assertEqual(len(keys),len(set(keys)))
 def test_no_duplicate_linecard_vendor(self):
  for row in self.d['distributors']:
   v=((row.get('fields') or {}).get('vendor_relations') or {}).get('value')
   if isinstance(v,list):self.assertEqual(len(v),len(dict.fromkeys(str(x).casefold() for x in v)),row['name'])
 def test_pages_does_not_publish_internal_research(self):
  t=(ROOT/'.github/workflows/pages-deploy.yml').read_text(encoding='utf-8')
  for x in ['research_ledger','research_learning','research_gaps','relationship_graph']:
   self.assertNotIn('cp data/current/'+x,t)
 def test_compact_gap_plan(self):
  self.assertTrue(all('passes' not in g and g.get('strategy_profile')=='cascade_48' for g in self.g['gaps']))

if __name__=='__main__':unittest.main()
