#!/usr/bin/env python3
from __future__ import annotations
import json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from v317.gap_engine import SECTIONS,evidence_rows,evidence_sufficient,has_value
def canonical(v):return re.sub(r'[^a-z0-9]+',' ',str(v or '').casefold()).strip()
def validate(root:Path|None=None):
 base=root or ROOT;errors=[]
 def check(ok,msg):
  if not ok:errors.append(msg)
 try:
  data=json.loads((base/'data/v317/intelligence.json').read_text(encoding='utf-8'));run=json.loads((base/'data/v317/last_run.json').read_text(encoding='utf-8'));gaps=json.loads((base/'data/v317/research_gaps.json').read_text(encoding='utf-8'));metrics=json.loads((base/'data/v317/metrics_before_after.json').read_text(encoding='utf-8'))
 except Exception as exc:return [f'No se pueden cargar los artefactos v317: {exc}']
 check((base/'VERSION').read_text(encoding='utf-8').strip()=='3.17.0','VERSION no es 3.17.0');check(data.get('meta',{}).get('version')=='3.17.0','dataset no es 3.17.0');check(run.get('version')=='3.17.0','last_run no es 3.17.0');check(gaps.get('version')=='3.17.0','gaps no es 3.17.0')
 for key,minimum in {'manufacturers':36,'distributors':50,'integrators':120,'clients_public':25,'clients_private':51,'trends':15,'architectures':10}.items():check(len(data.get(key) or [])>=minimum,f'{key} por debajo del mínimo')
 vendors={canonical(r.get('name')) for r in data['manufacturers']};distributors={canonical(r.get('name')) for r in data['distributors']};check(not vendors&distributors,f'Fabricantes clasificados como mayoristas: {vendors&distributors}');check(not {'westcon','comstor','westcon comstor'}&distributors,'Westcon/Comstor clasificado como competidor')
 for section in SECTIONS:
  schema=[c for c in data.get('schemas',{}).get(section,[]) if c.get('id')];check(all(c.get('expected') is True for c in schema),f'{section}: campo declarado no marcado expected')
  for row in data.get(section) or []:
   for field_id,spec in (row.get('fields') or {}).items():
    if not isinstance(spec,dict) or not has_value(spec.get('value')):continue
    values=spec.get('value') if isinstance(spec.get('value'),list) else [spec.get('value')]
    if any(str(v).upper().startswith('INTERPRETACIÓN') for v in values):check(spec.get('claim_type')=='interpretation',f'{section}/{row.get("name")}/{field_id}: interpretación presentada como hecho')
    if any(str(v).upper().startswith('SEÑAL') for v in values):check(spec.get('claim_type')=='signal',f'{section}/{row.get("name")}/{field_id}: señal presentada como hecho')
    if spec.get('claim_type')=='signal':check(spec.get('confidence_band')=='low' and spec.get('evidence_color')=='red',f'{section}/{row.get("name")}/{field_id}: señal no roja')
    if spec.get('claim_type')=='interpretation':check(spec.get('confidence_band')=='medium' and spec.get('evidence_color')=='yellow',f'{section}/{row.get("name")}/{field_id}: interpretación no amarilla')
    if float(spec.get('confidence') or 0)>=.8:check(any(all(str(ev.get(k) or '').strip() for k in ('source','title','url','date','description')) for ev in evidence_rows(spec)),f'{section}/{row.get("name")}/{field_id}: evidencia fuerte sin fuente completa')
 check(all(len(g.get('passes') or [])==48 for g in gaps.get('gaps') or []),'Algún gap no tiene 48 pases');check(gaps.get('engine',{}).get('contradiction_pass') is True,'Falta pase de contradicciones');check(all(g.get('research_state')=='Por investigar' for g in gaps.get('gaps') or []),'Estado de gap ambiguo');check(all(not evidence_sufficient(((next((r for r in data[g['section']] if r.get('id')==g.get('entity_id')),{}) or {}).get('fields') or {}).get(g['field']) or {}) for g in gaps.get('gaps') or []),'Gap activo con evidencia suficiente')
 check(metrics.get('before',{}).get('research_gaps',0)>metrics.get('after',{}).get('research_gaps',0),'No se reducen gaps con definición fija');check(metrics.get('new_information',{}).get('newly_populated_fields',0)>=350,'Menos de 350 campos nuevos');check(metrics.get('new_information',{}).get('new_values_added',0)>=500,'Menos de 500 valores nuevos');check(metrics.get('after',{}).get('sources',0)>metrics.get('before',{}).get('sources',0),'No aumenta el catálogo de fuentes')
 for name in ('metrics_before_after.json','source_report.json','coverage_report.json','research_gaps.json'):check((base/'data/v317'/name).exists(),f'Falta {name}')
 index=(base/'index.html').read_text(encoding='utf-8');js=(base/'assets/v317/intelligence.js').read_text(encoding='utf-8')
 check('assets/v317/intelligence.js?v=3.17.0' in index and 'assets/v317/intelligence.css?v=3.17.0' in index,'index no usa v3.17.0');check("fetch('data/v317/intelligence.json'" in js,'frontend no carga v317');check('Por investigar</span>' in js,'vacíos no muestran Por investigar');check('>—<' not in js,'guion usado como dato pendiente');check("let cols=schema.filter(col=>col.hidden!==true)" in js,'columnas esperadas pueden ocultarse por dispersión');check('fact_confidence' in js and 'interpretation_confidence' in js and 'action_risk' in js,'confianzas no separadas')
 forbidden=('solo se incluyen','se excluyen','hemos decidido','esta tabla no contiene');check(not any(x in index.casefold() for x in forbidden),'encabezado autojustificativo')
 for name in ('research-daily.yml','research-weekly.yml','research-monthly.yml'):
  text=(base/'.github/workflows'/name).read_text(encoding='utf-8');check('research_supervisor_v317.py' in text and 'tests/test_v317.py' in text and 'data/v317/' in text,f'{name} no usa v317')
 check('cp -R data/v317 _site/data/v317' in (base/'.github/workflows/pages-deploy.yml').read_text(encoding='utf-8'),'Pages no publica v317')
 for name in ('README_V317.md','CHANGELOG_V317.md'):check((base/name).exists(),f'Falta {name}')
 return errors
def main():
 errors=validate(ROOT)
 if errors:raise SystemExit('VALIDACIÓN v3.17.0 · FAIL · '+'; '.join(errors[:40]))
 print('VALIDACIÓN v3.17.0 · PASS')
if __name__=='__main__':main()
