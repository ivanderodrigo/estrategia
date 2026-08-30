#!/usr/bin/env python3
from __future__ import annotations
import json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def canon(v):return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9áéíóúüñçãõâêôàèìòùäëïöü]+',' ',str(v or '').casefold())).strip()
def fval(row,fid):return ((row.get('fields') or {}).get(fid) or {}).get('value')
def validate(root:Path|None=None):
 base=root or ROOT;errors=[]
 def check(ok,msg):
  if not ok:errors.append(msg)
 check((base/'VERSION').read_text(encoding='utf8').strip()=='3.14.0','VERSION no es 3.14.0')
 data=json.loads((base/'data/v314/intelligence.json').read_text(encoding='utf8'));run=json.loads((base/'data/v314/last_run.json').read_text(encoding='utf8'));gaps=json.loads((base/'data/v314/research_gaps.json').read_text(encoding='utf8'))
 check(data.get('meta',{}).get('version')=='3.14.0','dataset no es 3.14.0');check(run.get('version')=='3.14.0','last_run no es 3.14.0');check(gaps.get('version')=='3.14.0','gaps no es 3.14.0')
 for k,m in {'manufacturers':36,'distributors':50,'integrators':120,'clients_public':25,'clients_private':51,'trends':15,'architectures':10}.items():check(len(data.get(k,[]))>=m,f'{k} por debajo de mínimo')
 vendors={canon(r.get('name')) for r in data['manufacturers']};dists={canon(r.get('name')) for r in data['distributors']};check(not vendors&dists,f'Fabricantes en mayoristas: {vendors&dists}');check(not {'westcon','comstor','westcon comstor'}&dists,'Westcon/Comstor en mayoristas');check('forescout' not in vendors,'Forescout en portfolio')
 for row in data['distributors']:
  check(bool(((row.get('fields') or {}).get('validation_status') or {}).get('evidence')),f'{row["name"]}: sin validación positiva')
 sch={x['id']:x for x in data['schemas']['distributors']}
 for fid in ('revenue','vendor_relations','westcon_overlap','competitor_vendor_overlap','differential_capabilities'):check(fid in sch,f'Falta columna mayoristas {fid}')
 for fid in ('vendor_relations','westcon_overlap','competitor_vendor_overlap','differential_capabilities'):check(sch[fid].get('decision_required') is True,f'{fid} debe ser decisional')
 check(sum(bool(fval(r,'revenue')) for r in data['distributors'])>=14,'Facturación mayoristas insuficiente');check(sum(bool(fval(r,'differential_capabilities')) for r in data['distributors'])>=12,'Capacidades diferenciales insuficientes')
 check(sum(bool(fval(r,'competitors')) for r in data['manufacturers'])>=30,'Competidores fabricantes insuficientes')
 check(sum(fval(r,'index_universe')=='IBEX 35' for r in data['clients_private'])==35,'IBEX 35 incompleto');check(sum(fval(r,'index_universe')=='PSI' for r in data['clients_private'])==16,'PSI incompleto')
 check(len(data.get('source_catalog',[]))>=290,'Fuentes <290');check(gaps.get('total_gaps',9999)<800,'Gaps decisionales no reducidos');check('optional_missing_by_field' in gaps,'No se separa enriquecimiento opcional')
 check(run.get('integrator_graph',{}).get('unique_vendor_integrator_edges',0)>=230,'Grafo integradores insuficiente')
 index=(base/'index.html').read_text(encoding='utf8');js=(base/'assets/v314/intelligence.js').read_text(encoding='utf8');css=(base/'assets/v314/intelligence.css').read_text(encoding='utf8')
 check('assets/v314/intelligence.js?v=3.14.0' in index and 'assets/v314/intelligence.css?v=3.14.0' in index,'index no usa v314');check('Comparativa de mayoristas y distribuidores que compiten en España y Portugal.' in index,'Encabezado mayoristas no descriptivo');check('Panorama de clientes y oportunidades en España y Portugal.' in index,'Encabezado clientes no descriptivo');check('Solo mayoristas/distribuidores competidores.' not in index,'Cabecera mayoristas sigue justificando reglas internas')
 check("fetch('data/v314/intelligence.json'" in js,'JS no carga v314');check('missingMarkup' in js and 'Pendiente de evidencia' in js and 'no-public-data' in js,'UI no separa gaps críticos y opcionales');check("document.addEventListener('pointerover'" not in js,'Hover reintroducido');check('window.jspdf?.jsPDF' in js and 'v3.14.0.pdf' in js and 'v3.14.0.pptx' in js,'Export v314 roto')
 for name in ('research-daily.yml','research-weekly.yml','research-monthly.yml'):
  wf=(base/'.github/workflows'/name).read_text(encoding='utf8');check('research_supervisor_v314.py' in wf and 'tests/test_v314.py' in wf and 'data/v314/' in wf,f'{name} no usa v314')
 check('cp -R data/v314 _site/data/v314' in (base/'.github/workflows/pages-deploy.yml').read_text(encoding='utf8'),'Pages no publica v314')
 return errors
def main():
 e=validate(ROOT)
 if e:raise SystemExit('VALIDACIÓN v3.14.0 · FAIL · '+'; '.join(e[:30]))
 print('VALIDACIÓN v3.14.0 · PASS')
if __name__=='__main__':main()
