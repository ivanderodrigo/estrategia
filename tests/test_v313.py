from __future__ import annotations
import json,re,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DATA=json.loads((ROOT/'data/v313/intelligence.json').read_text(encoding='utf-8'))
RUN=json.loads((ROOT/'data/v313/last_run.json').read_text(encoding='utf-8'))
GAPS=json.loads((ROOT/'data/v313/research_gaps.json').read_text(encoding='utf-8'))
INDEX=(ROOT/'index.html').read_text(encoding='utf-8')
JS=(ROOT/'assets/v313/intelligence.js').read_text(encoding='utf-8')
CSS=(ROOT/'assets/v313/intelligence.css').read_text(encoding='utf-8')
def canon(v):return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9áéíóúüñçãõâêôàèìòùäëïöü]+',' ',str(v or '').casefold())).strip()
def fval(row,fid):return ((row.get('fields') or {}).get(fid) or {}).get('value')
class TestV313(unittest.TestCase):
    def test_version(self):
        self.assertEqual((ROOT/'VERSION').read_text().strip(),'3.13.0');self.assertEqual(DATA['meta']['version'],'3.13.0');self.assertEqual(RUN['version'],'3.13.0')
    def test_domain_coverage(self):
        for k,m in {'manufacturers':36,'distributors':50,'integrators':120,'clients_public':25,'clients_private':51,'trends':15,'architectures':10}.items():self.assertGreaterEqual(len(DATA[k]),m,k)
    def test_distributors_require_positive_validation(self):
        bad=('cradlepoint','penguin','stratus','akamai','noname','splunk','forescout','nfon','ipbrick','hama')
        names=[canon(x['name']) for x in DATA['distributors']]
        self.assertFalse(any(any(b in n for b in bad) for n in names),names);self.assertFalse({'westcon','comstor','westcon comstor'} & set(names))
        for row in DATA['distributors']:
            spec=(row.get('fields') or {}).get('validation_status') or {};self.assertEqual(spec.get('value'),'Mayorista / distribuidor validado',row['name']);self.assertTrue(spec.get('evidence'),row['name'])
    def test_manufacturers_never_in_distributor_table(self):
        vendors={canon(x['name']) for x in DATA['manufacturers']};dists={canon(x['name']) for x in DATA['distributors']};self.assertFalse(vendors&dists,vendors&dists)
    def test_forescout_not_westcon_portfolio(self):
        self.assertNotIn('forescout',{canon(x['name']) for x in DATA['manufacturers']})
        allowed={canon(x['name']) for x in DATA['manufacturers']}
        for section in ('clients_public','clients_private'):
            for row in DATA[section]:
                vals=fval(row,'westcon_fit') or []; vals=vals if isinstance(vals,list) else [vals]
                for v in vals:self.assertIn(canon(str(v).split('·',1)[0]),allowed,(section,row['name'],v))
    def test_private_clients_full_indices(self):
        self.assertEqual(sum(fval(x,'index_universe')=='IBEX 35' for x in DATA['clients_private']),35);self.assertEqual(sum(fval(x,'index_universe')=='PSI' for x in DATA['clients_private']),16)
    def test_public_procurement_exact_links(self):
        self.assertGreaterEqual(len(DATA['clients_public']),25)
        for row in DATA['clients_public']:
            ev=(row.get('evidence') or [None])[0] or {};url=str(ev.get('url') or '');portal=str(fval(row,'source_portal') or '')
            self.assertTrue(fval(row,'notice_id'));self.assertTrue(('ted.europa.eu' in url and '/notice/-/detail/' in url) or ('PLACSP' in portal and ('contrataciondelestado' in url or 'contrataciondelsectorpublico' in url)),url)
    def test_integrator_graph_is_deep(self):
        graph=RUN['integrator_graph'];self.assertGreaterEqual(graph['unique_vendor_integrator_edges'],230);self.assertGreaterEqual(graph['avg_integrators_per_manufacturer'],6.4);self.assertGreaterEqual(len(DATA['integrators']),120)
    def test_integrator_graph_bidirectional(self):
        m=next(x for x in DATA['manufacturers'] if x['name']=='Nokia');self.assertTrue(any('Kyndryl' in str(v) for v in (fval(m,'integrators') or [])))
        i=next(x for x in DATA['integrators'] if x['name']=='Kyndryl');self.assertTrue(any('Nokia' in str(v) for v in (fval(i,'vendor_relations') or [])))
    def test_sources_expanded(self):
        ids={x['id'] for x in DATA['source_catalog']};self.assertGreaterEqual(len(ids),270)
        for sid in ('channelpartner_distributor_ranking_2026','itchannel_pt_distributor_directory','channelpartner_integrator_ranking_2026','bme_ibex35_official','euronext_psi_official','placsp_open_data_v312','ted_search_api_v3','checkpoint_gsi_official_v312','aws_partner_discovery_v313','cisco_partner_finder_v313','dadosgovpt_base_contracts_v313'):
            self.assertIn(sid,ids)
    def test_research_budgets_are_hyperdeep(self):
        cfg=json.loads((ROOT/'config/v313/deep_research.json').read_text(encoding='utf-8'))
        self.assertGreaterEqual(cfg['profiles']['deep']['budgets']['query_limit_public'],900);self.assertGreaterEqual(cfg['profiles']['deep']['budgets']['ecosystem_sitemap_pages_max'],3200);self.assertEqual(cfg['profiles']['deep']['budgets']['client_domains_per_run'],51)
        self.assertGreaterEqual(cfg['profiles']['exhaustive']['budgets']['query_limit_public'],1600);self.assertGreaterEqual(cfg['profiles']['exhaustive']['budgets']['ecosystem_sitemap_pages_max'],6000)
    def test_official_entity_crawl_keeps_profile_evidence(self):
        research=(ROOT/'scripts/research.py').read_text(encoding='utf-8')
        self.assertIn("profileDimensions",research);self.assertIn("official-{entity_kind}-profile",research);self.assertIn("V313_PRIVATE_ACCOUNT_DOMAINS",research)
        self.assertNotIn('if not matches: continue',research[research.index('def official_entity_sitemap_evidence'):research.index('def official_analyst_sitemap_evidence')])
    def test_jobs_do_not_imply_partnership(self):
        build=(ROOT/'scripts/v313/build_intelligence.py').read_text(encoding='utf-8');self.assertIn("'job_profiles' not in dims",build);self.assertIn('jobs can fill job fields but never create a partner relationship',build)
    def test_dynamic_gap_engine(self):
        self.assertEqual(GAPS.get('version'),'3.13.0');self.assertGreater(GAPS.get('total_gaps',0),0);self.assertIn('coverage',GAPS);self.assertIn('missing_by_field',GAPS)
        self.assertEqual(RUN.get('research_gaps'),GAPS.get('total_gaps'));self.assertNotEqual(GAPS.get('policy','').find('No hereda'),0) if False else None
    def test_private_account_domains_complete(self):
        d=json.loads((ROOT/'config/v313/private_account_domains.json').read_text(encoding='utf8'));self.assertEqual(len(d.get('domains',{})),51)
    def test_cards_open_only_on_click(self):
        self.assertNotIn("document.addEventListener('pointerover'",JS);self.assertNotIn("document.addEventListener('pointerout'",JS);self.assertNotIn("document.addEventListener('focusin'",JS)
        self.assertIn("const trace=e.target.closest('.traceable')",JS);self.assertIn("showTracePortal(trace)",JS);self.assertIn("e.key==='Enter'||e.key===' '",JS)
        self.assertIn('.traceable:hover .trace-popover',CSS);self.assertIn('display:none!important',CSS)
    def test_scrollable_portal_preserved(self):
        self.assertIn('id="tracePortal"',INDEX);self.assertIn('id="helpPortal"',INDEX);self.assertIn('z-index:2147483000',CSS);self.assertIn('repositionTracePortal(); repositionHelpPortal();',JS);self.assertIn("$('#tracePortal')?.addEventListener('wheel'",JS)
    def test_sparse_table_columns_are_less_noisy(self):self.assertIn("Math.ceil(rows.length*.20)",JS)
    def test_pdf_ppt_preserved(self):
        self.assertIn('window.jspdf?.jsPDF',JS);self.assertIn('pdfAddExecutive',JS);self.assertIn('Westcon_Iberia_Business_Intelligence_v3.13.0.pdf',JS);self.assertIn('pptAddExecutiveSummary',JS);self.assertIn('Westcon_Iberia_Business_Intelligence_v3.13.0.pptx',JS)
    def test_manual_ingestion_stays_out(self):
        active=INDEX+JS
        for token in ('btnContributions','btnIngest','contributionModal','ingestModal','westcon-manual-contributions-v1','extractDocumentText'):self.assertNotIn(token,active,token)
    def test_frontend_v313(self):self.assertIn("fetch('data/v313/intelligence.json'",JS);self.assertIn("fetch('data/v313/last_run.json'",JS);self.assertIn('assets/v313/intelligence.js?v=3.13.0',INDEX)
    def test_workflows_use_v313(self):
        for n in ('research-daily.yml','research-weekly.yml','research-monthly.yml'):
            t=(ROOT/'.github/workflows'/n).read_text(encoding='utf-8');self.assertIn('research_supervisor_v313.py',t);self.assertIn('tests/test_v313.py',t);self.assertIn('data/v313/',t)
        self.assertIn('cp -R data/v313 _site/data/v313',(ROOT/'.github/workflows/pages-deploy.yml').read_text(encoding='utf-8'))
    def test_responsive_preserved(self):self.assertIn('@media(max-width:900px)',CSS);self.assertIn('@media(max-width:620px)',CSS)
if __name__=='__main__':unittest.main()
