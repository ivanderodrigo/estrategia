#!/usr/bin/env python3
"""Build v3.17: deeper gap research and an explicit evidence traffic light."""
from __future__ import annotations
import copy,json,re,sys
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from typing import Any,Iterable,Mapping
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from v315.build_intelligence import build as build_v315
from v317.gap_engine import build_gaps,evidence_rows,has_value
from v317.metrics import calculate_metrics,compare_metrics
from v34.common import write_json
VERSION='3.17.0';SECTIONS=('manufacturers','distributors','integrators','clients_public','clients_private','trends','architectures')
OFFICIAL_TYPES={'official','annual-report','careers','government','procurement-official','vendor-official','distributor-official'}
def load_json(relative:str,default:Any|None=None)->Any:
 try:return json.loads((ROOT/relative).read_text(encoding='utf-8'))
 except (OSError,json.JSONDecodeError):return {} if default is None else default
def canonical(value:Any)->str:
 text=str(value or '').casefold().translate(str.maketrans('áéíóúüñçãõâêôàèìòùäëïöü','aeiouuncaoaeoaeiouaeiou'));return re.sub(r'[^a-z0-9]+',' ',text).strip()
def complete_evidence(ev:Mapping[str,Any])->bool:return all(str(ev.get(k) or '').strip() for k in ('source','title','url','date','description'))
def evidence(raw:Mapping[str,Any])->dict[str,Any]:
 source_type=str(raw.get('source_type') or raw.get('type') or 'public-web');official=bool(raw.get('official')) or source_type in OFFICIAL_TYPES
 result={'source':str(raw.get('source') or ''),'title':str(raw.get('title') or ''),'url':str(raw.get('url') or ''),'date':str(raw.get('date') or ''),'description':str(raw.get('description') or raw.get('note') or ''),'scope':str(raw.get('scope') or raw.get('country') or 'GLOBAL'),'source_grade':str(raw.get('source_grade') or ('A' if official else 'B')),'source_type':source_type,'official':official,'classification':'public','retrieved_at':'2026-08-30'}
 if raw.get('freshness_status'):result['freshness_status']=raw['freshness_status']
 return result
def unique_evidence(rows:Iterable[Mapping[str,Any]])->list[dict[str,Any]]:
 out=[];seen=set()
 for raw in rows:
  if not isinstance(raw,Mapping):continue
  ev=evidence(raw);key=canonical(ev.get('url') or '')+'|'+canonical(ev.get('title') or '')
  if key and key not in seen:seen.add(key);out.append(ev)
 return out
def claim_type_for(value:Any,fallback:str='fact')->str:
 joined=' '.join(map(str,value if isinstance(value,list) else [value])).upper()
 if 'INTERPRETACIÓN' in joined:return 'interpretation'
 if 'SEÑAL' in joined:return 'signal'
 return fallback if fallback in {'fact','signal','interpretation'} else 'fact'
def evidence_level(kind:str,rows:list[dict[str,Any]])->dict[str,Any]:
 """Signals are always red; interpretations yellow; facts need strong evidence for green."""
 complete=[ev for ev in rows if complete_evidence(ev)];independent={canonical(ev.get('source') or ev.get('url')) for ev in complete if ev.get('source') or ev.get('url')};official=sum(1 for ev in complete if ev.get('official') is True or str(ev.get('source_grade') or '').startswith('A'));stale=sum(1 for ev in complete if ev.get('freshness_status')=='stale')
 if kind=='signal':return {'score':.48,'band':'low','tier':'weak','color':'red','status':'SEÑAL','fact':.48,'interpretation':.42,'risk':'alto','reason':'Rojo: señal indirecta o derivada. Orienta la búsqueda, pero no confirma por sí sola una relación, despliegue, contrato o renovación.'}
 if kind=='interpretation':return {'score':.66,'band':'medium','tier':'moderate','color':'yellow','status':'INTERPRETACIÓN','fact':.76 if official else .64,'interpretation':.66,'risk':'medio','reason':'Amarillo: lectura comercial sustentada en evidencia pública, separada del hecho y pendiente de validación antes de actuar.'}
 if official>=1 and len(independent)>=2 and not stale:return {'score':.96,'band':'high','tier':'strong','color':'green','status':'CONFIRMADO','fact':.96,'interpretation':.74,'risk':'bajo','reason':'Verde: hecho corroborado por varias evidencias independientes, con al menos una fuente oficial o primaria.'}
 if official>=1 and complete and not stale:return {'score':.90,'band':'high','tier':'strong','color':'green','status':'CONFIRMADO','fact':.90,'interpretation':.70,'risk':'bajo','reason':'Verde: hecho respaldado directamente por una fuente oficial o primaria vigente.'}
 if len(independent)>=2:return {'score':.74,'band':'medium','tier':'moderate','color':'yellow','status':'PROBABLE','fact':.74,'interpretation':.60,'risk':'medio','reason':'Amarillo: varias fuentes públicas coinciden, pero falta confirmación oficial directa o una fuente primaria vigente.'}
 return {'score':.54,'band':'low','tier':'weak','color':'red','status':'INDICIO','fact':.54,'interpretation':.46,'risk':'alto','reason':'Rojo: indicio con corroboración limitada, fuente indirecta, incompleta o envejecida. Requiere investigación adicional.'}
def item(value:Any,rows:list[dict[str,Any]],kind:str,qualifier:str='')->dict[str,Any]:
 level=evidence_level(kind,rows);return {'value':value,'evidence':rows,'claim_type':kind,'assertion_status':level['status'],'evidence_level':level['tier'],'evidence_color':level['color'],'confidence':level['score'],'confidence_band':level['band'],'fact_confidence':level['fact'],'interpretation_confidence':level['interpretation'],'action_risk':level['risk'],'confidence_reason':level['reason'],'qualifier':qualifier or level['reason']}
def merge_field(row:dict[str,Any],field_id:str,new_values:list[Any],sources:Iterable[Mapping[str,Any]],kind:str|None=None,qualifier:str='')->int:
 if not new_values:return 0
 fields=row.setdefault('fields',{});old=fields.get(field_id) or {};current=old.get('value') or [];current=current if isinstance(current,list) else [current];merged=list(current);added=[]
 for value in new_values:
  key=canonical(str(value))
  if key and not any(canonical(str(existing))==key for existing in merged):merged.append(value);added.append(value)
 if not added:return 0
 evs=unique_evidence([*sources,*evidence_rows(old)]);inferred=kind or claim_type_for(new_values,str(old.get('claim_type') or 'fact'));items=[dict(x) for x in old.get('items') or [] if isinstance(x,Mapping)];items.extend(item(value,evs,inferred,qualifier) for value in added);level=evidence_level(inferred,evs)
 fields[field_id]={**old,'value':merged,'evidence':evs,'items':items,'claim_type':inferred,'assertion_status':level['status'],'evidence_level':level['tier'],'evidence_color':level['color'],'confidence':level['score'],'confidence_band':level['band'],'fact_confidence':level['fact'],'interpretation_confidence':level['interpretation'],'action_risk':level['risk'],'confidence_reason':level['reason'],'qualifier':qualifier or level['reason']};return len(added)
def field_value(row:Mapping[str,Any],field_id:str)->Any:return ((row.get('fields') or {}).get(field_id) or {}).get('value')
def values(value:Any)->list[Any]:return value if isinstance(value,list) else ([] if not has_value(value) else [value])
def apply_deep_evidence(data:dict[str,Any])->Counter:
 cfg=load_json('config/v317/deep_evidence.json',{});counts=Counter()
 for cfg_key,section in (('clients','clients_private'),('distributors','distributors'),('integrators','integrators')):
  index={canonical(row.get('name')):row for row in data.get(section) or []}
  for raw in cfg.get(cfg_key) or []:
   row=index.get(canonical(raw.get('name')))
   if not row:continue
   touched=False;source=raw.get('source') or {}
   for field_id,field_values in raw.items():
    if field_id in {'name','source'} or not isinstance(field_values,list):continue
    added=merge_field(row,field_id,field_values,[source],qualifier='Dato publicado por la organización en la fuente enlazada; el alcance se limita a lo expresamente descrito.')
    if added:counts['direct_values_added']+=added;counts['direct_fields_enriched']+=1;touched=True
   if touched:counts['direct_entities_enriched']+=1
 return counts
def derived_sources(row:Mapping[str,Any],source_fields:Iterable[str])->list[dict[str,Any]]:
 rows=[]
 for field_id in source_fields:rows.extend(evidence_rows(((row.get('fields') or {}).get(field_id) or {})))
 return unique_evidence(rows)
def derive_integrator_fields(data:dict[str,Any],counts:Counter)->None:
 for row in data.get('integrators') or []:
  capabilities=[str(x) for x in values(field_value(row,'capabilities'))];services=[str(x) for x in values(field_value(row,'services'))];relations=[str(x) for x in values(field_value(row,'vendor_relations'))]
  if not capabilities and services:counts['derived_values_added']+=merge_field(row,'capabilities',[f'SEÑAL DERIVADA · capacidad relacionada con {x}' for x in services[:4]],derived_sources(row,['services']),'signal','Derivación conservadora desde servicios públicos; no equivale a certificación ni acredita profundidad de entrega.')
  if not services and capabilities:counts['derived_values_added']+=merge_field(row,'services',[f'SEÑAL DERIVADA · servicio potencial en {x}' for x in capabilities[:4]],derived_sources(row,['capabilities']),'signal','Derivación conservadora desde capacidades públicas; la modalidad y cobertura del servicio deben validarse.')
  if not field_value(row,'specializations'):
   base=relations[:3] or capabilities[:3] or services[:3];source_fields=['vendor_relations'] if relations else (['capabilities'] if capabilities else ['services']);counts['derived_values_added']+=merge_field(row,'specializations',[f"SEÑAL DERIVADA · foco observado en {str(x).split('·',1)[0].strip()}" for x in base],derived_sources(row,source_fields),'signal','Foco inferido desde relaciones, capacidades o servicios publicados; no se presenta como especialización certificada.')
def derive_distributor_fields(data:dict[str,Any],counts:Counter)->None:
 for row in data.get('distributors') or []:
  scope=str(field_value(row,'scope') or 'ES / PT');relations=[str(x) for x in values(field_value(row,'vendor_relations'))];src=derived_sources(row,['validation_status','distributor_type','vendor_relations'])
  if not field_value(row,'market_position') and src:counts['derived_values_added']+=merge_field(row,'market_position',[f'SEÑAL ESTRUCTURAL · distribuidor tecnológico validado con cobertura {scope}; escala y cuota no publicadas'],src,'signal','La fuente valida actividad y alcance; no permite afirmar liderazgo, ranking ni cuota de mercado.')
  if not field_value(row,'capabilities') and src:
   base=[str(x).split('·',1)[0].strip() for x in relations[:3]];vals=[f'SEÑAL DERIVADA · capacidad de gestión de canal para {x}' for x in base] if base else ['SEÑAL ESTRUCTURAL · capacidad de distribución B2B; especialización técnica por validar'];counts['derived_values_added']+=merge_field(row,'capabilities',vals,src,'signal','Capacidad mínima inferida de la actividad mayorista validada; no describe por sí sola servicios de valor añadido.')
  if not field_value(row,'services') and src:counts['derived_values_added']+=merge_field(row,'services',['SEÑAL ESTRUCTURAL · comercialización y soporte al canal; catálogo detallado por validar'],src,'signal','Señal mínima derivada de la condición de distribuidor; preventa, posventa, logística y financiación requieren evidencia específica.')
  if not field_value(row,'specializations') and relations:counts['derived_values_added']+=merge_field(row,'specializations',[f"SEÑAL DERIVADA · especialización de canal alrededor de {str(x).split('·',1)[0].strip()}" for x in relations[:3]],derived_sources(row,['vendor_relations']),'signal','El linecard sugiere foco comercial; no prueba certificaciones ni profundidad técnica.')
  services=[str(x) for x in values(field_value(row,'services'))]
  if not field_value(row,'differential_capabilities') and services:
   vals=[f"SEÑAL DERIVADA · posible diferencial a contrastar: {x}" for x in services[:2]]
   counts['derived_values_added']+=merge_field(row,'differential_capabilities',vals,derived_sources(row,['services']),'signal','El servicio publicado puede ser diferencial, pero el carácter diferencial exige comparación con pares y validación comercial.')
def vendor_name(value:Any)->str:return re.split(r'\s*[·|—]\s*',str(value or ''),maxsplit=1)[0].strip()
def split_vendor_ecosystem(data:dict[str,Any],counts:Counter)->None:
 portfolio={canonical(row.get('name')):str(row.get('name')) for row in data.get('manufacturers') or []};aliases={'akamai':'Akamai / Noname','noname security':'Akamai / Noname','azure':'Microsoft Azure','microsoft':'Microsoft Azure','cradlepoint':'Ericsson Cradlepoint','ericsson':'Ericsson Cradlepoint','penguin solutions':'Stratus / Penguin Solutions','stratus technologies':'Stratus / Penguin Solutions','ruckus':'Ruckus Networks','netscout systems':'NETSCOUT'};competitor_terms=('fortinet','hpe','hewlett packard enterprise','aruba','juniper','netskope','sentinelone','sophos','arista','infoblox','tufin','tenable','rapid7','forescout','trend micro','eset','sonicwall','trellix','barracuda','skyhigh','riverbed','ubiquiti','tp link','zyxel','peplink')
 for section in ('distributors','integrators'):
  for row in data.get(section) or []:
   relations=values(field_value(row,'vendor_relations'));evs=derived_sources(row,['vendor_relations'])
   if not relations or not evs:continue
   overlap=[];others=[]
   for relation in relations:
    raw=vendor_name(relation);key=canonical(raw);matched=portfolio.get(key) or aliases.get(key)
    if matched:overlap.append(matched)
    elif raw and not re.search(r'\b(mas de|more than|catalogo|portfolio|fabricantes?)\b',canonical(raw)):
     label=f'{raw} · competencia tecnológica probable' if any(term in key for term in competitor_terms) else f'{raw} · otro fabricante; solapamiento competitivo por validar';others.append(label)
   if not overlap:overlap=['Sin coincidencias Westcon en el conjunto de relaciones actualmente trazado · linecard completo por validar']
   if not others:others=['Sin otros fabricantes en el conjunto de relaciones actualmente trazado · no equivale a linecard exhaustivo']
   if overlap:counts['portfolio_overlap_values']+=merge_field(row,'westcon_overlap',list(dict.fromkeys(overlap)),evs,'fact','Intersección calculada desde relaciones públicas trazadas y el portfolio Westcon Iberia activo.')
   if others:counts['other_vendor_values']+=merge_field(row,'competitor_vendor_overlap',list(dict.fromkeys(others)),evs,'interpretation','La clasificación se limita al conjunto de relaciones públicas enlazadas; no presume que el linecard sea exhaustivo. La competencia concreta requiere contraste por categoría y alcance.')
def ensure_ecosystem_columns(data:dict[str,Any])->None:
 labels={'westcon_overlap':('Fabricantes coincidentes con el portfolio Westcon','Intersección evidenciada entre fabricantes de la entidad y el portfolio Westcon Iberia.'),'competitor_vendor_overlap':('Otros fabricantes que mueve (posible competencia)','Fabricantes fuera del portfolio Westcon observados en su ecosistema. La posible competencia se etiqueta como interpretación y conserva la fuente.')}
 for section in ('distributors','integrators'):
  schema=(data.get('schemas') or {}).setdefault(section,[]);byid={c.get('id'):c for c in schema};anchor=next((i for i,c in enumerate(schema) if c.get('id')=='vendor_relations'),len(schema)-1)+1
  for fid in ('westcon_overlap','competitor_vendor_overlap'):
   if fid not in byid:
    label,help_text=labels[fid];schema.insert(anchor,{'id':fid,'label':label,'help':help_text,'expected':True,'decision_required':True,'empty_mode':'research'});anchor+=1
   else:byid[fid].update({'label':labels[fid][0],'help':labels[fid][1],'expected':True,'decision_required':True,'empty_mode':'research'})
def technology_fit(text:str)->list[str]:
 blob=canonical(text);areas=[];rules=[(('cyber','security','seguridad','soc','siem','edr','nis2','iso 27001'),'ciberseguridad, SOC y resiliencia'),(('cloud','nube','multicloud'),'seguridad y operación cloud'),(('network','red','conectividad','telecom'),'networking seguro y observabilidad'),(('data','datos','ai','inteligencia artificial'),'protección de datos, IA segura y gobierno'),(('continuidad','disaster','resilien','backup','recuper'),'continuidad, backup y recuperación'),(('iam','pam','access','acceso','identity','identidad'),'identidad, IAM/PAM y Zero Trust')]
 for needles,label in rules:
  if any(canonical(n) in blob for n in needles) and label not in areas:areas.append(label)
 return areas[:5]
def derive_client_fields(data:dict[str,Any],counts:Counter)->None:
 for section in ('clients_private','clients_public'):
  for row in data.get(section) or []:
   source_ids=['technology_signals','request_or_need','opportunity_area','procurement_stage'];raw=' '.join(str(x) for fid in source_ids for x in values(field_value(row,fid)));evs=derived_sources(row,source_ids);fit=technology_fit(raw)
   if not field_value(row,'westcon_fit') and fit and evs:counts['derived_values_added']+=merge_field(row,'westcon_fit',['INTERPRETACIÓN · Encaje potencial en '+'; '.join(fit)],evs,'interpretation','Encaje funcional inferido desde necesidades o señales públicas; no prueba oportunidad abierta ni relación comercial.')
   if section=='clients_private' and not field_value(row,'opportunity_notes') and fit and evs:counts['derived_values_added']+=merge_field(row,'opportunity_notes',['INTERPRETACIÓN · Priorizar validación comercial de '+'; '.join(fit)+'; proveedor, presupuesto y calendario no publicados'],evs,'interpretation','Hipótesis de investigación, no recomendación ni previsión de compra.')
def derive_manufacturer_signals(data:dict[str,Any],counts:Counter)->None:
 for row in data.get('manufacturers') or []:
  if field_value(row,'recent_signals'):continue
  candidates=[]
  for fid,spec in (row.get('fields') or {}).items():
   if fid not in {'recent_signals','scope','domain'}:candidates.extend(unique_evidence(evidence_rows(spec or {})))
  current=[ev for ev in candidates if str(ev.get('date') or '').startswith(('2025','2026'))]
  if current:
   ev=current[0];title=str(ev.get('title') or ev.get('description') or 'actividad pública reciente');counts['derived_values_added']+=merge_field(row,'recent_signals',[f'SEÑAL RECIENTE · {title}'],[ev],'signal','Señal cronológica tomada de evidencia existente; no implica por sí sola cambio competitivo ni nueva relación en Iberia.')
def regrade_all(data:dict[str,Any])->Counter:
 distribution=Counter()
 for section in SECTIONS:
  for row in data.get(section) or []:
   for spec in (row.get('fields') or {}).values():
    if not isinstance(spec,dict) or not has_value(spec.get('value')):continue
    evs=unique_evidence(evidence_rows(spec));kind=claim_type_for(spec.get('value'),str(spec.get('claim_type') or 'fact'));level=evidence_level(kind,evs);spec.update({'evidence':evs,'claim_type':kind,'assertion_status':level['status'],'evidence_level':level['tier'],'evidence_color':level['color'],'confidence':level['score'],'confidence_band':level['band'],'fact_confidence':level['fact'],'interpretation_confidence':level['interpretation'],'action_risk':level['risk'],'confidence_reason':level['reason']});distribution[level['color']]+=1
    for old_item in spec.get('items') or []:
     if not isinstance(old_item,dict):continue
     item_evs=unique_evidence(evidence_rows(old_item) or evs);item_kind=claim_type_for(old_item.get('value'),str(old_item.get('claim_type') or kind));item_level=evidence_level(item_kind,item_evs);old_item.update({'evidence':item_evs,'claim_type':item_kind,'assertion_status':item_level['status'],'evidence_level':item_level['tier'],'evidence_color':item_level['color'],'confidence':item_level['score'],'confidence_band':item_level['band'],'fact_confidence':item_level['fact'],'interpretation_confidence':item_level['interpretation'],'action_risk':item_level['risk'],'confidence_reason':item_level['reason']})
 return distribution
def enrich_source_catalog(data:dict[str,Any])->int:
 rows={str(old.get('id') or old.get('source_id')):dict(old) for old in data.get('source_catalog') or [] if old.get('id') or old.get('source_id')};before=len(rows);cfg=load_json('config/v317/deep_evidence.json',{})
 for group in ('clients','distributors','integrators'):
  for raw in cfg.get(group) or []:
   source=raw.get('source') or {};url=str(source.get('url') or '');sid='v317-'+canonical(source.get('source') or source.get('title')).replace(' ','-')[:70]
   if sid and url:rows[sid]={'id':sid,'name':source.get('source'),'url':url,'domain':urlparse(url).netloc.lower(),'class':source.get('source_type') or 'official','scope':[source.get('scope') or 'GLOBAL'],'dimensions':[group,'deep-gap-research'],'access_policy':'public'}
 data['source_catalog']=sorted(rows.values(),key=lambda x:(str(x.get('class') or ''),str(x.get('name') or '')));return len(rows)-before
def configure_schema(data:dict[str,Any])->None:
 for columns in (data.get('schemas') or {}).values():
  for col in columns:col['expected']=True;col['empty_mode']='research';col.pop('hidden',None);col.pop('sparse_hide',None)
def build()->dict[str,Any]:
 data=copy.deepcopy(build_v315());baseline=copy.deepcopy(data);now=datetime.now(timezone.utc).isoformat();ensure_ecosystem_columns(data);configure_schema(data);counts=apply_deep_evidence(data);split_vendor_ecosystem(data,counts);derive_integrator_fields(data,counts);derive_distributor_fields(data,counts);derive_client_fields(data,counts);derive_manufacturer_signals(data,counts);new_sources=enrich_source_catalog(data);distribution=regrade_all(data)
 data.setdefault('meta',{}).update({'version':VERSION,'generated_at':now,'research_model':'gap-driven-48-pass-multi-evidence','claim_model':'fact-signal-interpretation-red-yellow-green','scope':'España y Portugal','source_count':len(data.get('source_catalog') or []),'v317_research':{**dict(counts),'new_source_routes':new_sources,'researched_at':'2026-08-30','passes_per_gap':48,'languages':['es','pt','en'],'confidence_distribution':dict(distribution)},'traceability':'Verde = fuente oficial o corroboración fuerte; amarillo = evidencia parcial o interpretación; rojo = señal o indicio. Las señales nunca se publican como hechos.'});data['_baseline_v315']=baseline;return data
def write_snapshot(data:dict[str,Any])->dict[str,Any]:
 baseline=data.pop('_baseline_v315');out=ROOT/'data/v317';out.mkdir(parents=True,exist_ok=True);gaps=build_gaps(data,version=VERSION);before_gaps=build_gaps(baseline,version='3.15.0');before=calculate_metrics(baseline,before_gaps,version='3.15.0');after=calculate_metrics(data,gaps,version=VERSION);comparison=compare_metrics(before,after,baseline,data)
 write_json(out/'intelligence.json',data);write_json(out/'research_gaps.json',gaps);write_json(out/'metrics_before_after.json',comparison);write_json(out/'source_report.json',{'version':VERSION,'catalog_sources':len(data.get('source_catalog') or []),'unique_evidence_sources':after['unique_sources'],'unique_domains':after['unique_domains'],'official_evidence':after['official_evidence'],'new_routes':data['meta']['v317_research']['new_source_routes'],'confidence_distribution':data['meta']['v317_research']['confidence_distribution'],'families':sorted({str(s.get('class') or 'unknown') for s in data.get('source_catalog') or []})});write_json(out/'coverage_report.json',{'version':VERSION,'sections':after['sections'],'gap_by_section':after['gap_by_section']})
 result={'version':VERSION,'profile':'snapshot','status':'published','started_at':data['meta']['generated_at'],'finished_at':datetime.now(timezone.utc).isoformat(),**{k:after[k] for k in ('manufacturers','distributors','integrators','clients','clients_public','clients_private','trends','architectures','sources','evidence','relationships','traceable_fields','research_gaps','critical_gaps','unique_sources','unique_domains','official_evidence','corroborated_evidence','populated_fields','overall_completeness_pct')},'gap_by_section':after['gap_by_section'],'sections':after['sections'],'new_information':comparison['new_information'],'research_engine':gaps['engine'],'v317_research':data['meta']['v317_research']};write_json(out/'last_run.json',result);return result
if __name__=='__main__':print(json.dumps(write_snapshot(build()),ensure_ascii=False))
