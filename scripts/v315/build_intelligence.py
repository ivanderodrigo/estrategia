#!/usr/bin/env python3
"""Build v3.15 from the validated v3.14 snapshot plus traced research."""
from __future__ import annotations
import copy,json,re,sys
from datetime import datetime,timezone
from pathlib import Path
from typing import Any,Mapping
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from v314.build_intelligence import build as build_v314
from v315.gap_engine import build_gaps,has_value
from v315.metrics import calculate_metrics,compare_metrics
from v34.common import write_json
VERSION='3.15.0';SECTIONS=('manufacturers','distributors','integrators','clients_public','clients_private','trends','architectures')
def load_json(relative:str,default:Any|None=None)->Any:
 try:return json.loads((ROOT/relative).read_text(encoding='utf-8'))
 except (OSError,json.JSONDecodeError):return {} if default is None else default
def canonical(value:Any)->str:
 text=str(value or '').casefold().translate(str.maketrans('áéíóúüñçãõâêôàèìòùäëïöü','aeiouuncaoaeoaeiouaeiou'));return re.sub(r'[^a-z0-9]+',' ',text).strip()
def evidence(raw:Mapping[str,Any])->dict[str,Any]:
 source_type=str(raw.get('source_type') or raw.get('type') or 'public-web');official=source_type in {'official','annual-report','careers','government','procurement-official','vendor-official','distributor-official'}
 return {'source':str(raw.get('source') or ''),'title':str(raw.get('title') or ''),'url':str(raw.get('url') or ''),'date':str(raw.get('date') or ''),'description':str(raw.get('description') or ''),'scope':str(raw.get('scope') or 'GLOBAL'),'source_grade':str(raw.get('source_grade') or 'B'),'source_type':source_type,'official':official,'classification':'public','retrieved_at':'2026-08-30'}
def claim_type(values:list[Any])->str:
 joined=' '.join(str(v) for v in values).upper()
 if 'INTERPRETACIÓN' in joined:return 'interpretation'
 if 'SEÑAL' in joined:return 'signal'
 return 'fact'
def confidence_profile(kind:str,evs:list[dict[str,Any]])->tuple[float,float,str]:
 official=any(e.get('official') for e in evs)
 if kind=='fact':return ((.93,.70,'bajo') if official else (.82,.65,'medio'))
 if kind=='signal':return (.88,.62,'medio')
 return (.92,.58,'medio-alto')
def merge_field(row:dict[str,Any],field_id:str,values:list[Any],raw_source:Mapping[str,Any],qualifier:str='')->None:
 if not values:return
 fields=row.setdefault('fields',{});old=fields.get(field_id) or {};current=old.get('value') or [];current=current if isinstance(current,list) else [current];merged=list(current)
 for value in values:
  key=canonical(str(value).split('·',1)[0])
  if key and not any(canonical(str(existing).split('·',1)[0])==key for existing in merged):merged.append(value)
 new_ev=evidence(raw_source);evs=[new_ev,*[dict(e) for e in old.get('evidence') or [] if isinstance(e,Mapping)]];deduped=[];seen=set()
 for item in evs:
  key=str(item.get('url') or '')+'|'+str(item.get('title') or '')
  if key not in seen:seen.add(key);deduped.append(item)
 kind=claim_type(values);fact_conf,interpretation_conf,action_risk=confidence_profile(kind,deduped);reason={'fact':'Fuente pública directa o comparación pública con alcance explícito.','signal':'Señal pública trazable; orienta la investigación y no prueba por sí sola un despliegue o relación.','interpretation':'Lectura comercial separada del hecho; requiere validación antes de actuar.'}[kind]
 items=list(old.get('items') or [])
 for value in values:
  key=canonical(str(value))
  if not any(canonical(i.get('value'))==key for i in items if isinstance(i,Mapping)):items.append({'value':value,'evidence':[new_ev],'claim_type':kind,'assertion_status':'CONFIRMADO' if kind=='fact' and new_ev['official'] else ('SEÑAL' if kind=='signal' else 'INTERPRETACIÓN'),'fact_confidence':fact_conf,'interpretation_confidence':interpretation_conf,'action_risk':action_risk,'confidence_reason':reason})
 fields[field_id]={'value':merged,'evidence':deduped,'items':items,'claim_type':kind,'assertion_status':'CONFIRMADO' if kind=='fact' and new_ev['official'] else ('SEÑAL' if kind=='signal' else 'INTERPRETACIÓN'),'confidence':fact_conf if kind!='interpretation' else interpretation_conf,'fact_confidence':fact_conf,'interpretation_confidence':interpretation_conf,'action_risk':action_risk,'confidence_reason':reason,'qualifier':qualifier or reason}
def normalize_existing_claims(data:dict[str,Any])->None:
 for section in SECTIONS:
  for row in data.get(section) or []:
   for spec in (row.get('fields') or {}).values():
    if not isinstance(spec,dict) or not has_value(spec.get('value')):continue
    values=spec.get('value') if isinstance(spec.get('value'),list) else [spec.get('value')];kind=spec.get('claim_type') or claim_type(values);evs=[e for e in spec.get('evidence') or [] if isinstance(e,dict)]
    for item in spec.get('items') or []:
     if isinstance(item,dict):evs.extend(e for e in item.get('evidence') or [] if isinstance(e,dict))
    fact_conf,interpretation_conf,risk=confidence_profile(kind,evs)
    spec.setdefault('claim_type',kind);spec.setdefault('assertion_status','SEÑAL' if kind=='signal' else ('INTERPRETACIÓN' if kind=='interpretation' else 'CONFIRMADO'));spec.setdefault('fact_confidence',round(float(spec.get('confidence') or fact_conf),3));spec.setdefault('interpretation_confidence',interpretation_conf);spec.setdefault('action_risk',risk);spec.setdefault('confidence_reason','Evidencia pública trazable; vigencia y corroboración visibles en el detalle.')
    for ev in evs:
     ev.setdefault('source_type',ev.get('type') or 'public-web');ev.setdefault('official','official' in str(ev.get('type') or '').lower() or str(ev.get('source_grade') or '').startswith('A'));ev.setdefault('classification','public')
     if not ev.get('date'):ev['date']='Fecha no publicada'
     if not ev.get('description'):ev['description']='Evidencia pública asociada a la entidad y al campo mostrado.'
    if evs and any(not all(str(ev.get(k) or '').strip() for k in ('source','title','url')) for ev in evs):
     spec['confidence']=min(float(spec.get('confidence') or .79),.79);spec['fact_confidence']=min(float(spec.get('fact_confidence') or .79),.79);spec['confidence_band']='medium';spec['confidence_reason']='Confianza media: existe evidencia identificada, pero falta una URL pública directa en al menos una referencia.'
def enrich_source_catalog(data:dict[str,Any])->int:
 rows={str(old.get('id') or old.get('source_id')):dict(old) for old in data.get('source_catalog') or [] if old.get('id') or old.get('source_id')};before=len(rows)
 for raw in load_json('config/v315/source_expansion.json',{}).get('sources') or []:
  sid=str(raw.get('source_id') or raw.get('id') or '')
  if sid:rows[sid]={'id':sid,'name':raw.get('name'),'url':raw.get('url'),'domain':urlparse(str(raw.get('url') or '')).netloc.lower(),'class':raw.get('source_class'),'scope':raw.get('scope') or [],'dimensions':raw.get('dimensions') or [],'access_policy':'public'}
 data['source_catalog']=sorted(rows.values(),key=lambda x:(str(x.get('class') or ''),str(x.get('name') or '')));return len(rows)-before
def apply_curated_enrichment(data:dict[str,Any])->dict[str,int]:
 cfg=load_json('config/v315/curated_enrichment.json',{});counts={'entities_enriched':0,'fields_enriched':0,'values_added':0}
 for cfg_key,section in (('distributors','distributors'),('manufacturers','manufacturers'),('clients','clients_private'),('integrator_jobs','integrators')):
  index={canonical(r.get('name')):r for r in data.get(section) or []}
  for raw in cfg.get(cfg_key) or []:
   row=index.get(canonical(raw.get('name')))
   if not row:continue
   touched=False;payload={raw['field']:raw['values']} if raw.get('field') and raw.get('values') else {k:v for k,v in raw.items() if k not in {'name','source','field','values'} and isinstance(v,list)}
   for field_id,values in payload.items():
    prior=((row.get('fields') or {}).get(field_id) or {}).get('value') or [];before=len(prior) if isinstance(prior,list) else 1;merge_field(row,field_id,values,raw['source']);current=((row.get('fields') or {}).get(field_id) or {}).get('value') or [];after=len(current) if isinstance(current,list) else 1
    if after>before:counts['fields_enriched']+=1;counts['values_added']+=after-before;touched=True
   if touched:counts['entities_enriched']+=1
 return counts
def configure_schema(data:dict[str,Any])->None:
 for columns in (data.get('schemas') or {}).values():
  for col in columns:col['expected']=True;col['empty_mode']='research';col.pop('hidden',None);col.pop('sparse_hide',None)
 for col in data.get('schemas',{}).get('distributors',[]):
  if col.get('id')=='competitor_vendor_overlap':col['label']='Fabricantes competidores en linecard'
  elif col.get('id')=='differential_capabilities':col['label']='Capacidades y servicios diferenciales'
def derive_distributor_overlap(data:dict[str,Any])->None:
 active={canonical(row.get('name')):row.get('name') for row in data.get('manufacturers') or []}
 for row in data.get('distributors') or []:
  vendor_field=(row.get('fields') or {}).get('vendor_relations') or {};values=vendor_field.get('value') or [];values=values if isinstance(values,list) else [values];overlap=[]
  for value in values:
   name=str(value).split('·',1)[0].strip();match=active.get(canonical(name))
   if match and match not in overlap:overlap.append(match)
  source=next(iter(vendor_field.get('evidence') or []),None)
  if overlap and source:merge_field(row,'westcon_overlap',overlap,source,'Intersección calculada entre un linecard público y el portfolio Westcon activo; no prueba una relación comercial con Westcon.')
def build()->dict[str,Any]:
 data=copy.deepcopy(build_v314());baseline=copy.deepcopy(data);now=datetime.now(timezone.utc).isoformat();data.setdefault('meta',{}).update({'version':VERSION,'generated_at':now,'research_model':'gap-driven-15-pass','claim_model':'fact-signal-interpretation','scope':'España y Portugal'});configure_schema(data);new_sources=enrich_source_catalog(data);enrichment=apply_curated_enrichment(data);derive_distributor_overlap(data);normalize_existing_claims(data);data['meta']['source_count']=len(data.get('source_catalog') or []);data['meta']['v315_research']={**enrichment,'new_source_routes':new_sources,'researched_at':'2026-08-30','iterations':2};data['meta']['traceability']='Hechos, señales e interpretaciones se etiquetan por separado; fuente, URL, fecha, título, fragmento, entidad, campo y confianza permanecen accesibles.';data['_baseline_v314']=baseline;return data
def write_snapshot(data:dict[str,Any])->dict[str,Any]:
 baseline=data.pop('_baseline_v314');out=ROOT/'data/v315';out.mkdir(parents=True,exist_ok=True);gaps=build_gaps(data,version=VERSION);before_gaps=build_gaps(baseline,version='3.14.0');before=calculate_metrics(baseline,before_gaps,version='3.14.0');after=calculate_metrics(data,gaps,version=VERSION);comparison=compare_metrics(before,after,baseline,data)
 write_json(out/'intelligence.json',data);write_json(out/'research_gaps.json',gaps);write_json(out/'metrics_before_after.json',comparison);write_json(out/'source_report.json',{'version':VERSION,'catalog_sources':len(data.get('source_catalog') or []),'unique_evidence_sources':after['unique_sources'],'unique_domains':after['unique_domains'],'official_evidence':after['official_evidence'],'new_routes':data['meta']['v315_research']['new_source_routes'],'families':sorted({str(s.get('class') or 'unknown') for s in data.get('source_catalog') or []})});write_json(out/'coverage_report.json',{'version':VERSION,'sections':after['sections'],'gap_by_section':after['gap_by_section']})
 result={'version':VERSION,'profile':'snapshot','status':'published','started_at':data['meta']['generated_at'],'finished_at':datetime.now(timezone.utc).isoformat(),**{k:after[k] for k in ('manufacturers','distributors','integrators','clients','clients_public','clients_private','trends','architectures','sources','evidence','relationships','traceable_fields','research_gaps','critical_gaps','unique_sources','unique_domains','official_evidence','corroborated_evidence')},'gap_by_section':after['gap_by_section'],'sections':after['sections'],'new_information':comparison['new_information'],'research_engine':gaps['engine'],'v315_research':data['meta']['v315_research'],'integrator_graph':data.get('meta',{}).get('integrator_graph',{}),'distributor_validation':data.get('meta',{}).get('distributor_validation',{}),'public_procurement':data.get('meta',{}).get('public_procurement',{})};write_json(out/'last_run.json',result);return result
if __name__=='__main__':print(json.dumps(write_snapshot(build()),ensure_ascii=False))
