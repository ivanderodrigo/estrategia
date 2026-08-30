"""Gap queue with fixed definitions and a 15-pass research plan."""
from __future__ import annotations
import re
from collections import Counter
from datetime import datetime,timezone
from typing import Any,Mapping
SECTIONS=('manufacturers','distributors','integrators','clients_public','clients_private','trends','architectures')
PLACEHOLDERS={'','-','--','—','n/d','nd','pendiente','pendiente de evidencia','por investigar','en investigacion','en investigación'}
IDENTITY_FIELDS={'scope','domain','entity_type','notice_id','source_portal','index_universe'}
PASS_NAMES=('fuente oficial directa','fuentes oficiales relacionadas','web específica','variantes semánticas','idioma alternativo','PDFs y documentación','directorios de partners','casos de éxito','empleo','contratación pública','prensa especializada','entidades relacionadas','archivo e histórico','relaciones del grafo','corroboración')
FIELD_TERMS={
 'competitors':'competitors alternatives peers competencia','distributors':'authorized distributor where to buy Spain Portugal','integrators':'partner locator certified reseller MSP MSSP Spain Portugal','vendor_relations':'partners vendors linecard fabricantes','westcon_overlap':'linecard Westcon portfolio vendors','competitor_vendor_overlap':'linecard competing vendors cybersecurity networking','differential_capabilities':'services training financing logistics marketplace support','specializations':'certifications competencies specializations','services':'managed professional services support implementation','capabilities':'SOC NOC cloud cybersecurity networking observability','verticals':'industries customers sectors','public_cases':'case study customer story Spain Portugal','job_vendors':'jobs careers technologies vendors','job_profiles':'jobs careers cloud security network architect','technology_signals':'technology cloud cybersecurity networking infrastructure','hiring_signals':'careers jobs cloud cybersecurity network','renewal_window':'renewal modernization investment roadmap','westcon_fit':'cloud security networking observability architecture','opportunity_notes':'project investment transformation opportunity','trend_market_metrics':'market size forecast CAGR Europe Iberia','adjacent_market_metrics':'adjacent market size forecast','market_players':'market vendors leaders competitors','westcon_vendors':'Westcon portfolio vendors market','iberia_context':'Spain Portugal Iberia adoption market','analyst_basis':'Gartner IDC Forrester NIST reference architecture','layers':'reference architecture layers','vendors':'reference architecture vendors','limits':'architecture limitations risks'}
def norm(value:Any)->str:return re.sub(r'\s+',' ',str(value or '').strip().casefold())
def has_value(value:Any)->bool:
 if value is None or value is False or value==[] or value=={}:return False
 if isinstance(value,str):return norm(value) not in PLACEHOLDERS
 return True
def evidence_rows(field:Mapping[str,Any])->list[Mapping[str,Any]]:
 rows=[e for e in field.get('evidence') or [] if isinstance(e,Mapping)]
 for item in field.get('items') or []:
  if isinstance(item,Mapping):rows.extend(e for e in item.get('evidence') or [] if isinstance(e,Mapping))
 return rows
def complete_evidence(ev:Mapping[str,Any])->bool:return all(str(ev.get(k) or '').strip() for k in ('source','title','url','date','description'))
def evidence_sufficient(field:Mapping[str,Any])->bool:
 if not has_value(field.get('value')):return False
 rows=[e for e in evidence_rows(field) if complete_evidence(e)]
 if not rows:return False
 kind=str(field.get('claim_type') or 'fact')
 if kind in {'signal','interpretation'} and not field.get('assertion_status'):return False
 official=any(e.get('official') is True or str(e.get('source_grade') or '').startswith('A') or 'official' in str(e.get('source_type') or e.get('type') or '').lower() for e in rows)
 independent={str(e.get('source') or '').casefold() for e in rows}
 return official or len(independent)>=2
def _scope(row:Mapping[str,Any])->str:
 value=(((row.get('fields') or {}).get('scope') or {}).get('value'))
 if isinstance(value,list):return ' / '.join(map(str,value))
 return str(value or 'ES / PT')
def _query(entity:str,field_id:str,pass_no:int,scope:str)->str:
 terms=FIELD_TERMS.get(field_id,field_id.replace('_',' '));quoted=f'"{entity}"'
 variants={
 1:f'{quoted} site:official-domain {terms}',2:f'{quoted} {terms} official partner customer',3:f'{quoted} {terms} {scope}',4:f'{quoted} {terms} certification alliance service',5:f'{quoted} {terms} España Portugal Spain Portuguese English',6:f'{quoted} {terms} filetype:pdf',7:f'{quoted} partner locator directory {terms}',8:f'{quoted} case study customer story {terms}',9:f'{quoted} jobs careers empleo emprego {terms}',10:f'{quoted} tender contrato licitación concurso {terms}',11:f'{quoted} {terms} channel news press release',12:f'{quoted} distributor integrator vendor customer {terms}',13:f'{quoted} {terms} archive history 2020..2026',14:f'{quoted} related partner customer project {terms}',15:f'{quoted} {terms} corroborate second source'}
 return variants[pass_no]
def research_plan(section:str,row:Mapping[str,Any],field_id:str)->list[dict[str,Any]]:
 entity=str(row.get('name') or '');scope=_scope(row)
 return [{'pass':i,'strategy':PASS_NAMES[i-1],'query':_query(entity,field_id,i,scope),'languages':['es','pt','en'] if i in {3,4,5,11} else ['es','pt'],'source_family':PASS_NAMES[i-1]} for i in range(1,16)]
def build_gaps(public:Mapping[str,Any],version:str='3.15.0')->dict[str,Any]:
 gaps=[];missing=Counter();critical=Counter();states=Counter();expected=Counter();populated=Counter()
 for section in SECTIONS:
  schema={c.get('id'):c for c in (public.get('schemas') or {}).get(section,[]) if c.get('id')}
  for row in public.get(section) or []:
   fields=row.get('fields') or {}
   for field_id,col in schema.items():
    expected[section]+=1;field=fields.get(field_id) or {};value_ok=has_value(field.get('value'))
    if value_ok:populated[section]+=1
    sufficient=evidence_sufficient(field)
    if value_ok and sufficient:continue
    reason='valor pendiente' if not value_ok else 'evidencia o trazabilidad insuficiente'
    priority=1 if col.get('decision_required') or field_id not in IDENTITY_FIELDS else 2
    state='Por investigar';states[state]+=1;missing[(section,field_id)]+=1
    if priority==1:critical[section]+=1
    gaps.append({'id':f'{section}:{norm(row.get("name"))}:{field_id}','section':section,'entity':row.get('name'),'entity_id':row.get('id'),'field':field_id,'country_context':_scope(row),'research_state':state,'priority':priority,'reason':reason,'attempts_completed':0,'close_policy':'Solo cerrar con valor y evidencia pública suficiente; cero resultados mantiene el gap activo.','passes':research_plan(section,row,field_id),'retry':{'max_attempts_per_pass':3,'backoff_seconds':[2,5,15],'resume_from_checkpoint':True}})
 gaps.sort(key=lambda g:(g['priority'],g['section'],norm(g['entity']),g['field']))
 by_section={s:sum(1 for g in gaps if g['section']==s) for s in SECTIONS};coverage={s:{'expected_fields':expected[s],'populated_fields':populated[s],'value_completeness_pct':round(populated[s]*100/max(1,expected[s]),2),'open_gaps':by_section[s]} for s in SECTIONS}
 return {'version':version,'generated_at':datetime.now(timezone.utc).isoformat(),'definition':'Misma definición v3.14→v3.15: todo campo declarado en el esquema cuenta; un valor solo cierra el gap con evidencia suficiente. No se ocultan opcionales.','total_gaps':len(gaps),'critical_gaps':sum(critical.values()),'high_priority_gaps':sum(critical.values()),'by_section':by_section,'critical_by_section':dict(critical),'missing_by_field':{f'{s}.{f}':n for (s,f),n in missing.most_common()},'research_states':dict(states),'coverage':coverage,'engine':{'passes_per_gap':15,'languages':['es','pt','en'],'timeouts_seconds':20,'retries':3,'backoff':'exponential','circuit_breaker_failures':5,'per_domain_concurrency':2,'global_concurrency':8,'checkpoint_every_results':25,'incremental':True,'resume':True,'failure_isolation':'per-source','learning_log':'data/v315/research_learning.json'},'gaps':gaps}
