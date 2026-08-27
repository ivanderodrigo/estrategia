from __future__ import annotations
from collections import Counter,defaultdict
from datetime import datetime,timezone,timedelta
from typing import Any,Mapping
from .common import load_json,norm,uniq,f,clamp,parse_date,stable_id

TECH_ORDER=["Cybersecurity","SASE/SSE","Networking","Cloud","Data Center","AI","Observability","Automation","Identity"]
MANAGED={"SOC / seguridad gestionada","NOC / red gestionada","Cloud gestionada"}
VALUE_ADDED={"Servicios profesionales","Formación y enablement","Financiación","Marketplace / plataforma","Staging / integración"}
REL_EVENT={"partnership","distribution_agreement","certification","customer_reference","award","channel_program"}
MOMENTUM_EVENTS={"distribution_agreement","partnership","managed_service","service_launch","market_expansion","ma_acquisition","certification","customer_reference","leadership_change","hiring","channel_program"}
GRADE_WEIGHT={"A":1.0,"B":.82,"C":.62,"D":.42}


def _scope_of(row):
    raw=(row.get("market_scope") or row.get("scope") or row.get("country") or "GLOBAL")
    n=norm(raw)
    if n in {"es","espana","spain"}:return "ES"
    if n in {"pt","portugal"}:return "PT"
    if "iber" in n:return "IBERIA"
    if n in {"emea"}:return "EMEA"
    if "europ" in n:return "EUROPE"
    if n in {"global","worldwide","world"}:return "GLOBAL"
    return str(raw).upper() if raw else "GLOBAL"


def _explicit_scope_from_name(name):
    """Return an explicit country scope encoded in the entity name, if any.

    This is intentionally conservative: only explicit country words are used.
    A name such as ``Bechtle Spain`` must not become IBERIA merely because a
    source row was tagged PT.  The contradictory source scope is preserved for
    audit, but the canonical entity keeps ES.
    """
    tokens=set(norm(name).split())
    if "spain" in tokens or "espana" in tokens:return "ES"
    if "portugal" in tokens:return "PT"
    return None


def _pick_scope(scopes,name=None):
    scopes=uniq([x for x in scopes if x])
    explicit=_explicit_scope_from_name(name)
    if explicit:
        return explicit
    if "IBERIA" in scopes or ("ES" in scopes and "PT" in scopes):return "IBERIA"
    for x in ("ES","PT","EUROPE","EMEA","GLOBAL"):
        if x in scopes:return x
    return scopes[0] if scopes else "GLOBAL"


def _entity_rows(doc,with_report=False):
    """Build one canonical company profile per exact normalized name and entity type.

    v3.3.3 does not call repeated source rows "duplicate companies".  They are
    source/operation variants of the same exact company name.  Country/region
    information is preserved in ``operations`` and ``scope_variants`` and every
    consolidation is emitted in a deduplication report.
    """
    groups=defaultdict(list);raw_count=0
    for kind,etype in (("distributors","distributor"),("integrators","integrator")):
        for idx,x in enumerate(doc.get(kind,[]) or []):
            name=x.get("name") or x.get("entity_name")
            if not name:continue
            raw_count+=1;groups[(etype,norm(name))].append((idx,dict(x),name))
    rows=[];detail=[];country_ops=0;scope_variants_preserved=0;name_scope_conflicts=0;resolved_name_scope_conflicts=0
    for (etype,_),items in groups.items():
        first=items[0][1];name=items[0][2];y=dict(first)
        y["name"]=name;y["entity_type"]=etype
        aliases=[];scopes=[];operations=[]
        explicit_scope=_explicit_scope_from_name(name)
        for idx,x,raw_name in items:
            aliases=uniq(aliases+(x.get("aliases") or [])+[raw_name])
            sc=_scope_of(x);scopes=uniq(scopes+[sc])
            conflicts_with_name=bool(explicit_scope and sc in {"ES","PT"} and sc!=explicit_scope)
            operations.append({"name":raw_name,"scope":sc,"country":x.get("country"),"market_scope":x.get("market_scope"),"source_row_index":idx,"scope_conflict_with_name":conflicts_with_name})
            for lk in ("vendors","technologies","technology_focus","services","certifications","verticals","customers","evidence"):
                if isinstance(y.get(lk),list) or isinstance(x.get(lk),list):
                    y[lk]=uniq((y.get(lk) or [])+(x.get(lk) or [])) if lk!="evidence" else (y.get(lk) or [])+(x.get(lk) or [])
            y["confidence"]=max(f(y.get("confidence")),f(x.get("confidence")))
        primary=_pick_scope(scopes,name)
        conflicting_scopes=uniq([op["scope"] for op in operations if op.get("scope_conflict_with_name")])
        if conflicting_scopes:
            name_scope_conflicts+=1
            if explicit_scope and primary==explicit_scope:resolved_name_scope_conflicts+=1
        y["aliases"]=aliases;y["canonical_name"]=name;y["canonical_group"]=y.get("corporate_group") or name
        y["scope"]=primary;y["scope_variants"]=scopes;y["operations"]=operations;y["operation_count"]=len(scopes);y["source_variant_count"]=len(items)
        y["entity_level"]=("iberia_operation" if primary=="IBERIA" else "country_operation" if primary in {"ES","PT"} else "regional_operation" if primary in {"EUROPE","EMEA"} else "corporate_group")
        rows.append(y)
        if len(items)>1:
            scope_variants_preserved+=max(0,len(scopes)-1);country_ops+=len({s for s in scopes if s in {"ES","PT"}})
            detail.append({"entity_type":etype,"canonical_name":name,"normalized_name":norm(name),"input_rows":len(items),"consolidated_variants":len(items)-1,"scope_variants":scopes,"selected_scope":primary,"explicit_name_scope":explicit_scope,"conflicting_scopes":conflicting_scopes,"name_scope_conflict_resolved":bool(conflicting_scopes and explicit_scope and primary==explicit_scope),"operations_preserved":operations,"aliases":aliases,"reason":"Mismo tipo de entidad + nombre normalizado exactamente igual; se consolida el perfil de compañía y se preservan las variantes de ámbito. Si el nombre contiene un país explícito, ese país prevalece sobre ámbitos contradictorios inferidos de fuentes, que permanecen trazados como anomalía."})
    report={"summary":{"input_rows":raw_count,"canonical_companies":len(rows),"consolidated_source_variants":max(0,raw_count-len(rows)),"groups_with_variants":len(detail),"scope_variants_preserved":scope_variants_preserved,"country_operations_preserved":country_ops,"ambiguous_merges":0,"name_scope_conflicts_detected":name_scope_conflicts,"name_scope_conflicts_resolved":resolved_name_scope_conflicts,"unresolved_name_scope_conflicts":max(0,name_scope_conflicts-resolved_name_scope_conflicts)},"groups":detail}
    return (rows,report) if with_report else rows


def _evidence_item(title="",source="",url="",date="",confidence=.6,method="public_evidence",classification="signal",source_grade=""):
    return {"title":title,"source":source,"url":url,"date":date,"confidence":round(f(confidence),3),"method":method,"classification":classification,"source_grade":source_grade or None}


def _prov(text,evidence,formula=None):
    ev=[];seen=set()
    for x in evidence:
        k=(x.get("url"),x.get("title"))
        if k in seen:continue
        seen.add(k);ev.append(x)
    return {"explanation":text,"formula":formula,"sources":ev[:8],"source_count":len(ev)}


def _event_evidence(e):
    srcs=e.get("sources") or []
    if not srcs and e.get("source"):srcs=[{"source":e.get("source"),"url":e.get("url"),"title":e.get("title")}]
    out=[]
    for s in srcs:
        if isinstance(s,str):out.append(_evidence_item(e.get("title"),s,"",e.get("published_at"),e.get("confidence"),"event_intelligence",e.get("event_type")))
        else:out.append(_evidence_item(s.get("title") or e.get("title"),s.get("source") or s.get("name"),s.get("url"),s.get("date") or e.get("published_at"),e.get("confidence"),"event_intelligence",e.get("event_type")))
    return out


def _has(v):
    if v in (None,"",0,[],{}):return False
    return True


def _grade(all_ev,confidence,source_diversity):
    grades=[x.get("source_grade") for x in all_ev if x.get("source_grade")]
    a=sum(1 for x in grades if x=="A");b=sum(1 for x in grades if x=="B")
    if a>=1 and source_diversity>=2 and confidence>=.78:return "A"
    if a>=1 or (b>=2 and source_diversity>=2) or confidence>=.82:return "B"
    if source_diversity>=2 or confidence>=.66:return "C"
    return "D"


def _coverage(etype,vals):
    if etype=="integrator":
        checks=[
            ("Fabricantes",vals.get("vendors")),("Certificaciones/especializaciones",vals.get("certifications") or vals.get("certification_signals")),
            ("Capacidades tecnológicas",vals.get("technology_focus")),("Sectores",vals.get("verticals")),
            ("Clientes/casos",vals.get("customer_cases") or vals.get("customer_case_examples")),("Servicios gestionados",vals.get("managed_services"))
        ]
    else:
        checks=[
            ("Fabricantes",vals.get("vendors")),("Foco tecnológico",vals.get("technology_focus")),
            ("Servicios de valor añadido",vals.get("value_added")),("Servicios gestionados",vals.get("managed_services")),
            ("Movimientos de canal",vals.get("channel_moves"))
        ]
    covered=sum(1 for _,v in checks if _has(v));score=round(100*covered/max(1,len(checks)))
    gaps=[label for label,v in checks if not _has(v)]
    return score,gaps


def _tiering(etype,scope,westcon_rel,capability,pressure,activation,response,momentum,confidence,coverage_score):
    """Backward-compatible absolute tier helper.

    Confidence and coverage are deliberately excluded from the tier score: they
    measure how well we know an actor, not how strategically important it is.
    The final production tier is assigned relatively by ``_assign_relative_tiers``.
    """
    business=(activation if etype=="integrator" else response)/100
    operational=(capability if etype=="integrator" else pressure)/100
    scope_weight=1.0 if scope in {"ES","PT","IBERIA"} else .72 if scope in {"EUROPE","EMEA"} else .45
    score=100*clamp(.33*westcon_rel+.27*business+.20*operational+.08*momentum+.12*scope_weight)
    tier="T1" if score>=68 else "T2" if score>=46 else "T3"
    targets={"integrator":{"T1":85,"T2":65,"T3":40},"distributor":{"T1":80,"T2":60,"T3":35}}
    target=targets[etype][tier];gap=max(0,target-coverage_score);attainment=round(100*coverage_score/max(1,target))
    rationale="Tier provisional de importancia estructural; confianza y cobertura se muestran aparte."
    return round(score),tier,target,gap,min(100,attainment),rationale


def _structural_importance(etype,scope,vendors,overlap,tech,managed,value_added,pub_count,ws_score,pressure_score,momentum):
    scope_w=1.0 if scope in {"ES","PT","IBERIA"} else .72 if scope in {"EUROPE","EMEA"} else .45
    vendor_b=min(1,len(vendors)/6);overlap_b=min(1,len(overlap)/3);tech_b=min(1,len(tech)/5)
    services_b=min(1,(len(managed)+len(value_added))/4);public_b=min(1,pub_count/4)
    if etype=="integrator":
        score=.22*scope_w+.17*vendor_b+.20*overlap_b+.14*tech_b+.10*services_b+.09*public_b+.08*ws_score
    else:
        score=.20*scope_w+.20*vendor_b+.24*overlap_b+.11*tech_b+.10*services_b+.10*clamp(pressure_score)+.05*clamp(momentum)
    return round(100*clamp(score))


def _assign_relative_tiers(profiles):
    """Assign T1/T2/T3 by structural importance within each entity class.

    Tiers are research-depth bands, not revenue segmentation.  A low-confidence
    actor can therefore remain T1 and be given a larger knowledge-debt priority.
    """
    targets={"integrator":{"T1":85,"T2":65,"T3":40},"distributor":{"T1":80,"T2":60,"T3":35}}
    for etype in ("distributor","integrator"):
        rows=[x for x in profiles if x.get("entity_type")==etype]
        rows.sort(key=lambda x:(f(x.get("strategic_importance_score")),f(x.get("westcon_relevance")),f(x.get("activation_priority") or x.get("competitive_response_priority"))),reverse=True)
        n=len(rows)
        if not n:continue
        t1_n=max(1,round(n*(.18 if etype=="distributor" else .15)))
        t2_n=max(1,round(n*.35))
        for i,p in enumerate(rows):
            tier="T1" if i<t1_n else "T2" if i<t1_n+t2_n else "T3"
            target=targets[etype][tier];cov=f(p.get("coverage_score"));gap=max(0,target-cov);att=min(100,round(100*cov/max(1,target)))
            p["entity_tier"]=tier;p["tier_score"]=p.get("strategic_importance_score");p["coverage_target"]=target;p["coverage_gap"]=round(gap,1);p["coverage_attainment"]=att
            p["tier_rationale"]=(f"{tier} relativo dentro de los {n} {('integradores' if etype=='integrator' else 'mayoristas')} analizados, según importancia estructural observada. La confianza ({round(100*f(p.get('confidence')))}%) y la cobertura ({round(cov)}%) no reducen el tier; determinan cuánto debemos investigar.")
            pv=p.get("provenance") or {};p["provenance"]=pv
            ev=p.get("evidence") or []
            pv["entity_tier"]=_prov("Prioridad relativa de profundidad de investigación dentro del universo actual. Se calcula a partir de importancia estructural observada y no baja porque falte información.",ev,"ranking relativo por tipo; T1≈15–18%, T2≈35%, T3 resto")
            pv["tier_score"]=_prov("Importancia estratégica relativa observada. No usa confianza ni cobertura como penalización y no representa facturación ni cuota.",ev,"0–100; alcance + relaciones de fabricantes + solape Westcon + capacidades/servicios + señales sectoriales")
            pv["coverage_target"]=_prov("Objetivo de cobertura asignado según el tier estratégico relativo. Un actor T1 requiere mucha más profundidad.",ev,"T1/T2/T3 con objetivos distintos por tipo")
            pv["coverage_gap"]=_prov("Deuda de conocimiento de esta entidad: puntos que faltan para alcanzar su objetivo individual.",ev,"max(0, objetivo individual - cobertura actual)")
    return profiles


def build_profiles(root, targeted_rows, entity_rows=None):
    entity=load_json(root/"data/v31/entity_intelligence.json",{})
    events=(load_json(root/"data/v32/events.json",{}).get("events") or [])
    pressure=(load_json(root/"data/v32/competitive_pressure.json",{}).get("entities") or [])
    whitespace_doc=load_json(root/"data/v32/whitespace_candidates.json",{})
    decisions=(load_json(root/"data/v32/decisions.json",{}).get("decisions") or [])
    westcon_doc=load_json(root/"config/v31/westcon_vendor_scope.json",{})
    westcon_vendors=uniq((westcon_doc.get("vendors") or westcon_doc.get("active_vendors") or []))
    if westcon_vendors and isinstance(westcon_vendors[0],dict):westcon_vendors=[x.get("name") for x in westcon_vendors if x.get("name")]
    westcon_norm={norm(x):x for x in westcon_vendors}
    pmap={norm(x.get("entity_name")):x for x in pressure}
    erows=entity_rows if entity_rows is not None else _entity_rows(entity)
    tmap=defaultdict(list)
    for r in targeted_rows:tmap[norm(r.get("name"))].append(r)
    emap=defaultdict(list)
    for e in events:
        for name in [e.get("entity_name"),e.get("object_entity")]:
            if name:emap[norm(name)].append(e)
    dmap=defaultdict(list)
    for d in decisions:
        name=d.get("entity_name") or d.get("subject")
        if name:dmap[norm(name)].append(d)
    whites=(whitespace_doc.get("candidates") or [])+(whitespace_doc.get("research") or [])+(whitespace_doc.get("shortlist") or [])
    wmap=defaultdict(list)
    for w in whites:
        if w.get("integrator"):wmap[norm(w.get("integrator"))].append(w)
    now=datetime.now(timezone.utc);profiles=[]
    for base in erows:
        name=base.get("name");key=norm(name);etype=base.get("entity_type")
        be=[]
        for x in base.get("evidence") or []:be.append(_evidence_item(x.get("title"),x.get("source"),x.get("url"),x.get("published_at") or x.get("date"),x.get("confidence") or base.get("confidence"),"v31_entity_intelligence",x.get("classification")))
        tev=tmap.get(key,[]);ee=emap.get(key,[]);all_ev=be[:]
        for x in tev:all_ev.append(_evidence_item(x.get("title"),x.get("source"),x.get("url"),x.get("published_at"),x.get("confidence"),"targeted_research",x.get("field"),x.get("source_grade")))
        for e in ee:all_ev.extend(_event_evidence(e))

        vendors=uniq(base.get("vendors") or [])
        for x in tev:vendors=uniq(vendors+(x.get("vendors") or [])+([x.get("vendor")] if x.get("field")=="vendor_pair_verification" and x.get("vendor") else []))
        for e in ee:
            if e.get("event_type") in REL_EVENT:
                a=e.get("entity_name");b=e.get("object_entity");other=b if norm(a)==key else a
                if other and (norm(other) in westcon_norm or e.get("object_entity_type")=="vendor" or e.get("entity_type")=="vendor"):vendors=uniq(vendors+[other])
        tech=uniq(base.get("technologies") or base.get("technology_focus") or [])
        for e in ee:tech=uniq(tech+(e.get("technology_domains") or []))
        for x in tev:tech=uniq(tech+(x.get("technologies") or []))
        tech=sorted(tech,key=lambda x:(TECH_ORDER.index(x) if x in TECH_ORDER else 99,x))
        services=uniq(base.get("services") or [])
        for x in tev:services=uniq(services+(x.get("services") or []))
        certs=uniq(base.get("certifications") or [])
        cert_signals=[];verticals=uniq(base.get("verticals") or [])
        for x in tev:
            verticals=uniq(verticals+(x.get("verticals") or []))
            if x.get("certification_signal"):
                cert_signals=uniq(cert_signals+[x.get("title")])
                if x.get("vendors"):certs=uniq(certs+[f"Especialización/certificación relacionada con {v}" for v in x.get("vendors")])
        customers=uniq(base.get("customers") or []);customer_examples=[]
        for e in ee:
            if e.get("event_type")=="customer_reference" and norm(e.get("entity_name"))==key and e.get("object_entity"):customers=uniq(customers+[e.get("object_entity")])
        for x in tev:
            if x.get("field")=="customers" and x.get("customer_signal"):customer_examples=uniq(customer_examples+[x.get("title")])
        managed=uniq([x for x in services if x in MANAGED]);value_added=uniq([x for x in services if x in VALUE_ADDED])
        scope=(pmap.get(key) or {}).get("market_scope") or base.get("scope") or base.get("country") or "GLOBAL"
        pe=pmap.get(key) or {};pressure_score=f(pe.get("pressure_score"));pressure_val=round(pressure_score*100)
        cutoff=now-timedelta(days=90);recent=[]
        for e in ee:
            d=parse_date(e.get("published_at"))
            if d and d>=cutoff and e.get("event_type") in MOMENTUM_EVENTS:recent.append(e)
        momentum=clamp(.13*len(recent)+sum(f(x.get("materiality")) for x in recent)*.13)
        pub=[e for e in ee if e.get("event_type") in {"procurement_award","procurement_notice"} and e.get("market_scope") in {"ES","PT","IBERIA"}]
        ws=sorted(wmap.get(key,[]),key=lambda x:f(x.get("research_priority_score") or x.get("priority_score")),reverse=True)
        ws_score=f(ws[0].get("research_priority_score") or ws[0].get("priority_score")) if ws else 0
        if ws_score>1:ws_score/=100
        decisions_here=dmap.get(key,[]);opp=sum(1 for d in decisions_here if d.get("impact")=="opportunity");thr=sum(1 for d in decisions_here if d.get("impact")=="threat")
        evidence_count=len({(x.get("url"),x.get("title")) for x in all_ev if x.get("title") or x.get("url")});sources={norm(x.get("source")) for x in all_ev if x.get("source")};source_diversity=len(sources)
        base_conf=f(base.get("confidence"));conf=clamp(max(base_conf,.42)+min(.28,.018*evidence_count)+(.06 if source_diversity>=2 else 0))
        overlap=[v for v in vendors if norm(v) in westcon_norm]
        breadth=min(1,len(tech)/6);cert_strength=min(1,(len(certs)+.5*len(cert_signals))/5);client_strength=min(1,(len(customers)+.5*len(customer_examples))/6);managed_strength=min(1,len(managed)/3)
        capability=clamp(.20+.23*breadth+.18*cert_strength+.16*client_strength+.14*managed_strength+.09*min(1,evidence_count/12))
        westcon_rel=clamp(.24+.10*min(4,len(overlap))+.10*min(1,len(set(tech)&set(TECH_ORDER))/4)+.12*min(1,len(pub)/3)+.16*ws_score+.08*min(1,evidence_count/10))
        dates=[parse_date(x.get("date")) for x in all_ev];dates=[x for x in dates if x];last=max(dates).isoformat() if dates else base.get("last_verified")
        preliminary={"vendors":vendors,"technology_focus":tech,"value_added":value_added,"managed_services":managed,"channel_moves":len([e for e in recent if e.get("event_type") in {"distribution_agreement","partnership","market_expansion","ma_acquisition","channel_program"}]),"certifications":certs,"certification_signals":cert_signals,"verticals":verticals,"customer_cases":customers,"customer_case_examples":customer_examples}
        coverage_score,research_gaps=_coverage(etype,preliminary)
        evidence_grade=_grade(all_ev,conf,source_diversity)
        recurring=round(100*clamp(.18*min(1,len(managed)/2)+.20*min(1,len(value_added)/3)+.22*breadth+.18*min(1,evidence_count/10)+.22*conf))
        public_sector_score=round(100*clamp(.30*min(1,len(pub)/4)+.30*min(1,sum(f(e.get("materiality")) for e in pub)/3)+.20*conf+.20*(1 if scope in {"ES","PT","IBERIA"} else .25))) if pub else 0
        if etype=="integrator":
            activation=round(100*clamp(.27*westcon_rel+.21*capability+.14*ws_score+.09*momentum+.14*conf+.15*(coverage_score/100)))
            response=0
        else:
            overlap_factor=min(1,len(overlap)/4);response=round(100*clamp(.30*pressure_score+.20*overlap_factor+.13*momentum+.18*westcon_rel+.11*conf+.08*(coverage_score/100)))
            activation=0
        strategic_importance=_structural_importance(etype,scope,vendors,overlap,tech,managed,value_added,len(pub),ws_score,pressure_score,momentum)
        tier_score,entity_tier,coverage_target,coverage_gap,coverage_attainment,tier_rationale=_tiering(etype,scope,westcon_rel,capability,pressure_val,activation,response,momentum,conf,coverage_score)
        profile={
          "profile_id":stable_id(etype,name),"name":name,"canonical_name":base.get("canonical_name") or name,"canonical_group":base.get("canonical_group") or name,"entity_type":etype,"entity_level":base.get("entity_level") or "company","scope":scope,"scope_variants":base.get("scope_variants") or [scope],"operations":base.get("operations") or [],"operation_count":base.get("operation_count") or 1,"source_variant_count":base.get("source_variant_count") or 1,"aliases":base.get("aliases") or [name],"vendors":vendors,"vendor_relation_count":len(vendors),"westcon_overlap":overlap,"westcon_overlap_count":len(overlap),
          "technology_focus":tech,"services":services,"managed_services":managed,"value_added":value_added,"certifications":certs,"certification_signals":cert_signals[:8],"verticals":verticals,"customer_cases":customers,"customer_case_examples":customer_examples[:8],
          "public_sector_events":len(pub),"public_sector_score":public_sector_score,"channel_moves":preliminary["channel_moves"],
          "competitive_pressure":pressure_val,"competitive_pressure_band":pe.get("pressure_band") or ("HIGH" if pressure_val>=70 else "MEDIUM" if pressure_val>=42 else "LOW"),
          "momentum_90d":round(momentum*100),"westcon_relevance":round(westcon_rel*100),"capability_score":round(capability*100),"recurring_services_potential":recurring,
          "activation_priority":activation,"competitive_response_priority":response,
          "whitespace_score":round(ws_score*100),"whitespace_candidates":ws[:12],"opportunities":opp,"threats":thr,"evidence_count":evidence_count,"source_diversity":source_diversity,"evidence_grade":evidence_grade,"confidence":round(conf,3),"coverage_score":coverage_score,"coverage_target":coverage_target,"coverage_gap":coverage_gap,"coverage_attainment":coverage_attainment,"entity_tier":entity_tier,"tier_score":tier_score,"strategic_importance_score":strategic_importance,"tier_rationale":tier_rationale,"research_gaps":research_gaps,"last_verified":last,
          "evidence":all_ev[:100],"provenance":{}
        }
        pv=profile["provenance"]
        def tev_ev(fields):return [_evidence_item(x.get("title"),x.get("source"),x.get("url"),x.get("published_at"),x.get("confidence"),"targeted_research",x.get("field"),x.get("source_grade")) for x in tev if x.get("field") in fields]
        def event_ev(types=None,require_tech=False):
            chosen=[e for e in ee if (not types or e.get("event_type") in types) and (not require_tech or e.get("technology_domains"))]
            return [z for e in chosen for z in _event_evidence(e)]
        vendor_ev=be+tev_ev({"vendors","certifications","vendor_pair_verification"})+event_ev(REL_EVENT)
        tech_ev=be+tev_ev({"services","managed_services","value_added","certifications","verticals"})+event_ev(require_tech=True)
        service_ev=be+tev_ev({"services","managed_services","value_added"})+event_ev({"managed_service","service_launch","capability_expansion"})
        cert_ev=be+tev_ev({"certifications","vendors","vendor_pair_verification"})+event_ev({"certification","award","partnership"})
        vert_ev=be+tev_ev({"verticals","customers"})+event_ev({"customer_reference","procurement_award","procurement_notice"})
        customer_ev=be+tev_ev({"customers"})+event_ev({"customer_reference"})
        pv["vendors"]=_prov("Relaciones públicas encontradas en portfolio, acuerdos, certificaciones, casos y búsqueda dirigida.",vendor_ev)
        pv["vendor_relation_count"]=_prov("Número de fabricantes para los que existe alguna relación pública identificada.",vendor_ev,"conteo de fabricantes relacionados")
        pv["westcon_overlap"]=_prov("Cruce entre fabricantes relacionados públicamente con la entidad y el ámbito de fabricantes configurado para Westcon.",vendor_ev,"conteo de fabricantes coincidentes")
        pv["westcon_overlap_count"]=pv["westcon_overlap"]
        pv["technology_focus"]=_prov("Áreas tecnológicas repetidas en eventos, servicios y evidencias públicas.",tech_ev)
        pv["managed_services"]=_prov("Servicios gestionados detectados explícitamente en evidencias públicas; no se infieren por el nombre de la empresa.",service_ev)
        pv["value_added"]=_prov("Capacidades de valor añadido identificadas explícitamente en evidencias públicas.",service_ev)
        pv["certifications"]=_prov("Certificaciones/especializaciones explícitas. Se excluyen certificaciones de alumnos, clientes o terceros.",cert_ev)
        pv["verticals"]=_prov("Sectores con referencias o actividad pública identificable.",vert_ev)
        pv["customer_cases"]=_prov("Clientes/casos que aparecen como relación explícita en evidencia pública.",customer_ev)
        pv["public_sector"]=_prov(f"{len(pub)} eventos de contratación pública tecnológica con alcance Iberia.",[z for e in pub for z in _event_evidence(e)],"conteo de notices/adjudicaciones tecnológicas")
        pv["public_sector_score"]=_prov("Indicador relativo de tracción pública: volumen, materialidad, confianza y proximidad a Iberia.",[z for e in pub for z in _event_evidence(e)],"0–100; no representa cuota de contratación")
        pv["channel_moves"]=_prov(f"{profile['channel_moves']} movimientos de canal materiales en los últimos 90 días.",[z for e in recent for z in _event_evidence(e)])
        pv["competitive_pressure"]=_prov("Score relativo de presión competitiva de v3.2, ponderado por tipo de movimiento, geografía, materialidad y confianza.",[z for e in ee for z in _event_evidence(e)],"0–100; no es cuota de mercado")
        pv["momentum_90d"]=_prov("Score relativo de actividad reciente a partir de señales materiales de los últimos 90 días.",[z for e in recent for z in _event_evidence(e)],"eventos recientes + materialidad")
        pv["westcon_relevance"]=_prov("Score relativo de encaje con fabricantes, tecnologías, sector público y whitespace de Westcon Iberia.",all_ev,"0–100; indicador interno de priorización")
        pv["capability_score"]=_prov("Score relativo de madurez pública: amplitud tecnológica, certificaciones, clientes, servicios gestionados y evidencia.",all_ev,"0–100; no es una certificación oficial")
        pv["recurring_services_potential"]=_prov("Potencial relativo para adjuntar servicios recurrentes según servicios gestionados, capacidades, evidencia y confianza.",service_ev+tech_ev,"0–100; proxy de negocio, no previsión de ingresos")
        pv["activation_priority"]=_prov("Prioridad relativa para trabajar comercial/técnicamente con el integrador: relevancia Westcon, capacidad, whitespace, momentum, confianza y cobertura.",all_ev,"0–100; priorización, no forecast")
        pv["competitive_response_priority"]=_prov("Prioridad relativa de respuesta frente al mayorista: presión, solape, momentum, relevancia, confianza y cobertura.",all_ev,"0–100; priorización competitiva")
        pv["whitespace"]=_prov("Prioridad de investigación fabricante–integrador. Ausencia de evidencia pública no equivale a ausencia de relación.",all_ev,"máximo research_priority_score")
        pv["evidence_count"]=_prov("Número de evidencias públicas deduplicadas utilizadas para construir este perfil.",all_ev)
        pv["source_diversity"]=_prov("Número de fuentes públicas distintas que contribuyen al perfil.",all_ev,"conteo de fuentes únicas")
        pv["evidence_grade"]=_prov("Calidad agregada de evidencia: A es más sólida; D indica evidencia todavía débil. Combina fuentes, diversidad y confianza.",all_ev,"A/B/C/D; no sustituye revisión humana")
        pv["coverage_score"]=_prov("Porcentaje de áreas de información de negocio prioritarias que tienen al menos una evidencia útil.",all_ev,"campos cubiertos / campos prioritarios")
        pv["coverage_target"]=_prov("Objetivo de cobertura asignado según el tier estratégico de la entidad. Los actores T1 requieren mucha más profundidad que el long tail.",all_ev,"T1/T2/T3 con objetivos distintos por tipo de entidad")
        pv["coverage_gap"]=_prov("Puntos de cobertura que faltan para alcanzar el objetivo del tier. Es la deuda de conocimiento accionable de esta entidad.",all_ev,"max(0, objetivo - cobertura actual)")
        pv["coverage_attainment"]=_prov("Porcentaje del objetivo de cobertura del tier que ya se ha alcanzado.",all_ev,"cobertura actual / objetivo del tier")
        pv["entity_tier"]=_prov("Nivel de profundidad recomendado para investigar la entidad, calculado con relevancia Westcon, prioridad de negocio, capacidades/presión, actividad reciente, confianza y ámbito geográfico.",all_ev,"T1 estratégico · T2 relevante · T3 long tail")
        pv["strategic_importance_score"]=_prov("Importancia estratégica relativa observada: alcance Iberia, relaciones de fabricantes, solape con Westcon, capacidades/servicios y señales de mercado. No se reduce por falta de evidencia.",all_ev,"0–100; indicador relativo, no facturación ni cuota")
        pv["tier_score"]=_prov("Score de importancia estructural usado para ordenar el tier de investigación; confianza y cobertura se tratan por separado.",all_ev,"0–100")
        pv["research_gaps"]=_prov("Áreas prioritarias del perfil para las que todavía falta evidencia pública suficiente.",all_ev)
        pv["confidence"]=_prov("Confianza global basada en confianza previa, número de evidencias y diversidad de fuentes.",all_ev)
        pv["last_verified"]=_prov("Fecha más reciente entre las evidencias públicas utilizadas.",all_ev)
        profiles.append(profile)
    profiles=_assign_relative_tiers(profiles)
    return profiles,westcon_vendors
