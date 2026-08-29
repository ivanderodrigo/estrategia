#!/usr/bin/env python3
from __future__ import annotations
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def canon(v):return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9áéíóúüñçãõâêôàèìòùäëïöü]+',' ',str(v or '').casefold())).strip()
def validate(root:Path|None=None)->list[str]:
    base=root or ROOT;errors=[]
    def check(ok,msg):
        if not ok:errors.append(msg)
    check((base/'VERSION').read_text(encoding='utf-8').strip()=='3.11.0','VERSION no es 3.11.0')
    data=json.loads((base/'data/v311/intelligence.json').read_text(encoding='utf-8'));run=json.loads((base/'data/v311/last_run.json').read_text(encoding='utf-8'))
    check(data.get('meta',{}).get('version')=='3.11.0','dataset no es 3.11.0');check(run.get('version')=='3.11.0','last_run no es 3.11.0')
    for k,m in {'manufacturers':36,'distributors':8,'integrators':60,'clients_public':8,'clients_private':8,'trends':15,'architectures':10}.items():check(len(data.get(k,[]))>=m,f'{k} por debajo de mínimo')
    vendors={canon(r.get('name')) for r in data.get('manufacturers',[])};dists={canon(r.get('name')) for r in data.get('distributors',[])}
    overlap=sorted(x for x in vendors & dists if x);check(not overlap,f'Fabricantes presentes como mayoristas: {overlap[:12]}')
    check(not ({'westcon','comstor','westcon comstor'} & dists),'Westcon/Comstor aparecen como mayoristas competidores')
    check(all(isinstance(r.get('direct_sales',False),bool) for r in data.get('manufacturers',[])),'direct_sales no es booleano')
    ids={x.get('id') for x in data.get('source_catalog',[])};check('manual_intelligence_contributions' not in ids,'Fuente manual sigue activa');check('repository_document_intelligence' not in ids,'Fuente documental sigue activa')
    index=(base/'index.html').read_text(encoding='utf-8');js=(base/'assets/v311/intelligence.js').read_text(encoding='utf-8');css=(base/'assets/v311/intelligence.css').read_text(encoding='utf-8')
    check('assets/v311/intelligence.js?v=3.11.0' in index and 'assets/v311/intelligence.css?v=3.11.0' in index,'index no usa assets v311')
    for forbidden in ('btnContributions','btnIngest','contributionModal','ingestModal','Aportaciones manuales','Ingerir documento'):
        check(forbidden not in index+js,f'Función retirada sigue activa: {forbidden}')
    check('window.jspdf?.jsPDF' in js and 'pdfAddExecutive' in js and 'pdfAddDomain' in js,'PDF nativo ejecutivo no activo')
    check('html2pdf' not in index+js,'html2pdf sigue activo')
    check('id="tracePortal"' in index and 'id="helpPortal"' in index,'Faltan portales flotantes')
    check('z-index:2147483000' in css,'Portales no usan capa superior')
    check("window.addEventListener('scroll', ()=>{ repositionTracePortal(); repositionHelpPortal(); }, true)" in js,'El scroll sigue cerrando tarjetas')
    check('direct-sales-badge' in js+css,'Falta indicador de venta directa')
    for name in ('research-daily.yml','research-weekly.yml','research-monthly.yml'):
        wf=(base/'.github/workflows'/name).read_text(encoding='utf-8');check('research_supervisor_v311.py' in wf and 'tests/test_v311.py' in wf and 'data/v311/' in wf,f'{name} no usa v311');check('PRIVATE_INPUT_REPO' not in wf and 'inputs/manual' not in wf and 'inputs/documents' not in wf,f'{name} mantiene ingesta activa')
    pages=(base/'.github/workflows/pages-deploy.yml').read_text(encoding='utf-8');check('cp -R data/v311 _site/data/v311' in pages,'Pages no publica v311');check('config/v310/runtime.json' not in pages,'Pages aún publica runtime de ingesta')
    return errors

def main():
    e=validate(ROOT)
    if e:raise SystemExit('VALIDACIÓN v3.11.0 · FAIL · '+'; '.join(e[:16]))
    print('VALIDACIÓN v3.11.0 · PASS')
if __name__=='__main__':main()
