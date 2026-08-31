from __future__ import annotations
import json,re,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
import sys;sys.path.insert(0,str(ROOT/'scripts'))
from v316.gap_engine import SECTIONS,evidence_rows,evidence_sufficient,has_value
DATA=json.loads((ROOT/'data/v316/intelligence.json').read_text(encoding='utf-8'));RUN=json.loads((ROOT/'data/v316/last_run.json').read_text(encoding='utf-8'));GAPS=json.loads((ROOT/'data/v316/research_gaps.json').read_text(encoding='utf-8'));METRICS=json.loads((ROOT/'data/v316/metrics_before_after.json').read_text(encoding='utf-8'));INDEX=(ROOT/'index.html').read_text(encoding='utf-8');JS=(ROOT/'assets/v316/intelligence.js').read_text(encoding='utf-8');CSS=(ROOT/'assets/v316/intelligence.css').read_text(encoding='utf-8')
def canon(v):return re.sub(r'[^a-z0-9]+',' ',str(v or '').casefold()).strip()
def field(row,fid):return (row.get('fields') or {}).get(fid) or {}
def row(section,name):return next(r for r in DATA[section] if r['name']==name)
class TestV316(unittest.TestCase):
 def test_01_version_everywhere(self):self.assertEqual((ROOT/'VERSION').read_text().strip(),'3.16.0');self.assertEqual(DATA['meta']['version'],'3.16.0');self.assertEqual(RUN['version'],'3.16.0');self.assertEqual(GAPS['version'],'3.16.0')
 def test_02_domain_coverage(self):
  for k,m in {'manufacturers':36,'distributors':50,'integrators':120,'clients_public':25,'clients_private':51,'trends':15,'architectures':10}.items():self.assertGreaterEqual(len(DATA[k]),m,k)
 def test_03_comstor_never_competitor(self):self.assertNotIn('comstor',{canon(x['name']) for x in DATA['distributors']});self.assertNotIn('westcon comstor',{canon(x['name']) for x in DATA['distributors']})
 def test_04_manufacturers_not_distributors(self):self.assertFalse({canon(x['name']) for x in DATA['manufacturers']}&{canon(x['name']) for x in DATA['distributors']})
 def test_05_distributors_positive_validation(self):
  for r in DATA['distributors']:self.assertTrue(evidence_rows(field(r,'validation_status')),r['name'])
 def test_06_expected_fields_preserved(self):
  for section in SECTIONS:self.assertTrue(all(c.get('expected') for c in DATA['schemas'][section]),section)
 def test_07_ui_never_renders_dash_pending(self):self.assertNotIn('>—<',JS);self.assertNotIn('>N/D<',JS)
 def test_08_ui_uses_por_investigar(self):self.assertIn('Por investigar</span>',JS);self.assertIn('function missingMarkup',JS)
 def test_09_empty_fields_route_to_missing_markup(self):self.assertIn("f&&hasValue(f.value)?renderValue(f,null,'table'):missingMarkup(col)",JS)
 def test_10_expected_columns_not_sparse_hidden(self):self.assertIn("let cols=schema.filter(col=>col.hidden!==true)",JS);self.assertNotIn('Math.ceil(rows.length*.20)',JS)
 def test_11_gap_fixed_definition(self):self.assertIn('Misma definición v3.15→v3.16',GAPS['definition']);self.assertGreater(GAPS['total_gaps'],0)
 def test_12_gap_has_32_passes(self):self.assertTrue(all(len(g['passes'])==32 for g in GAPS['gaps']))
 def test_13_gap_languages(self):self.assertEqual(GAPS['engine']['languages'],['es','pt','en'])
 def test_14_zero_results_do_not_close_gap(self):self.assertTrue(all('cero resultados' in g['close_policy'] for g in GAPS['gaps']))
 def test_15_gap_not_closed_without_evidence(self):
  byid={(s,r.get('id')):r for s in SECTIONS for r in DATA[s]}
  for g in GAPS['gaps']:self.assertFalse(evidence_sufficient(field(byid[(g['section'],g['entity_id'])],g['field'])),g['id'])
 def test_16_gap_states(self):self.assertEqual(set(GAPS['research_states']),{'Por investigar'})
 def test_17_resilience(self):
  e=GAPS['engine'];self.assertEqual(e['retries'],4);self.assertEqual(e['backoff'],'exponential');self.assertTrue(e['resume']);self.assertTrue(e['incremental']);self.assertTrue(e['contradiction_pass']);self.assertGreater(e['checkpoint_every_results'],0)
 def test_18_source_growth(self):self.assertGreater(METRICS['after']['sources'],METRICS['before']['sources']);self.assertGreaterEqual(METRICS['delta']['sources'],20)
 def test_19_source_diversity(self):self.assertGreater(METRICS['after']['unique_domains'],METRICS['before']['unique_domains']);self.assertGreaterEqual(METRICS['after']['unique_domains'],175)
 def test_20_real_new_information(self):self.assertGreaterEqual(METRICS['new_information']['newly_populated_fields'],350);self.assertGreaterEqual(METRICS['new_information']['new_values_added'],500)
 def test_21_gaps_reduced(self):self.assertLess(METRICS['after']['research_gaps'],METRICS['before']['research_gaps']);self.assertGreater(METRICS['gap_reduction_pct'],17)
 def test_22_traceable_fields_grow(self):self.assertGreater(METRICS['after']['traceable_fields'],METRICS['before']['traceable_fields'])
 def test_23_official_evidence_grows(self):self.assertGreater(METRICS['after']['official_evidence'],METRICS['before']['official_evidence'])
 def test_24_reports_exist(self):
  for n in ('metrics_before_after.json','source_report.json','coverage_report.json','research_gaps.json'):self.assertTrue((ROOT/'data/v316'/n).is_file(),n)
 def test_25_curated_entities(self):
  for section,names in {'distributors':['Infinigate','Esprinet / V-Valley','EET Portugal','Jarltech'],'clients_private':['ACS','Acciona','Fluidra','Banco Comercial Português','Mota-Engil'],'integrators':['Inetum Spain','Deloitte','IBM Consulting','Devoteam Portugal']}.items():
   actual={r['name'] for r in DATA[section]};self.assertTrue(set(names)<=actual)
 def test_26_signals_not_facts(self):
  for section in SECTIONS:
   for r in DATA[section]:
    for fid,spec in (r.get('fields') or {}).items():
     vals=spec.get('value') if isinstance(spec.get('value'),list) else [spec.get('value')]
     if any(str(v).upper().startswith('SEÑAL') for v in vals):self.assertEqual(spec.get('claim_type'),'signal',(section,r['name'],fid))
 def test_27_interpretations_not_facts(self):
  for section in SECTIONS:
   for r in DATA[section]:
    for fid,spec in (r.get('fields') or {}).items():
     vals=spec.get('value') if isinstance(spec.get('value'),list) else [spec.get('value')]
     if any(str(v).upper().startswith('INTERPRETACIÓN') for v in vals):self.assertEqual(spec.get('claim_type'),'interpretation',(section,r['name'],fid))
 def test_28_strong_evidence_traceable(self):
  for section in SECTIONS:
   for r in DATA[section]:
    for fid,spec in (r.get('fields') or {}).items():
     if float(spec.get('confidence') or 0)>=.8:self.assertTrue(any(all(str(ev.get(k) or '').strip() for k in ('source','title','url','date','description')) for ev in evidence_rows(spec)),(section,r['name'],fid))
 def test_29_secondary_not_official(self):
  for name in ('Ciena','NETSCOUT','Weblib'):
   ev=field(row('manufacturers',name),'competitors')['evidence'][0];self.assertFalse(ev['official']);self.assertIn(ev['source_type'],{'peer-review','public-web'})
 def test_30_confidence_dimensions(self):self.assertIn('fact_confidence',JS);self.assertIn('interpretation_confidence',JS);self.assertIn('action_risk',JS);self.assertIn('Riesgo de acción',INDEX)
 def test_31_user_facing_headers(self):
  self.assertIn('Linecard, escala y capacidades diferenciales.',INDEX);self.assertIn('Ecosistema de partners y capacidades.',INDEX)
  for phrase in ('solo se incluyen','se excluyen','hemos decidido','esta tabla no contiene'):self.assertNotIn(phrase,INDEX.casefold())
 def test_32_frontend_version(self):self.assertIn("fetch('data/v316/intelligence.json'",JS);self.assertIn('assets/v316/intelligence.js?v=3.16.0',INDEX)
 def test_33_exports(self):self.assertIn('window.jspdf?.jsPDF',JS);self.assertIn('v3.16.0.pdf',JS);self.assertIn('v3.16.0.pptx',JS)
 def test_34_workflows(self):
  for n in ('research-daily.yml','research-weekly.yml','research-monthly.yml'):
   t=(ROOT/'.github/workflows'/n).read_text();self.assertIn('research_supervisor_v316.py',t);self.assertIn('tests/test_v316.py',t);self.assertIn('data/v316/',t)
 def test_35_pages(self):self.assertIn('cp -R data/v316 _site/data/v316',(ROOT/'.github/workflows/pages-deploy.yml').read_text())
 def test_36_responsive(self):self.assertIn('@media(max-width:900px)',CSS);self.assertIn('@media(max-width:620px)',CSS)
 def test_37_documentation(self):self.assertTrue((ROOT/'README_V316.md').exists());self.assertTrue((ROOT/'CHANGELOG_V316.md').exists())
 def test_38_signals_are_red(self):
  for section in SECTIONS:
   for r in DATA[section]:
    for spec in (r.get('fields') or {}).values():
     if spec.get('claim_type')=='signal':self.assertEqual((spec.get('evidence_color'),spec.get('confidence_band')),('red','low'))
 def test_39_interpretations_are_yellow(self):
  for section in SECTIONS:
   for r in DATA[section]:
    for spec in (r.get('fields') or {}).values():
     if spec.get('claim_type')=='interpretation':self.assertEqual((spec.get('evidence_color'),spec.get('confidence_band')),('yellow','medium'))
 def test_40_ui_explains_traffic_light(self):
  for text in ('VERDE · evidencia fuerte','AMARILLO · evidencia parcial','ROJO · señal o indicio'):self.assertIn(text,INDEX+JS)
if __name__=='__main__':unittest.main()
