from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .common import clamp, dedupe_evidence, evidence_reference, load_json, norm, number, stable_id, unique


ACTION_RANK = {"ACTUAR": 4, "PREPARAR / VALIDAR": 3, "INVESTIGAR": 2, "VIGILAR": 1}

OWNER_BY_EVENT = {
    "procurement_notice": "Comercial / PSM / Preventa",
    "procurement_award": "Comercial / PSM / Inteligencia de negocio",
    "distribution_agreement": "Dirección / PSM",
    "pricing_licensing": "PSM / Comercial / Finanzas",
    "end_of_sale": "PSM / Ingeniería / Servicios",
    "security_incident": "Ingeniería / Servicios / PSM",
    "operational_incident": "Ingeniería / Servicios",
    "managed_service": "Servicios / Ingeniería / Comercial",
    "service_launch": "Servicios / Marketing / Comercial",
    "partnership": "PSM / Comercial / Preventa",
    "certification": "Preventa / Ingeniería / PSM",
    "capability_expansion": "Dirección / Ingeniería / Servicios",
}


def _band(score: float) -> str:
    return "alta" if score >= 0.82 else "media" if score >= 0.62 else "baja"


def _confidence(score: float, label: str, explanation: str) -> dict[str, Any]:
    score = round(clamp(score), 3)
    return {"score": score, "band": _band(score), "label": label, "explanation": explanation}


def _risk(score: float, explanation: str) -> dict[str, Any]:
    score = round(clamp(score), 3)
    band = "bajo" if score <= 0.35 else "medio" if score <= 0.65 else "alto"
    return {"score": score, "band": band, "explanation": explanation}


def _relative(score: float, explanation: str = "Indicador relativo; no es forecast ni cifra financiera.") -> dict[str, Any]:
    score = round(clamp(score) * 100)
    return {"score": score, "band": "alto" if score >= 70 else "medio" if score >= 45 else "bajo", "explanation": explanation}


def _services(technologies: Iterable[str], event_type: str = "") -> list[str]:
    blob = norm(" ".join(technologies) + " " + event_type)
    result: list[str] = []
    if any(token in blob for token in ("cyber", "security", "soc", "identity", "sase")):
        result.extend(["Assessment de seguridad", "Diseño de arquitectura", "PoC / validación técnica", "Attach de servicios gestionados"])
    if any(token in blob for token in ("network", "naas", "conectividad")):
        result.extend(["Assessment de red", "Diseño multivendor", "Staging y configuración", "Lifecycle de red"])
    if any(token in blob for token in ("cloud", "data center", "observability")):
        result.extend(["Cloud readiness", "Observabilidad", "Optimización y FinOps", "Operación gestionada"])
    if any(token in blob for token in ("ai", "automation")):
        result.extend(["Workshop de casos de uso", "Gobierno y seguridad de IA", "Automatización operativa"])
    if "procurement" in event_type:
        result.extend(["Lectura técnica de pliegos", "Diseño y BOM", "Soporte al partner en oferta"])
    return unique(result)[:6] or ["Discovery técnico-comercial", "Validación de oportunidad"]


def _recommendation(
    *, candidate_id: str, title: str, action: str, why: str, why_now: str,
    evidence: list[dict[str, Any]], fact_score: float, interpretation_score: float,
    action_risk: float, action_type: str, impact: float, urgency: str, effort: str,
    horizon: str, owner: str, vendors: Iterable[str] = (), integrators: Iterable[str] = (),
    distributors: Iterable[str] = (), technologies: Iterable[str] = (), risks: Iterable[str] = (),
    missing: Iterable[str] = (), change_evidence: str = "", target: str = "",
) -> dict[str, Any]:
    evidence, _ = dedupe_evidence(evidence)
    refs = [evidence_reference(row) for row in evidence if row.get("url")]
    recurrence = 0.72 if any(token in norm(" ".join(technologies)) for token in ("cloud", "sase", "soc", "managed", "observability", "naas")) else 0.52
    margin = 0.68 if any("servic" in norm(item) or "assessment" in norm(item) or "poc" in norm(item) for item in _services(technologies)) else 0.48
    combined = min(fact_score, interpretation_score)
    return {
        "recommendation_id": stable_id("rec", candidate_id, action), "candidate_id": candidate_id,
        "title": title, "action": action, "why": why, "why_now": why_now,
        "evidence": refs,
        "fact_confidence": _confidence(fact_score, "Confianza en los hechos", "Mide si los hechos citados están demostrados por las fuentes enlazadas."),
        "interpretation_confidence": _confidence(interpretation_score, "Confianza en la interpretación", "Mide cuánto soportan esos hechos la lectura de negocio propuesta; no reutiliza la confianza factual."),
        "action_risk": _risk(action_risk, "Riesgo de actuar antes de completar la información pendiente; condiciona el tipo de acción mostrado."),
        "confidence": {"score": round(clamp(combined), 3), "band": _band(combined), "explanation": "La confianza ejecutiva toma la menor entre hecho e interpretación; el riesgo de acción se muestra aparte."},
        "action_type": action_type,
        "impact_potential": _relative(impact, "Impacto relativo por relevancia, urgencia, alcance y posibilidad de attach; no representa ingresos."),
        "urgency": urgency, "effort": effort, "horizon": horizon,
        "proposed_owner": owner,
        "vendors_involved": unique(vendors), "integrators_involved": unique(integrators),
        "distributors_involved": unique(distributors), "technologies": unique(technologies),
        "potential_services": _services(technologies),
        "recurring_revenue_potential": _relative(recurrence),
        "relative_margin_potential": _relative(margin),
        "risks": unique(risks) or ["Interpretar una señal pública como demanda interna confirmada."],
        "missing_information": unique(missing) or ["Validación interna de pipeline, margen, partner y capacidad disponible."],
        "evidence_that_would_change_recommendation": change_evidence or "Nueva evidencia primaria contradictoria, pérdida de vigencia o datos internos que demuestren bajo encaje económico.",
        "sources": unique(ref["source"] for ref in refs),
        "source_dates": unique(ref["date"] for ref in refs if ref.get("date")),
        "target": target,
        "economic_disclaimer": "Potencial, recurrencia y margen son indicadores relativos; no son forecasts ni cifras financieras.",
        "audit_status": "PENDING",
    }


def _market_candidates(root: Path) -> list[dict[str, Any]]:
    facts = load_json(root / "data/market_reality.json", {}).get("facts", []) or []
    candidates: list[dict[str, Any]] = []
    for fact in facts:
        confidence = number(fact.get("confidence"), 50) / 100
        if confidence < 0.7 or not fact.get("url"):
            continue
        tags = list(fact.get("tags") or [])
        technologies = unique(tags + list(fact.get("vendors") or []))
        blob = norm(" ".join(tags) + " " + str(fact.get("title")))
        if any(token in blob for token in ("incident", "nis2", "soc", "ot", "iot")):
            action = "Preparar en 30 días un play de resiliencia SOC/OT para banca, transporte y energía; validar con dos integradores la capacidad gestionada y seleccionar un caso de cliente para PoC."
            title = "Convertir el aumento de incidentes en un play SOC/OT verificable"
            owner, impact, urgency = "Servicios / Ingeniería / Comercial", 0.84, "Alta"
            missing = ["Integradores con SOC/OT operativo en ES/PT", "Attach y margen internos", "Caso de cliente y criterio de PoC"]
        elif any(token in blob for token in ("skill", "adopcion", "adoption", "especialistas")):
            action = "Validar un paquete repetible de assessment, arquitectura y capacitación para acelerar adopción de cloud, IA y automatización en partners Iberia; elegir dos cuentas piloto antes de invertir."
            title = "Cerrar la brecha de adopción con servicios repetibles"
            owner, impact, urgency = "Dirección / Servicios / Marketing", 0.78, "Media"
            missing = ["Demanda interna y pipeline por tecnología", "Partners piloto", "Coste y capacidad de enablement"]
        elif any(token in blob for token in ("market size", "competition", "mercado", "crecimiento")):
            action = "Validar por ES y PT dónde Westcon puede diferenciarse con servicios y ecosistema, comparando tres plays concretos frente al solape de catálogo antes de ampliar inversión."
            title = "Responder al crecimiento de mercado con diferenciación medible"
            owner, impact, urgency = "Dirección / PSM / Servicios", 0.75, "Media"
            missing = ["Pipeline y margen por play", "Benchmark competitivo interno", "Capacidad de entrega por país"]
        else:
            continue
        candidates.append(_recommendation(
            candidate_id=f"market:{fact.get('id')}", title=title, action=action,
            why=str(fact.get("summary") or fact.get("title")), why_now=str(fact.get("implication") or "La señal pública es vigente y material para Iberia."),
            evidence=[fact], fact_score=confidence, interpretation_score=min(0.86, confidence * 0.76 + 0.16),
            action_risk=0.34, action_type="PREPARAR / VALIDAR", impact=impact, urgency=urgency,
            effort="Medio", horizon="30 días", owner=owner, vendors=fact.get("vendors") or [], technologies=technologies,
            risks=["Diseñar una oferta sin demanda interna validada.", "Confundir crecimiento de mercado con cuota accesible para Westcon."],
            missing=missing, target=fact.get("country") or fact.get("scope") or "IBERIA",
        ))
    return candidates[:6]


def _event_action(event: Mapping[str, Any]) -> tuple[str, str, str, float, str, str, list[str], list[str]]:
    event_type = str(event.get("event_type") or "")
    entity = str(event.get("entity_name") or "la entidad")
    object_entity = str(event.get("object_entity") or "")
    buyer = str(event.get("buyer_name") or "el comprador")
    winner = str(event.get("winner_name") or entity)
    if event_type == "procurement_notice":
        return (
            "ACTUAR", f"Calificar en cinco días el pliego de {buyer}: confirmar tecnologías, fecha límite, partner elegible y encaje con portfolio; registrar una decisión bid/no-bid con responsable.",
            "Dirección procedimental de bajo riesgo sobre una licitación pública vigente.", 0.84, "Alta", "Ahora",
            ["Requisitos y presupuesto del pliego", "Partner con acceso a la cuenta", "Margen y capacidad de preventa"],
            ["Consumir preventa en una licitación sin fit real.", "Plazo o requisitos incompatibles."],
        )
    if event_type == "procurement_award":
        return (
            "PREPARAR / VALIDAR", f"Extraer del contrato adjudicado a {winner} para {buyer} la arquitectura, ciclo de renovación y cuentas homólogas; decidir si existe un play replicable sin tratar la adjudicación cerrada como oportunidad abierta.",
            "Aprendizaje comercial de bajo riesgo a partir de una adjudicación oficial.", 0.70, "Media", "30 días",
            ["Tecnologías y fabricantes realmente suministrados", "Duración y renovación", "Cuentas públicas homólogas"],
            ["Inferir fabricantes no citados.", "Confundir adjudicación cerrada con pipeline disponible."],
        )
    if event_type == "distribution_agreement":
        return (
            "PREPARAR / VALIDAR", f"Verificar por España y Portugal el alcance del acuerdo de distribución de {entity}{' con ' + object_entity if object_entity else ''}; cuantificar solape y preparar una respuesta por fabricante solo si la relación está vigente.",
            "Validación competitiva antes de responder comercialmente.", 0.80, "Alta", "30 días",
            ["Países y líneas cubiertas", "Fecha efectiva", "Solape real con Westcon", "Impacto en partners"],
            ["Responder a un acuerdo global sin efecto Iberia.", "Asumir linecard completa por una nota de prensa."],
        )
    if event_type in {"pricing_licensing", "end_of_sale"}:
        return (
            "PREPARAR / VALIDAR", f"Evaluar con PSM y Servicios el cambio de {entity}: identificar base afectada, renovaciones próximas y alternativa técnica; publicar una guía de impacto solo tras confirmar alcance Iberia.",
            "Preparación de lifecycle/licensing con exposición controlada.", 0.74, "Alta", "30 días",
            ["Base instalada y renovaciones internas", "SKU/licencia y fecha efectiva", "Alternativas y esfuerzo de migración"],
            ["Comunicar impacto antes de confirmar el alcance.", "Subestimar coste de migración o soporte."],
        )
    if event_type in {"security_incident", "operational_incident"}:
        return (
            "VIGILAR", f"Confirmar con {entity} el alcance técnico e Iberia del incidente, revisar exposición en partners y clientes y elevar a acción solo si existe afectación, advisory primario o cambio de riesgo.",
            "Vigilancia técnica; no convierte una noticia en alarma comercial.", 0.72, "Alta", "Ahora",
            ["Advisory primario", "Productos/versiones afectados", "Exposición de clientes y partners"],
            ["Amplificar una señal no confirmada.", "Mezclar vulnerabilidad con explotación activa."],
        )
    if event_type in {"managed_service", "service_launch", "capability_expansion", "certification", "partnership"}:
        return (
            "PREPARAR / VALIDAR", f"Validar el alcance Iberia de la nueva capacidad de {entity} y elegir un integrador y una cuenta para un workshop; definir oferta, attach y KPI antes de lanzar campaña.",
            "Prueba comercial acotada antes de escalar una capacidad pública.", 0.73, "Media", "Trimestre",
            ["Disponibilidad ES/PT", "Integrador capacitado", "Cliente/caso", "Economics internos"],
            ["Lanzar una campaña sin capacidad local.", "Confundir partnership global con preparación comercial."],
        )
    return (
        "VIGILAR", f"Revalidar la señal sobre {entity} en una fuente primaria y medir su efecto en portfolio, partners y servicios; no escalar inversión hasta disponer de alcance Iberia.",
        "Seguimiento de señal material todavía insuficiente para una preparación comercial.", 0.58, "Media", "Trimestre",
        ["Fuente primaria", "Alcance ES/PT", "Efecto en portfolio o canal"],
        ["Consumir atención ejecutiva sin materialidad confirmada."],
    )


def _event_candidates(root: Path) -> list[dict[str, Any]]:
    events = {row.get("event_id"): row for row in load_json(root / "data/v32/events.json", {}).get("events", []) or []}
    decisions = load_json(root / "data/v32/decisions.json", {}).get("decisions", []) or []
    candidates: list[dict[str, Any]] = []
    for decision in sorted(decisions, key=lambda row: number(row.get("priority_score")), reverse=True):
        event = events.get(str(decision.get("decision_id") or "").removeprefix("d_"))
        if not event or not event.get("url"):
            continue
        materiality = number(event.get("materiality"))
        fact_score = number(event.get("confidence"))
        if materiality < 0.62 or fact_score < 0.55:
            continue
        action_type, action, rationale, impact, urgency, horizon, missing, risks = _event_action(event)
        interpretation = min(0.92, fact_score * 0.68 + number(event.get("strategic_fit")) * 0.24 + materiality * 0.08)
        risk = 0.24 if action_type == "ACTUAR" else 0.34 if action_type == "PREPARAR / VALIDAR" else 0.18
        if action_type == "ACTUAR" and not (event.get("direct_evidence") and fact_score >= 0.82 and interpretation >= 0.68 and risk <= 0.35):
            action_type = "PREPARAR / VALIDAR"
            action = "Validar los requisitos, vigencia y encaje interno antes de ejecutar: " + action[0].lower() + action[1:]
        entity_type = event.get("entity_type")
        vendors = [event.get("entity_name")] if entity_type == "vendor" else []
        integrators = [event.get("entity_name")] if entity_type == "integrator" else []
        candidates.append(_recommendation(
            candidate_id=f"event:{event.get('event_id')}", title=f"{action_type.title()} — {event.get('title')}",
            action=action, why=f"{event.get('title')}. {event.get('summary') or rationale}",
            why_now=f"Publicado el {event.get('published_at')}; materialidad {round(materiality * 100)}/100 y alcance {event.get('market_scope') or 'por validar'}.",
            evidence=[event], fact_score=fact_score, interpretation_score=interpretation, action_risk=risk,
            action_type=action_type, impact=impact, urgency=urgency, effort="Bajo" if action_type in {"ACTUAR", "VIGILAR"} else "Medio",
            horizon=horizon, owner=OWNER_BY_EVENT.get(str(event.get("event_type")), "Dirección / PSM"),
            vendors=vendors, integrators=integrators, technologies=event.get("technology_domains") or [],
            risks=risks, missing=missing,
            change_evidence="Un desmentido, cierre/cancelación del expediente, pérdida de vigencia o datos internos sin encaje cambiarían la acción.",
            target=event.get("market_scope") or "GLOBAL",
        ))
    return candidates[:10]


def _entity_candidates(entities: Mapping[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    integrators = sorted(
        [row for row in entities.get("integrators", []) if row.get("evidence") and row.get("entity_tier") in {"T1", "T2"}],
        key=lambda row: (number(row.get("activation_priority")), number(row.get("strategic_importance_score"))), reverse=True,
    )
    for row in integrators[:5]:
        vendors = row.get("vendors") or []
        gaps = row.get("research_gaps") or []
        vendor_text = ", ".join(vendors[:4]) if vendors else "los fabricantes Westcon compatibles"
        action = (
            f"Validar con {row.get('name')} un plan de activación de 30 días: confirmar relación y nivel con {vendor_text}, seleccionar un play y una cuenta, y cerrar los gaps de {', '.join(gaps[:2]) or 'economics internos'} antes de campaña."
        )
        fact = number(row.get("confidence"))
        interpretation = min(0.86, fact * 0.66 + number(row.get("activation_priority")) / 100 * 0.24 + number(row.get("westcon_relevance")) / 100 * 0.10)
        candidates.append(_recommendation(
            candidate_id=f"entity:{row.get('entity_id')}", title=f"Validar activación con {row.get('name')}", action=action,
            why=f"Integrador {row.get('entity_tier')} con relevancia para Westcon {row.get('westcon_relevance')}/100, prioridad de activación {row.get('activation_priority')}/100 y cobertura pública {row.get('coverage', {}).get('score')}/100.",
            why_now=f"Momentum 90 días {row.get('momentum_90d', {}).get('score')}/100; quedan {len(gaps)} áreas de información pendientes.",
            evidence=row.get("evidence", [])[:4], fact_score=fact, interpretation_score=interpretation, action_risk=0.32,
            action_type="PREPARAR / VALIDAR", impact=min(0.88, number(row.get("activation_priority")) / 100 + 0.12),
            urgency="Alta" if number(row.get("activation_priority")) >= 70 else "Media", effort="Medio", horizon="30 días",
            owner="Comercial / PSM / Preventa", vendors=vendors, integrators=[row.get("name")],
            technologies=row.get("technology_focus") or [],
            risks=["Relaciones públicas no equivalen a preferencia de compra.", "No confirmar cuenta, competencia ni disponibilidad de especialistas."],
            missing=gaps + ["Pipeline, margen y sponsor interno"],
            change_evidence="Una relación de fabricante no vigente, falta de interés del integrador o ausencia de cuenta/pipeline reduciría la prioridad.",
            target=row.get("scope") or "IBERIA",
        ))
    distributors = sorted(
        [row for row in entities.get("distributors", []) if row.get("evidence") and norm(row.get("name")) not in {"westcon comstor", "comstor"}],
        key=lambda row: (number(row.get("competitive_response_priority")), number(row.get("strategic_importance_score"))), reverse=True,
    )
    for row in distributors[:3]:
        overlap = row.get("westcon_overlap") or []
        action = f"Verificar por ES/PT el linecard y los servicios de {row.get('name')}; contrastar el solape {', '.join(overlap[:5]) or 'todavía no demostrado'} y preparar una respuesta diferenciada solo en los fabricantes y plays confirmados."
        fact = number(row.get("confidence"))
        interpretation = min(0.84, fact * 0.68 + number(row.get("competitive_response_priority")) / 100 * 0.22 + number(row.get("strategic_importance_score")) / 100 * 0.10)
        candidates.append(_recommendation(
            candidate_id=f"entity:{row.get('entity_id')}", title=f"Calibrar la presión competitiva de {row.get('name')}", action=action,
            why=f"Mayorista {row.get('entity_tier')} con importancia relativa {row.get('strategic_importance_score')}/100, presión {row.get('competitive_pressure')}/100 y {len(overlap)} fabricantes en solape público.",
            why_now=f"Prioridad de respuesta {row.get('competitive_response_priority')}/100; momentum 90 días {row.get('momentum_90d', {}).get('score')}/100.",
            evidence=row.get("evidence", [])[:4], fact_score=fact, interpretation_score=interpretation, action_risk=0.30,
            action_type="PREPARAR / VALIDAR" if number(row.get("competitive_response_priority")) >= 45 else "VIGILAR",
            impact=min(0.9, number(row.get("strategic_importance_score")) / 100 + 0.1), urgency="Alta" if number(row.get("competitive_response_priority")) >= 70 else "Media",
            effort="Bajo", horizon="30 días", owner="Dirección / PSM", vendors=overlap, distributors=[row.get("name")],
            technologies=row.get("technology_focus") or [],
            risks=["Confundir solape de catálogo con presión comercial efectiva.", "Mezclar ámbito global con presencia operativa ES/PT."],
            missing=row.get("research_gaps") or [],
            change_evidence="Linecard por país, datos internos de win/loss o evidencia de baja actividad cambiarían la respuesta.", target=row.get("scope") or "IBERIA",
        ))
    return candidates


def _relationship_candidates(entities: Mapping[str, Any], relationships: Mapping[str, Any]) -> list[dict[str, Any]]:
    profiles = {norm(row.get("name")): row for row in entities.get("integrators", [])}
    rows = [row for row in relationships.get("integrator_vendor", []) if row.get("status") in {"PROBABLE", "RESEARCH PRIORITY"} and row.get("entity_tier") in {"T1", "T2"}]
    rows.sort(key=lambda row: (number(row.get("priority_score")), number(row.get("westcon_relevance"))), reverse=True)
    candidates: list[dict[str, Any]] = []
    for row in rows[:4]:
        profile = profiles.get(norm(row.get("integrator"))) or {}
        support = row.get("evidence") or profile.get("evidence") or []
        if not support:
            continue
        relation_has_evidence = bool(row.get("evidence"))
        action_type = "PREPARAR / VALIDAR" if row.get("status") == "PROBABLE" else "INVESTIGAR"
        action = (
            f"Comprobar la relación {row.get('integrator')} × {row.get('vendor')} en partner locator, certificaciones y casos ES/PT; registrar país, nivel y vigencia. "
            + ("Preparar una conversación de activación si se confirma." if relation_has_evidence else "No presentar whitespace como hecho hasta obtener evidencia de la relación o de su ausencia comercial interna.")
        )
        fact = number((row.get("fact_confidence") or {}).get("score")) if relation_has_evidence else number(profile.get("confidence"))
        interpretation = min(0.76, fact * 0.62 + number(row.get("priority_score")) / 100 * 0.23 + number(row.get("westcon_relevance")) / 100 * 0.15)
        candidates.append(_recommendation(
            candidate_id=f"relationship:{row.get('relationship_id')}", title=f"{action_type.title()} — {row.get('integrator')} × {row.get('vendor')}",
            action=action,
            why=(f"Existe evidencia pública probable con intensidad {row.get('relationship_intensity')}/100." if relation_has_evidence else f"El integrador es material, pero la relación concreta carece de evidencia pública suficiente; prioridad {row.get('priority_score')}/100."),
            why_now=f"Estado v3.4: {row.get('status_label')}; última verificación {row.get('last_verified') or 'pendiente'}.",
            evidence=support[:4], fact_score=fact, interpretation_score=interpretation, action_risk=0.18,
            action_type=action_type, impact=min(0.8, number(row.get("priority_score")) / 100), urgency="Media", effort="Bajo", horizon="30 días",
            owner="PSM / Comercial / Preventa", vendors=[row.get("vendor")], integrators=[row.get("integrator")],
            technologies=row.get("technology_fit") or [],
            risks=["Afirmar una relación que solo es probable.", "Convertir ausencia de prueba pública en whitespace confirmado."],
            missing=["Partnership level", "Certificaciones vigentes", "Casos ES/PT", "Interés comercial y pipeline interno"],
            change_evidence="Un directorio oficial vigente elevaría la confianza; una confirmación interna de relación activa eliminaría la hipótesis de whitespace.",
            target=(row.get("geography") or {}).get("scope") or "IBERIA",
        ))
    return candidates


def _pair_candidates(root: Path, entities: Mapping[str, Any]) -> list[dict[str, Any]]:
    pairs = load_json(root / "data/v33/vendor_pair_intelligence.json", {}).get("pairs", []) or []
    facts = load_json(root / "data/market_reality.json", {}).get("facts", []) or []
    profile_evidence = [row for entity in entities.get("entities", []) for row in entity.get("evidence", [])]
    candidates: list[dict[str, Any]] = []
    for pair in sorted(pairs, key=lambda row: number(row.get("commercial_play_readiness")), reverse=True)[:5]:
        vendors = [pair.get("vendor_a"), pair.get("vendor_b")]
        support = [fact for fact in facts if set(vendors) & set(fact.get("vendors") or [])]
        if not support:
            support = [row for row in profile_evidence if any(norm(vendor) in norm(" ".join(str(row.get(key) or "") for key in ("title", "source"))) for vendor in vendors)]
        support, _ = dedupe_evidence(support)
        if not support:
            continue
        plays = pair.get("plays") or []
        action = f"Investigar un play {vendors[0]} + {vendors[1]} para {', '.join(plays[:2]) or 'una arquitectura multivendor'}: verificar integración documentada, dos integradores capaces, frontera de solape, attach y economics antes de habilitarlo comercialmente."
        evidence_strength = number(pair.get("evidence_strength"))
        interpretation = min(0.70, evidence_strength * 0.55 + number(pair.get("commercial_play_readiness")) * 0.30 + min(0.15, number(pair.get("shared_integrator_count")) * 0.05))
        candidates.append(_recommendation(
            candidate_id=f"pair:{pair.get('pair_id')}", title=f"Investigar play {vendors[0]} + {vendors[1]}", action=action,
            why=f"Complementariedad relativa {round(number(pair.get('synergy_score')) * 100)}/100, solape potencial {round(number(pair.get('potential_overlap_score')) * 100)}/100 y {pair.get('shared_integrator_count')} integradores compartidos detectados.",
            why_now=f"Preparación comercial relativa {round(number(pair.get('commercial_play_readiness')) * 100)}/100; la integración específica todavía no está demostrada.",
            evidence=support[:4], fact_score=min(0.9, max(number(row.get("confidence"), 0.65) / (100 if number(row.get("confidence")) > 1 else 1) for row in support)),
            interpretation_score=interpretation, action_risk=0.22, action_type="INVESTIGAR", impact=number(pair.get("commercial_play_readiness")),
            urgency="Media", effort="Medio", horizon="Trimestre", owner="PSM / Preventa / Servicios", vendors=vendors,
            technologies=plays,
            risks=["Asumir integración técnica sin documentación.", "No definir frontera de solape ni ownership comercial."],
            missing=["Integración oficial", "Integradores certificados", "Cuenta/caso", "Arquitectura y BOM", "Margen, attach y time-to-revenue"],
            change_evidence="Documentación conjunta, caso Iberia y dos integradores preparados elevarían la acción; solape no gobernable o economics débiles la descartarían.",
            target="IBERIA",
        ))
    return candidates[:3]


def build_recommendations(root: Path, entities: Mapping[str, Any], relationships: Mapping[str, Any], policy: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    candidates = (
        _market_candidates(root) + _event_candidates(root) + _entity_candidates(entities)
        + _relationship_candidates(entities, relationships) + _pair_candidates(root, entities)
    )
    max_published = int(policy.get("recommendations", {}).get("max_published", 32))
    deduped: dict[str, dict[str, Any]] = {}
    dispositions: list[dict[str, Any]] = []
    for recommendation in candidates:
        key = norm(recommendation.get("action"))
        if key in deduped:
            dispositions.append({"candidate_id": recommendation.get("candidate_id"), "disposition": "DESCARTAR / NO MOSTRAR", "reason": "Acción duplicada semánticamente."})
            continue
        if not recommendation.get("evidence"):
            dispositions.append({"candidate_id": recommendation.get("candidate_id"), "disposition": "DESCARTAR / NO MOSTRAR", "reason": "No hay evidencia enlazada; no puede publicarse."})
            continue
        deduped[key] = recommendation
    ranked = sorted(
        deduped.values(),
        key=lambda row: (ACTION_RANK.get(row.get("action_type"), 0), number((row.get("impact_potential") or {}).get("score")), number((row.get("confidence") or {}).get("score"))),
        reverse=True,
    )
    published = ranked[:max_published]
    for recommendation in ranked[max_published:]:
        dispositions.append({"candidate_id": recommendation.get("candidate_id"), "disposition": "DESCARTAR / NO MOSTRAR", "reason": "Fuera del límite de atención ejecutiva; permanece como candidato trazable."})
    for recommendation in published:
        recommendation["audit_status"] = "PASS"
        dispositions.append({"candidate_id": recommendation.get("candidate_id"), "recommendation_id": recommendation.get("recommendation_id"), "disposition": recommendation.get("action_type"), "reason": "Acción graduada según evidencia, interpretación y riesgo."})
    distribution = Counter(row.get("action_type") for row in published)
    document = {
        "meta": {
            "version": "3.4.0", "generated_at": datetime.now(timezone.utc).isoformat(),
            "published": len(published), "candidate_count": len(candidates), "action_distribution": dict(distribution),
            "paradigm": "La evidencia determina el tipo de acción; una señal material no desaparece por no superar un umbral único.",
            "economics": "Todos los indicadores económicos son relativos hasta cargar datos internos.",
        },
        "recommendations": published,
        "executive_top": published[:8],
    }
    return document, dispositions
