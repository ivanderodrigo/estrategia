from __future__ import annotations
import json,re,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DATA=json.loads((ROOT/'data/v311/intelligence.json').read_text(encoding='utf-8'))
RUN=json.loads((ROOT/'data/v311/last_run.json').read_text(encoding='utf-8'))
INDEX=(ROOT/'index.html').read_text(encoding='utf-8')
JS=(ROOT/'assets/v311/intelligence.js').read_text(encoding='utf-8')
CSS=(ROOT/'assets/v311/intelligence.css').read_text(encoding='utf-8')
def canon(v):return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9áéíóúüñçãõâêôàèìòùäëïöü]+',' ',str(v or '').casefold())).strip()
class TestV311(unittest.TestCase):
    def test_version(self):self.assertEqual((ROOT/'VERSION').read_text().strip(),'3.11.0');self.assertEqual(DATA['meta']['version'],'3.11.0');self.assertEqual(RUN['version'],'3.11.0')
    def test_domains(self):
        for k,m in {'manufacturers':36,'distributors':8,'integrators':60,'clients_public':8,'clients_private':8,'trends':15,'architectures':10}.items():self.assertGreaterEqual(len(DATA[k]),m,k)
    def test_manufacturers_never_in_distributor_table(self):
        vendors={canon(x['name']) for x in DATA['manufacturers']};dists={canon(x['name']) for x in DATA['distributors']};self.assertFalse(vendors&dists,vendors&dists)
    def test_comstor_never_competitor(self):self.assertFalse(any(x in {'westcon','comstor','westcon comstor'} for x in {canon(r['name']) for r in DATA['distributors']}))
    def test_direct_sales_indicator_supported(self):self.assertIn('direct_sales',DATA['manufacturers'][0]);self.assertIn('direct-sales-badge',JS);self.assertIn('Venta directa',JS)
    def test_builder_filters_before_marking(self):
        b=(ROOT/'scripts/v311/build_intelligence.py').read_text(encoding='utf-8');self.assertIn('clean_distributors_and_mark_direct_sales',b);self.assertIn('has_direct_sales_signal',b);self.assertIn("data['distributors'] = kept",b)
    def test_trace_and_help_escape_stacking(self):
        self.assertIn('id="tracePortal"',INDEX);self.assertIn('id="helpPortal"',INDEX);self.assertIn('z-index:2147483000',CSS);self.assertIn('.help-wrap>.help-tip,.traceable>.trace-popover{display:none!important}',CSS)
    def test_large_trace_card_survives_scroll(self):self.assertNotIn("window.addEventListener('scroll', hideTracePortal",JS);self.assertIn('repositionTracePortal(); repositionHelpPortal();',JS);self.assertIn("$('#tracePortal')?.addEventListener('wheel'",JS);self.assertIn('max-height:min(560px,76vh)',CSS)
    def test_manual_and_ingestion_removed_from_active_release(self):
        active=INDEX+JS
        for token in ('btnContributions','btnIngest','contributionModal','ingestModal','westcon-manual-contributions-v1','extractDocumentText','inputs/manual/','inputs/documents/'):
            self.assertNotIn(token,active,token)
        ids={x['id'] for x in DATA['source_catalog']};self.assertNotIn('manual_intelligence_contributions',ids);self.assertNotIn('repository_document_intelligence',ids)
    def test_pdf_is_native_and_executive(self):
        self.assertIn('jspdf.umd.min.js',INDEX);self.assertNotIn('html2pdf',INDEX+JS)
        for token in ('pdfAddCover','pdfAddExecutive','pdfAddDomain','pdfAddMethodology','window.jspdf?.jsPDF','Westcon_Iberia_Business_Intelligence_v3.11.0.pdf'):self.assertIn(token,JS)
    def test_ppt_preserved(self):
        for token in ('pptAddExecutiveSummary','pptAddDomainExecutive','pptAddMethodology','Westcon_Iberia_Business_Intelligence_v3.11.0.pptx'):self.assertIn(token,JS)
    def test_workflows_use_v311_without_ingestion(self):
        for n in ('research-daily.yml','research-weekly.yml','research-monthly.yml'):
            t=(ROOT/'.github/workflows'/n).read_text(encoding='utf-8');self.assertIn('research_supervisor_v311.py',t);self.assertIn('tests/test_v311.py',t);self.assertIn('data/v311/',t);self.assertNotIn('PRIVATE_INPUT_REPO',t);self.assertNotIn('inputs/manual',t)
    def test_pages_uses_v311(self):
        t=(ROOT/'.github/workflows/pages-deploy.yml').read_text(encoding='utf-8');self.assertIn('cp -R data/v311 _site/data/v311',t);self.assertNotIn('config/v310/runtime.json',t)
    def test_frontend_v311(self):self.assertIn("fetch('data/v311/intelligence.json'",JS);self.assertIn("fetch('data/v311/last_run.json'",JS);self.assertIn('assets/v311/intelligence.js?v=3.11.0',INDEX)
    def test_source_count(self):self.assertGreaterEqual(DATA['meta']['source_count'],235)
    def test_responsive_preserved(self):self.assertIn('@media(max-width:900px)',CSS);self.assertIn('@media(max-width:620px)',CSS)
if __name__=='__main__':unittest.main()
