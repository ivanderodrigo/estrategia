from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from v34.common import load_json, write_json
from v34.ecosystem_motion import build_ecosystem_motion
from v34.entity_intelligence import build_entities
from v34.intelligence_outputs import build_adaptive_queue, build_history, build_source_catalog, build_source_coverage
from v34.relationship_engine import build_relationships
from v310.build_intelligence import build as build_public_intelligence

OBSOLETE_DECISION_OUTPUTS = ('recommendations.json','recommendation_audit.json','business_intelligence_report.json','quality_report.json','metrics_before_after.json','last_run.json')


def _merged_source_expansion(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    source_expansion=load_json(root/'config/v34/source_expansion.json',{})
    audience_routes=load_json(root/'config/v34/audience_source_routes.json',{})
    relationship_playbook=load_json(root/'config/v34/relationship_source_playbook.json',{})
    additions=[load_json(root/p,{}) for p in ('config/v35/source_additions.json','config/v36/source_additions.json','config/v38/source_additions.json','config/v39/source_additions.json','config/v310/source_additions.json')]
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
    started=datetime.now(timezone.utc);source_expansion,audience_routes,playbook=_merged_source_expansion(root)
    entities,identity_audit=build_entities(root);relationships=build_relationships(root,entities);motion=build_ecosystem_motion(root,entities,relationships,audience_routes,playbook);coverage=build_source_coverage(root,entities,source_expansion);catalog=build_source_catalog(source_expansion);history=build_history(root);queue=build_adaptive_queue(entities,relationships,coverage)
    out34=root/'data/v34';out34.mkdir(parents=True,exist_ok=True)
    for name,obj in [('entities.json',entities),('identity_audit.json',identity_audit),('relationships.json',relationships),('ecosystem_motion_intelligence.json',motion),('source_coverage.json',coverage),('source_catalog.json',catalog),('historical_intelligence.json',history),('research_queue.json',queue)]:write_json(out34/name,obj)
    legacy_arch=out34/'architectures.json'
    if legacy_arch.exists():legacy_arch.unlink()
    removed=_remove_obsolete(root)
    external_raw=os.getenv('WESTCON_INPUTS_DIR','').strip();external=Path(external_raw).resolve() if external_raw else None
    public=build_public_intelligence(external);out=root/'data/v310';out.mkdir(parents=True,exist_ok=True);write_json(out/'intelligence.json',public)
    gaps=load_json(root/'data/v39/research_gaps.json',{}) or load_json(root/'data/v38/research_gaps.json',{}) or {};write_json(out/'research_gaps.json',{**gaps,'version':'3.10.0','note':'v3.10 hereda huecos públicos y añade ingesta de aportaciones/documentos.'})
    finished=datetime.now(timezone.utc);repo=public.get('meta',{}).get('repo_inputs',{}) or {}
    result={'version':'3.10.0','profile':profile,'status':'published','started_at':started.isoformat(),'finished_at':finished.isoformat(),'runtime_seconds':round((finished-started).total_seconds(),3),'foundation_rc':foundation_rc,'manufacturers':len(public.get('manufacturers',[])),'distributors':len(public.get('distributors',[])),'integrators':len(public.get('integrators',[])),'clients':len(public.get('clients_public',[]))+len(public.get('clients_private',[])),'clients_public':len(public.get('clients_public',[])),'clients_private':len(public.get('clients_private',[])),'trends':len(public.get('trends',[])),'architectures':len(public.get('architectures',[])),'source_count':len(public.get('source_catalog',[])),'research_gaps':gaps.get('total_gaps',0),'high_priority_research_gaps':gaps.get('high_priority_gaps',0),'traceable_fields':sum(1 for section in ('manufacturers','distributors','integrators','clients_public','clients_private','trends','architectures') for row in public.get(section,[]) for value in (row.get('fields') or {}).values() if value and value.get('evidence')),'repo_inputs':repo,'obsolete_decision_outputs_removed':removed}
    write_json(out/'last_run.json',result);return result
