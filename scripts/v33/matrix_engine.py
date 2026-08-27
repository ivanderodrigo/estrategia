from __future__ import annotations
from itertools import combinations
from .common import norm,f,clamp,stable_id,iso_now

ADJ={
 "Cybersecurity":{"SASE/SSE","Identity","Observability","Networking","AI"},
 "SASE/SSE":{"Cybersecurity","Identity","Networking","Observability"},
 "Networking":{"SASE/SSE","Cybersecurity","Observability","Automation","Data Center"},
 "Cloud":{"Cybersecurity","Observability","Automation","Data Center","AI","Identity"},
 "Data Center":{"Cloud","Networking","Observability","Automation","Cybersecurity"},
 "AI":{"Cybersecurity","Cloud","Observability","Automation","Data Center"},
 "Observability":{"Cybersecurity","Cloud","Networking","Automation","AI"},
 "Automation":{"Networking","Cloud","Observability","AI","Data Center"},
 "Identity":{"Cybersecurity","SASE/SSE","Cloud"}
}
GRADE_SCORE={"A":1.0,"B":.82,"C":.62,"D":.42,None:.5}


def _relation_evidence(profile,vendor):
    vn=norm(vendor);out=[]
    for x in profile.get("evidence") or []:
        hay=norm((x.get("title") or "")+" "+(x.get("source") or ""))
        if vn and vn in hay:out.append(x)
    return out


def _evidence_grade(ev):
    if not ev:return "D"
    vals=[]
    for x in ev:
        g=x.get("source_grade");vals.append(GRADE_SCORE.get(g,.5)*.55+f(x.get("confidence"))*.45)
    m=max(vals);div=len({norm(x.get("source")) for x in ev if x.get("source")})
    if m>=.83 and div>=2:return "A"
    if m>=.72:return "B"
    if m>=.58:return "C"
    return "D"


def _relationship_intensity(ev,grade,profile_confidence):
    """Strength of a demonstrated public relationship, separate from certainty/status."""
    if not ev:return 0
    div=len({norm(x.get("source")) for x in ev if x.get("source")});official=sum(1 for x in ev if x.get("source_grade")=="A")
    certification=sum(1 for x in ev if "certif" in norm((x.get("classification") or "")+" "+(x.get("title") or "")))
    customer=sum(1 for x in ev if any(k in norm(x.get("title")) for k in ("cliente","customer","case study","caso de exito")))
    v=.20+.18*min(1,len(ev)/4)+.17*min(1,div/3)+.20*GRADE_SCORE.get(grade,.5)+.12*min(1,official/2)+.07*min(1,certification/2)+.04*min(1,customer/2)+.02*f(profile_confidence)
    return round(100*clamp(v))


def build_relationship_matrix(profiles,westcon_vendors,thresholds):
    rows=[];confirmed=float(thresholds.get("confirmed",.82));probable=float(thresholds.get("probable",.64));min_ev=int(thresholds.get("confirmed_min_evidence",2))
    for p in profiles:
        if p.get("entity_type")!="integrator":continue
        known={norm(x) for x in p.get("vendors") or []};ws={norm(x.get("vendor")):x for x in p.get("whitespace_candidates") or []}
        for vendor in westcon_vendors:
            vn=norm(vendor);ev=_relation_evidence(p,vendor);relation=vn in known;wsx=ws.get(vn);w=0;grade=_evidence_grade(ev);src_div=len({norm(x.get("source")) for x in ev if x.get("source")})
            score=0
            if relation:
                score=.48+.09*min(3,len(ev))+.10*f(p.get("confidence"))+.07*min(1,src_div/2)+.06*GRADE_SCORE.get(grade,.5)
            elif wsx:
                w=f(wsx.get("research_priority_score") or wsx.get("priority_score") or wsx.get("whitespace_score"));w=w/100 if w>1 else w
                score=.20+.38*w+.08*f(p.get("westcon_relevance"))/100+.06*f(p.get("capability_score"))/100
            else:
                score=.10+.12*f(p.get("westcon_relevance"))/100+.05*f(p.get("capability_score"))/100
            score=clamp(score)
            strong_evidence=len(ev)>=min_ev or grade in {"A","B"} and len(ev)>=1
            intensity=_relationship_intensity(ev,grade,p.get("confidence"));official_count=sum(1 for x in ev if x.get("source_grade")=="A")
            if relation and score>=confirmed and strong_evidence:status="CONFIRMED_RELATION"
            elif relation and score>=probable:status="PROBABLE_RELATION"
            elif wsx:
                w=f(wsx.get("research_priority_score") or wsx.get("priority_score") or wsx.get("whitespace_score"));w=w/100 if w>1 else w
                status="WHITESPACE_RESEARCH_PRIORITY" if w>=float(thresholds.get("whitespace_shortlist",.68)) else "INSUFFICIENT_PUBLIC_EVIDENCE"
            else:status="INSUFFICIENT_PUBLIC_EVIDENCE"
            if status=="WHITESPACE_RESEARCH_PRIORITY":priority=round(100*max(score,.65*(w if wsx else 0)))
            else:priority=round(100*score)
            next_research=("Validar en partner locator/directorio oficial y certificaciones del fabricante." if status=="WHITESPACE_RESEARCH_PRIORITY" else
                           "Buscar una segunda fuente independiente o evidencia oficial." if status=="PROBABLE_RELATION" else
                           "Mantener vigilancia; la ausencia de evidencia no demuestra ausencia de relación." if status=="INSUFFICIENT_PUBLIC_EVIDENCE" else
                           "Revalidar periódicamente alcance, tier y especializaciones.")
            rows.append({
                "matrix_id":stable_id(p.get("name"),vendor),"integrator":p.get("name"),"vendor":vendor,"status":status,
                "status_label":{"CONFIRMED_RELATION":"Relación pública confirmada","PROBABLE_RELATION":"Relación pública probable","WHITESPACE_RESEARCH_PRIORITY":"Posible whitespace a investigar","INSUFFICIENT_PUBLIC_EVIDENCE":"Evidencia pública insuficiente"}[status],
                "relationship_strength":round(score,3),"priority_score":priority,"technology_fit":p.get("technology_focus") or [],"whitespace_score":round((w if wsx else 0)*100),
                "confidence":p.get("confidence"),"evidence_grade":grade,"evidence_count":len(ev),"source_diversity":src_div,"official_evidence_count":official_count,"relationship_intensity":intensity,"evidence":ev[:8],"next_research":next_research,
                "caution":"Ausencia de evidencia pública no demuestra ausencia de relación."
            })
    return {"meta":{"generated_at":iso_now(),"rows":len(rows)},"rows":rows}


def build_distributor_matrix(profiles,westcon_vendors):
    rows=[]
    for p in profiles:
        if p.get("entity_type")!="distributor":continue
        known={norm(x) for x in p.get("vendors") or []}
        for vendor in westcon_vendors:
            relation=norm(vendor) in known;ev=_relation_evidence(p,vendor);grade=_evidence_grade(ev);src_div=len({norm(x.get("source")) for x in ev if x.get("source")});official_count=sum(1 for x in ev if x.get("source_grade")=="A")
            strength=clamp((.50 if relation else .10)+.08*min(3,len(ev))+.10*f(p.get("confidence"))+.07*GRADE_SCORE.get(grade,.5));intensity=_relationship_intensity(ev,grade,p.get("confidence"))
            if relation and (len(ev)>=2 or grade in {"A","B"}):status="CONFIRMED_DISTRIBUTION"
            elif relation:status="PROBABLE_PUBLIC_RELATION"
            else:status="NO_PUBLIC_EVIDENCE"
            priority=round(100*clamp(.34*(f(p.get("competitive_pressure"))/100)+.22*(f(p.get("competitive_response_priority"))/100)+.18*strength+.14*(f(p.get("westcon_relevance"))/100)+.12*f(p.get("confidence"))))
            rows.append({
                "matrix_id":stable_id(p.get("name"),vendor),"distributor":p.get("name"),"vendor":vendor,"status":status,
                "status_label":{"CONFIRMED_DISTRIBUTION":"Distribución pública confirmada","PROBABLE_PUBLIC_RELATION":"Relación pública probable","NO_PUBLIC_EVIDENCE":"Sin evidencia pública suficiente"}[status],
                "public_relation":relation,"relationship_strength":round(strength,3),"priority_score":priority,"scope":p.get("scope"),"competitive_pressure":p.get("competitive_pressure"),
                "evidence_grade":grade,"evidence_count":len(ev),"source_diversity":src_div,"official_evidence_count":official_count,"relationship_intensity":intensity,"evidence":ev[:8],
                "next_research":"Verificar linecard/distributor locator oficial y alcance geográfico." if status!="CONFIRMED_DISTRIBUTION" else "Revalidar alcance, exclusividad y fecha del acuerdo.",
                "caution":"La tabla refleja evidencia pública y puede no representar la totalidad de acuerdos contractuales."
            })
    return {"meta":{"generated_at":iso_now(),"rows":len(rows)},"rows":rows}


def build_vendor_pairs(portfolio_doc,westcon_vendors,profiles=None):
    pdata={norm(x.get("vendor")):x for x in portfolio_doc.get("vendors",[]) or []};profiles=profiles or [];rows=[]
    for a,b in combinations(westcon_vendors,2):
        pa=pdata.get(norm(a),{});pb=pdata.get(norm(b),{});ta=set(pa.get("top_technologies") or []);tb=set(pb.get("top_technologies") or [])
        overlap=ta&tb;adj=sum(1 for x in ta for y in tb if y in ADJ.get(x,set()));complement=clamp(.16*adj+.07*len((ta|tb)-overlap));functional_overlap=clamp(.22*len(overlap))
        ma=f(pa.get("avg_materiality"));mb=f(pb.get("avg_materiality"));ea=f(pa.get("evidence_events"));eb=f(pb.get("evidence_events"));evidence_strength=clamp(.45*((ma+mb)/2)+.25*min(1,(ea+eb)/12)+.30*(1 if ta and tb else .25))
        shared_integrators=0
        for p in profiles:
            if p.get("entity_type")!="integrator":continue
            ks={norm(x) for x in p.get("vendors") or []}
            if norm(a) in ks and norm(b) in ks:shared_integrators+=1
        partner_signal=min(1,shared_integrators/5)
        synergy=clamp(.18+.48*complement+.10*evidence_strength+.12*partner_signal-.16*functional_overlap)
        conflict=clamp(.10+.55*functional_overlap-.18*complement)
        plays=[];domains=ta|tb
        if {"SASE/SSE","Identity"}<=domains:plays.append("Acceso seguro + identidad")
        if {"Cybersecurity","Observability"}<=domains:plays.append("SecOps + observabilidad")
        if {"Networking","Automation"}<=domains:plays.append("Networking automatizado / NaaS")
        if {"Cloud","Data Center"}<=domains:plays.append("Hybrid cloud + data center")
        if {"AI","Cybersecurity"}<=domains:plays.append("Seguridad para IA / IA para SecOps")
        readiness=clamp(.48*synergy+.20*evidence_strength+.18*partner_signal+.14*(1 if plays else .2))
        rows.append({
            "pair_id":stable_id(a,b),"vendor_a":a,"vendor_b":b,"synergy_score":round(synergy,3),"potential_overlap_score":round(conflict,3),"overlap_score":round(conflict,3),
            "evidence_strength":round(evidence_strength,3),"shared_integrator_count":shared_integrators,"commercial_play_readiness":round(readiness,3),
            "shared_domains":sorted(overlap),"complementary_domains":sorted(domains-overlap),"plays":plays,
            "synergy_band":"ALTA" if synergy>=.68 else "MEDIA" if synergy>=.50 else "BAJA","overlap_band":"ALTO" if conflict>=.60 else "MEDIO" if conflict>=.38 else "BAJO",
            "interpretation":"Sinergia potencial" if synergy>=.62 else ("Revisar solape funcional" if conflict>=.58 else "Complementariedad limitada"),
            "caution":"El solape funcional no implica conflicto comercial o contractual; la sinergia es una hipótesis basada en evidencia pública y complementariedad tecnológica."
        })
    rows.sort(key=lambda x:(x["commercial_play_readiness"],x["synergy_score"]),reverse=True)
    return {"meta":{"generated_at":iso_now(),"pairs":len(rows)},"pairs":rows}
