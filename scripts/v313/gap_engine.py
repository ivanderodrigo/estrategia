from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
TODAY = datetime.now(timezone.utc)
SECTIONS = ("manufacturers","integrators","distributors","clients_public","clients_private","trends","architectures")

TARGET_FIELDS = {
    "manufacturers": {"integrators":110,"distributors":102,"competitors":82,"analyst_signals":76,"recent_signals":72},
    "integrators": {"vendor_relations":110,"services":100,"specializations":98,"capabilities":98,"verticals":90,"public_cases":88,"job_vendors":78,"job_profiles":76},
    "distributors": {"vendor_relations":110,"westcon_overlap":104,"services":98,"specializations":94,"capabilities":94,"market_position":84,"job_vendors":72,"job_profiles":70},
    "clients_public": {"estimated_amount":86,"technology_signals":92,"westcon_fit":72,"opportunity_area":96,"procurement_stage":92},
    "clients_private": {"technology_signals":104,"hiring_signals":100,"westcon_fit":88,"opportunity_notes":86,"renewal_window":60},
    "trends": {"trend_market_metrics":104,"market_players":100,"westcon_vendors":94,"iberia_context":94,"buyer_priorities":84,"drivers":80,"evolution":78,"adjacent_market_metrics":62},
    "architectures": {"analyst_basis":96,"layers":94,"vendors":92,"limits":72},
}

REVALIDATE_DAYS={"vendor_relations":180,"integrators":180,"distributors":180,"westcon_overlap":180,"technology_signals":150,"hiring_signals":120,"recent_signals":90,"estimated_amount":180,"procurement_stage":120,"market_position":365,"default":365}

def norm(v:Any)->str:
    text=str(v or '').lower().translate(str.maketrans('áéíóúüñç','aeiouunc'))
    return re.sub(r'\s+',' ',text).strip()

def has_value(v:Any)->bool:
    return v not in (None,'',[],{}) and norm(v) not in {'en investigacion','investigacion','pendiente'}

def evidence_rows(field:Mapping[str,Any])->list[Mapping[str,Any]]:
    rows=list(field.get('evidence') or [])
    for item in field.get('items') or []: rows.extend(item.get('evidence') or [])
    return [x for x in rows if isinstance(x,Mapping)]

def parse_date(v:Any):
    raw=str(v or '').strip().replace('Z','+00:00')
    if not raw:return None
    for c in (raw,raw[:10]):
        try:
            d=datetime.fromisoformat(c); return d.replace(tzinfo=d.tzinfo or timezone.utc).astimezone(timezone.utc)
        except Exception: pass
    return None

def confidence(field:Mapping[str,Any])->float:
    try:
        v=float(field.get('confidence') or 0); return v/100 if v>1 else v
    except Exception:return 0.0

def entity_domain(name:str)->str|None:
    try:d=json.loads((ROOT/'config/source_universe.json').read_text(encoding='utf8'))
    except Exception:return None
    target=norm(name)
    for bucket in ('integrators','distributors'):
        for row in d.get(bucket,[]) or []:
            if norm(row.get('name'))==target and row.get('domain'):return str(row['domain'])
    return None

def queries(section:str,name:str,fid:str,vendors:list[str])->list[str]:
    q=[]; dom=entity_domain(name)
    if section=='manufacturers':
        routes={
          'integrators':['partner locator integrator reseller VAR MSP MSSP certified partner','partner awards systems integrator service provider Spain Portugal'],
          'distributors':['authorized distributor distribution VAD Spain Portugal','Iberia mayorista distribuidor official'],
          'competitors':['competitors alternatives market landscape 2026','Gartner Forrester IDC market competitors 2026'],
          'analyst_signals':['Gartner Forrester IDC public research 2026','market share forecast 2026'],
          'recent_signals':['2026 partner product launch customer case Spain Portugal','press release Iberia 2026'],
        }
        q += [f'"{name}" {x}' for x in routes.get(fid,[])]
    elif section in {'integrators','distributors'}:
        route={
          'vendor_relations':'technology partners alliances vendors portfolio linecard fabricantes',
          'westcon_overlap':'vendors portfolio linecard cybersecurity networking cloud',
          'services':'managed professional services support consulting implementation training marketplace',
          'capabilities':'SOC NOC MSP MSSP cloud cybersecurity networking observability automation',
          'specializations':'certifications specializations competencies accreditations partner level',
          'verticals':'industries sectors customers finance public healthcare retail industrial energy',
          'public_cases':'customer case study success story reference Spain Portugal',
          'job_profiles':'careers jobs vacancies architect engineer consultant SOC cloud security network',
          'job_vendors':'careers jobs Cisco Check Point Palo Alto AWS Microsoft CrowdStrike Extreme F5',
          'market_position':'ranking revenue facturacion ingresos 2025 2026 distributor mayorista',
        }.get(fid,fid.replace('_',' '))
        q += [f'"{name}" {route}',f'"{name}" Spain Portugal {route}']
        if dom:
            q += [f'site:{dom} {route}',f'site:{dom} partners services cases careers certifications']
    elif section=='clients_private':
        route={
          'technology_signals':'technology cybersecurity cloud networking infrastructure digital transformation case study vendor',
          'hiring_signals':'careers jobs cybersecurity cloud network SOC infrastructure architect engineer',
          'westcon_fit':'cybersecurity networking cloud technology partners architecture',
          'opportunity_notes':'digital transformation cybersecurity cloud network investment project 2026',
          'renewal_window':'contract renewal tender procurement technology managed service expiration',
        }.get(fid,fid.replace('_',' '))
        q += [f'"{name}" {route}',f'"{name}" Spain Portugal {route}']
    elif section=='clients_public':
        q += [f'"{name}" expediente licitacion {fid.replace("_"," ")} tecnologia',f'"{name}" TED PLACSP BASE procurement ICT']
    elif section=='trends':
        q += [f'"{name}" {fid.replace("_"," ")} 2026 Europe Spain Portugal Gartner IDC Forrester',f'"{name}" market forecast CAGR vendors 2026']
    elif section=='architectures': q += [f'"{name}" reference architecture NIST Gartner Forrester vendor validated design 2026']
    out=[];seen=set()
    for x in q:
        if x and x not in seen:seen.add(x);out.append(x)
    return out[:10]

def build_gaps(public:Mapping[str,Any])->dict[str,Any]:
    vendors=[x.get('name') for x in public.get('manufacturers',[]) if x.get('name')]
    gaps=[]; missing_counts=Counter(); total_targets=Counter(); populated_counts=Counter()
    for section in SECTIONS:
        targets=TARGET_FIELDS.get(section,{})
        rows=public.get(section,[]) or []
        for fid in targets: total_targets[(section,fid)] = len(rows)
        for row in rows:
            name=str(row.get('name') or ''); fields=row.get('fields') or {}
            for fid,base in targets.items():
                fld=fields.get(fid) or {}; val=fld.get('value'); missing=not has_value(val)
                conf=confidence(fld); low=bool(not missing and conf<.60)
                dates=[parse_date(x.get('date')) for x in evidence_rows(fld)]; dates=[x for x in dates if x]
                age=(TODAY-max(dates)).days if dates else None
                stale=bool(age is not None and age>REVALIDATE_DAYS.get(fid,REVALIDATE_DAYS['default']))
                if not missing: populated_counts[(section,fid)]+=1
                if not (missing or low or stale):continue
                reason=[];priority=base
                if missing:reason.append('campo vacío');priority+=16;missing_counts[(section,fid)]+=1
                if low:reason.append(f'confianza baja ({round(conf*100)}%)');priority+=8
                if stale:reason.append(f'evidencia envejecida ({age} días)');priority+=8
                if fid in {'integrators','distributors','vendor_relations','technology_signals','westcon_overlap'}:priority+=10
                gaps.append({'section':section,'entity':name,'entity_id':row.get('id'),'field':fid,'priority':min(135,int(priority)),'reason':'; '.join(reason),'confidence':round(conf,3) if fld else None,'age_days':age,'query_hints':queries(section,name,fid,vendors)})
    gaps.sort(key=lambda x:(-x['priority'],x['section'],norm(x['entity']),x['field']))
    by_section={s:sum(1 for x in gaps if x['section']==s) for s in SECTIONS}
    coverage={}
    for (section,fid),total in total_targets.items():
        populated=populated_counts[(section,fid)]
        coverage.setdefault(section,{})[fid]={'populated':populated,'total':total,'coverage_pct':round(populated*100/max(1,total),1),'missing':total-populated}
    missing_by_field={f'{s}.{f}':n for (s,f),n in sorted(missing_counts.items(),key=lambda x:-x[1])}
    return {'version':'3.13.0','generated_at':TODAY.isoformat(),'policy':'Cola dinámica v3.13: cada hueco real del dataset publicado genera rutas de investigación primaria/recíproca; no se heredan contadores de versiones anteriores.','total_gaps':len(gaps),'high_priority_gaps':sum(1 for x in gaps if x['priority']>=100),'by_section':by_section,'missing_by_field':missing_by_field,'coverage':coverage,'gaps':gaps}
