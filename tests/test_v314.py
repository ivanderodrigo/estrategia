from __future__ import annotations
import json,re,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DATA=json.loads((ROOT/'data/v314/intelligence.json').read_text(encoding='utf8'))
RUN=json.loads((ROOT/'data/v314/last_run.json').read_text(encoding='utf8'))
GAPS=json.loads((ROOT/'data/v314/research_gaps.json').read_text(encoding='utf8'))
INDEX=(ROOT/'index.html').read_text(encoding='utf8');JS=(ROOT/'assets/v314/intelligence.js').read_text(encoding='utf8');CSS=(ROOT/'assets/v314/intelligence.css').read_text(encoding='utf8')
def canon(v):return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9áéíóúüñçãõâêôàèìòùäëïöü]+',' ',str(v or '').casefold())).strip()
def fval(row,fid):return ((row.get('fields') or {}).get(fid) or {}).get('value')
class TestV314(unittest.TestCase):
 def test_01_version(self):self.assertEqual((ROOT/'VERSION').read_text().strip(),'3.14.0');self.assertEqual(DATA['meta']['version'],'3.14.0');self.assertEqual(RUN['version'],'3.14.0')
 def test_02_domain_coverage(self):
  for k,m in {'manufacturers':36,'distributors':50,'integrators':120,'clients_public':25,'clients_private':51,'trends':15,'architectures':10}.items():self.assertGreaterEqual(len(DATA[k]),m,k)
 def test_03_distributors_positive_only(self):
  vendors={canon(x['name']) for x in DATA['manufacturers']};dists={canon(x['name']) for x in DATA['distributors']};self.assertFalse(vendors&dists);self.assertFalse({'westcon','comstor','westcon comstor'}&dists)
  for r in DATA['distributors']:self.assertTrue(((r.get('fields') or {}).get('validation_status') or {}).get('evidence'),r['name'])
 def test_04_forescout_out(self):self.assertNotIn('forescout',{canon(x['name']) for x in DATA['manufacturers']})
 def test_05_distributor_decision_columns(self):
  s={x['id']:x for x in DATA['schemas']['distributors']}
  for fid in ('revenue','vendor_relations','westcon_overlap','competitor_vendor_overlap','differential_capabilities'):self.assertIn(fid,s)
  for fid in ('vendor_relations','westcon_overlap','competitor_vendor_overlap','differential_capabilities'):self.assertTrue(s[fid].get('decision_required'),fid)
 def test_06_distributor_revenue(self):self.assertGreaterEqual(sum(bool(fval(r,'revenue')) for r in DATA['distributors']),14)
 def test_07_distributor_capabilities(self):self.assertGreaterEqual(sum(bool(fval(r,'differential_capabilities')) for r in DATA['distributors']),12)
 def test_08_competitive_linecard(self):
  ex=next(r for r in DATA['distributors'] if r['name']=='Exclusive Networks');self.assertTrue(any('Fortinet' in str(x) for x in fval(ex,'competitor_vendor_overlap')))
 def test_09_manufacturer_competitors(self):self.assertGreaterEqual(sum(bool(fval(r,'competitors')) for r in DATA['manufacturers']),30)
 def test_10_missing_competitors_small(self):self.assertLessEqual(sum(not bool(fval(r,'competitors')) for r in DATA['manufacturers']),6)
 def test_11_ibex_complete(self):self.assertEqual(sum(fval(r,'index_universe')=='IBEX 35' for r in DATA['clients_private']),35)
 def test_12_psi_complete(self):self.assertEqual(sum(fval(r,'index_universe')=='PSI' for r in DATA['clients_private']),16)
 def test_13_procurement_exact(self):
  for r in DATA['clients_public']:
   ev=(r.get('evidence') or [{}])[0];url=str(ev.get('url') or '');portal=str(fval(r,'source_portal') or '');self.assertTrue(fval(r,'notice_id'));self.assertTrue(('ted.europa.eu' in url and '/notice/-/detail/' in url) or ('PLACSP' in portal and ('contrataciondelestado' in url or 'contrataciondelsectorpublico' in url)),url)
 def test_14_graph(self):self.assertGreaterEqual(RUN['integrator_graph']['unique_vendor_integrator_edges'],230);self.assertGreaterEqual(RUN['integrator_graph']['avg_integrators_per_manufacturer'],6.4)
 def test_15_sources(self):self.assertGreaterEqual(len(DATA['source_catalog']),290)
 def test_16_gap_model(self):self.assertEqual(GAPS['version'],'3.14.0');self.assertGreater(GAPS['total_gaps'],0);self.assertLess(GAPS['total_gaps'],800);self.assertIn('optional_missing_by_field',GAPS)
 def test_17_gap_reduction(self):self.assertLessEqual(GAPS['by_section']['distributors'],150);self.assertLessEqual(GAPS['by_section']['integrators'],300)
 def test_18_user_facing_headers(self):
  self.assertIn('Comparativa de mayoristas y distribuidores que compiten en España y Portugal.',INDEX);self.assertIn('Panorama de clientes y oportunidades en España y Portugal.',INDEX);self.assertIn('Mapa de integradores, instaladores, resellers/VAR, MSP, MSSP, service providers y consultoras relevantes',INDEX);self.assertNotIn('Solo mayoristas/distribuidores competidores.',INDEX);self.assertNotIn('Se separan clientes públicos y privados porque la evidencia admisible es distinta.',INDEX)
 def test_19_optional_empty_not_research(self):self.assertIn('missingMarkup',JS);self.assertIn('Pendiente de evidencia',JS);self.assertIn('no-public-data',JS)
 def test_20_required_columns_persist(self):self.assertIn('if(col.decision_required) return true;',JS);self.assertIn('Math.ceil(rows.length*.20)',JS)
 def test_21_trace_click(self):self.assertNotIn("document.addEventListener('pointerover'",JS);self.assertIn("const trace=e.target.closest('.traceable')",JS);self.assertIn('id="tracePortal"',INDEX)
 def test_22_exports(self):self.assertIn('window.jspdf?.jsPDF',JS);self.assertIn('v3.14.0.pdf',JS);self.assertIn('v3.14.0.pptx',JS)
 def test_23_frontend(self):self.assertIn("fetch('data/v314/intelligence.json'",JS);self.assertIn('assets/v314/intelligence.js?v=3.14.0',INDEX)
 def test_24_workflows(self):
  for n in ('research-daily.yml','research-weekly.yml','research-monthly.yml'):
   t=(ROOT/'.github/workflows'/n).read_text(encoding='utf8');self.assertIn('research_supervisor_v314.py',t);self.assertIn('tests/test_v314.py',t);self.assertIn('data/v314/',t)
 def test_25_pages(self):self.assertIn('cp -R data/v314 _site/data/v314',(ROOT/'.github/workflows/pages-deploy.yml').read_text(encoding='utf8'))
 def test_26_responsive(self):self.assertIn('@media(max-width:900px)',CSS);self.assertIn('@media(max-width:620px)',CSS)
if __name__=='__main__':unittest.main()
