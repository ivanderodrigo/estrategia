from __future__ import annotations

from typing import Any, Dict, Iterable, List
from .confidence import recommendation_threshold


def _has(words, items):
    blob = " ".join(str(x).lower() for x in items)
    return any(w in blob for w in words)


def enrich_entity(entity: Dict[str, Any], westcon_vendor_names: Iterable[str] = ()) -> Dict[str, Any]:
    et = entity.get("entity_type")
    conf = float(entity.get("confidence", 0.45))
    signals = entity.get("signals") or {}
    vendors = entity.get("vendors") or []
    services = entity.get("services") or []
    certs = entity.get("certifications") or []
    evidence_count = int(entity.get("evidence_count", 0))

    pressure = min(100, 10 + 4 * len(vendors) + 2 * evidence_count + 7 * signals.get("distribution_agreement", 0) + 4 * signals.get("ma_activity", 0)) if et == "distributor" else 0
    capability = min(100, 10 + 5 * len(certs) + 3 * len(services) + 2 * evidence_count) if et == "integrator" else 0
    westcon_names = {x.lower() for x in westcon_vendor_names}
    overlap = len({x.lower() for x in vendors} & westcon_names) if westcon_names else 0
    whitespace = max(0, min(100, 65 - 7 * overlap + 2 * capability)) if et == "integrator" else 0

    recs: List[Dict[str, Any]] = []
    if et == "distributor":
        kind = "channel_defense" if pressure >= 45 else "watch"
        threshold = recommendation_threshold(kind)
        if conf >= threshold:
            recs.append({
                "kind": kind,
                "title": "Defender diferenciación de canal" if kind == "channel_defense" else "Vigilar presión competitiva",
                "why": f"Presión pública estimada {pressure}/100 con {len(vendors)} relaciones tecnológicas detectadas.",
                "opportunity": "Identificar fabricantes/partners donde Westcon pueda diferenciarse por especialización, servicios, lifecycle y capacidad técnica.",
                "monetization": "Protección de share, captación de proyectos, servicios attach y recurrencia.",
                "kpi": "wins competitivos, partners activados, attach de servicios y evolución de solapamiento",
                "confidence": conf,
                "threshold": threshold,
                "counter_evidence": "Revisar si el solapamiento es solo nominal, geográfico o basado en relaciones históricas.",
                "change_trigger": "Bajar prioridad si desaparece evidencia reciente de actividad o si la cobertura real en Iberia no se confirma.",
            })
    elif et == "integrator":
        kind = "partner_recruitment" if whitespace >= 58 and capability >= 35 else "investigate"
        threshold = recommendation_threshold(kind)
        if conf >= threshold:
            recs.append({
                "kind": kind,
                "title": "Atacar whitespace con partner" if kind == "partner_recruitment" else "Completar mapa de capacidad del partner",
                "why": f"Capacidad pública {capability}/100; whitespace estimado {whitespace}/100; solapamiento con portfolio detectado: {overlap}.",
                "opportunity": "Introducir fabricantes compatibles con las capacidades existentes del integrador y construir ofertas multivendor verificables.",
                "monetization": "Cross-sell, new logos, servicios profesionales, formación y lifecycle.",
                "kpi": "fabricantes activados, oportunidades cualificadas, certificaciones, pipeline atribuido y servicios attach",
                "confidence": conf,
                "threshold": threshold,
                "counter_evidence": "No asumir capacidad por aparecer en un partner directory; exigir certificaciones, casos o actividad reciente.",
                "change_trigger": "Elevar prioridad si aparecen casos, adjudicaciones o certificaciones recientes; reducirla si solo hay menciones débiles.",
            })
    entity["business_intelligence"] = {
        "competitive_pressure": pressure,
        "capability_score": capability,
        "whitespace_score": whitespace,
        "portfolio_overlap_count": overlap,
        "recommendations": recs,
    }
    return entity


def enrich_views(views: Dict[str, Any], westcon_vendor_names: Iterable[str] = ()): 
    for group in ("vendors", "distributors", "integrators"):
        views[group] = [enrich_entity(x, westcon_vendor_names) for x in views.get(group, [])]
    return views
