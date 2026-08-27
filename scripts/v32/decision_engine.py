from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Mapping

from .event_intelligence import decision_hint

MONETIZATION={
 "distribution_agreement":"Defensa/captura de share, activación de partners, servicios attach y lifecycle.",
 "procurement_notice":"Pipeline de sector público, identificación temprana de partners, arquitectura, servicios profesionales y soporte.",
 "procurement_award":"Inteligencia de adjudicatarios, réplica de arquitectura, campañas por organismo/vertical y servicios attach.",
 "customer_reference":"Campañas por vertical, cross-sell multivendor y servicios de adopción.",
 "certification":"Enablement, formación, nuevas oportunidades y attach de servicios.",
 "managed_service":"MRR/ARR de servicios gestionados, SOC/NOC white-label y consumo recurrente.",
 "service_launch":"Servicios profesionales, bundles, soporte premium y recurrencia.",
 "product_release":"Upgrade/migración, demos, PoC, servicios profesionales y renewal pull-through.",
 "security_incident":"Assessment, hardening, managed security, remediation y renovación tecnológica.",
 "regulatory_change":"Assessment de cumplimiento, proyectos de adecuación y managed compliance.",
 "partnership":"Ofertas conjuntas, campañas, pipeline compartido y solución multivendor.",
 "ma_acquisition":"Captura de cuentas durante transición, consolidación de portfolio e integración.",
 "ma_rumor":"No monetizar como hecho consumado; usar para escenarios, vigilancia de cuentas y preparación defensiva hasta corroboración primaria.",
 "analyst_positioning":"Campañas de demanda y argumentario comercial basado en evidencia externa.",
 "known_exploited_vulnerability":"Assessment, hardening, servicios gestionados y aceleración de renovación/remediación sobre base instalada afectada.",
 "market_expansion":"Defensa/captura de cuentas y partners ante cambio de cobertura competitiva.",
}
KPI={
 "distribution_agreement":"share protegido/capturado; partners activados; pipeline; attach rate",
 "procurement_notice":"licitaciones cualificadas; partners mapeados; pipeline público; win-rate",
 "procurement_award":"adjudicatarios mapeados; oportunidades análogas; pipeline influenciado; attach",
 "customer_reference":"cuentas target; oportunidades; conversiones; pipeline por vertical",
 "certification":"certificaciones; partners activos; oportunidades; pipeline atribuido",
 "managed_service":"MRR/ARR; attach rate; partners consumiendo; margen de servicio",
 "security_incident":"assessments; remediaciones; attach; renovaciones aceleradas",
 "product_release":"PoC; upgrades; pipeline; attach de servicios",
 "partnership":"pipeline conjunto; campañas; nuevos logos; revenue influenciado",
 "known_exploited_vulnerability":"partners afectados; assessments; remediaciones; pipeline de hardening; attach gestionado",
 "market_expansion":"cuentas defendidas; partners retenidos/captados; pipeline competitivo",
}

RECURRING_TYPES={"managed_service","security_incident","known_exploited_vulnerability","regulatory_change","service_launch","pricing_licensing"}
FAST_TYPES={"procurement_notice","distribution_agreement","security_incident","known_exploited_vulnerability","product_release","customer_reference"}
HIGH_MARGIN_TYPES={"managed_service","security_incident","known_exploited_vulnerability","certification","service_launch","regulatory_change"}


def _impact(event: Mapping[str,Any]) -> str:
    t=str(event.get("event_type") or "")
    et=str(event.get("entity_type") or "")
    ot=str(event.get("object_entity_type") or "")
    entity=str(event.get("entity_name") or "").casefold()
    obj=str(event.get("object_entity") or "").casefold()
    scope=str(event.get("market_scope") or "")
    rel=float(event.get("westcon_relevance") or 0)
    fit=float(event.get("strategic_fit") or 0)
    procurement_fit=float(event.get("procurement_fit_score") or 0)
    subject_w=bool(event.get("subject_is_westcon_vendor"))
    object_w=bool(event.get("object_is_westcon_vendor"))
    tech_proc=bool(event.get("technology_procurement"))

    if "westcon" in entity:
        return "opportunity"

    if t=="procurement_notice":
        return "opportunity" if tech_proc and procurement_fit>=.62 and scope in {"ES","PT","IBERIA"} and rel>=.48 else "context"
    if t=="procurement_award":
        return "watch" if tech_proc and procurement_fit>=.52 else "context"

    # KEV is first a technical watch. It becomes commercial only when evidence points to a
    # strategically relevant Westcon vendor and the fit is high enough; EPSS can strengthen it.
    if t=="known_exploited_vulnerability":
        epss=float(event.get("epss") or 0)
        return "opportunity" if subject_w and fit>=.68 and (epss>=.35 or float(event.get("materiality") or 0)>=.78) else "watch"

    if t=="distribution_agreement":
        competitor_dist = et=="distributor" and "westcon" not in entity
        object_competitor_dist = ot=="distributor" and "westcon" not in obj
        if subject_w and object_competitor_dist: return "threat"
        if object_w and competitor_dist: return "threat"
        if competitor_dist and scope in {"ES","PT","IBERIA","EUROPE","EMEA"}: return "threat"
        return "watch"

    if t=="market_expansion" and et in {"distributor","integrator"} and scope in {"ES","PT","IBERIA"}:
        return "threat"
    if t in {"managed_service","service_launch"} and et=="distributor" and "westcon" not in entity and scope in {"ES","PT","IBERIA"}:
        return "threat" if t=="managed_service" else "watch"
    if t=="ma_acquisition" and et=="distributor" and "westcon" not in entity and scope in {"ES","PT","IBERIA","EUROPE","EMEA"}:
        return "threat"
    if t=="partnership" and et in {"distributor","integrator"} and (subject_w or object_w):
        return "threat" if et=="distributor" else "watch"

    if t in {"product_release","service_launch","managed_service","customer_reference","certification","analyst_positioning","channel_program","regulatory_change"}:
        return "opportunity" if subject_w and fit>=.58 else "watch"
    if t=="ma_rumor": return "watch"
    if t in {"ma_acquisition","investment","partnership","market_expansion","security_incident","operational_incident","end_of_sale","pricing_licensing"}: return "watch"
    return "context"


def _owner(event_type:str)->str:
    if event_type in {"distribution_agreement","partnership","channel_program","market_expansion"}:return "Dirección de Canal / Vendor Management"
    if event_type in {"certification","product_release","service_launch","managed_service","security_incident","known_exploited_vulnerability","security_vulnerability"}:return "Preventa / Ingeniería / Servicios"
    if event_type in {"procurement_award","procurement_notice"}:return "Ventas / PSM / Preventa"
    return "Estrategia / Vendor Management"


def _priority(score:float, impact:str) -> str:
    if impact in {"opportunity","threat"} and score>=.84:return "P1"
    if score>=.76:return "P2"
    if score>=.68:return "P3"
    return "P4"


def _economic_profile(event: Mapping[str,Any], impact:str) -> Dict[str,Any]:
    """Proxy economics, not invented euros. Gives a comparable prioritization until CRM/margin data exists."""
    t=str(event.get("event_type") or "")
    fit=float(event.get("strategic_fit") or 0)
    rel=float(event.get("westcon_relevance") or 0)
    mat=float(event.get("materiality") or 0)
    scope=str(event.get("market_scope") or "")
    techs=set(event.get("technology_domains") or [])
    procurement_fit=float(event.get("procurement_fit_score") or 0)

    revenue=.42+.24*fit+.18*rel+.10*mat
    if t=="procurement_notice": revenue=.30+.45*procurement_fit+.15*rel
    if t in {"distribution_agreement","ma_acquisition","market_expansion"}: revenue+=.08
    margin=.42+.18*fit+(.20 if t in HIGH_MARGIN_TYPES else .06)
    recurrence=.24+(.46 if t in RECURRING_TYPES else .12)
    if {"Cybersecurity","SASE/SSE","Observability","Cloud"}.intersection(techs): recurrence+=.08
    time_to_revenue=.72 if t in FAST_TYPES else (.52 if t in {"partnership","certification","managed_service"} else .38)
    effort=.46
    if t in {"procurement_notice","customer_reference","known_exploited_vulnerability"}: effort=.38
    if t in {"ma_acquisition","market_expansion","partnership"}: effort=.60
    if scope not in {"ES","PT","IBERIA"}: time_to_revenue-=.14; effort+=.08
    if impact=="threat": revenue=.55; recurrence=.45

    revenue=max(.05,min(1.0,revenue));margin=max(.05,min(1.0,margin));recurrence=max(.05,min(1.0,recurrence));time_to_revenue=max(.05,min(1.0,time_to_revenue));effort=max(.05,min(1.0,effort))
    econ=.28*revenue+.22*margin+.20*recurrence+.18*time_to_revenue+.12*(1-effort)
    band="HIGH" if econ>=.72 else ("MEDIUM" if econ>=.56 else "LOW")
    return {
        "economic_priority_score":round(econ,3),"economic_potential":band,
        "revenue_potential":round(revenue,3),"margin_potential":round(margin,3),"recurrence_potential":round(recurrence,3),
        "time_to_revenue_score":round(time_to_revenue,3),"enablement_effort_score":round(effort,3),
        "economic_note":"Proxy relativo basado en tipo de evento, fit tecnológico, alcance y recurrencia. No representa euros hasta integrar datos internos de pipeline/margen."
    }


def build_decisions(events: Iterable[Mapping[str,Any]], policy: Mapping[str,Any]) -> Dict[str,Any]:
    floor_m=float(policy.get("materiality_floor_recommendation",.68));floor_c=float(policy.get("confidence_floor_recommendation",.72));ranked=[]
    for e0 in events:
        e=dict(e0);m=float(e.get("materiality") or 0);c=float(e.get("confidence") or 0);rel=float(e.get("westcon_relevance") or 0);fit=float(e.get("strategic_fit") or .5)
        if m<floor_m or c<floor_c or rel<.45:continue
        t=str(e.get("event_type") or "")
        if t in {"unknown","financial_performance","hiring","leadership_change","award","strategy","technology_trend"} and m<.88: continue
        if t=="ma_rumor" and (m<.76 or c<.74): continue
        # Broad public-sector IT is evidence, not an automatic business recommendation.
        if t in {"procurement_notice","procurement_award"} and float(e.get("procurement_fit_score") or 0)<.50: continue
        impact=_impact(e)
        if impact=="context": continue
        # High-impact calls need stronger evidence: primary/direct or corroboration.
        sources=e.get("corroborating_sources") or ([e.get("source")] if e.get("source") else [])
        corroboration=int(e.get("corroboration_count") or len(sources) or 0)
        direct=bool(e.get("direct_evidence"));grade=str(e.get("evidence_grade") or "D")
        if impact in {"opportunity","threat"} and not direct and corroboration<2 and grade not in {"A","B"}:
            impact="watch"
        score=round(.36*m+.25*c+.22*rel+.17*fit,3)
        econ=_economic_profile(e,impact)
        combined=round(.72*score+.28*float(econ["economic_priority_score"]),3)
        prio=_priority(combined,impact)
        urls=e.get("corroborating_urls") or ([e.get("url")] if e.get("url") else [])
        ranked.append({
            "decision_id":"d_"+str(e.get("event_id")),"impact":impact,"priority":prio,"priority_score":combined,"evidence_priority_score":score,
            "title":e.get("title"),"entity_name":e.get("entity_name"),"object_entity":e.get("object_entity"),"event_type":t,
            "technology_domains":e.get("technology_domains") or [],"market_scope":e.get("market_scope"),"materiality":m,"confidence":c,"westcon_relevance":rel,
            "strategic_fit":fit,"evidence_grade":grade,"procurement_fit_score":e.get("procurement_fit_score"),
            "why":f"Evento {t}: materialidad {m:.2f}, fit estratégico {fit:.2f}, relevancia Westcon/Iberia {rel:.2f}, confianza {c:.2f}.","recommended_action":decision_hint(e),
            "monetization":MONETIZATION.get(t,"Validar impacto comercial y convertirlo en campaña, servicio o acción de canal solo si la evidencia lo soporta."),
            "kpi":KPI.get(t,"pipeline influenciado; acciones completadas; cambio de confianza/materialidad"),"owner_hint":_owner(t),"horizon":"0–30 días" if prio=="P1" else ("30–90 días" if prio in {"P2","P3"} else "90–180 días"),
            "evidence_sources":sources,"evidence_urls":urls,"sources":sources,"source_count":len(sources),
            "counter_evidence":"Buscar evidencia primaria y señales que contradigan alcance, relación o relevancia antes de decisiones de alto impacto.",
            "change_trigger":"Recalcular si cambia la relación de canal, aparece evidencia Iberia, se confirma una fuente primaria o la materialidad cae por obsolescencia.",
            **econ
        })
    ranked.sort(key=lambda x:(x["priority_score"],x["economic_priority_score"],x["confidence"]),reverse=True)
    impacts=Counter(x["impact"] for x in ranked);types=Counter(x["event_type"] for x in ranked);priorities=Counter(x["priority"] for x in ranked);econ=Counter(x["economic_potential"] for x in ranked)
    return {"meta":{"generated_at":datetime.now(timezone.utc).isoformat(),"decision_count":len(ranked),"impact_counts":dict(impacts),"event_type_counts":dict(types),"priority_counts":dict(priorities),"economic_potential_counts":dict(econ)},"decisions":ranked[:160]}


def build_briefing(events: Iterable[Mapping[str,Any]], decisions: Mapping[str,Any]) -> Dict[str,Any]:
    es=list(events);ds=list(decisions.get("decisions") or []);scopes=Counter(str(e.get("market_scope")) for e in es);types=Counter(str(e.get("event_type")) for e in es);tech=Counter(t for e in es for t in (e.get("technology_domains") or []));prio=Counter(str(d.get("priority")) for d in ds);econ=Counter(str(d.get("economic_potential")) for d in ds);grades=Counter(str(d.get("evidence_grade")) for d in ds)
    max_econ=max([float(d.get("economic_priority_score") or 0) for d in ds] or [0])
    direct_count=sum(1 for d in ds if str(d.get("evidence_grade"))=="A" or int(d.get("source_count") or 0)>=2)
    return {"generated_at":datetime.now(timezone.utc).isoformat(),"headline_metrics":{"events":len(es),"high_materiality_events":sum(float(e.get("materiality") or 0)>=.70 for e in es),"iberia_events":sum(str(e.get("market_scope")) in {"ES","PT","IBERIA"} for e in es),"actionable_decisions":len(ds),"threats":sum(x.get("impact")=="threat" for x in ds),"opportunities":sum(x.get("impact")=="opportunity" for x in ds),"watches":sum(x.get("impact")=="watch" for x in ds),"p1":prio.get("P1",0),"p2":prio.get("P2",0),"high_economic_potential":econ.get("HIGH",0),"medium_economic_potential":econ.get("MEDIUM",0),"max_economic_priority_score":round(max_econ,3),"strong_evidence_decisions":direct_count},"decision_evidence_grades":dict(grades),"top_event_types":types.most_common(12),"top_technologies":tech.most_common(10),"scope_mix":dict(scopes),"top_decisions":ds[:12]}
