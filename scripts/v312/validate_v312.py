#!/usr/bin/env python3
from __future__ import annotations
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def canon(v):return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9áéíóúüñçãõâêôàèìòùäëïöü]+',' ',str(v or '').casefold())).strip()
def fval(row,fid):return ((row.get('fields') or {}).get(fid) or {}).get('value')
def validate(root:Path|None=None)->list[str]:
    base=root or ROOT;errors=[]
    def check(ok,msg):
        if not ok:errors.append(msg)
    check((base/'VERSION').read_text(encoding='utf-8').strip()=='3.12.0','VERSION no es 3.12.0')
    data=json.loads((base/'data/v312/intelligence.json').read_text(encoding='utf-8'));run=json.loads((base/'data/v312/last_run.json').read_text(encoding='utf-8'))
    check(data.get('meta',{}).get('version')=='3.12.0','dataset no es 3.12.0');check(run.get('version')=='3.12.0','last_run no es 3.12.0')
    for k,m in {'manufacturers':36,'distributors':50,'integrators':120,'clients_public':25,'clients_private':51,'trends':15,'architectures':10}.items():check(len(data.get(k,[]))>=m,f'{k} por debajo de mínimo')
    vendors={canon(r.get('name')) for r in data.get('manufacturers',[])};dists={canon(r.get('name')) for r in data.get('distributors',[])}
    check(not (vendors&dists),f'Fabricantes presentes como mayoristas: {sorted(vendors&dists)[:12]}');check(not ({'westcon','comstor','westcon comstor'}&dists),'Westcon/Comstor aparecen como mayoristas')
    bad=('cradlepoint','penguin','stratus','akamai','noname','splunk','forescout','nfon','ipbrick','hama');check(not any(any(b in n for b in bad) for n in dists),'Mayoristas contiene marcas/fabricantes excluidos')
    check(all(((r.get('fields') or {}).get('validation_status') or {}).get('evidence') for r in data.get('distributors',[])),'Hay mayoristas sin evidencia positiva')
    allowed=vendors
    check('forescout' not in allowed,'Forescout aparece en fabricantes activos')
    for section in ('clients_public','clients_private'):
        for row in data.get(section,[]):
            vals=fval(row,'westcon_fit') or []
            if not isinstance(vals,list):vals=[vals]
            check(all(canon(str(v).split('·',1)[0]) in allowed for v in vals),f'{section}/{row.get("name")}: westcon_fit contiene fabricante fuera de portfolio')
    ibex=sum(1 for r in data.get('clients_private',[]) if fval(r,'index_universe')=='IBEX 35');psi=sum(1 for r in data.get('clients_private',[]) if fval(r,'index_universe')=='PSI')
    check(ibex==35 and psi==16,f'Universo privado incompleto: IBEX {ibex}, PSI {psi}')
    for row in data.get('clients_public',[]):
        ev=(row.get('evidence') or [{}])[0];url=str(ev.get('url') or '');portal=str(fval(row,'source_portal') or '')
        check(bool(fval(row,'notice_id')),f'Pliego sin identificador: {row.get("name")}')
        check(('ted.europa.eu' in url and '/notice/-/detail/' in url) or ('PLACSP' in portal and ('contrataciondelestado' in url or 'contrataciondelsectorpublico' in url)),f'Pliego sin enlace exacto: {url}')
    graph=run.get('integrator_graph') or {};check(graph.get('unique_vendor_integrator_edges',0)>=230,'Grafo fabricante↔integrador demasiado pequeño');check(graph.get('avg_integrators_per_manufacturer',0)>=6.4,'Media de integradores/fabricante demasiado baja')
    check(data.get('meta',{}).get('source_count',0)>=265,'Catálogo de fuentes v3.12 insuficiente')
    index=(base/'index.html').read_text(encoding='utf-8');js=(base/'assets/v312/intelligence.js').read_text(encoding='utf-8');css=(base/'assets/v312/intelligence.css').read_text(encoding='utf-8')
    check('assets/v312/intelligence.js?v=3.12.0' in index and 'assets/v312/intelligence.css?v=3.12.0' in index,'index no usa assets v312')
    check('window.jspdf?.jsPDF' in js and 'pdfAddExecutive' in js,'PDF ejecutivo no activo');check('id="tracePortal"' in index and 'id="helpPortal"' in index and 'z-index:2147483000' in css,'Portales hover no protegidos')
    for forbidden in ('btnContributions','btnIngest','contributionModal','ingestModal'):
        check(forbidden not in index+js,f'Función retirada sigue activa: {forbidden}')
    for name in ('research-daily.yml','research-weekly.yml','research-monthly.yml'):
        wf=(base/'.github/workflows'/name).read_text(encoding='utf-8');check('research_supervisor_v312.py' in wf and 'tests/test_v312.py' in wf and 'data/v312/' in wf,f'{name} no usa v312')
    pages=(base/'.github/workflows/pages-deploy.yml').read_text(encoding='utf-8');check('cp -R data/v312 _site/data/v312' in pages,'Pages no publica v312')
    return errors
def main():
    e=validate(ROOT)
    if e:raise SystemExit('VALIDACIÓN v3.12.0 · FAIL · '+'; '.join(e[:20]))
    print('VALIDACIÓN v3.12.0 · PASS')
if __name__=='__main__':main()
