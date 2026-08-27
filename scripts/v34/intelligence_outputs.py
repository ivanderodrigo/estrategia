from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .common import age_days, clamp, dedupe_evidence, domain_of, evidence_reference, load_json, norm, number, stable_id, unique


def build_source_catalog(source_expansion: Mapping[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for source in source_expansion.get("sources", []) or []:
        dimensions = source.get("dimensions") or []
        blob = norm(" ".join(dimensions))
        source_class = source.get("class") or "secondary"
        priority = 100 if source_class in {"primary", "primary-public-service"} else 92 if "primary" in source_class else 78 if "secondary" in source_class else 58
        frequency = "daily" if any(token in blob for token in ("advisories", "vulnerabilities", "procurement", "incidents", "funding calls")) else "weekly" if any(token in blob for token in ("hiring", "relationship", "linecard", "customer", "partners", "technology change")) else "monthly" if any(token in blob for token in ("market", "financial", "investment", "companies")) else "quarterly"
        url = str(source.get("url") or "")
        access_policy = str(source.get("access_policy") or "public")
        method = "dynamic entity routing" if url.startswith("dynamic://") else "API/open data" if any(token in norm(access_policy) for token in ("api", "open data", "csv", "json", "xml")) else "public web/RSS"
        algorithms: list[str] = []
        if any(token in blob for token in ("relationship", "partner", "certification", "specialization", "linecard", "customer")):
            algorithms.extend(["relationship_state", "relationship_intensity", "integrator_activation", "distributor_pressure"])
        if any(token in blob for token in ("hiring", "skills", "employment")):
            algorithms.extend(["technology_hiring_momentum", "capability_demand", "vendor_motion_hypothesis"])
        if any(token in blob for token in ("procurement", "awards", "funding", "future demand")):
            algorithms.extend(["demand_signal", "renewal_hypothesis", "account_play"])
        if any(token in blob for token in ("security", "vulnerabilities", "advisories", "threat")):
            algorithms.extend(["threat_to_business_play", "portfolio_risk", "services_attach"])
        if any(token in blob for token in ("market", "financial", "investment", "funding", "acquisitions")):
            algorithms.extend(["market_momentum", "relative_economics", "new_vendor_watch"])
        rows.append({
            "source_id": source.get("id"), "name": source.get("name"), "url": url,
            "free_or_paid": "public metadata only" if "no_paid" in access_policy or "public_metadata_only" in access_policy else "free/public",
            "scope": source.get("scope") or [], "source_class": source_class,
            "dimensions": dimensions, "query_method": method,
            "recommended_frequency": frequency, "priority": priority,
            "reliability_rule": "La fiabilidad final depende del dato, fecha, geografía, directitud y corroboración; la clase de fuente no sustituye esas comprobaciones.",
            "access_policy": access_policy,
            "feeds": unique(algorithms) or ["source_discovery", "knowledge_gap"],
        })
    rows.sort(key=lambda row: (number(row.get("priority")), norm(row.get("name"))), reverse=True)
    return {
        "meta": {
            "version": "3.4.0", "generated_at": datetime.now(timezone.utc).isoformat(),
            "sources": len(rows), "target_range": "100-150",
            "principle": "Catálogo operativo gratuito/público; las fuentes premium solo aportan metadatos o resúmenes públicos y nunca se reconstruye contenido de pago.",
        },
        "sources": rows,
    }


def build_source_coverage(root: Path, entities: Mapping[str, Any], source_expansion: Mapping[str, Any]) -> dict[str, Any]:
    registry = load_json(root / "config/v31/source_registry.json", {}).get("sources", []) or []
    targeted_doc = load_json(root / "data/v33/targeted_evidence.json", {})
    targeted = targeted_doc.get("evidence", []) or []
    entity_index = {norm(row.get("name")): row for row in entities.get("entities", [])}
    source_health = load_json(root / "data/source_health.json", {}).get("sources", {}) or {}
    query_stats = targeted_doc.get("meta") or {}
    buckets: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    seen_urls: Counter[str] = Counter(str(row.get("url") or "") for row in targeted if row.get("url"))
    for evidence in targeted:
        entity = entity_index.get(norm(evidence.get("name"))) or {}
        country = entity.get("scope") or ("PT" if " portugal" in norm(evidence.get("query")) else "ES" if any(token in norm(evidence.get("query")) for token in (" spain", " espana")) else "UNKNOWN")
        source_kind = "primary" if evidence.get("source_grade") == "A" else "secondary-quality" if evidence.get("source_grade") == "B" else "aggregator/discovery"
        key = (str(evidence.get("entity_type") or entity.get("entity_type") or "unknown"), str(evidence.get("field") or "unknown"), str(country), source_kind)
        bucket = buckets.setdefault(key, {
            "entity_type": key[0], "dimension": key[1], "country": key[2], "source_type": key[3],
            "queries": set(), "evidence_accepted": 0, "quality_total": 0.0, "fresh_rows": 0,
            "duplicates": 0, "latencies": [], "errors": 0, "sources": set(),
        })
        if evidence.get("query"):
            bucket["queries"].add(str(evidence.get("query")))
        bucket["evidence_accepted"] += 1
        bucket["quality_total"] += number(evidence.get("confidence"), 0.5)
        if age_days(evidence.get("published_at") or evidence.get("date")) is not None and age_days(evidence.get("published_at") or evidence.get("date")) <= 365:
            bucket["fresh_rows"] += 1
        if evidence.get("url") and seen_urls[str(evidence.get("url"))] > 1:
            bucket["duplicates"] += 1
        domain = domain_of(evidence.get("url"))
        bucket["sources"].add(domain or str(evidence.get("source") or "unknown"))
        health = source_health.get(domain) or {}
        if health.get("latencyMsEma") is not None:
            bucket["latencies"].append(number(health.get("latencyMsEma")))
        bucket["errors"] += int(number(health.get("failures")))
    rows: list[dict[str, Any]] = []
    for bucket in buckets.values():
        accepted = int(bucket["evidence_accepted"])
        queries = len(bucket["queries"])
        rows.append({
            "entity_type": bucket["entity_type"], "dimension": bucket["dimension"], "country": bucket["country"], "source_type": bucket["source_type"],
            "queries": queries, "success_rate": round(min(1, accepted / max(1, queries)), 3),
            "evidence_accepted": accepted, "average_quality": round(bucket["quality_total"] / max(1, accepted), 3),
            "freshness_rate_365d": round(bucket["fresh_rows"] / max(1, accepted), 3),
            "duplication_rate": round(bucket["duplicates"] / max(1, accepted), 3),
            "average_latency_ms": round(sum(bucket["latencies"]) / len(bucket["latencies"]), 1) if bucket["latencies"] else None,
            "errors": bucket["errors"], "source_diversity": len(bucket["sources"]),
            "next_use_priority": round(clamp(0.30 * min(1, accepted / max(1, queries)) + 0.25 * bucket["quality_total"] / max(1, accepted) + 0.20 * bucket["fresh_rows"] / max(1, accepted) + 0.15 * min(1, len(bucket["sources"]) / 4) + 0.10 * (1 - min(1, bucket["duplicates"] / max(1, accepted)))), 3),
            "formula": "30% éxito + 25% calidad + 20% actualidad + 15% diversidad + 10% baja duplicación; errores y latencia se usan como restricciones operativas.",
        })
    rows.sort(key=lambda row: (row["next_use_priority"], row["evidence_accepted"]), reverse=True)
    expansion_sources = source_expansion.get("sources", []) or []
    return {
        "meta": {
            "version": "3.4.0", "generated_at": datetime.now(timezone.utc).isoformat(),
            "registered_sources_v31": len(registry), "v34_public_expansion_sources": len(expansion_sources),
            "total_public_source_candidates": len(registry) + len(expansion_sources),
            "planned_queries_last_run": query_stats.get("planned_queries", 0), "attempted_queries_last_run": query_stats.get("attempted_queries", 0),
            "accepted_evidence_last_run": query_stats.get("evidence_rows", 0), "errors_last_run": len(query_stats.get("errors") or []),
            "learning_granularity": "entidad × dimensión × país × tipo de fuente",
            "principle": "Una fuente fallida reduce prioridad temporal; no interrumpe el pipeline ni borra evidencias válidas previas.",
        },
        "coverage": rows,
        "source_expansion": expansion_sources,
        "audience_source_routes": source_expansion.get("audience_routes", []),
        "audience_source_rules": source_expansion.get("audience_rules", []),
    }


def build_history(root: Path) -> dict[str, Any]:
    events = load_json(root / "data/v32/events.json", {}).get("events", []) or []
    windows: dict[str, Any] = {}
    for days in (30, 90, 365):
        selected = [event for event in events if age_days(event.get("published_at")) is not None and age_days(event.get("published_at")) <= days]
        selected.sort(key=lambda row: (str(row.get("published_at") or ""), number(row.get("materiality"))), reverse=True)
        windows[str(days)] = {
            "days": days, "events": len(selected),
            "by_type": dict(Counter(event.get("event_type") or "unknown" for event in selected)),
            "by_scope": dict(Counter(event.get("market_scope") or "unknown" for event in selected)),
            "vendors": dict(Counter(event.get("entity_name") for event in selected if event.get("entity_type") == "vendor").most_common(12)),
            "integrators": dict(Counter(event.get("entity_name") for event in selected if event.get("entity_type") == "integrator").most_common(12)),
            "technologies": dict(Counter(technology for event in selected for technology in event.get("technology_domains") or []).most_common(12)),
            "changes": [{
                "event_id": event.get("event_id"), "date": event.get("published_at"), "type": event.get("event_type"),
                "entity": event.get("entity_name"), "scope": event.get("market_scope"), "title": event.get("title"),
                "materiality": event.get("materiality"), "confidence": event.get("confidence"), "source": event.get("source"), "url": event.get("url"),
            } for event in selected[:30]],
        }
    movement = load_json(root / "data/v33/relationship_movement.json", {})
    return {
        "meta": {
            "version": "3.4.0", "generated_at": datetime.now(timezone.utc).isoformat(),
            "method": "Ventanas móviles sobre fechas de evidencia; no se inventa una serie temporal cuando no existen snapshots comparables.",
        },
        "windows": windows,
        "relationship_movement": movement,
    }


ARCHITECTURE_TEMPLATES = [
    ("sase-sse", "SASE / SSE", "Reducir herramientas y políticas desconectadas para usuarios, sedes y cloud.", ["Acceso", "SSE", "SD-WAN", "Operación"], ["sase", "sse", "zero trust", "sd wan", "network"], ["Assessment SASE", "Workshop de políticas", "PoC multivendor", "Servicio gestionado"]),
    ("zero-trust", "Zero Trust", "Aplicar controles continuos de identidad, dispositivo, red y datos.", ["Identidad", "Postura", "Acceso", "Telemetría"], ["identity", "zero trust", "segmentation", "xdr"], ["Assessment Zero Trust", "Diseño de controles", "Plan de adopción", "Lifecycle"]),
    ("network-security", "Network + Security", "Diseñar red y seguridad como una arquitectura operable, no como silos.", ["Campus/WAN", "Seguridad", "Observabilidad", "Automatización"], ["network", "firewall", "ddos", "dns", "observability"], ["Assessment de red", "Diseño seguro", "Staging", "Soporte y lifecycle"]),
    ("modern-soc", "SOC moderno", "Mejorar detección y respuesta sin crecer linealmente en personas.", ["Telemetría", "Analítica", "Respuesta", "Operación gestionada"], ["soc", "xdr", "siem", "threat", "security"], ["SOC maturity assessment", "Integración de telemetría", "Use cases", "Managed SOC attach"]),
    ("ai-security", "AI Security", "Proteger datos, identidades, modelos y uso de IA; aplicar IA con gobierno a SecOps.", ["Datos/modelos", "Identidad", "Protección", "Gobierno"], ["ai", "data security", "identity", "api", "threat"], ["AI security workshop", "Threat model", "PoC", "Gobierno y operación"]),
    ("observability", "Observability", "Unificar experiencia, red, aplicación y seguridad con señal accionable.", ["Fuentes", "Ingesta", "Correlación", "Acción"], ["observability", "monitor", "visibility", "network", "xdr"], ["Assessment de observabilidad", "Diseño de telemetría", "Dashboard/KPI", "Operación gestionada"]),
    ("hybrid-cloud", "Hybrid Cloud", "Mover y operar cargas con seguridad, visibilidad y control de coste.", ["Workloads", "Conectividad", "Seguridad", "Operación"], ["cloud", "aws", "azure", "network", "security"], ["Cloud readiness", "Landing zone", "Seguridad cloud", "FinOps / operación"]),
    ("data-center", "Data Center", "Modernizar infraestructura manteniendo resiliencia y continuidad.", ["Compute/edge", "Red DC", "Seguridad", "Continuidad"], ["data center", "server", "switch", "network", "resilience"], ["Assessment DC", "Diseño y BOM", "Staging", "Migración y soporte"]),
    ("naas", "NaaS", "Convertir conectividad y operación en un servicio medible y recurrente.", ["Acceso", "Control", "Experiencia", "Lifecycle"], ["naas", "network", "wifi", "sd wan", "managed"], ["NaaS business case", "Diseño", "Onboarding", "Lifecycle gestionado"]),
    ("identity", "Identity", "Reducir riesgo y fricción con identidad como plano de control.", ["Directorio", "Acceso", "Privilegio", "Gobierno"], ["identity", "iam", "pam", "authentication", "zero trust"], ["Identity assessment", "Diseño IAM", "Migración", "Servicio de lifecycle"]),
    ("automation", "Automation", "Eliminar tareas repetitivas y acelerar cambios con control y trazabilidad.", ["Procesos", "Orquestación", "Políticas", "Medición"], ["automation", "rpa", "orchestration", "ai", "network"], ["Automation discovery", "Backlog priorizado", "MVP", "Operación y mejora continua"]),
    ("resilience", "Resilience", "Preparar continuidad ante incidentes, vulnerabilidades y fallos de proveedor.", ["Exposición", "Protección", "Recuperación", "Crisis"], ["resilience", "backup", "security", "ddos", "incident"], ["Resilience assessment", "Tabletop", "Arquitectura de recuperación", "Retainer / lifecycle"]),
]


def _vendor_candidates(vendors: list[Mapping[str, Any]], keywords: Iterable[str], limit: int = 7) -> list[dict[str, Any]]:
    scored: list[tuple[int, Mapping[str, Any]]] = []
    for vendor in vendors:
        blob = norm(f"{vendor.get('domain')} {' '.join(vendor.get('capabilities') or [])}")
        score = sum(1 for keyword in keywords if norm(keyword) in blob)
        if score:
            scored.append((score, vendor))
    scored.sort(key=lambda item: (item[0], norm(item[1].get("name"))), reverse=True)
    return [{"vendor": vendor.get("name"), "fit_basis": unique([keyword for keyword in keywords if norm(keyword) in norm(f"{vendor.get('domain')} {' '.join(vendor.get('capabilities') or [])}")])} for _, vendor in scored[:limit]]


def build_architectures(root: Path, entities: Mapping[str, Any]) -> dict[str, Any]:
    vendors = load_json(root / "data/vendor_intelligence.json", {}).get("vendors", []) or []
    facts = load_json(root / "data/market_reality.json", {}).get("facts", []) or []
    integrators = entities.get("integrators", []) or []
    architectures: list[dict[str, Any]] = []
    for architecture_id, title, problem, layer_names, keywords, services in ARCHITECTURE_TEMPLATES:
        candidates = _vendor_candidates(vendors, keywords)
        matching_integrators = [
            row for row in integrators
            if any(norm(keyword) in norm(" ".join((row.get("technology_focus") or []) + (row.get("competencies") or []) + (row.get("managed_services") or []))) for keyword in keywords)
        ]
        matching_integrators.sort(key=lambda row: (number(row.get("activation_priority")), number(row.get("confidence"))), reverse=True)
        supporting = [fact for fact in facts if any(norm(keyword) in norm(" ".join((fact.get("tags") or []) + [str(fact.get("title") or "")])) for keyword in keywords)]
        supporting = supporting[:4] or facts[:1]
        layers = []
        for index, layer_name in enumerate(layer_names):
            selected = candidates[index::len(layer_names)][:3] or candidates[:2]
            layers.append({
                "layer_id": f"{architecture_id}-layer-{index + 1}", "name": layer_name,
                "vendors": selected, "integration_status": "A VALIDAR",
                "note": "La asignación indica encaje funcional público; no afirma integración certificada entre fabricantes.",
            })
        evidence_score = sum(number(fact.get("confidence"), 60) / 100 for fact in supporting) / max(1, len(supporting))
        layer_coverage = sum(bool(layer.get("vendors")) for layer in layers) / len(layers)
        integrator_score = min(1, len(matching_integrators) / 4)
        readiness = round(clamp(0.35 * evidence_score + 0.30 * layer_coverage + 0.20 * integrator_score + 0.15 * (1 if len(candidates) >= 3 else len(candidates) / 3)), 3)
        architectures.append({
            "architecture_id": architecture_id, "title": title, "problem": problem,
            "opportunity": f"Crear una oferta repetible de {title} que combine arquitectura, enablement, PoC y servicios de ciclo de vida.",
            "layers": layers, "vendors": candidates,
            "integrations": [{"from": layers[index]["layer_id"], "to": layers[index + 1]["layer_id"], "status": "A VALIDAR"} for index in range(len(layers) - 1)],
            "integrators": [{"name": row.get("name"), "scope": row.get("scope"), "activation_priority": row.get("activation_priority"), "confidence": row.get("confidence")} for row in matching_integrators[:6]],
            "gaps": ["Integración oficial entre componentes", "Dos integradores con capacidad vigente", "Cuenta/caso Iberia", "BOM y modelo económico", "Frontera de solape y ownership"],
            "westcon_services": services,
            "monetization": ["Assessment", "Diseño/BOM", "PoC", "Enablement", "Servicios profesionales", "Lifecycle o servicio gestionado"],
            "recurrence": {"band": "alta" if any(token in norm(title) for token in ("soc", "naas", "observability", "sase", "cloud")) else "media", "basis": "Lifecycle, suscripción, soporte y/o operación gestionada; validar attach y margen internos."},
            "kpis": ["Integradores habilitados", "Oportunidades calificadas", "Tiempo a primera oportunidad", "Attach de servicios", "Ingresos recurrentes influenciados", "Cobertura de evidencias"],
            "risks": ["Asumir integración no documentada", "Solape funcional sin segmentación", "Falta de capacidad de entrega", "Economics internos no validados"],
            "readiness": {"score": round(readiness * 100), "band": "alta" if readiness >= 0.75 else "media" if readiness >= 0.55 else "baja", "formula": "35% evidencia de mercado + 30% capas cubiertas + 20% integradores compatibles + 15% amplitud de fabricantes; no es readiness comercial interna."},
            "evidence": [evidence_reference(fact) for fact in supporting],
            "diagram": {"nodes": [{"id": layer["layer_id"], "label": layer["name"]} for layer in layers], "edges": [{"from": layers[index]["layer_id"], "to": layers[index + 1]["layer_id"]} for index in range(len(layers) - 1)]},
            "originality": "Diagrama original generado por capas funcionales; no reproduce gráficos propietarios de analistas.",
        })
    architectures.sort(key=lambda row: number((row.get("readiness") or {}).get("score")), reverse=True)
    return {
        "meta": {"version": "3.4.0", "generated_at": datetime.now(timezone.utc).isoformat(), "architectures": len(architectures), "style": "original, business-first, non-proprietary", "caution": "Cada arquitectura es una hipótesis comercial a validar; la presencia de fabricantes en capas no prueba integración."},
        "architectures": architectures,
    }


def build_adaptive_queue(entities: Mapping[str, Any], relationships: Mapping[str, Any], source_coverage: Mapping[str, Any]) -> dict[str, Any]:
    learned = source_coverage.get("coverage", []) or []
    source_priority = max((number(row.get("next_use_priority")) for row in learned), default=0.5)
    queue: list[dict[str, Any]] = []
    sources = source_coverage.get("source_expansion", []) or []
    gap_dimensions = {
        "relevant_hiring": {"hiring", "skills_demand", "technology_priority", "channel_investment"},
        "vendors": {"relationship", "partnership_level", "certifications", "customers", "integrators"},
        "confirmed_linecard": {"linecard", "country_relation", "relationship"},
        "probable_linecard": {"linecard", "country_relation", "relationship"},
        "customers_public_cases": {"customers", "customer_cases", "verticals"},
        "specializations": {"specializations", "certifications", "partnership_level"},
        "managed_services": {"managed_services", "services", "msp", "mssp"},
    }
    for entity in entities.get("entities", []) or []:
        tier_weight = {"T1": 1.0, "T2": 0.72, "T3": 0.38}.get(entity.get("entity_tier"), 0.38)
        gap = 1 - number((entity.get("coverage") or {}).get("score")) / 100
        relevance = number(entity.get("westcon_relevance")) / 100
        staleness = 1.0 if not entity.get("last_verified") else min(1, number(age_days(entity.get("last_verified")), 365) / 365)
        business = number(entity.get("activation_priority") or entity.get("competitive_response_priority")) / 100
        gaps = entity.get("research_gaps") or []
        wanted_dimensions = set().union(*(gap_dimensions.get(gap, {gap}) for gap in gaps[:5])) if gaps else {"relationship"}
        recommended_sources = [
            {"source_id": source.get("id"), "name": source.get("name"), "class": source.get("class"), "dimensions": sorted(wanted_dimensions & set(source.get("dimensions") or []))}
            for source in sources if wanted_dimensions & set(source.get("dimensions") or [])
        ]
        recommended_sources.sort(key=lambda row: ({"primary": 4, "primary-public-service": 4, "primary-or-company": 3, "secondary-specialist": 2, "secondary-quality": 2, "aggregator": 1, "discovery": 1}.get(row.get("class"), 0), len(row.get("dimensions") or [])), reverse=True)
        priority = clamp(0.30 * tier_weight + 0.25 * gap + 0.16 * relevance + 0.12 * staleness + 0.12 * business + 0.05 * source_priority)
        queue.append({
            "queue_id": stable_id("rq", entity.get("entity_id"), entity.get("research_gaps")),
            "entity": entity.get("name"), "entity_type": entity.get("entity_type"), "entity_tier": entity.get("entity_tier"),
            "priority_score": round(priority, 3), "gaps": gaps,
            "priority_breakdown": {"tier": round(tier_weight, 3), "knowledge_gap": round(gap, 3), "westcon_relevance": round(relevance, 3), "staleness": round(staleness, 3), "business_value": round(business, 3), "best_source_learning": round(source_priority, 3)},
            "formula": "30% tier + 25% información pendiente + 16% relevancia Westcon + 12% antigüedad + 12% valor empresarial + 5% probabilidad aprendida de fuente",
            "next_action": f"Investigar {', '.join((entity.get('research_gaps') or [])[:3]) or 'evidencia de vigencia'} con prioridad en fuente primaria y registrar resultado negativo si no aparece.",
            "recommended_sources": recommended_sources[:8],
            "query_plan": [
                f'"{entity.get("name")}" (partner OR certification OR specialization OR case study) (Spain OR Portugal)',
                f'"{entity.get("name")}" (jobs OR careers OR empleo OR vagas) (Cisco OR Palo Alto OR Fortinet OR Check Point OR AWS OR Azure)',
            ],
            "negative_result_policy": "Registrar consulta, fuente y fecha; no convertir un resultado vacío en ausencia de capacidad o relación.",
        })
    for relation in relationships.get("integrator_vendor", []) + relationships.get("distributor_vendor", []):
        if relation.get("status") not in {"PROBABLE", "RESEARCH PRIORITY"}:
            continue
        priority = clamp(0.34 * ({"T1": 1.0, "T2": 0.72, "T3": 0.38}.get(relation.get("entity_tier"), 0.38)) + 0.28 * number(relation.get("priority_score")) / 100 + 0.20 * (1 - number((relation.get("fact_confidence") or {}).get("score"))) + 0.18 * number(relation.get("westcon_relevance")) / 100)
        queue.append({
            "queue_id": stable_id("rq", relation.get("relationship_id")), "entity": relation.get("integrator") or relation.get("distributor"),
            "entity_type": relation.get("relationship_type"), "vendor": relation.get("vendor"), "entity_tier": relation.get("entity_tier"),
            "priority_score": round(priority, 3), "gaps": ["Estado de relación", "País", "Partnership/certificaciones", "Vigencia"],
            "priority_breakdown": {"tier": relation.get("entity_tier"), "relationship_priority": relation.get("priority_score"), "uncertainty": round(1 - number((relation.get("fact_confidence") or {}).get("score")), 3), "westcon_relevance": relation.get("westcon_relevance")},
            "formula": "34% tier + 28% materialidad de relación + 20% incertidumbre + 18% relevancia Westcon",
            "next_action": relation.get("next_research"),
            "recommended_sources": ["vendor_partner_locators", "public_certification_directories", "vendor_customer_stories", "integrator_case_studies", "official_careers", "employer_ats"],
            "query_plan": [f'"{relation.get("integrator") or relation.get("distributor")}" "{relation.get("vendor")}" (partner OR certification OR specialization OR customer story) (Spain OR Portugal)'],
            "negative_result_policy": "Resultado negativo trazado; no equivale a relación inexistente.",
        })
    queue.sort(key=lambda row: number(row.get("priority_score")), reverse=True)
    return {
        "meta": {"version": "3.4.0", "candidates": len(queue), "principle": "T1 > T2 > T3, pero gaps, contradicciones, antigüedad, valor y probabilidad de fuente pueden reordenar dentro de cada tier."},
        "queue": queue[:160],
    }


def build_business_report(
    recommendations: Mapping[str, Any], entities: Mapping[str, Any], relationships: Mapping[str, Any],
    architectures: Mapping[str, Any], history: Mapping[str, Any], source_coverage: Mapping[str, Any],
) -> dict[str, Any]:
    recs = recommendations.get("recommendations", []) or []
    integrators = sorted(entities.get("integrators", []), key=lambda row: (number(row.get("activation_priority")), number(row.get("strategic_importance_score"))), reverse=True)
    distributors = sorted(entities.get("distributors", []), key=lambda row: (number(row.get("competitive_response_priority")), number(row.get("strategic_importance_score"))), reverse=True)
    relation_research = [row for row in relationships.get("integrator_vendor", []) if row.get("status") == "RESEARCH PRIORITY"]
    probable = [row for row in relationships.get("integrator_vendor", []) if row.get("status") == "PROBABLE"]
    coverage_scores = [number((row.get("coverage") or {}).get("score")) for row in entities.get("entities", [])]
    knowledge_debt = round(100 - sum(coverage_scores) / max(1, len(coverage_scores)), 1)
    latest = history.get("windows", {}).get("30", {})
    return {
        "meta": {"version": "3.4.0", "generated_at": datetime.now(timezone.utc).isoformat(), "title": "Westcon Iberia Executive Decision Brief", "economic_disclaimer": "Los potenciales son relativos; no son forecasts ni sustituyen ventas, margen, pipeline, rebates o renewals internos."},
        "executive_decision_brief": {
            "what_changed": [
                f"Las recomendaciones pasan de un gate absoluto 100/100 a {len(recs)} acciones graduadas y auditadas.",
                f"La capa v3.4 elimina {entities.get('meta', {}).get('duplicate_evidence_removed', 0)} repeticiones de evidencia en perfiles y separa estado, intensidad y confianza de relaciones.",
                f"El histórico móvil identifica {latest.get('events', 0)} cambios materiales en 30 días.",
            ],
            "why_it_matters": "Dirección recibe una acción proporcional a la evidencia —actuar, validar, investigar o vigilar— sin convertir hipótesis en hechos ni ocultar señales materiales.",
            "what_to_do": [row.get("action") for row in recs[:5]],
            "top_recommendations": recs[:8],
            "opportunities": [row for row in recs if row.get("action_type") in {"ACTUAR", "PREPARAR / VALIDAR"} and number((row.get("impact_potential") or {}).get("score")) >= 70][:8],
            "threats": [{"distributor": row.get("name"), "pressure": row.get("competitive_pressure"), "response_priority": row.get("competitive_response_priority"), "overlap": row.get("westcon_overlap"), "caution": "Presión relativa; no es cuota de mercado."} for row in distributors[:6]],
            "integrators_to_activate": [{"integrator": row.get("name"), "scope": row.get("scope"), "tier": row.get("entity_tier"), "activation_priority": row.get("activation_priority"), "coverage": (row.get("coverage") or {}).get("score"), "gaps": row.get("research_gaps"), "vendors": row.get("vendors")} for row in integrators[:10]],
            "competitive_distributor_pressure": [{"distributor": row.get("name"), "scope": row.get("scope"), "pressure": row.get("competitive_pressure"), "overlap": row.get("westcon_overlap"), "last_verified": row.get("last_verified")} for row in distributors[:8]],
            "new_or_strengthened_relationships": (history.get("relationship_movement", {}).get("integrator", {}).get("changes") or [])[:10],
            "whitespace": [{"integrator": row.get("integrator"), "vendor": row.get("vendor"), "status": row.get("status"), "priority": row.get("priority_score"), "next_research": row.get("next_research")} for row in relation_research[:10]],
            "multivendor_plays": [{"title": row.get("title"), "readiness": row.get("readiness"), "vendors": [vendor.get("vendor") for vendor in row.get("vendors", [])], "services": row.get("westcon_services"), "gaps": row.get("gaps")} for row in architectures.get("architectures", [])[:8]],
            "portfolio_risks": ["Solape tecnológico interpretado como conflicto sin evidencia contractual.", "Alcance global o EMEA tratado como Iberia.", "Evidencia pública repetida inflando relaciones.", "Economics relativos usados como forecast.", "Dependencia excesiva de agregadores en algunos gaps."],
            "growth_technologies": latest.get("technologies", {}),
            "knowledge_debt": {"score": knowledge_debt, "entities_below_50_coverage": sum(score < 50 for score in coverage_scores), "explanation": "100 menos cobertura media de campos de negocio; no reduce el tier, aumenta investigación."},
            "priority_investigations": [{"integrator": row.get("integrator"), "vendor": row.get("vendor"), "status": row.get("status"), "next_research": row.get("next_research")} for row in (probable + relation_research)[:12]],
        },
        "economics": {
            "current_mode": "relative indicators only",
            "relative_dimensions": ["revenue potential", "recurring revenue potential", "service attach", "margin potential", "time-to-revenue", "enablement effort", "defensibility", "strategic fit", "competitive urgency"],
            "future_internal_model": ["ventas", "margen", "pipeline", "rebates", "renewals", "attach", "partner base", "certificaciones", "headcount", "coste de enablement"],
            "rule": "No se calcula forecast financiero hasta cargar y gobernar datos internos.",
        },
        "methodology": {
            "source_hierarchy": "Fuente primaria > secundaria de calidad > agregador.",
            "recommendation_governance": "Hecho, interpretación y riesgo de acción se puntúan por separado.",
            "relation_governance": "Estado, intensidad y confianza se calculan por separado; ausencia de evidencia no es ausencia de relación.",
            "source_learning": source_coverage.get("meta", {}).get("learning_granularity"),
        },
    }
