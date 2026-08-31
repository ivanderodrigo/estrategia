"""Comparable v3.15/v3.17 metrics using one fixed field definition."""
from __future__ import annotations
from typing import Any,Mapping
from urllib.parse import urlparse
from v317.gap_engine import SECTIONS,evidence_rows,has_value
def _field_map(data:Mapping[str,Any])->dict[tuple[str,str,str],Mapping[str,Any]]:
 out={}
 for section in SECTIONS:
  for row in data.get(section) or []:
   entity=str(row.get('id') or row.get('name') or '')
   for field_id,spec in (row.get('fields') or {}).items():out[(section,entity,field_id)]=spec or {}
 return out
def calculate_metrics(data:Mapping[str,Any],gaps:Mapping[str,Any],version:str)->dict[str,Any]:
 evs=[];traceable=0;expected_total=0;populated_total=0;sections={};urls=set();sources=set();domains=set();official=0;corroborated=0
 for section in SECTIONS:
  schema=[c.get('id') for c in (data.get('schemas') or {}).get(section,[]) if c.get('id')];rows=data.get(section) or [];expected=len(schema)*len(rows);populated=0;evidenced=0
  for row in rows:
   for field_id in schema:
    spec=(row.get('fields') or {}).get(field_id) or {}
    if has_value(spec.get('value')):populated+=1
    field_evs=evidence_rows(spec)
    if field_evs:traceable+=1;evidenced+=1;evs.extend(field_evs)
    independent={str(e.get('source') or '').casefold() for e in field_evs if e.get('source')}
    if len(independent)>=2:corroborated+=1
  expected_total+=expected;populated_total+=populated;sections[section]={'entities':len(rows),'expected_fields':expected,'populated_fields':populated,'completeness_pct':round(populated*100/max(1,expected),2),'fields_with_evidence':evidenced,'evidence_coverage_pct':round(evidenced*100/max(1,expected),2),'gaps':(gaps.get('by_section') or {}).get(section,0)}
 for ev in evs:
  source=str(ev.get('source') or '').strip();url=str(ev.get('url') or '').strip()
  if source:sources.add(source.casefold())
  if url:urls.add(url);host=urlparse(url).netloc.casefold();domains.add(host) if host else None
  if ev.get('official') is True or str(ev.get('source_grade') or '').startswith('A') or 'official' in str(ev.get('source_type') or ev.get('type') or '').lower():official+=1
 rels=0
 for section,field_ids in {'manufacturers':('distributors','integrators','competitors'),'distributors':('vendor_relations','westcon_overlap','competitor_vendor_overlap'),'integrators':('vendor_relations','public_cases'),'clients_private':('technology_signals',),'clients_public':('technology_signals',)}.items():
  for row in data.get(section) or []:
   for field_id in field_ids:
    value=((row.get('fields') or {}).get(field_id) or {}).get('value') or []
    rels+=len(value) if isinstance(value,list) else int(has_value(value))
 return {'version':version,'manufacturers':len(data.get('manufacturers') or []),'distributors':len(data.get('distributors') or []),'integrators':len(data.get('integrators') or []),'clients_public':len(data.get('clients_public') or []),'clients_private':len(data.get('clients_private') or []),'clients':len(data.get('clients_public') or [])+len(data.get('clients_private') or []),'trends':len(data.get('trends') or []),'architectures':len(data.get('architectures') or []),'sources':len(data.get('source_catalog') or []),'evidence':len(evs),'relationships':rels,'traceable_fields':traceable,'expected_fields':expected_total,'populated_fields':populated_total,'overall_completeness_pct':round(populated_total*100/max(1,expected_total),2),'evidence_coverage_pct':round(traceable*100/max(1,expected_total),2),'research_gaps':int(gaps.get('total_gaps') or 0),'critical_gaps':int(gaps.get('critical_gaps') or gaps.get('high_priority_gaps') or 0),'gap_by_section':dict(gaps.get('by_section') or {}),'unique_sources':len(sources),'unique_domains':len(domains),'unique_evidence_urls':len(urls),'official_evidence':official,'corroborated_evidence':corroborated,'sections':sections}
def compare_metrics(before:Mapping[str,Any],after:Mapping[str,Any],before_data:Mapping[str,Any],after_data:Mapping[str,Any])->dict[str,Any]:
 before_fields=_field_map(before_data);after_fields=_field_map(after_data);new_fields=[];new_values=0
 for key,spec in after_fields.items():
  old=before_fields.get(key) or {};old_value=old.get('value');new_value=spec.get('value')
  if not has_value(old_value) and has_value(new_value):new_fields.append({'section':key[0],'entity_id':key[1],'field':key[2]})
  if isinstance(new_value,list):
   old_list=old_value if isinstance(old_value,list) else ([] if not has_value(old_value) else [old_value]);new_values+=max(0,len(new_value)-len(old_list))
 return {'definition':'Comparación de las mismas entidades, esquemas y reglas de suficiencia; no se han ocultado ni eliminado campos.','before':dict(before),'after':dict(after),'delta':{k:after.get(k,0)-before.get(k,0) for k in ('sources','evidence','relationships','traceable_fields','research_gaps','critical_gaps','unique_sources','unique_domains','official_evidence','corroborated_evidence','populated_fields')},'gap_reduction_pct':round((before.get('research_gaps',0)-after.get('research_gaps',0))*100/max(1,before.get('research_gaps',0)),2),'new_information':{'newly_populated_fields':len(new_fields),'new_values_added':new_values,'sample':new_fields[:100]}}
