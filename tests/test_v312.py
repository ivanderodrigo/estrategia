from __future__ import annotations
import json,re,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DATA=json.loads((ROOT/'data/v312/intelligence.json').read_text(encoding='utf-8'))
RUN=json.loads((ROOT/'data/v312/last_run.json').read_text(encoding='utf-8'))
INDEX=(ROOT/'index.html').read_text(encoding='utf-8')
JS=(ROOT/'assets/v312/intelligence.js').read_text(encoding='utf-8')
CSS=(ROOT/'assets/v312/intelligence.css').read_text(encoding='utf-8')
def canon(v):return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9áéíóúüñçãõâêôàèìòùäëïöü]+',' ',str(v or '').casefold())).strip()
def fval(row,fid):return ((row.get('fields') or {}).get(fid) or {}).get('value')
class TestV312(unittest.TestCase):
    def test_version(self):
        self.assertEqual((ROOT/'VERSION').read_text().strip(),'3.12.0');self.assertEqual(DATA['meta']['version'],'3.12.0');self.assertEqual(RUN['version'],'3.12.0')
    def test_domain_coverage(self):
        for k,m in {'manufacturers':36,'distributors':50,'integrators':120,'clients_public':25,'clients_private':51,'trends':15,'architectures':10}.items():self.assertGreaterEqual(len(DATA[k]),m,k)
    def test_distributors_require_positive_validation(self):
        bad=('cradlepoint','penguin','stratus','akamai','noname','splunk','forescout','nfon','ipbrick','hama')
        names=[canon(x['name']) for x in DATA['distributors']]
        self.assertFalse(any(any(b in n for b in bad) for n in names),names)
        self.assertFalse({'westcon','comstor','westcon comstor'} & set(names))
        for row in DATA['distributors']:
            spec=(row.get('fields') or {}).get('validation_status') or {};self.assertEqual(spec.get('value'),'Mayorista / distribuidor validado',row['name']);self.assertTrue(spec.get('evidence'),row['name'])
    def test_manufacturers_never_in_distributor_table(self):
        vendors={canon(x['name']) for x in DATA['manufacturers']};dists={canon(x['name']) for x in DATA['distributors']};self.assertFalse(vendors&dists,vendors&dists)
    def test_forescout_not_westcon_portfolio(self):
        self.assertNotIn('forescout',{canon(x['name']) for x in DATA['manufacturers']})
        allowed={canon(x['name']) for x in DATA['manufacturers']}
        for section in ('clients_public','clients_private'):
            for row in DATA[section]:
                vals=fval(row,'westcon_fit') or []
                if not isinstance(vals,list):vals=[vals]
                for v in vals:self.assertIn(canon(str(v).split('·',1)[0]),allowed,(section,row['name'],v))
    def test_private_clients_full_indices(self):
        es=[x for x in DATA['clients_private'] if fval(x,'index_universe')=='IBEX 35'];pt=[x for x in DATA['clients_private'] if fval(x,'index_universe')=='PSI']
        self.assertEqual(len(es),35);self.assertEqual(len(pt),16);self.assertEqual(len(DATA['clients_private']),51)
    def test_public_procurement_exact_links(self):
        self.assertGreaterEqual(len(DATA['clients_public']),25)
        for row in DATA['clients_public']:
            nid=fval(row,'notice_id');portal=fval(row,'source_portal');self.assertTrue(nid,row['name']);self.assertTrue(portal,row['name'])
            ev=(row.get('evidence') or [None])[0] or {};url=str(ev.get('url') or '')
            self.assertTrue(('ted.europa.eu' in url and '/notice/-/detail/' in url) or ('PLACSP' in str(portal) and ('contrataciondelestado' in url or 'contrataciondelsectorpublico' in url)),url)
    def test_integrator_graph_is_much_deeper(self):
        graph=RUN['integrator_graph'];self.assertGreaterEqual(graph['unique_vendor_integrator_edges'],230);self.assertGreaterEqual(graph['avg_integrators_per_manufacturer'],6.4);self.assertGreaterEqual(len(DATA['integrators']),120)
    def test_integrator_graph_bidirectional(self):
        m=next(x for x in DATA['manufacturers'] if x['name']=='Nokia');ivals=fval(m,'integrators') or [];self.assertTrue(any('Kyndryl' in str(v) for v in ivals))
        i=next(x for x in DATA['integrators'] if x['name']=='Kyndryl');vvals=fval(i,'vendor_relations') or [];self.assertTrue(any('Nokia' in str(v) for v in vvals))
        extreme=next(x for x in DATA['manufacturers'] if x['name']=='Extreme Networks');self.assertTrue(any('Axians Spain' in str(v) for v in (fval(extreme,'integrators') or [])))
    def test_sources_expanded(self):
        ids={x['id'] for x in DATA['source_catalog']};self.assertGreaterEqual(len(ids),265)
        for sid in ('channelpartner_distributor_ranking_2026','itchannel_pt_distributor_directory','channelpartner_integrator_ranking_2026','bme_ibex35_official','euronext_psi_official','placsp_open_data_v312','ted_search_api_v3','checkpoint_gsi_official_v312','zscaler_emea_partner_awards_2026','extreme_partner_locator_spain','ruckus_partner_locator'):
            self.assertIn(sid,ids)
    def test_research_budgets_and_universe_expanded(self):
        cfg=json.loads((ROOT/'config/v312/deep_research.json').read_text(encoding='utf-8'));self.assertGreaterEqual(cfg['budgets']['partner_anchor_candidates_max'],220);self.assertGreaterEqual(cfg['budgets']['partner_page_anchors_max'],900)
        research=(ROOT/'scripts/research.py').read_text(encoding='utf-8');self.assertIn('config/v312/deep_research.json',research);self.assertIn('discovered_integrators(1200)',research)
    def test_procurement_live_collector_exists(self):
        t=(ROOT/'scripts/v312/procurement_research.py').read_text(encoding='utf-8');self.assertIn('ted_search',t);self.assertIn('atom_feed',t);self.assertIn('exact',t.casefold());self.assertIn('procurement_live.json',t)
    def test_hover_and_scroll_fixes_preserved(self):
        self.assertIn('id="tracePortal"',INDEX);self.assertIn('id="helpPortal"',INDEX);self.assertIn('z-index:2147483000',CSS);self.assertIn('repositionTracePortal(); repositionHelpPortal();',JS);self.assertIn("$('#tracePortal')?.addEventListener('wheel'",JS)
    def test_pdf_ppt_preserved(self):
        self.assertIn('window.jspdf?.jsPDF',JS);self.assertIn('pdfAddExecutive',JS);self.assertIn('Westcon_Iberia_Business_Intelligence_v3.12.0.pdf',JS);self.assertIn('pptAddExecutiveSummary',JS);self.assertIn('Westcon_Iberia_Business_Intelligence_v3.12.0.pptx',JS)
    def test_manual_ingestion_stays_out(self):
        active=INDEX+JS
        for token in ('btnContributions','btnIngest','contributionModal','ingestModal','westcon-manual-contributions-v1','extractDocumentText'):
            self.assertNotIn(token,active,token)
    def test_frontend_v312(self):
        self.assertIn("fetch('data/v312/intelligence.json'",JS);self.assertIn("fetch('data/v312/last_run.json'",JS);self.assertIn('assets/v312/intelligence.js?v=3.12.0',INDEX)
    def test_workflows_use_v312(self):
        for n in ('research-daily.yml','research-weekly.yml','research-monthly.yml'):
            t=(ROOT/'.github/workflows'/n).read_text(encoding='utf-8');self.assertIn('research_supervisor_v312.py',t);self.assertIn('tests/test_v312.py',t);self.assertIn('data/v312/',t)
        pages=(ROOT/'.github/workflows/pages-deploy.yml').read_text(encoding='utf-8');self.assertIn('cp -R data/v312 _site/data/v312',pages)
    def test_responsive_preserved(self):self.assertIn('@media(max-width:900px)',CSS);self.assertIn('@media(max-width:620px)',CSS)
if __name__=='__main__':unittest.main()
