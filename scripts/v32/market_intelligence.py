from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Mapping, Sequence


def _f(v:Any)->float:
    try:return float(v or 0)
    except Exception:return 0.0


def build_competitive_pressure(events: Iterable[Mapping[str,Any]]) -> Dict[str,Any]:
    rows=defaultdict(lambda:{"events":0,"pressure":0.0,"technologies":Counter(),"signals":[],"country":"","entity_type":""})
    weights={
        "distribution_agreement":1.00,"managed_service":.90,"market_expansion":.88,"ma_acquisition":.85,
        "partnership":.72,"certification":.62,"service_launch":.60,"customer_reference":.54,"investment":.50,
    }
    for e in events:
        et=str(e.get("entity_type") or "")
        name=str(e.get("entity_name") or "").strip()
        if not name or et not in {"distributor","integrator"}:continue
        if "westcon" in name.casefold():continue
        t=str(e.get("event_type") or "")
        w=weights.get(t,0)
        if not w:continue
        scope=str(e.get("market_scope") or "")
        scope_w=1.0 if scope in {"ES","PT","IBERIA"} else (.82 if scope in {"EUROPE","EMEA"} else .55)
        p=w*scope_w*_f(e.get("materiality"))*max(.35,_f(e.get("confidence")))*max(.45,_f(e.get("strategic_fit")))
        r=rows[name];r["events"]+=1;r["pressure"]+=p;r["country"]=str(e.get("market_scope") or e.get("country") or "");r["entity_type"]=et
        for tech in e.get("technology_domains") or []:r["technologies"][str(tech)]+=1
        if p>=.20:r["signals"].append({"event_id":e.get("event_id"),"event_type":t,"title":e.get("title"),"score":round(p,3),"scope":scope})
    out=[]
    for name,r in rows.items():
        score=min(1.0,r["pressure"])
        out.append({"entity_name":name,"entity_type":r["entity_type"],"market_scope":r["country"],"pressure_score":round(score,3),"pressure_band":"HIGH" if score>=.70 else ("MEDIUM" if score>=.42 else "LOW"),"evidence_events":r["events"],"top_technologies":[x for x,_ in r["technologies"].most_common(6)],"top_signals":sorted(r["signals"],key=lambda x:x["score"],reverse=True)[:6]})
    out.sort(key=lambda x:x["pressure_score"],reverse=True)
    high=sum(1 for x in out if x["pressure_band"]=="HIGH"); medium=sum(1 for x in out if x["pressure_band"]=="MEDIUM")
    alerts=[{**x,"alert_type":"competitive_threat" if x["pressure_band"]=="HIGH" else "competitive_watch"} for x in out if x["pressure_band"] in {"HIGH","MEDIUM"}]
    return {"meta":{"generated_at":datetime.now(timezone.utc).isoformat(),"entities":len(out),"high_pressure":high,"medium_pressure":medium,"alerts":len(alerts)},"alerts":alerts[:30],"entities":out}


def build_portfolio_intelligence(events: Iterable[Mapping[str,Any]], westcon_vendors:set[str]) -> Dict[str,Any]:
    rows=defaultdict(lambda:{"events":0,"materiality":0.0,"technologies":Counter(),"scopes":Counter(),"event_types":Counter(),"signals":[]})
    for e in events:
        name=str(e.get("entity_name") or "").strip()
        if name.casefold() not in westcon_vendors:continue
        r=rows[name];r["events"]+=1;r["materiality"]+=_f(e.get("materiality"));r["scopes"][str(e.get("market_scope") or "")]+=1;r["event_types"][str(e.get("event_type") or "")]+=1
        for tech in e.get("technology_domains") or []:r["technologies"][str(tech)]+=1
        if _f(e.get("materiality"))>=.65:r["signals"].append({"event_id":e.get("event_id"),"event_type":e.get("event_type"),"title":e.get("title"),"materiality":e.get("materiality"),"confidence":e.get("confidence")})
    out=[]
    for name,r in rows.items():
        avg=r["materiality"]/max(1,r["events"])
        out.append({"vendor":name,"evidence_events":r["events"],"avg_materiality":round(avg,3),"top_technologies":[x for x,_ in r["technologies"].most_common(8)],"top_event_types":r["event_types"].most_common(8),"scope_mix":dict(r["scopes"]),"top_signals":sorted(r["signals"],key=lambda x:_f(x.get("materiality")),reverse=True)[:8]})
    out.sort(key=lambda x:(x["avg_materiality"],x["evidence_events"]),reverse=True)
    return {"meta":{"generated_at":datetime.now(timezone.utc).isoformat(),"vendors":len(out)},"vendors":out}


def build_whitespace_candidates(events: Sequence[Mapping[str,Any]], westcon_vendors:set[str]) -> Dict[str,Any]:
    """Conservative research candidates, not asserted partner relationships.

    Requires demonstrated technology overlap in evidence and excludes any vendor/integrator pair
    already present as a direct partnership/certification/customer/distribution relation.
    """
    vendor_tech=defaultdict(Counter); integ_tech=defaultdict(Counter); integ_ev=Counter(); known=set(); samples=defaultdict(list)
    for e in events:
        subj=str(e.get("entity_name") or "").strip(); obj=str(e.get("object_entity") or "").strip(); et=str(e.get("entity_type") or ""); ot=str(e.get("object_entity_type") or "")
        techs=[str(x) for x in e.get("technology_domains") or []]
        if subj.casefold() in westcon_vendors:
            for t in techs:vendor_tech[subj][t]+=1
        if et=="integrator":
            integ_ev[subj]+=1
            for t in techs:integ_tech[subj][t]+=1
            if len(samples[subj])<4:samples[subj].append(str(e.get("title") or ""))
        if obj and str(e.get("event_type") or "") in {"partnership","certification","distribution_agreement","customer_reference"}:
            known.add((subj.casefold(),obj.casefold()));known.add((obj.casefold(),subj.casefold()))
        if ot=="integrator" and obj:
            integ_ev[obj]+=1
            for t in techs:integ_tech[obj][t]+=1
    candidates=[]
    for integ,ic in integ_tech.items():
        if integ_ev[integ]<2:continue
        it=set(ic)
        for vendor,vc in vendor_tech.items():
            if (integ.casefold(),vendor.casefold()) in known:continue
            overlap=it & set(vc)
            if not overlap:continue
            strength=min(1.0,.22+.10*min(5,integ_ev[integ])+.12*min(3,len(overlap))+.04*sum(min(ic[t],3) for t in overlap))
            if strength<.55:continue
            candidates.append({"integrator":integ,"vendor":vendor,"technology_overlap":sorted(overlap),"research_priority_score":round(strength,3),"status":"RESEARCH_CANDIDATE_NOT_ASSERTED","why":"Existe solapamiento tecnológico demostrado en evidencia pública, pero no una relación pública suficientemente corroborada entre este integrador y fabricante.","next_research":"Verificar partner locator/certificaciones, casos de cliente, portfolio público y relación de distribución antes de tratarlo como whitespace comercial.","integrator_evidence_events":integ_ev[integ],"sample_evidence":samples[integ][:3]})
    candidates.sort(key=lambda x:x["research_priority_score"],reverse=True)
    for x in candidates:
        sc=float(x.get("research_priority_score") or 0)
        x["research_band"]="HIGH" if sc>=.82 else ("MEDIUM" if sc>=.68 else "LOW")
    shortlist=[x for x in candidates if x.get("research_band") in {"HIGH","MEDIUM"}][:25]
    return {"meta":{"generated_at":datetime.now(timezone.utc).isoformat(),"count":len(candidates),"shortlist_count":len(shortlist),"warning":"Candidatos de investigación, no oportunidades comerciales confirmadas."},"shortlist":shortlist,"candidates":candidates[:250]}
