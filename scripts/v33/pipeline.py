from __future__ import annotations
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime,timezone,timedelta
from .common import load_json,write_json,iso_now,norm,f,clamp,parse_date
from .targeted_research import run_targeted_research
from .ecosystem_engine import build_profiles,_entity_rows
from .matrix_engine import build_relationship_matrix,build_distributor_matrix,build_vendor_pairs
from .architecture_engine import build_architectures

GRADE_RANK={"A":4,"B":3,"C":2,"D":1,None:0}


def _priority_pairs(root:Path):
    rows=[];seen=set()
    w=load_json(root/"data/v32/whitespace_candidates.json",{})
    for key in ("shortlist","candidates","research"):
        for x in w.get(key,[]) or []:
            if not x.get("integrator") or not x.get("vendor"):continue
            k=(norm(x.get("integrator")),norm(x.get("vendor")))
            if k in seen:continue
            seen.add(k);rows.append(x)
    old=load_json(root/"data/v33/integrator_vendor_matrix.json",{})
    for x in old.get("rows",[]) or []:
        if x.get("status") not in {"WHITESPACE_RESEARCH_PRIORITY","PROBABLE_RELATION"}:continue
        k=(norm(x.get("integrator")),norm(x.get("vendor")))
        if k in seen:continue
        seen.add(k);rows.append({"integrator":x.get("integrator"),"vendor":x.get("vendor"),"priority_score":x.get("priority_score") or round(f(x.get("relationship_strength"))*100)})
    rows.sort(key=lambda x:f(x.get("research_priority_score") or x.get("priority_score") or x.get("whitespace_score")),reverse=True)
    return rows


def _evidence_key(x):
    return "|".join([norm(x.get("name")),norm(x.get("field")),norm(x.get("vendor")),norm(x.get("title")),norm(x.get("source"))])


def _merge_targeted(previous_doc,current,profile):
    """Accumulate targeted evidence so a short daily run never erases a deeper weekly run."""
    now=iso_now();merged={}
    for x in previous_doc.get("evidence",[]) or []:
        if not x.get("title"):continue
        y=dict(x);y.setdefault("first_seen_at",x.get("observed_at") or now);y.setdefault("last_seen_at",x.get("observed_at") or y.get("first_seen_at"));y.setdefault("seen_count",1)
        merged[_evidence_key(y)]=y
    new_unique=0
    for x in current:
        k=_evidence_key(x);old=merged.get(k)
        if old:
            y=dict(old);y["last_seen_at"]=x.get("observed_at") or now;y["seen_count"]=int(y.get("seen_count") or 1)+1
            if f(x.get("confidence"))>f(y.get("confidence")):y.update({k2:v for k2,v in x.items() if v not in (None,"",[],{})})
            if GRADE_RANK.get(x.get("source_grade"),0)>GRADE_RANK.get(y.get("source_grade"),0):y["source_grade"]=x.get("source_grade")
            y["last_seen_profile"]=profile;merged[k]=y
        else:
            y=dict(x);y["first_seen_at"]=x.get("observed_at") or now;y["last_seen_at"]=x.get("observed_at") or now;y["seen_count"]=1;y["last_seen_profile"]=profile;merged[k]=y;new_unique+=1
    # Keep a long but finite evidence horizon. Rows without a reliable date are retained.
    cutoff=datetime.now(timezone.utc)-timedelta(days=1095);kept=[]
    for x in merged.values():
        d=parse_date(x.get("published_at"))
        if d and d<cutoff:continue
        kept.append(x)
    kept.sort(key=lambda x:(x.get("last_seen_at") or x.get("observed_at") or ""),reverse=True)
    return kept[:6000],new_unique


def _coverage_report(profiles):
    fields={
      "distributor":["vendors","technology_focus","value_added","managed_services","channel_moves"],
      "integrator":["vendors","certifications","technology_focus","verticals","customer_cases","managed_services"]
    }
    report={"generated_at":iso_now(),"summary":{},"by_type":{},"by_tier":{}}
    for et in ("distributor","integrator"):
        rows=[x for x in profiles if x.get("entity_type")==et];fc={}
        for field in fields[et]:
            n=0
            for x in rows:
                val=x.get(field)
                if field=="certifications" and not val:val=x.get("certification_signals")
                if field=="customer_cases" and not val:val=x.get("customer_case_examples")
                if field=="channel_moves":ok=f(val)>0
                else:ok=val not in (None,"",[],{},0)
                n+=1 if ok else 0
            fc[field]={"covered":n,"total":len(rows),"coverage_pct":round(100*n/max(1,len(rows)),1)}
        avg=round(sum(f(x.get("coverage_score")) for x in rows)/max(1,len(rows)),1);low=sum(1 for x in rows if f(x.get("coverage_score"))<50)
        report["by_type"][et]={"entities":len(rows),"average_profile_coverage":avg,"profiles_below_50":low,"fields":fc}
    for tier in ("T1","T2","T3"):
        rows=[x for x in profiles if x.get("entity_tier")==tier]
        report["by_tier"][tier]={
            "entities":len(rows),"average_coverage":round(sum(f(x.get("coverage_score")) for x in rows)/max(1,len(rows)),1) if rows else 0,
            "average_target":round(sum(f(x.get("coverage_target")) for x in rows)/max(1,len(rows)),1) if rows else 0,
            "average_gap":round(sum(f(x.get("coverage_gap")) for x in rows)/max(1,len(rows)),1) if rows else 0,
            "at_target":sum(1 for x in rows if f(x.get("coverage_gap"))<=0)
        }
    avg_cov=round(sum(f(x.get("coverage_score")) for x in profiles)/max(1,len(profiles)),1)
    avg_target=round(sum(f(x.get("coverage_target")) for x in profiles)/max(1,len(profiles)),1)
    avg_debt=round(sum(f(x.get("coverage_gap")) for x in profiles)/max(1,len(profiles)),1)
    report["summary"]={"profiles":len(profiles),"average_coverage":avg_cov,"average_target":avg_target,"difference_between_averages":round(avg_target-avg_cov,1),"average_knowledge_debt":avg_debt,"average_gap":avg_debt,"knowledge_debt_explanation":"La deuda media se calcula entidad por entidad como max(0, objetivo-cobertura); por eso puede diferir de objetivo medio menos cobertura media.","grade_distribution":dict(Counter(x.get("evidence_grade") for x in profiles)),"tier_distribution":dict(Counter(x.get("entity_tier") for x in profiles))}
    return report


def _research_plan(profiles,limit=100):
    rows=[];tw={"T1":1.35,"T2":1.0,"T3":.58}
    for p in profiles:
        gaps=p.get("research_gaps") or [];cov_gap=f(p.get("coverage_gap"))/100
        if not gaps and cov_gap<=0:continue
        rel=f(p.get("westcon_relevance"))/100;conf=f(p.get("confidence"));business=f(p.get("activation_priority") or p.get("competitive_response_priority"))/100;tier=p.get("entity_tier") or "T2"
        priority=clamp(tw.get(tier,1)*(.43*cov_gap+.20*rel+.18*business+.10*(1-conf)+.09*(1-f(p.get("evidence_count"))/12)))
        rows.append({"entity":p.get("name"),"entity_type":p.get("entity_type"),"entity_tier":tier,"priority_score":round(priority,3),"coverage_score":p.get("coverage_score"),"coverage_target":p.get("coverage_target"),"coverage_gap":p.get("coverage_gap"),"westcon_relevance":p.get("westcon_relevance"),"gaps":gaps,"next_action":"Investigar primero: "+", ".join(gaps[:3])+"."})
    rows.sort(key=lambda x:x["priority_score"],reverse=True)
    return {"meta":{"generated_at":iso_now(),"candidates":len(rows)},"priorities":rows[:limit]}


def _enrich_profile_relationship_counts(profiles,imatrix,dmatrix):
    im=defaultdict(list);dm=defaultdict(list)
    for x in imatrix.get("rows",[]) or []:im[norm(x.get("integrator"))].append(x)
    for x in dmatrix.get("rows",[]) or []:dm[norm(x.get("distributor"))].append(x)
    for p in profiles:
        rows=im[norm(p.get("name"))] if p.get("entity_type")=="integrator" else dm[norm(p.get("name"))]
        if p.get("entity_type")=="integrator":
            p["relationship_confirmed_count"]=sum(1 for x in rows if x.get("status")=="CONFIRMED_RELATION")
            p["relationship_probable_count"]=sum(1 for x in rows if x.get("status")=="PROBABLE_RELATION")
            p["relationship_research_count"]=sum(1 for x in rows if x.get("status")=="WHITESPACE_RESEARCH_PRIORITY")
        else:
            p["distribution_confirmed_count"]=sum(1 for x in rows if x.get("status")=="CONFIRMED_DISTRIBUTION")
            p["distribution_probable_count"]=sum(1 for x in rows if x.get("status")=="PROBABLE_PUBLIC_RELATION")
        p["relationship_intensity_max"]=max([f(x.get("relationship_intensity")) for x in rows] or [0])
    return profiles


def _verification_queue(imatrix,dmatrix,limit=120):
    q=[]
    for x in imatrix.get("rows",[]) or []:
        if x.get("status") not in {"PROBABLE_RELATION","WHITESPACE_RESEARCH_PRIORITY"}:continue
        q.append({"entity_type":"integrator","entity":x.get("integrator"),"vendor":x.get("vendor"),"status":x.get("status"),"priority_score":x.get("priority_score"),"relationship_intensity":x.get("relationship_intensity"),"evidence_grade":x.get("evidence_grade"),"evidence_count":x.get("evidence_count"),"next_research":x.get("next_research")})
    for x in dmatrix.get("rows",[]) or []:
        if x.get("status")!="PROBABLE_PUBLIC_RELATION":continue
        q.append({"entity_type":"distributor","entity":x.get("distributor"),"vendor":x.get("vendor"),"status":x.get("status"),"priority_score":x.get("priority_score"),"relationship_intensity":x.get("relationship_intensity"),"evidence_grade":x.get("evidence_grade"),"evidence_count":x.get("evidence_count"),"next_research":x.get("next_research")})
    q.sort(key=lambda x:(f(x.get("priority_score")),100-f(x.get("relationship_intensity"))),reverse=True)
    return {"meta":{"generated_at":iso_now(),"candidates":len(q)},"queue":q[:limit]}



def _relationship_movement(previous,current,kind):
    if kind=="integrator":
        keyfn=lambda x:(norm(x.get("integrator")),norm(x.get("vendor")))
    else:
        keyfn=lambda x:(norm(x.get("distributor")),norm(x.get("vendor")))
    old={keyfn(x):x for x in (previous.get("rows") or []) if all(keyfn(x))}
    new={keyfn(x):x for x in (current.get("rows") or []) if all(keyfn(x))}
    transitions=Counter();changes=[];resolved=0
    for k,row in new.items():
        if k not in old:continue
        a=old[k].get("status");b=row.get("status")
        transitions[f"{a}→{b}"]+=1
        if a!=b:
            item={"entity":row.get("integrator") or row.get("distributor"),"vendor":row.get("vendor"),"from":a,"to":b,"priority_score":row.get("priority_score"),"relationship_intensity":row.get("relationship_intensity")}
            changes.append(item)
            if b in {"CONFIRMED_RELATION","CONFIRMED_DISTRIBUTION"} and a not in {"CONFIRMED_RELATION","CONFIRMED_DISTRIBUTION"}:resolved+=1
    changes.sort(key=lambda x:f(x.get("priority_score")),reverse=True)
    return {"comparable_pairs":len(set(old)&set(new)),"new_pairs":len(set(new)-set(old)),"removed_pairs":len(set(old)-set(new)),"changed_pairs":len(changes),"uncertainty_resolved":resolved,"transitions":dict(transitions),"changes":changes[:120]}

def run(root:Path,profile:str,policy:dict,runtime_seconds:int):
    entity=load_json(root/"data/v31/entity_intelligence.json",{});raw_entities=[]
    for kind,etype in (("distributors","distributor"),("integrators","integrator")):
        for x in entity.get(kind,[]) or []:raw_entities.append({**x,"entity_type":etype})
    canonical_entities,dedupe_report=_entity_rows(entity,with_report=True)
    scope=load_json(root/"config/v31/westcon_vendor_scope.json",{});vendors=scope.get("vendors") or scope.get("active_vendors") or []
    if vendors and isinstance(vendors[0],dict):vendors=[x.get("name") for x in vendors if x.get("name")]
    previous_profiles=load_json(root/"data/v33/ecosystem_profiles.json",{});previous_coverage=load_json(root/"data/v33/coverage_report.json",{})
    previous_imatrix=load_json(root/"data/v33/integrator_vendor_matrix.json",{});previous_dmatrix=load_json(root/"data/v33/distributor_vendor_matrix.json",{})
    pairs_to_verify=_priority_pairs(root);research_budget=max(18,int(runtime_seconds*.66))
    current_targeted,stats=run_targeted_research(canonical_entities,vendors,profile,policy,research_budget,previous_profiles=previous_profiles,priority_pairs=pairs_to_verify)
    previous_targeted=load_json(root/"data/v33/targeted_evidence.json",{});targeted,new_unique=_merge_targeted(previous_targeted,current_targeted,profile)
    profiles,westcon_vendors=build_profiles(root,targeted,entity_rows=canonical_entities)
    thresholds=policy.get("relationship_thresholds",{});imatrix=build_relationship_matrix(profiles,westcon_vendors,thresholds);dmatrix=build_distributor_matrix(profiles,westcon_vendors)
    movement={"generated_at":iso_now(),"integrator":_relationship_movement(previous_imatrix,imatrix,"integrator"),"distributor":_relationship_movement(previous_dmatrix,dmatrix,"distributor")}
    profiles=_enrich_profile_relationship_counts(profiles,imatrix,dmatrix)
    distributors=[x for x in profiles if x.get("entity_type")=="distributor"];integrators=[x for x in profiles if x.get("entity_type")=="integrator"]
    portfolio=load_json(root/"data/v32/portfolio_intelligence.json",{});vpairs=build_vendor_pairs(portfolio,westcon_vendors,profiles);arch=build_architectures(portfolio,westcon_vendors,profiles)
    coverage=_coverage_report(profiles);research_plan=_research_plan(profiles);verification=_verification_queue(imatrix,dmatrix)
    prev_cov=f(previous_coverage.get("summary",{}).get("average_coverage"));coverage_delta=round(f(coverage.get("summary",{}).get("average_coverage"))-prev_cov,1) if previous_coverage else None
    out=root/"data/v33";out.mkdir(parents=True,exist_ok=True)
    ds=dedupe_report.get("summary",{})
    write_json(out/"ecosystem_profiles.json",{"meta":{"version":"3.3.3a","generated_at":iso_now(),"input_rows":len(raw_entities),"canonical_entities":len(profiles),"consolidated_source_variants":ds.get("consolidated_source_variants",0),"groups_with_variants":ds.get("groups_with_variants",0),"distributors":len(distributors),"integrators":len(integrators),"targeted_research":stats},"profiles":profiles,"distributors":distributors,"integrators":integrators})
    write_json(out/"integrator_vendor_matrix.json",imatrix);write_json(out/"distributor_vendor_matrix.json",dmatrix);write_json(out/"vendor_pair_intelligence.json",vpairs);write_json(out/"architectures.json",arch)
    write_json(out/"targeted_evidence.json",{"meta":{"version":"3.3.3a","generated_at":iso_now(),"new_evidence":new_unique,"cumulative_evidence":len(targeted),**stats},"evidence":targeted})
    write_json(out/"coverage_report.json",coverage);write_json(out/"research_plan.json",research_plan);write_json(out/"relationship_verification_queue.json",verification);write_json(out/"deduplication_report.json",dedupe_report);write_json(out/"relationship_movement.json",movement)
    istates=Counter(x.get("status") for x in imatrix.get("rows",[]));dstates=Counter(x.get("status") for x in dmatrix.get("rows",[]));tiers=Counter(x.get("entity_tier") for x in profiles)
    metrics={
      "version":"3.3.3a","generated_at":iso_now(),"input_rows":len(raw_entities),"profiles":len(profiles),"consolidated_source_variants":dedupe_report.get("summary",{}).get("consolidated_source_variants",0),"groups_with_variants":dedupe_report.get("summary",{}).get("groups_with_variants",0),"name_scope_conflicts_detected":dedupe_report.get("summary",{}).get("name_scope_conflicts_detected",0),"name_scope_conflicts_resolved":dedupe_report.get("summary",{}).get("name_scope_conflicts_resolved",0),"unresolved_name_scope_conflicts":dedupe_report.get("summary",{}).get("unresolved_name_scope_conflicts",0),"distributors":len(distributors),"integrators":len(integrators),
      "targeted_evidence":len(targeted),"new_targeted_evidence":new_unique,"relationship_rows":len(imatrix.get("rows",[])),"distributor_rows":len(dmatrix.get("rows",[])),"vendor_pairs":len(vpairs.get("pairs",[])),"architectures":len(arch.get("architectures",[])),"targeted_stats":stats,
      "average_profile_coverage":coverage.get("summary",{}).get("average_coverage"),"coverage_delta":coverage_delta,"average_coverage_target":coverage.get("summary",{}).get("average_target"),"difference_between_averages":coverage.get("summary",{}).get("difference_between_averages"),"average_coverage_gap":coverage.get("summary",{}).get("average_knowledge_debt"),"tier_distribution":dict(tiers),
      "relationship_changes":movement["integrator"]["changed_pairs"]+movement["distributor"]["changed_pairs"],"uncertainty_resolved":movement["integrator"]["uncertainty_resolved"]+movement["distributor"]["uncertainty_resolved"],
      "integrator_confirmed":istates.get("CONFIRMED_RELATION",0),"integrator_probable":istates.get("PROBABLE_RELATION",0),"integrator_whitespace":istates.get("WHITESPACE_RESEARCH_PRIORITY",0),"distributor_confirmed":dstates.get("CONFIRMED_DISTRIBUTION",0),"distributor_probable":dstates.get("PROBABLE_PUBLIC_RELATION",0),
      "research_priorities":len(research_plan.get("priorities",[])),"verification_queue":len(verification.get("queue",[]))
    }
    write_json(out/"last_run.json",metrics);return metrics
