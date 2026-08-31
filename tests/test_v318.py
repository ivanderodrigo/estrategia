import json,re,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
D=json.load(open(ROOT/'data/v318/intelligence.json',encoding='utf-8'));G=json.load(open(ROOT/'data/v318/relationship_graph.json',encoding='utf-8'));M=json.load(open(ROOT/'data/v318/metrics_before_after.json',encoding='utf-8'));JS=(ROOT/'assets/v318/intelligence.js').read_text(encoding='utf-8')
def c(v):return re.sub(r'[^a-z0-9]+',' ',str(v or '').casefold()).strip()
class TestV318(unittest.TestCase):
 def test_version(self):self.assertEqual((ROOT/'VERSION').read_text().strip(),'3.18.0')
 def test_graph(self):self.assertGreaterEqual(len(G['relationships']),1000);self.assertTrue(G['model']['bidirectional_projection'])
 def test_linecards(self):self.assertGreaterEqual(M['graph']['linecards_found'],9);self.assertGreaterEqual(M['graph']['linecard_vendors_extracted'],160)
 def test_gap_reduction_real(self):self.assertLess(M['after']['research_gaps'],M['before']['research_gaps'])
 def test_no_manufacturer_as_distributor(self):self.assertFalse({c(x['name']) for x in D['manufacturers']}&{c(x['name']) for x in D['distributors']})
 def test_comstor(self):self.assertNotIn('comstor',{c(x['name']) for x in D['distributors']})
 def test_forescout(self):self.assertNotIn('forescout',{c(x['name']) for x in D['manufacturers']})
 def test_shared_table_clients_rerender(self):self.assertIn('clients_public:renderClients',JS);self.assertIn('clients_private:renderClients',JS)
 def test_table_drag(self):self.assertIn('reorderColumn',JS);self.assertIn('draggable="true"',JS)
 def test_table_resize(self):self.assertIn('col-resizer',JS);self.assertIn('setColumnWidth',JS)
 def test_table_visibility(self):self.assertIn('data-col-toggle',JS);self.assertIn('setColumnVisible',JS)
 def test_table_persistence(self):self.assertIn('westcon-table-widths',JS);self.assertIn('westcon-cols-',JS)
 def test_reset(self):self.assertIn('resetTablePrefs',JS)
 def test_schema_order_distributors(self):self.assertEqual([x['id'] for x in D['schemas']['distributors']][:5],['scope','revenue','westcon_overlap','competitor_vendor_overlap','vendor_relations'])
 def test_confirmed_relations_evidence(self):self.assertTrue(all(r['evidence'] for r in G['relationships'] if r['status']=='CONFIRMED'))
if __name__=='__main__':unittest.main()
