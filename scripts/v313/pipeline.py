from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from v34.common import load_json, write_json
from v34.ecosystem_motion import build_ecosystem_motion
from v34.entity_intelligence import build_entities
from v34.intelligence_outputs import build_adaptive_queue, build_history, build_source_catalog, build_source_coverage
from v34.relationship_engine import build_relationships
from v313.build_intelligence import build as build_public_intelligence
from v313.procurement_research import run as refresh_procurement
from v313.gap_engine import build_gaps

OBSOLETE_DECISION_OUTPUTS = (
    'recommendations.json','recommendation_audit.json','business_intelligence_report.json',
    'quality_report.json','metrics_before_after.json','last_run.json'
)


def _merged_source_expansion(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    source_expansion=load_json(root/'config/v34/source_expansion.json',{})
    audience_routes=load_json(root/'config/v34/audience_source_routes.json',{})
    relationship_playbook=load_json(root/'config/v34/relationship_source_playbook.json',{})
    additions=[load_json(root/p,{}) for p in (
        'config/v35/source_additions.json','config/v36/source_additions.json','config/v38/source_additions.json',
        'config/v39/source_additions.json','config/v313/source_additions.json'
    )]
    merged_sources={}
    all_sources=[*(source_expansion.get('sources') or []),*(audience_routes.get('sources') or []),*[s for block in additions for s in (block.get('sources') or [])]]
    for source in all_sources:
        sid=source.get('id') or source.get('source_id')
        if sid: merged_sources[str(sid)]={**source,'id':sid}
    return {**source_expansion,'sources':list(merged_sources.values()),'audience_routes':audience_routes.get('routes') or [],'audience_rules':audience_routes.get('rules') or []},audience_routes,relationship_playbook


def _remove_obsolete(root: Path) -> list[str]:
    removed=[];directory=root/'data/v34'
    for name in OBSOLETE_DECISION_OUTPUTS:
        p=directory/name
        if p.exists():p.unlink();removed.append(name)
    return removed


def run(root: Path, profile: str='daily', foundation_rc: int=0) -> dict[str, Any]:
    started=datetime.now(timezone.utc)
    source_expansion,audience_routes,playbook=_merged_source_expansion(root)
    entities,identity_audit=build_entities(root)
    relationships=build_relationships(root,entities)
    motion=build_ecosystem_motion(root,entities,relationships,audience_routes,playbook)
    coverage=build_source_coverage(root,entities,source_expansion)
    catalog=build_source_catalog(source_expansion)
    history=build_history(root)
    queue=build_adaptive_queue(entities,relationships,coverage)
    out34=root/'data/v34';out34.mkdir(parents=True,exist_ok=True)
    for name,obj in [('entities.json',entities),('identity_audit.json',identity_audit),('relationships.json',relationships),('ecosystem_motion_intelligence.json',motion),('source_coverage.json',coverage),('source_catalog.json',catalog),('historical_intelligence.json',history),('research_queue.json',queue)]:
        write_json(out34/name,obj)
    legacy_arch=out34/'architectures.json'
    if legacy_arch.exists():legacy_arch.unlink()
    removed=_remove_obsolete(root)

    procurement_diag={'live_notices':0,'cache_fallback':False}
    try:
        pprofile={'deep':'weekly','exhaustive':'monthly'}.get(profile,profile)
        live=refresh_procurement(pprofile,timeout=18)
        procurement_diag={'live_notices':len(live.get('notices') or []),'cache_fallback':bool(live.get('cache_fallback'))}
    except Exception as exc:
        procurement_diag={'live_notices':0,'cache_fallback':True,'error':f'{type(exc).__name__}: {exc}'}

    public=build_public_intelligence();out=root/'data/v313';out.mkdir(parents=True,exist_ok=True);write_json(out/'intelligence.json',public)
    gaps=build_gaps(public)
    graph=(public.get('meta') or {}).get('integrator_graph') or {}
    gaps['note']='v3.13 calcula la cola sobre el dataset actual; los perfiles de integrador/mayorista y grandes cuentas reciben rutas oficiales, recíprocas, empleo, casos y canal.'
    gaps['v313_priority_manufacturers']=graph.get('manufacturers_below_3_integrators',[])
    write_json(out/'research_gaps.json',gaps)
    finished=datetime.now(timezone.utc)
    meta=public.get('meta',{})
    result={
        'version':'3.13.0','profile':profile,'status':'published','started_at':started.isoformat(),'finished_at':finished.isoformat(),
        'runtime_seconds':round((finished-started).total_seconds(),3),'foundation_rc':foundation_rc,
        'manufacturers':len(public.get('manufacturers',[])),'distributors':len(public.get('distributors',[])),'integrators':len(public.get('integrators',[])),
        'clients':len(public.get('clients_public',[]))+len(public.get('clients_private',[])),'clients_public':len(public.get('clients_public',[])),'clients_private':len(public.get('clients_private',[])),
        'clients_private_es':meta.get('private_account_universe',{}).get('ibex35',0),'clients_private_pt':meta.get('private_account_universe',{}).get('psi',0),
        'trends':len(public.get('trends',[])),'architectures':len(public.get('architectures',[])),'source_count':len(public.get('source_catalog',[])),
        'research_gaps':gaps.get('total_gaps',0),'high_priority_research_gaps':gaps.get('high_priority_gaps',0),'gap_by_section':gaps.get('by_section',{}),
        'traceable_fields':sum(1 for section in ('manufacturers','distributors','integrators','clients_public','clients_private','trends','architectures') for row in public.get(section,[]) for value in (row.get('fields') or {}).values() if value and value.get('evidence')),
        'distributor_validation':meta.get('distributor_validation',{}),'portfolio_fit_cleanup':meta.get('portfolio_fit_cleanup',{}),
        'public_procurement':meta.get('public_procurement',{}),'integrator_graph':graph,'procurement_refresh':procurement_diag,
        'obsolete_decision_outputs_removed':removed
    }
    write_json(out/'last_run.json',result);return result
