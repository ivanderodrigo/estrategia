from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

from v31.atomic_publish import atomic_write_json
from .decision_engine import build_briefing, build_decisions
from .direct_sources import run_direct_sources
from .event_intelligence import build_candidate_event, cluster_events
from .knowledge_graph import build_graph
from .market_intelligence import build_competitive_pressure, build_portfolio_intelligence, build_whitespace_candidates
from .source_policy import domain_index, seeded_entities, source_authority, source_for_url


def _load(path:Path, default):
    try:return json.loads(path.read_text(encoding="utf-8"))
    except Exception:return default


def _westcon(root:Path):
    return {str(x).casefold() for x in _load(root/"config/v31/westcon_vendor_scope.json",{}).get("vendors",[])}

def _dedupe_direct_rows(rows):
    out=[];seen=set()
    for r in rows:
        key=(str(r.get("source_id") or r.get("source") or "").casefold(),str(r.get("entity_name") or "").casefold(),str(r.get("url") or "").strip(),str(r.get("title") or "").casefold().strip())
        if key in seen:continue
        seen.add(key);out.append(r)
    return out

def run_pipeline(root:Path, registry:list[dict], policy:Mapping[str,Any], direct_cfg:Mapping[str,Any], *, profile:str, runtime_seconds:int) -> Dict[str,Any]:
    outdir=root/"data/v32";outdir.mkdir(parents=True,exist_ok=True);state=root/".v32_state";state.mkdir(exist_ok=True)
    entities=seeded_entities(registry); entity_types={str(e.get("name")).casefold():str(e.get("entity_type")) for e in entities}
    v31=_load(root/"data/v31/discovery_signals.json",{"signals":[]}); news=[x for x in v31.get("signals",[]) if isinstance(x,dict)]
    timeout=int((policy.get("direct_api_timeout_seconds") or {}).get(profile,6)); cap=int((policy.get("generic_feed_source_cap") or {}).get(profile,18))
    direct_rows,direct_stats=run_direct_sources(registry,entities,direct_cfg,profile=profile,timeout=timeout,source_cap=cap,state_dir=state)
    direct_raw_count=len(direct_rows);direct_rows=_dedupe_direct_rows(direct_rows);direct_deduped=direct_raw_count-len(direct_rows)
    atomic_write_json(outdir/"direct_signals.json",{"meta":{"generated_at":datetime.now(timezone.utc).isoformat(),"profile":profile,"rows":len(direct_rows),"raw_rows":direct_raw_count,"deduplicated_rows":direct_deduped},"signals":direct_rows})
    domains=domain_index(registry); westcon=_westcon(root); candidates=[]
    name_index={}
    for src0 in registry:
        for key in (str(src0.get("name") or ""),str(src0.get("id") or "")):
            if key.strip(): name_index[key.casefold().strip()]=src0
    for r0 in news+direct_rows:
        r=dict(r0); src=source_for_url(str(r.get("url") or ""),domains)
        if not src:
            sname=str(r.get("source") or r.get("source_name") or "").casefold().strip()
            src=name_index.get(sname)
            if not src and sname:
                src=next((v for k,v in name_index.items() if len(k)>4 and (k in sname or sname in k)),None)
        if src:
            r.setdefault("source_id",src.get("id"));r.setdefault("source_category",src.get("category"));r.setdefault("source_authority",src.get("authority"))
        authority=float(r.get("source_authority") or source_authority(src,.58))
        candidates.append(build_candidate_event(r,source_authority=authority,westcon_vendors=westcon,entity_types=entity_types,direct=bool(r.get("direct_evidence"))))
    clustered=cluster_events(candidates)
    unclassified=[e for e in clustered if str(e.get("event_type") or "unknown")=="unknown"]
    events=[e for e in clustered if str(e.get("event_type") or "unknown")!="unknown"]
    atomic_write_json(outdir/"unclassified_candidates.json",{
        "meta":{"generated_at":datetime.now(timezone.utc).isoformat(),"count":len(unclassified)},
        "candidates":unclassified[:2000]
    })
    # Feed back event quality into adaptive source learning. A source that merely returns rows is not
    # rewarded as much as one that repeatedly yields high-materiality, high-confidence events.
    learning_path=state/"source_learning.json"
    try: learning=_load(learning_path,{})
    except Exception: learning={}
    by_source={}
    for e in events:
        sid=str(e.get("source_id") or "")
        if not sid: continue
        q=by_source.setdefault(sid,{"event_count":0,"high_materiality":0,"materiality_sum":0.0,"confidence_sum":0.0})
        q["event_count"]+=1; q["high_materiality"]+=int(float(e.get("materiality") or 0)>=.70); q["materiality_sum"]+=float(e.get("materiality") or 0); q["confidence_sum"]+=float(e.get("confidence") or 0)
    for sid,q in by_source.items():
        st=learning.setdefault(sid,{"attempts":0,"successes":0,"rows":0}); old_n=int(st.get("event_count",0)); new_n=q["event_count"]; total=old_n+new_n
        old_avg=float(st.get("avg_materiality",.5)); old_conf=float(st.get("avg_confidence",.5))
        st["avg_materiality"]=round((old_avg*old_n+q["materiality_sum"])/max(1,total),4); st["avg_confidence"]=round((old_conf*old_n+q["confidence_sum"])/max(1,total),4); st["event_count"]=total; st["high_materiality"]=int(st.get("high_materiality",0))+q["high_materiality"]
    atomic_write_json(learning_path,learning); atomic_write_json(outdir/"source_learning.json",learning)
    # Hard dashboard materiality filter but retain low-value events in event_store for research history.
    event_store={"meta":{"generated_at":datetime.now(timezone.utc).isoformat(),"profile":profile,"candidate_articles":len(candidates),"clustered_events":len(clustered),"classified_events":len(events),"unclassified_events":len(unclassified),"direct_rows":len(direct_rows),"event_type_counts":dict(Counter(e.get("event_type") for e in events)),"scope_counts":dict(Counter(e.get("market_scope") for e in events))},"events":events[:4000]}
    atomic_write_json(outdir/"events.json",event_store)
    graph=build_graph(events);atomic_write_json(outdir/"knowledge_graph.json",graph)
    decisions=build_decisions(events,policy);atomic_write_json(outdir/"decisions.json",decisions)
    briefing=build_briefing(events,decisions);atomic_write_json(outdir/"briefing.json",briefing)
    competitive=build_competitive_pressure(events);atomic_write_json(outdir/"competitive_pressure.json",competitive)
    portfolio=build_portfolio_intelligence(events,westcon);atomic_write_json(outdir/"portfolio_intelligence.json",portfolio)
    whitespace=build_whitespace_candidates(events,westcon);atomic_write_json(outdir/"whitespace_candidates.json",whitespace)
    # Decision-quality dashboard: volume alone is not intelligence. Track evidence strength,
    # source concentration and actionability so regressions are visible without manual inspection.
    ds=list(decisions.get("decisions") or [])
    source_counts=Counter()
    for d in ds:
        for src_name in (d.get("sources") or []): source_counts[str(src_name)]+=1
    top_source_count=source_counts.most_common(1)[0][1] if source_counts else 0
    quality_report={
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "events":len(events),"decisions":len(ds),
        "decision_rate":round(len(ds)/max(1,len(events)),3),
        "evidence_grade_counts":dict(Counter(str(d.get("evidence_grade") or "?") for d in ds)),
        "impact_counts":dict(Counter(str(d.get("impact") or "?") for d in ds)),
        "priority_counts":dict(Counter(str(d.get("priority") or "?") for d in ds)),
        "top_sources":source_counts.most_common(15),
        "top_source_share":round(top_source_count/max(1,len(ds)),3),
        "competitive_pressure":competitive.get("meta") or {},
        "whitespace_shortlist":len(whitespace.get("shortlist") or []),
    }
    atomic_write_json(outdir/"quality_report.json",quality_report)
    flat_health={}
    for sid,st in direct_stats.items():
        if sid=="generic_feeds":
            flat_health[sid]={k:v for k,v in st.items() if k!="per_source"}
            for fsid,fst in (st.get("per_source") or {}).items():
                flat_health[f"feed:{fsid}"]=fst
        else:
            flat_health[sid]=st
    source_health={"meta":{"generated_at":datetime.now(timezone.utc).isoformat(),"registered_sources":len(registry),"direct_source_rows":len(direct_rows),"direct_raw_rows":direct_raw_count,"direct_deduplicated_rows":direct_deduped},"direct_connectors":direct_stats,"sources":flat_health}
    atomic_write_json(outdir/"source_health.json",source_health)
    # Full 151-source operating map: every source is either direct API/feed capable, already direct-successful,
    # scheduled for adaptive feed probing, or retained as discovery fallback. This makes source coverage explicit.
    connector_cfg={str(x.get("source_id")):x for x in (direct_cfg.get("connectors") or []) if x.get("source_id")}
    direct_source_ids={sid for sid,x in connector_cfg.items() if x.get("enabled",True)}
    feed_per=((direct_stats.get("generic_feeds") or {}).get("per_source") or {})
    coverage=[]
    for src in registry:
        sid=str(src.get("id")); mode="discovery_fallback"
        if sid in connector_cfg and not connector_cfg[sid].get("enabled",True): mode="token_or_policy_gated"
        elif sid in direct_source_ids: mode="direct_connector"
        if sid in feed_per:
            mode="direct_feed" if (feed_per[sid].get("feed_rows") or 0)>0 else "direct_feed_probe"
        coverage.append({"source_id":sid,"name":src.get("name"),"category":src.get("category"),"authority":src.get("authority"),"mode":mode,"domains":src.get("domains") or [],"feed_probe":feed_per.get(sid)})
    atomic_write_json(outdir/"source_coverage.json",{"meta":{"generated_at":datetime.now(timezone.utc).isoformat(),"registered":len(coverage),"direct_connector":sum(x["mode"]=="direct_connector" for x in coverage),"direct_feed":sum(x["mode"]=="direct_feed" for x in coverage),"direct_feed_probe":sum(x["mode"]=="direct_feed_probe" for x in coverage)},"sources":coverage})
    # Priority queue: high relevance/uncertainty, no direct corroboration, Iberia first.
    priorities=[]
    for e in events:
        uncertainty=1-float(e.get("confidence") or 0); direct_gap=0 if e.get("direct_evidence") else .18; ib=.18 if e.get("market_scope") in {"ES","PT","IBERIA"} else 0
        p=round(.42*float(e.get("westcon_relevance") or 0)+.25*float(e.get("materiality") or 0)+.15*uncertainty+direct_gap+ib,3)
        if p>=.55:priorities.append({"event_id":e.get("event_id"),"entity_name":e.get("entity_name"),"event_type":e.get("event_type"),"priority_score":p,"research_goal":"Buscar fuente primaria, corroboración independiente, relación concreta y evidencia Iberia."})
    priorities.sort(key=lambda x:x["priority_score"],reverse=True);atomic_write_json(outdir/"research_priorities.json",{"meta":{"generated_at":datetime.now(timezone.utc).isoformat(),"count":len(priorities)},"priorities":priorities[:500]})
    return {"events":len(events),"unclassified":len(unclassified),"candidates":len(candidates),"deduplicated":max(0,len(candidates)-len(clustered)),"decisions":len(decisions.get("decisions",[])),"direct_rows":len(direct_rows),"direct_raw_rows":direct_raw_count,"direct_deduplicated_rows":direct_deduped,"nodes":len(graph.get("nodes",[])),"edges":len(graph.get("edges",[])),"direct_stats":direct_stats,"briefing":briefing,"competitive_entities":len(competitive.get("entities",[])),"competitive_high":int((competitive.get("meta") or {}).get("high_pressure") or 0),"competitive_medium":int((competitive.get("meta") or {}).get("medium_pressure") or 0),"whitespace_candidates":len(whitespace.get("candidates",[])),"whitespace_shortlist":len(whitespace.get("shortlist",[])),"portfolio_vendors":len(portfolio.get("vendors",[])),"event_type_counts":event_store["meta"].get("event_type_counts",{}),"quality_report":quality_report}
