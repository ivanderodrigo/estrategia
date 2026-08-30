from __future__ import annotations
import json,re
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from typing import Any,Mapping
ROOT=Path(__file__).resolve().parents[2];TODAY=datetime.now(timezone.utc)
SECTIONS=("manufacturers","integrators","distributors","clients_public","clients_private","trends","architectures")
# v3.14 separates decision-critical gaps from optional enrichment. Optional absence is not treated as a product defect.
CORE_TARGET_FIELDS={
 "manufacturers":{"integrators":110,"distributors":104,"competitors":96},
 "integrators":{"vendor_relations":112,"services":100,"specializations":98,"capabilities":98},
 "distributors":{"vendor_relations":114,"westcon_overlap":110,"competitor_vendor_overlap":106,"differential_capabilities":104},
 "clients_public":{"technology_signals":96,"opportunity_area":98,"procurement_stage":94},
 "clients_private":{"technology_signals":104,"hiring_signals":96,"westcon_fit":92,"opportunity_notes":88},
 "trends":{"trend_market_metrics":104,"market_players":100,"westcon_vendors":94,"iberia_context":94},
 "architectures":{"analyst_basis":96,"layers":94,"vendors":92},
}
OPTIONAL_FIELDS={
 "manufacturers":["analyst_signals","recent_signals"],"integrators":["verticals","public_cases","job_vendors","job_profiles"],
 "distributors":["revenue","market_position","services","specializations","capabilities","job_vendors","job_profiles"],
 "clients_public":["estimated_amount","westcon_fit"],"clients_private":["renewal_window"],
 "trends":["buyer_priorities","drivers","evolution","adjacent_market_metrics"],"architectures":["limits"]}
REVALIDATE_DAYS={"vendor_relations":180,"integrators":180,"distributors":180,"westcon_overlap":180,"competitor_vendor_overlap":180,"technology_signals":150,"hiring_signals":120,"default":365}
def norm(v:Any)->str:
 text=str(v or '').lower().translate(str.maketrans('áéíóúüñç','aeiouunc'));return re.sub(r'\s+',' ',text).strip()
def has_value(v:Any)->bool:return v not in (None,'',[],{}) and norm(v) not in {'en investigacion','investigacion','pendiente'}
def evidence_rows(field:Mapping[str,Any])->list[Mapping[str,Any]]:
 rows=list(field.get('evidence') or [])
 for item in field.get('items') or []:rows.extend(item.get('evidence') or [])
 return [x for x in rows if isinstance(x,Mapping)]
def parse_date(v:Any):
 raw=str(v or '').strip().replace('Z','+00:00')
 if not raw:return None
 for c in (raw,raw[:10]):
  try:
   d=datetime.fromisoformat(c);return d.replace(tzinfo=d.tzinfo or timezone.utc).astimezone(timezone.utc)
  except Exception:pass
 return None
def confidence(field:Mapping[str,Any])->float:
 try:
  v=float(field.get('confidence') or 0);return v/100 if v>1 else v
 except Exception:return 0.0
def entity_domain(name:str)->str|None:
 try:d=json.loads((ROOT/'config/source_universe.json').read_text(encoding='utf8'))
 except Exception:return None
 target=norm(name)
 for bucket in ('integrators','distributors'):
  for row in d.get(bucket,[]) or []:
   if norm(row.get('name'))==target and row.get('domain'):return str(row['domain'])
 return None
def queries(section:str,name:str,fid:str)->list[str]:
 dom=entity_domain(name);routes={
 'vendor_relations':'technology partners vendors portfolio linecard fabricantes','westcon_overlap':'portfolio vendors cybersecurity networking cloud',
 'competitor_vendor_overlap':'linecard Fortinet HPE Netskope SentinelOne Sophos Arista Infoblox Tufin competitors',
 'differential_capabilities':'services training financing marketplace logistics managed services professional services support',
 'services':'managed professional services support consulting implementation training','specializations':'certifications specializations competencies partner level',
 'capabilities':'SOC NOC MSP MSSP cloud cybersecurity networking observability automation','integrators':'partner locator reseller VAR MSP MSSP certified partner Spain Portugal',
 'distributors':'authorized distributor distribution VAD Spain Portugal','competitors':'competitors alternatives Gartner Peer Insights market 2026',
 'technology_signals':'technology cybersecurity cloud networking infrastructure digital transformation','hiring_signals':'careers jobs cybersecurity cloud network SOC infrastructure architect',
 'westcon_fit':'cybersecurity networking cloud technology partners architecture','opportunity_notes':'digital transformation cybersecurity cloud network investment project 2026',
 'opportunity_area':'licitacion expediente ICT cloud cybersecurity networking','procurement_stage':'licitacion expediente adjudicacion estado','trend_market_metrics':'market forecast CAGR 2026 Europe Iberia',
 'market_players':'market vendors competitors Gartner IDC Forrester 2026','westcon_vendors':'vendors market portfolio','iberia_context':'Spain Portugal Iberia market 2026',
 'analyst_basis':'Gartner Forrester IDC NIST reference architecture','layers':'reference architecture layers','vendors':'reference architecture vendors'}
 route=routes.get(fid,fid.replace('_',' '));q=[f'"{name}" {route}',f'"{name}" Spain Portugal {route}']
 if dom:q += [f'site:{dom} {route}',f'site:{dom} partners services cases careers certifications']
 out=[]
 for x in q:
  if x not in out:out.append(x)
 return out[:10]
def _applicable(section:str,row:Mapping[str,Any],fid:str)->bool:
 # Do not demand competitor overlap before any linecard is known: first resolve the linecard itself.
 if section=='distributors' and fid in {'westcon_overlap','competitor_vendor_overlap'}:
  return has_value(((row.get('fields') or {}).get('vendor_relations') or {}).get('value'))
 return True
def build_gaps(public:Mapping[str,Any])->dict[str,Any]:
 gaps=[];missing_counts=Counter();total_targets=Counter();populated_counts=Counter();optional_missing=Counter()
 for section in SECTIONS:
  rows=public.get(section,[]) or [];targets=CORE_TARGET_FIELDS.get(section,{})
  for row in rows:
   fields=row.get('fields') or {};name=str(row.get('name') or '')
   for fid in OPTIONAL_FIELDS.get(section,[]):
    if not has_value((fields.get(fid) or {}).get('value')):optional_missing[(section,fid)]+=1
   for fid,base in targets.items():
    if not _applicable(section,row,fid):continue
    total_targets[(section,fid)]+=1;fld=fields.get(fid) or {};val=fld.get('value');missing=not has_value(val);conf=confidence(fld);low=bool(not missing and conf<.60)
    dates=[parse_date(x.get('date')) for x in evidence_rows(fld)];dates=[x for x in dates if x];age=(TODAY-max(dates)).days if dates else None;stale=bool(age is not None and age>REVALIDATE_DAYS.get(fid,REVALIDATE_DAYS['default']))
    if not missing:populated_counts[(section,fid)]+=1
    if not (missing or low or stale):continue
    reason=[];priority=base
    if missing:reason.append('evidencia decisional ausente');priority+=16;missing_counts[(section,fid)]+=1
    if low:reason.append(f'confianza baja ({round(conf*100)}%)');priority+=8
    if stale:reason.append(f'evidencia envejecida ({age} días)');priority+=8
    gaps.append({'section':section,'entity':name,'entity_id':row.get('id'),'field':fid,'priority':min(135,int(priority)),'reason':'; '.join(reason),'confidence':round(conf,3) if fld else None,'age_days':age,'query_hints':queries(section,name,fid)})
 gaps.sort(key=lambda x:(-x['priority'],x['section'],norm(x['entity']),x['field']))
 coverage={}
 for (s,f),total in total_targets.items():
  pop=populated_counts[(s,f)];coverage.setdefault(s,{})[f]={'populated':pop,'total':total,'coverage_pct':round(pop*100/max(1,total),1),'missing':total-pop}
 return {'version':'3.14.0','generated_at':TODAY.isoformat(),'policy':'v3.14 separa gaps de decisión de enriquecimiento opcional. Solo la ausencia que afecta a una lectura de negocio genera un gap crítico; empleo, casos, verticales, renovaciones y otros extras siguen investigándose sin contaminar la UI con falsos pendientes.','total_gaps':len(gaps),'high_priority_gaps':sum(1 for x in gaps if x['priority']>=100),'by_section':{s:sum(1 for x in gaps if x['section']==s) for s in SECTIONS},'missing_by_field':{f'{s}.{f}':n for (s,f),n in missing_counts.most_common()},'optional_missing_by_field':{f'{s}.{f}':n for (s,f),n in optional_missing.most_common()},'coverage':coverage,'gaps':gaps}
