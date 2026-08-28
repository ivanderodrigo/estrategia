#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def validate(root:Path|None=None)->list[str]:
    base=root or ROOT;errors=[]
    def check(cond,msg):
        if not cond:errors.append(msg)
    check((base/'VERSION').read_text(encoding='utf-8').strip()=='3.10.0','VERSION no es 3.10.0')
    data=json.loads((base/'data/v310/intelligence.json').read_text(encoding='utf-8'))
    check(data.get('meta',{}).get('version')=='3.10.0','meta.version no es 3.10.0')
    for key in ('manufacturers','distributors','integrators','clients_public','clients_private','trends','architectures','source_catalog'):
        check(key in data,f'falta {key}')
    check(len(data.get('clients_public',[]))>=8,'pocos clientes públicos')
    check(len(data.get('clients_private',[]))>=8,'pocos clientes privados')
    ids={x.get('id') for x in data.get('source_catalog',[])}
    check('manual_intelligence_contributions' in ids,'falta fuente manual')
    check('repository_document_intelligence' in ids,'falta fuente documental')
    index=(base/'index.html').read_text(encoding='utf-8')
    for token in ('assets/v310/intelligence.css?v=3.10.0','assets/v310/intelligence.js?v=3.10.0','utilityMenuToggle','btnContributions','btnIngest','tracePortal','exportDetailedAppendix'):
        check(token in index,f'index falta {token}')
    js=(base/'assets/v310/intelligence.js').read_text(encoding='utf-8')
    for token in ('data/v310/intelligence.json','showTracePortal','tracePortal','openContributionEditor','extractDocumentText','reportExecutivePage','pptAddExecutiveSummary','pptAddDomainExecutive','Westcon_Iberia_Business_Intelligence_v3.10.0.pdf','Westcon_Iberia_Business_Intelligence_v3.10.0.pptx','report-export-active'):
        check(token in js,f'JS falta {token}')
    css=(base/'assets/v310/intelligence.css').read_text(encoding='utf-8')
    for token in ('.utility-menu','.trace-portal','.contribution-form','.ingest-form','body.report-export-active','.r-executive-grid','@media(max-width:620px)'):
        check(token in css,f'CSS falta {token}')
    scanner=(base/'scripts/v310/ingest_repo_inputs.py').read_text(encoding='utf-8')
    for token in ('extract_pptx','extract_docx','extract_pdf','inputs','documents','manual'):
        check(token in scanner,f'scanner falta {token}')
    run=json.loads((base/'data/v310/last_run.json').read_text(encoding='utf-8'))
    check(run.get('version')=='3.10.0','last_run no es 3.10.0')
    check('repo_inputs' in run,'last_run no incluye ingesta')
    return errors

def main():
    errors=validate(ROOT)
    if errors:raise SystemExit('VALIDACIÓN v3.10.0 · FAIL · '+'; '.join(errors[:16]))
    print('VALIDACIÓN v3.10.0 · PASS')

if __name__=='__main__':main()
