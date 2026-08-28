from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=json.loads((ROOT/'data/v310/intelligence.json').read_text(encoding='utf-8'))
RUN=json.loads((ROOT/'data/v310/last_run.json').read_text(encoding='utf-8'))
INDEX=(ROOT/'index.html').read_text(encoding='utf-8')
JS=(ROOT/'assets/v310/intelligence.js').read_text(encoding='utf-8')
CSS=(ROOT/'assets/v310/intelligence.css').read_text(encoding='utf-8')

class TestV310(unittest.TestCase):
    def test_version_and_dataset(self):
        self.assertEqual((ROOT/'VERSION').read_text(encoding='utf-8').strip(),'3.10.0')
        self.assertEqual(DATA['meta']['version'],'3.10.0')
        self.assertEqual(RUN['version'],'3.10.0')
        self.assertGreaterEqual(DATA['meta']['source_count'],240)

    def test_all_domains_preserved(self):
        minimums={'manufacturers':36,'distributors':8,'integrators':60,'clients_public':8,'clients_private':8,'trends':15,'architectures':10}
        for key,minimum in minimums.items():self.assertGreaterEqual(len(DATA[key]),minimum,key)

    def test_trace_portal_escapes_table_stacking(self):
        self.assertIn('id="tracePortal"',INDEX)
        self.assertIn('showTracePortal',JS)
        self.assertIn("position:fixed;z-index:5000",CSS)
        self.assertIn('.traceable>.trace-popover{display:none!important}',CSS)

    def test_header_uses_professional_utility_menu(self):
        self.assertIn('id="utilityMenuToggle"',INDEX)
        self.assertIn('id="utilityMenu"',INDEX)
        self.assertNotIn('id="navToggle"',INDEX)
        for token in ('btnSources','btnContributions','btnIngest','btnExport','dataStatusBtn','confidenceHelpBtn'):
            self.assertIn(f'id="{token}"',INDEX)
        self.assertIn('toggleUtilityMenu',JS)

    def test_navigation_order(self):
        tokens=['data-view="fabricantes"','data-view="mayoristas"','data-view="integradores"','data-view="clientes"','data-view="tendencias"','data-view="arquitecturas"']
        pos=[INDEX.index(x) for x in tokens];self.assertEqual(pos,sorted(pos))

    def test_pdf_export_is_not_offscreen(self):
        self.assertIn('body.report-export-active',CSS)
        self.assertIn('left:0!important',CSS)
        self.assertIn('document.body.classList.add(\'report-export-active\')',JS)
        self.assertIn('requestAnimationFrame(()=>requestAnimationFrame(resolve))',JS)
        self.assertIn('Westcon_Iberia_Business_Intelligence_v3.10.0.pdf',JS)

    def test_ppt_is_executive_first(self):
        for token in ('pptAddExecutiveSummary','pptAddDomainExecutive','pptAddMethodology','Lectura ejecutiva','Cuentas y ecosistema'):
            self.assertIn(token,JS)
        self.assertIn('id="exportDetailedAppendix"',INDEX)
        self.assertIn('Westcon_Iberia_Business_Intelligence_v3.10.0.pptx',JS)

    def test_manual_intelligence_layer(self):
        for token in ('openContributionEditor','westcon-manual-contributions-v1','exportContributions','inputs/manual/','Aportaciones manuales'):
            self.assertIn(token,JS+INDEX)
        self.assertIn('manual_intelligence_contributions',{x['id'] for x in DATA['source_catalog']})

    def test_document_ingestion_layer(self):
        for token in ('extractDocumentText','extractZipXmlText','extractPdfText','downloadIngestPackage','inputs/documents/'):
            self.assertIn(token,JS+INDEX)
        scanner=(ROOT/'scripts/v310/ingest_repo_inputs.py').read_text(encoding='utf-8')
        for token in ('extract_pptx','extract_docx','extract_pdf','detect_entities','detect_areas'):
            self.assertIn(token,scanner)
        self.assertIn('repository_document_intelligence',{x['id'] for x in DATA['source_catalog']})

    def test_repo_inputs_status(self):
        self.assertIn('repo_inputs',RUN)
        self.assertIn('repo_inputs',DATA['meta'])
        for token in ('manual_contributions','documents','document_mentions_applied'):
            self.assertIn(token,RUN['repo_inputs'])

    def test_privacy_warning_is_visible(self):
        self.assertIn('si el repositorio que publica GitHub Pages es público, no subas documentos confidenciales',INDEX)
        self.assertIn('PRIVATE_INPUT_REPO', (ROOT/'.github/workflows/research-daily.yml').read_text(encoding='utf-8'))

    def test_workflows_use_v310(self):
        for name in ('research-daily.yml','research-weekly.yml','research-monthly.yml'):
            text=(ROOT/'.github/workflows'/name).read_text(encoding='utf-8')
            for token in ('research_supervisor_v310.py','tests/test_v310.py','v310/validate_v310.py','assets/v310/intelligence.js','data/v310/'):
                self.assertIn(token,text,name)

    def test_publisher_validates_v310(self):
        text=(ROOT/'scripts/publish_research_update.py').read_text(encoding='utf-8')
        self.assertIn('data/v310',text)
        self.assertIn('scripts/v310/validate_v310.py',text)
        self.assertIn('tests/ui_smoke_v310.js',text)

    def test_responsive_mobile_table_and_header(self):
        self.assertIn('@media(max-width:900px)',CSS)
        self.assertIn('@media(max-width:620px)',CSS)
        self.assertIn('grid-template-areas:\'brand utility\' \'nav nav\'',CSS)

    def test_pages_deploy_publishes_minimal_site(self):
        text=(ROOT/'.github/workflows/pages-deploy.yml').read_text(encoding='utf-8')
        for token in ('actions/configure-pages@v5','actions/upload-pages-artifact@v4','actions/deploy-pages@v4','cp -R data/v310','cp config/v310/runtime.json'):
            self.assertIn(token,text)
        self.assertNotIn('cp -R inputs',text)

    def test_active_frontend_loads_v310(self):
        self.assertIn("fetch('data/v310/intelligence.json'",JS)
        self.assertIn("fetch('data/v310/last_run.json'",JS)
        self.assertIn('assets/v310/intelligence.js?v=3.10.0',INDEX)
        self.assertIn('assets/v310/intelligence.css?v=3.10.0',INDEX)

    def test_no_secret_token_in_frontend(self):
        self.assertIsNone(re.search(r'ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}',JS+INDEX))

if __name__=='__main__':unittest.main()
