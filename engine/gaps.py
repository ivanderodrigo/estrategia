"""Exhaustive 48-pass queue for every value or evidence gap."""
from __future__ import annotations
import re
from collections import Counter
from datetime import datetime,timezone
from typing import Any,Mapping
SECTIONS=('manufacturers','distributors','integrators','clients_public','clients_private','trends','architectures')
PLACEHOLDERS={'','-','--','—','n/d','nd','pendiente','pendiente de evidencia','por investigar','en investigacion','en investigación'}
IDENTITY_FIELDS={'scope','domain','entity_type','notice_id','source_portal','index_universe'}
PASS_NAMES=('dominio oficial','buscador interno oficial','informes anuales','gobierno corporativo','relaciones con inversores','notas de prensa oficiales','catálogo o linecard','páginas de servicios','partner locator','directorios de certificación','casos de éxito','referencias de clientes','portal de empleo','vacantes por tecnología','contratación pública TED','contratación pública nacional','reguladores y registros','documentos PDF','prensa de canal','prensa tecnológica','analistas','peer reviews','directorios sectoriales','fuentes en español','fuentes en portugués','fuentes en inglés','variantes de marca y filial','adquisiciones y razón social','entidades relacionadas','relaciones del grafo','corroboración independiente','búsqueda de contradicciones','sitemap oficial','PDFs del dominio oficial','páginas archivadas','directorio del fabricante','directorio del hyperscaler','marketplace cloud','casos del fabricante','certificaciones del fabricante','noticias por razón social','empleo por filial','tecnología en vacantes','licitaciones por adjudicatario','contratos Portugal','expedientes España','segunda fuente sectorial','revalidación de vigencia','cierre por evidencia')
FIELD_TERMS={'competitors':'competitors alternatives peers competencia','distributors':'authorized distributor where to buy Spain Portugal','integrators':'partner locator certified reseller MSP MSSP Spain Portugal','vendor_relations':'partners vendors linecard fabricantes','westcon_overlap':'linecard Westcon portfolio vendors','competitor_vendor_overlap':'linecard competing vendors cybersecurity networking','differential_capabilities':'services training financing logistics marketplace support','specializations':'certifications competencies specializations','services':'managed professional services support implementation','capabilities':'SOC NOC cloud cybersecurity networking observability','verticals':'industries customers sectors','public_cases':'case study customer story Spain Portugal','job_vendors':'jobs careers technologies vendors','job_profiles':'jobs careers cloud security network architect','technology_signals':'technology cloud cybersecurity networking infrastructure','hiring_signals':'careers jobs cloud cybersecurity network','renewal_window':'renewal modernization investment roadmap','westcon_fit':'cloud security networking observability architecture','opportunity_notes':'project investment transformation opportunity','trend_market_metrics':'market size forecast CAGR Europe Iberia','adjacent_market_metrics':'adjacent market size forecast','market_players':'market vendors leaders competitors','westcon_vendors':'Westcon portfolio vendors market','iberia_context':'Spain Portugal Iberia adoption market','analyst_basis':'Gartner IDC Forrester NIST reference architecture','layers':'reference architecture layers','vendors':'reference architecture vendors','limits':'architecture limitations risks'}
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
 value=(((row.get('fields') or {}).get('scope') or {}).get('value'));return ' / '.join(map(str,value)) if isinstance(value,list) else str(value or 'ES / PT')
def _query(entity:str,field_id:str,pass_no:int,scope:str)->str:
 terms=FIELD_TERMS.get(field_id,field_id.replace('_',' '));q=f'"{entity}"';year='2024..2026'
 variants={
 1:f'{q} official {terms}',2:f'site:official-domain {q} {terms}',3:f'{q} annual report integrated report {terms} {year}',4:f'{q} corporate governance cybersecurity technology {year}',5:f'{q} investors results presentation {terms}',6:f'{q} press release newsroom {terms} {year}',7:f'{q} catalog linecard vendors marcas fabricantes',8:f'{q} services solutions capabilities {terms}',9:f'{q} partner locator certified partner Spain Portugal',10:f'{q} certification competency specialization directory',11:f'{q} case study success story customer {terms}',12:f'{q} customers references projects Spain Portugal',13:f'{q} careers jobs empleo emprego {terms}',14:f'{q} vacancy architect engineer SOC cloud security vendors',15:f'{q} site:ted.europa.eu tender procurement {terms}',16:f'{q} licitación concurso contrato contratação pública {terms}',17:f'{q} regulator registry certification accreditation {terms}',18:f'{q} {terms} filetype:pdf {year}',19:f'{q} channel news distributor integrator {terms}',20:f'{q} technology press project alliance {terms}',21:f'{q} Gartner IDC Forrester market guide alternatives',22:f'{q} Peer Insights G2 reviews alternatives',23:f'{q} directory association ecosystem {scope}',24:f'{q} {terms} España español',25:f'{q} {terms} Portugal português',26:f'{q} {terms} Spain Portugal English',27:f'("{entity}" OR brand alias) {terms}',28:f'{q} acquisition subsidiary legal name {terms}',29:f'{q} vendor distributor integrator customer related {terms}',30:f'{q} graph neighbor relationship evidence {terms}',31:f'{q} {terms} corroborate independent second source',32:f'{q} {terms} denied ended expired no longer contradiction'}
 if pass_no in variants:return variants[pass_no]
 extra={33:f'{q} official sitemap {terms}',34:f'{q} site:official-domain filetype:pdf {terms}',35:f'{q} archived history {terms}',36:f'{q} certified partner directory vendor {terms}',37:f'{q} AWS Azure Google partner finder {terms}',38:f'{q} marketplace cloud solutions {terms}',39:f'{q} customer story partner case study {terms}',40:f'{q} specialization certification badge {terms}',41:f'"{entity}" subsidiary legal company news {terms}',42:f'"{entity}" jobs careers filial Spain Portugal {terms}',43:f'"{entity}" vacancy technology stack {terms}',44:f'"{entity}" awarded contract tender supplier {terms}',45:f'"{entity}" site:base.gov.pt contrato tecnologia',46:f'"{entity}" site:contrataciondelestado.es adjudicatario tecnologia',47:f'"{entity}" {terms} channel independent second source',48:f'"{entity}" {terms} 2025 2026 current expired discontinued'}
 return extra[pass_no]
def research_plan(section:str,row:Mapping[str,Any],field_id:str)->list[dict[str,Any]]:
 entity=str(row.get('name') or '');scope=_scope(row)
 return [{'pass':i,'strategy':PASS_NAMES[i-1],'query':_query(entity,field_id,i,scope),'languages':['es','pt','en'],'source_family':PASS_NAMES[i-1],'objective':'confirm' if i<31 else ('corroborate' if i in {31,47} else 'challenge' if i in {32,48} else 'expand')} for i in range(1,49)]
def build_gaps(public:Mapping[str,Any],version:str='3.19.0')->dict[str,Any]:
 gaps=[];missing=Counter();critical=Counter();states=Counter();expected=Counter();populated=Counter()
 for section in SECTIONS:
  schema={c.get('id'):c for c in (public.get('schemas') or {}).get(section,[]) if c.get('id')}
  for row in public.get(section) or []:
   fields=row.get('fields') or {}
   for field_id,col in schema.items():
    expected[section]+=1;field=fields.get(field_id) or {};value_ok=has_value(field.get('value'));populated[section]+=int(value_ok);sufficient=evidence_sufficient(field)
    if value_ok and sufficient:continue
    reason='valor pendiente' if not value_ok else 'evidencia o trazabilidad insuficiente';priority=1 if col.get('decision_required') or field_id not in IDENTITY_FIELDS else 2;state='Por investigar';states[state]+=1;missing[(section,field_id)]+=1;critical[section]+=int(priority==1)
    gaps.append({'id':f'{section}:{norm(row.get("name"))}:{field_id}','section':section,'entity':row.get('name'),'entity_id':row.get('id'),'field':field_id,'country_context':_scope(row),'research_state':state,'priority':priority,'reason':reason,'attempts_completed':0,'close_policy':'Solo cerrar con valor y evidencia pública suficiente; cero resultados mantiene el gap activo. Una señal se publica en rojo y no se convierte en hecho.','strategy_profile':'cascade_48','next_pass':1,'retry_policy':'resilient_default'})
 gaps.sort(key=lambda g:(g['priority'],g['section'],norm(g['entity']),g['field']));by_section={s:sum(1 for g in gaps if g['section']==s) for s in SECTIONS};coverage={s:{'expected_fields':expected[s],'populated_fields':populated[s],'value_completeness_pct':round(populated[s]*100/max(1,expected[s]),2),'open_gaps':by_section[s]} for s in SECTIONS}
 return {'version':version,'generated_at':datetime.now(timezone.utc).isoformat(),'definition':'Misma definición v3.15→v3.17: todo campo declarado cuenta; un valor solo cierra el gap con evidencia suficiente y sin ocultar opcionales.','total_gaps':len(gaps),'critical_gaps':sum(critical.values()),'high_priority_gaps':sum(critical.values()),'by_section':by_section,'critical_by_section':dict(critical),'missing_by_field':{f'{s}.{f}':n for (s,f),n in missing.most_common()},'research_states':dict(states),'coverage':coverage,'engine':{'strategy_profile':'cascade_48','plan_storage':'normalized: generated on demand, never duplicated in every gap','languages':['es','pt','en'],'timeouts_seconds':25,'retries':4,'backoff':'exponential','circuit_breaker_failures':5,'per_domain_concurrency':2,'global_concurrency':12,'checkpoint_every_results':20,'incremental':True,'resume':True,'failure_isolation':'per-source','contradiction_pass':True,'learning_log':'data/current/research_learning.json','ledger':'data/current/research_ledger.json'},'gaps':gaps}
