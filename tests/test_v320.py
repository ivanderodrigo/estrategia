import json,re,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class T(unittest.TestCase):
 def setUp(self):
  self.d=json.loads((ROOT/'data/current/intelligence.json').read_text(encoding='utf-8'))
  self.g=json.loads((ROOT/'data/current/research_gaps.json').read_text(encoding='utf-8'))
  self.r=json.loads((ROOT/'data/current/relationship_graph.json').read_text(encoding='utf-8'))
  self.q=json.loads((ROOT/'data/current/quality_report.json').read_text(encoding='utf-8'))
 def test_version(self): self.assertEqual(self.d['meta']['version'],'3.20.0');self.assertEqual((ROOT/'VERSION').read_text(encoding='utf-8').strip(),'3.20.0')
 def test_no_embedded_baselines(self): self.assertFalse(any(k.startswith('_baseline_') for k in self.d))
 def test_business_rules(self):
  self.assertNotIn('Comstor',[r['name'] for r in self.d['distributors']]);self.assertNotIn('Forescout',[r['name'] for r in self.d['manufacturers']])
  self.assertFalse(set(r['name'] for r in self.d['distributors']) & set(r['name'] for r in self.d['manufacturers']))
 def test_alias_merges(self): self.assertNotIn('Arrow Electronics',[r['name'] for r in self.d['distributors']]);self.assertNotIn('Digicomp',[r['name'] for r in self.d['distributors']])
 def test_relationship_evidence(self): self.assertTrue(self.r['relationships']);self.assertTrue(all(x.get('evidence') and all(str(e.get('url') or '').startswith('http') for e in x['evidence']) for x in self.r['relationships']))
 def test_relationship_unique_canonical_edge(self):
  keys=[(x.get('entity_a_id'),x.get('relation'),x.get('entity_b_id')) for x in self.r['relationships']];self.assertEqual(len(keys),len(set(keys)))
 def test_gaps_strict(self): self.assertTrue(all(g['research_state']=='Por investigar' for g in self.g['gaps']))
 def test_release_improves_baseline(self): self.assertLess(self.g['total_gaps'],1450);self.assertLess(self.g['by_section']['integrators'],737);self.assertLessEqual(self.g['by_section']['distributors'],190)
 def test_current_only(self):
  for d in ['assets','data','config','scripts']: self.assertFalse(list((ROOT/d).glob('v[0-9]*')))
 def test_no_duplicate_linecard_vendor(self):
  for section in ['distributors','integrators']:
   for row in self.d[section]:
    v=((row.get('fields') or {}).get('vendor_relations') or {}).get('value')
    if isinstance(v,list):
     keys=[str(x).split(' · ',1)[0].casefold() for x in v];self.assertEqual(len(keys),len(set(keys)),f'{section}/{row["name"]}')
 def test_table_common_component(self):
  js=(ROOT/'assets/app/intelligence.js').read_text(encoding='utf-8')
  for v in ['manufacturers','integrators','distributors','clients_public','clients_private']: self.assertIn(v,js)
  for token in ['reorderColumn','setColumnVisible','currentColumnWidth','columnChooser']: self.assertIn(token,js)
 def test_public_projection_is_only_frontend_dataset(self):
  js=(ROOT/'assets/app/intelligence.js').read_text(encoding='utf-8');pages=(ROOT/'.github/workflows/pages-deploy.yml').read_text(encoding='utf-8')
  self.assertIn('data/public/manifest.json',js);self.assertNotIn('data/current/intelligence.json',js);self.assertIn('data/public',pages);self.assertNotIn('cp data/current',pages)
  manifest=json.loads((ROOT/'data/public/manifest.json').read_text(encoding='utf-8'));self.assertEqual(set(manifest['sections']),{'manufacturers','distributors','integrators','clients_public','clients_private','trends','architectures'})
 def test_quality_gate(self): self.assertEqual(self.q['errors'],[]);self.assertGreaterEqual(self.q['score'],95)
 def test_research_semantics(self):
  s=(ROOT/'scripts/research_supervisor.py').read_text(encoding='utf-8')
  for token in ['fetch_attempts','pages_relevant','accepted_evidences','fields_enriched','gaps_closed_vs_release_baseline']: self.assertIn(token,s)
  planner=(ROOT/'engine/research/planner.py').read_text(encoding='utf-8');self.assertIn('"integrators": 1.55',planner);self.assertIn('"distributors": 1.45',planner)
 def test_compact_gap_plan(self): self.assertTrue(all('passes' not in g and g.get('strategy_profile')=='cascade_48' for g in self.g['gaps']))
if __name__=='__main__':unittest.main()
