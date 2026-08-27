#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[2]


def load(rel: str, default: Any) -> Any:
    path = ROOT / rel
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write(rel: str, value: Any) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def norm(value: Any) -> str:
    text = str(value or "").lower()
    text = text.translate(str.maketrans("áéíóúüñç", "aeiouunc"))
    return re.sub(r"\s+", " ", text).strip()


def uniq(values: Iterable[Any]) -> list[Any]:
    out: list[Any] = []
    seen: set[str] = set()
    for value in values:
        if value in (None, "", [], {}, False):
            continue
        key = json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else norm(value)
        if key and key not in seen:
            seen.add(key)
            out.append(value)
    return out


def evidence(row: Mapping[str, Any] | None, note: str | None = None) -> dict[str, Any] | None:
    if not row:
        return None
    url = row.get("url")
    source = row.get("source") or row.get("analyst") or row.get("name")
    title = row.get("title") or row.get("evidence") or row.get("fact") or source
    if not source and not title:
        return None
    value = {
        "source": source or "Fuente pública",
        "title": title or source or "Evidencia",
        "url": url,
        "date": row.get("date") or row.get("published") or row.get("last_verified"),
        "confidence": row.get("confidence") if not isinstance(row.get("confidence"), dict) else row.get("confidence", {}).get("score"),
        "type": row.get("classification") or row.get("source_type") or row.get("kind"),
    }
    if note:
        value["note"] = note
    return value


def dedupe_evidence(rows: Iterable[Mapping[str, Any] | None], limit: int = 8) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not row:
            continue
        item = evidence(row) if "source" not in row or "title" not in row else dict(row)
        if not item:
            continue
        title_norm = norm(item.get("title"))
        # Financial analyst buy/sell calls are noise for technology/channel intelligence.
        if any(token in title_norm for token in ("recomendacion de compra", "recomendacion de venta", "buy rating", "sell rating", "price target", "precio objetivo")):
            continue
        key = norm(item.get("url") or "") + "|" + title_norm + "|" + norm(item.get("source"))
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= limit:
            break
    return out


def internal_evidence(title: str, note: str) -> dict[str, Any]:
    return {"source": "Westcon España · documentación aportada", "title": title, "url": None, "date": "FY27", "type": "user-provided", "note": note}


def field(value: Any, sources: Iterable[Mapping[str, Any] | None], confidence: float | int | None = None, qualifier: str | None = None) -> dict[str, Any] | None:
    if value in (None, "", [], {}, False):
        return None
    linked = dedupe_evidence(sources)
    if not linked:
        return None
    result = {"value": value, "evidence": linked}
    if confidence is not None:
        score = float(confidence)
        result["confidence"] = round(score if score <= 1 else score / 100, 3)
    if qualifier:
        result["qualifier"] = qualifier
    return result


def entity_field_evidence(row: Mapping[str, Any], keywords: Iterable[str], limit: int = 6) -> list[dict[str, Any]]:
    words = [norm(x) for x in keywords]
    candidates = []
    for ev in row.get("evidence", []) or []:
        blob = norm(" ".join(str(ev.get(k) or "") for k in ("title", "source", "classification")))
        if any(word and word in blob for word in words):
            candidates.append(ev)
    return dedupe_evidence(candidates or (row.get("evidence", []) or []), limit)


def relationship_index(relationships: Mapping[str, Any], key: str) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rel in relationships.get(key, []) or []:
        entity = rel.get("integrator") or rel.get("distributor")
        if entity:
            out[norm(entity)].append(rel)
    return out


def rel_evidence(rel: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for key in ("partnership_level_evidence", "certification_specialization_evidence", "customer_case_evidence", "relationship_evidence", "evidence"):
        value = rel.get(key) or []
        if isinstance(value, dict):
            value = [value]
        rows.extend(value)
    return dedupe_evidence(rows, 8)


def build_manufacturers() -> list[dict[str, Any]]:
    base = load("data/vendor_intelligence.json", {})
    v31 = load("data/v31/entity_intelligence.json", {})
    relationships = load("data/v34/relationships.json", {})
    current = base.get("vendors", []) or []

    alias = {
        "akamai": "akamai / noname", "noname security": "akamai / noname", "cradlepoint": "ericsson cradlepoint",
        "stratus technologies": "stratus / penguin solutions", "penguin solutions": "stratus / penguin solutions",
    }
    canonical = lambda value: alias.get(norm(value), norm(value))
    current_names = {canonical(v.get("name")) for v in current}

    v31_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in v31.get("vendors", []) or []:
        v31_by_name[canonical(row.get("name"))].append(row)

    # Analyst peer lists are unusually valuable here: they let the UI expose external
    # manufacturers as first-class intelligence while preserving exact source lineage.
    peer_support: dict[str, dict[str, Any]] = {}
    for portfolio_vendor in current:
        for signal in portfolio_vendor.get("analystSignals", []) or []:
            ev = evidence(signal)
            if not ev:
                continue
            for peer in signal.get("peers", []) or []:
                key = canonical(peer)
                if not key or key in current_names:
                    continue
                item = peer_support.setdefault(key, {"name": peer, "portfolio": [], "evidence": []})
                item["portfolio"].append(portfolio_vendor.get("name"))
                item["evidence"].append(ev)

    # Keep any externally observed competitor that exists in the deeper entity layer,
    # even when it was not present in a structured analyst peer list.
    competitor_mentions = set()
    for vendor in current:
        competitor_mentions.update(canonical(x) for x in vendor.get("marketCompetitors", []) or [])
    for key, v31_rows in v31_by_name.items():
        if key in current_names or key in peer_support or key not in competitor_mentions:
            continue
        evs = dedupe_evidence([ev for row in v31_rows for ev in (row.get("evidence", []) or [])], 8)
        if evs:
            peer_support[key] = {"name": v31_rows[0].get("name"), "portfolio": [], "evidence": evs}

    competitor_rows = [
        {
            "name": item["name"], "domain": "", "capabilities": [], "countries": [],
            "marketCompetitors": [], "analystSignals": [], "channelCompetitors": [],
            "_external": True, "_peer_support": item,
        }
        for item in peer_support.values()
    ]
    all_vendors = current + competitor_rows

    int_by_vendor: dict[str, list[dict[str, Any]]] = defaultdict(list)
    dist_by_vendor: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rel in relationships.get("integrator_vendor", []) or []:
        if rel.get("status") in {"CONFIRMED", "PROBABLE"}:
            int_by_vendor[canonical(rel.get("vendor"))].append(rel)
    for rel in relationships.get("distributor_vendor", []) or []:
        if rel.get("status") in {"CONFIRMED", "PROBABLE"}:
            dist_by_vendor[canonical(rel.get("vendor"))].append(rel)

    portfolio_src = internal_evidence("Westcon España – Presentación Corporativa FY2027", "Se usa solo para taxonomía, cobertura y semilla de portfolio; no como evidencia independiente de mercado.")
    rows: list[dict[str, Any]] = []
    for vendor in all_vendors:
        name = vendor.get("name")
        key = canonical(name)
        v31_rows = v31_by_name.get(key, [])
        public_evidence = dedupe_evidence([ev for r in v31_rows for ev in (r.get("evidence", []) or [])], 12)
        analyst = [evidence(x) for x in vendor.get("analystSignals", []) or []]
        channel = [evidence({"source": x.get("name"), "title": x.get("evidence") or f"Distribución de {name}", "url": x.get("url"), "date": None, "confidence": x.get("confidence"), "classification": "distribution"}) for x in vendor.get("channelCompetitors", []) or []]
        peer_info = vendor.get("_peer_support") or {}
        peer_evidence = dedupe_evidence(peer_info.get("evidence", []) or [], 12)
        direct_pool = dedupe_evidence([*analyst, *channel, *peer_evidence, *public_evidence], 12)
        int_rels = int_by_vendor.get(key, [])
        dist_rels = dist_by_vendor.get(key, [])

        peers = uniq([peer for sig in vendor.get("analystSignals", []) or [] for peer in (sig.get("peers", []) or [])])
        dist_values = []
        dist_evs: list[dict[str, Any]] = []
        for x in vendor.get("channelCompetitors", []) or []:
            dist_values.append(f"{x.get('name')} · {x.get('country')}")
            ev = evidence({"source": x.get("name"), "title": x.get("evidence"), "url": x.get("url"), "confidence": x.get("confidence"), "classification": "distribution"})
            if ev: dist_evs.append(ev)
        for rel in dist_rels:
            dist = rel.get("distributor")
            if dist and "westcon" not in norm(dist):
                dist_values.append(f"{dist} · {(rel.get('geography') or {}).get('scope') or '—'} · {rel.get('status_label') or rel.get('status')}")
                dist_evs.extend(rel_evidence(rel))
        int_values, int_evs = [], []
        for rel in int_rels:
            int_values.append(f"{rel.get('integrator')} · {(rel.get('geography') or {}).get('scope') or '—'} · {rel.get('status_label') or rel.get('status')}")
            int_evs.extend(rel_evidence(rel))

        analyst_values = [f"{x.get('analyst')}: {x.get('title')}" for x in vendor.get("analystSignals", []) or []]
        latest_public = sorted(public_evidence, key=lambda x: str(x.get("date") or ""), reverse=True)[:4]
        latest_values = [x.get("title") for x in latest_public if x.get("title")]
        portfolio_compared = uniq(peer_info.get("portfolio", []) or [])
        role = "Portfolio Westcon Iberia" if not vendor.get("_external") else "Fabricante competidor / adyacente"
        role_sources = [portfolio_src] if not vendor.get("_external") else direct_pool
        fields = {
            "portfolio_role": field(role, role_sources),
            "scope": field(" / ".join(vendor.get("countries", []) or []), [portfolio_src]) if vendor.get("countries") else None,
            "domain": field(vendor.get("domain"), [portfolio_src] if not vendor.get("_external") else direct_pool),
            "capabilities": field(vendor.get("capabilities", []), [portfolio_src] if not vendor.get("_external") else direct_pool),
            "market_peers": field(peers, analyst, qualifier="Peers citados en señales públicas de analistas; no equivale a cuota ni ranking propio."),
            "portfolio_compared": field(portfolio_compared, peer_evidence, qualifier="Fabricantes del portfolio Westcon junto a los que esta entidad aparece como peer/competidor en las señales enlazadas."),
            "distributors": field(uniq(dist_values), dist_evs, qualifier="Relaciones públicas detectadas por país; ausencia de dato no implica exclusividad."),
            "integrators": field(uniq(int_values), int_evs, qualifier="Relaciones confirmadas o probables con evidencia pública; no representa el canal completo."),
            "analyst_signals": field(analyst_values, analyst, qualifier="Contenido público disponible de analistas; no reconstruye informes de pago."),
            "recent_signals": field(latest_values, latest_public, qualifier="Señales públicas recientes asociadas al fabricante; revisar la fuente para contexto completo."),
        }
        rows.append({"id": f"mfr-{re.sub('[^a-z0-9]+','-',norm(name))}", "name": name, "evidence": dedupe_evidence(role_sources, 8), "fields": {k: v for k, v in fields.items() if v}})
    return sorted(rows, key=lambda r: (0 if (r.get("fields", {}).get("portfolio_role", {}).get("value") == "Portfolio Westcon Iberia") else 1, norm(r.get("name"))))


def build_ecosystem(kind: str) -> list[dict[str, Any]]:
    entities_doc = load("data/v34/entities.json", {})
    relationships = load("data/v34/relationships.json", {})
    motion_doc = load("data/v34/ecosystem_motion_intelligence.json", {})
    entity_rows = entities_doc.get("integrators" if kind == "integrator" else "distributors", []) or []
    rel_index = relationship_index(relationships, "integrator_vendor" if kind == "integrator" else "distributor_vendor")
    motion = {norm(x.get("entity")): x for x in motion_doc.get("entities", []) or []}
    rows = []
    for row in entity_rows:
        name = row.get("name")
        if kind == "distributor" and "westcon" in norm(name):
            continue
        rels = rel_index.get(norm(name), [])
        m = motion.get(norm(name), {})
        confirmed = [r for r in rels if r.get("status") == "CONFIRMED"]
        probable = [r for r in rels if r.get("status") == "PROBABLE"]
        relation_values = [f"{r.get('vendor')} · Confirmada · {(r.get('geography') or {}).get('scope') or '—'}" for r in confirmed]
        relation_values += [f"{r.get('vendor')} · Probable · {(r.get('geography') or {}).get('scope') or '—'}" for r in probable]
        relation_evs = [ev for r in (confirmed + probable) for ev in rel_evidence(r)]
        talent_signals = m.get("talent_signals", []) or []
        job_vendors = [f"{x.get('vendor')} · {x.get('signals')} señal(es)" for x in (m.get("manufacturers_in_job_profiles", []) or [])]
        job_profiles = [f"{x.get('family')} · {x.get('signals')} señal(es)" for x in (m.get("profiles_sought", []) or [])]
        generic = dedupe_evidence(row.get("evidence", []) or [], 8)
        services = uniq([*(row.get("managed_services", []) or []), *(row.get("services", []) or [])])
        specializations = uniq([*(row.get("specializations", []) or []), *(row.get("competencies", []) or [])])
        capabilities = []
        for key, label in (("soc","SOC"),("noc","NOC"),("mssp","MSSP"),("msp","MSP"),("professional_services","Servicios profesionales"),("financing","Financiación"),("marketplace","Marketplace"),("cloud_marketplace","Marketplace cloud"),("training_enablement","Formación / enablement"),("labs_demos","Labs / demos"),("poc","PoC"),("staging_configuration","Staging / configuración"),("logistics","Logística")):
            if row.get(key): capabilities.append(label)
        if kind == "distributor":
            overlap = row.get("westcon_overlap", []) or []
            overlap_evs = relation_evs + [internal_evidence("Westcon España – Presentación Corporativa FY2027", "El solape se calcula contra la semilla de portfolio aportada.")]
        else:
            overlap, overlap_evs = [], []
        fields = {
            "scope": field(row.get("scope"), generic),
            "vendor_relations": field(uniq(relation_values), relation_evs, qualifier="Estado de relación separado de intensidad y volumen. Confirmada/probable se basa en evidencia pública."),
            "westcon_overlap": field(overlap, overlap_evs, qualifier="Intersección de linecard público con el portfolio Westcon aportado; no mide presión comercial ni cuota."),
            "specializations": field(specializations, entity_field_evidence(row, ["certif", "special", "competenc", "partner"]), qualifier="Solo señales públicas; no se infieren certificaciones por afinidad tecnológica."),
            "services": field(services, entity_field_evidence(row, ["service", "servicio", "soc", "noc", "managed", "gestion"])),
            "capabilities": field(capabilities, entity_field_evidence(row, ["service", "servicio", "marketplace", "training", "formacion", "lab", "poc", "staging", "logistic", "financ"])),
            "verticals": field(row.get("verticals", []) or [], entity_field_evidence(row, ["customer", "cliente", "case", "caso", "sector", "vertical"])),
            "public_cases": field(row.get("customers_public_cases", []) or [], entity_field_evidence(row, ["customer", "cliente", "case", "caso"]), qualifier="Casos públicos detectados; no representa la base completa de clientes."),
            "public_procurement": field(row.get("public_procurement_awards"), entity_field_evidence(row, ["contract", "licit", "award", "adjud", "procurement"]), qualifier="Número de eventos públicos detectados; no es cuota de adjudicación."),
            "job_vendors": field(job_vendors, talent_signals, qualifier="Menciones de fabricantes/certificaciones en vacantes. Es señal de demanda de skills, no prueba de partnership ni ventas."),
            "job_profiles": field(job_profiles, talent_signals, qualifier="Familias de perfiles demandadas en fuentes públicas; una vacante no equivale a headcount efectivo."),
            "last_verified": field(row.get("last_verified"), generic),
            "confidence": field(round(float(row.get("confidence") or 0) * 100) if row.get("confidence") is not None else None, generic, confidence=row.get("confidence"), qualifier="Confianza agregada en la evidencia pública del perfil; no mide importancia comercial."),
        }
        published_fields = {k: v for k, v in fields.items() if v}
        field_evidence = [ev for value in published_fields.values() for ev in (value.get("evidence") or [])]
        identity_evidence = dedupe_evidence([*generic, *relation_evs, *talent_signals, *field_evidence], 8)
        if not identity_evidence:
            continue
        rows.append({"id": row.get("entity_id") or f"{kind}-{norm(name)}", "name": name, "evidence": identity_evidence, "fields": published_fields})
    return sorted(rows, key=lambda r: norm(r.get("name")))


TREND_KEYWORDS = {
    "ai-security": ["ai", "agent", "security", "governance", "ia"],
    "sase": ["sase", "sse", "zero trust", "lan", "security convergence"],
    "secops": ["secops", "xdr", "mdr", "ctem", "soc", "security platform", "plataform"],
    "identity": ["identity", "iam", "password", "authentication", "identidad", "itdr"],
    "data-security": ["data security", "dspm", "data protection", "crypto", "post-quantum", "quantum", "sovereign"],
    "cloud-security": ["cloud security", "cnapp", "cloud", "sovereign", "security"],
    "network-aiops": ["aiops", "autonomous network", "agentic operations", "lan", "network", "ai"],
    "secure-lan": ["secure lan", "lan", "campus", "zero trust", "network security"],
    "naas": ["naas", "managed network", "network as a service", "lan", "network operations", "managed service"],
    "ai-infra": ["ai infrastructure", "data center", "gpu", "ai spending", "infrastructure", "ai platform", "neocloud"],
    "observability": ["observability", "telemetry", "monitoring", "digital experience", "network operations", "aiops"],
    "ot": ["ot", "ics", "iot", "cps", "cyber-physical", "industrial"],
    "services": ["managed service", "professional service", "lifecycle", "services", "platformization", "plataform"],
    "sovereignty": ["sovereign", "sovereignty", "soberan", "cloud", "data residency"],
    "agentic-automation": ["automation", "agentic", "rpa", "orchestration", "agent"],
}


def build_trends() -> list[dict[str, Any]]:
    base = load("data/base.json", {})
    vendors = load("data/vendor_intelligence.json", {})
    research = load("data/research.latest.json", {})
    market_signals = list(vendors.get("marketSignals", []) or [])
    market_signals += [x for x in (research.get("analystSignals", []) or []) if x.get("url")]
    for vendor in vendors.get("vendors", []) or []:
        for signal in vendor.get("analystSignals", []) or []:
            if signal.get("url"):
                market_signals.append({**signal, "label": signal.get("title"), "detail": signal.get("summary"), "vendor": vendor.get("name")})
    v31 = load("data/v31/entity_intelligence.json", {})
    for vendor in v31.get("vendors", []) or []:
        for signal in vendor.get("evidence", []) or []:
            if signal.get("url") and any(token in norm(signal.get("classification")) for token in ("analyst", "market", "product", "service", "other_signal")):
                market_signals.append({**signal, "analyst": signal.get("source"), "label": signal.get("title"), "detail": signal.get("summary") or signal.get("title"), "vendor": vendor.get("name")})
    rows = []
    for theme in base.get("themes", []) or []:
        keywords = TREND_KEYWORDS.get(theme.get("id"), [norm(theme.get("name"))])
        matched = []
        for s in market_signals:
            blob = norm(" ".join(str(s.get(k) or "") for k in ("title", "label", "detail", "summary", "analyst", "tags")))
            if any(norm(k) in blob for k in keywords):
                matched.append(s)
        evs = dedupe_evidence(matched, 8)
        if not evs:
            continue
        metrics = []
        for s in matched[:6]:
            metric = s.get("metric")
            label = s.get("label") or s.get("title")
            if metric and label:
                metrics.append(f"{metric} · {label}")
        fields = {
            "domain": field(theme.get("domain"), evs),
            "observed": field(theme.get("why"), evs, qualifier="Síntesis descriptiva propia construida a partir del conjunto de señales enlazadas; no prescribe acciones."),
            "market_metrics": field(uniq(metrics), matched, qualifier="Métricas tal como aparecen en fuentes públicas; revisar fecha, geografía y metodología de cada fuente."),
            "sources": field([f"{x.get('source') or x.get('analyst')} · {x.get('title') or x.get('label')}" for x in matched[:6]], matched),
        }
        rows.append({"id": theme.get("id"), "name": theme.get("name"), "evidence": evs, "fields": {k: v for k, v in fields.items() if v}})
    # Direct market signals that do not map cleanly still appear as evidence cards.
    return rows


def build_architectures() -> list[dict[str, Any]]:
    doc = load("data/v34/architectures.json", {})
    rows = []
    for arch in doc.get("architectures", []) or []:
        evs = dedupe_evidence(arch.get("evidence", []) or [], 10)
        layers = []
        for layer in arch.get("layers", []) or []:
            vendors = [v.get("vendor") for v in layer.get("vendors", []) or [] if v.get("vendor")]
            layers.append({"layer": layer.get("name"), "vendors": vendors, "note": layer.get("note")})
        integrations = []
        for x in arch.get("integrations", []) or []:
            if isinstance(x, dict):
                integrations.append(" · ".join(str(x.get(k)) for k in ("from", "to", "status") if x.get(k)))
            elif x:
                integrations.append(str(x))
        vendor_names = [x.get("vendor") for x in arch.get("vendors", []) or [] if x.get("vendor")]
        fields = {
            "context": field(arch.get("problem"), evs, qualifier="Contexto de mercado/tecnología sintetizado a partir de las fuentes; no prescribe una acción."),
            "layers": field(layers, evs, qualifier="Mapa funcional propio. La presencia en una capa no implica integración certificada entre fabricantes."),
            "vendors": field(vendor_names, evs, qualifier="Fabricantes usados para representar capacidades funcionales observadas; su coexistencia en el mapa no implica preferencia ni combinación certificada."),
            "integrations": field(uniq(integrations), evs, qualifier="Solo se considera integración cuando existe soporte explícito; de lo contrario se trata como encaje funcional a validar."),
            "risks": field(arch.get("risks", []) or [], evs, qualifier="Limitaciones y cautelas del mapa arquitectónico."),
        }
        rows.append({"id": arch.get("architecture_id"), "name": arch.get("title"), "evidence": evs, "fields": {k: v for k, v in fields.items() if v}})
    return rows


def merge_source_catalog() -> list[dict[str, Any]]:
    current = load("data/v34/source_catalog.json", {}).get("sources", []) or []
    additions = load("config/v35/source_additions.json", {}).get("sources", []) or []
    rows: dict[str, dict[str, Any]] = {}
    for raw in [*current, *additions]:
        sid = raw.get("source_id") or raw.get("id")
        if not sid:
            continue
        item = {
            "id": sid,
            "name": raw.get("name"), "url": raw.get("url"),
            "class": raw.get("source_class") or raw.get("class"),
            "scope": raw.get("scope") or [], "dimensions": raw.get("dimensions") or [],
            "access_policy": raw.get("access_policy"),
        }
        rows[sid] = item
    return sorted(rows.values(), key=lambda x: (str(x.get("class") or ""), str(x.get("name") or "")))


SCHEMAS = {
    "manufacturers": [
        {"id":"portfolio_role","label":"Posición","help":"Distingue fabricantes del portfolio Westcon Iberia de fabricantes externos detectados como competidores o adyacentes.","clarify":True},
        {"id":"scope","label":"Cobertura Westcon","help":"Países en los que el fabricante forma parte de la semilla de portfolio aportada. No describe presencia total del fabricante.","clarify":True},
        {"id":"domain","label":"Área tecnológica","help":"Taxonomía tecnológica usada para agrupar la inteligencia; en portfolio Westcon procede de la documentación aportada.","clarify":True},
        {"id":"capabilities","label":"Capacidades","help":"Capacidades tecnológicas asociadas con soporte documental. No se muestran si no hay información utilizable.","clarify":True},
        {"id":"market_peers","label":"Competidores / peers","help":"Peers citados en señales públicas de analistas. No equivale a ranking, cuota ni valoración propia.","clarify":True},
        {"id":"portfolio_compared","label":"Comparado con portfolio","help":"Para fabricantes externos: fabricantes del portfolio Westcon junto a los que aparece como peer o competidor en señales públicas enlazadas.","clarify":True},
        {"id":"distributors","label":"Mayoristas alternativos","help":"Relaciones públicas de distribución por país detectadas en fuentes oficiales o corroboradas.","clarify":True},
        {"id":"integrators","label":"Integradores relacionados","help":"Relaciones públicas confirmadas o probables; no representa la totalidad del ecosistema.","clarify":True},
        {"id":"analyst_signals","label":"Analistas","help":"Señales públicas de Gartner, IDC, Forrester u otras firmas. No se reconstruye contenido de pago.","clarify":True},
        {"id":"recent_signals","label":"Señales recientes","help":"Noticias, cambios o evidencias públicas recientes asociadas al fabricante.","clarify":True}
    ],
    "integrators": [
        {"id":"scope","label":"Ámbito","help":"Geografía explícitamente respaldada por las evidencias; Iberia no se desdobla en ES/PT sin prueba.","clarify":True},
        {"id":"vendor_relations","label":"Fabricantes relacionados","help":"Relaciones confirmadas o probables con evidencia pública. Estado de relación no implica volumen de negocio.","clarify":True},
        {"id":"specializations","label":"Certificaciones / especializaciones","help":"Solo señales explícitas; no se infieren certificaciones por tecnología o por una vacante.","clarify":True},
        {"id":"services","label":"Servicios","help":"Servicios gestionados/profesionales publicados por la entidad o respaldados por casos públicos.","clarify":True},
        {"id":"capabilities","label":"Capacidades operativas","help":"SOC, NOC, MSSP, MSP u otras capacidades cuando existen señales públicas explícitas.","clarify":True},
        {"id":"verticals","label":"Verticales","help":"Sectores con actividad o casos públicos; no representa toda la cartera de clientes.","clarify":True},
        {"id":"public_cases","label":"Casos / clientes públicos","help":"Referencias públicas trazables; no equivale a base total de clientes.","clarify":True},
        {"id":"public_procurement","label":"Contratación pública","help":"Eventos públicos detectados; no es cuota de adjudicación ni cifra comercial completa.","clarify":True},
        {"id":"job_vendors","label":"Fabricantes en ofertas","help":"Menciones de fabricantes/certificaciones en vacantes. Señal de skills demandados, nunca prueba de partnership o ventas.","clarify":True},
        {"id":"job_profiles","label":"Perfiles buscados","help":"Familias de roles observadas en portales y ATS públicos. Una vacante no equivale a headcount efectivo.","clarify":True},
        {"id":"confidence","label":"Confianza","help":"Confianza agregada en la evidencia pública del perfil; no mide importancia comercial.","clarify":True},
        {"id":"last_verified","label":"Última verificación","help":"Fecha más reciente de evidencia utilizada en el perfil.","clarify":True}
    ],
    "distributors": [
        {"id":"scope","label":"Ámbito","help":"Geografía explícitamente respaldada por evidencia.","clarify":True},
        {"id":"vendor_relations","label":"Fabricantes / linecard","help":"Relaciones de distribución confirmadas o probables por fuente pública; no representa necesariamente el linecard completo.","clarify":True},
        {"id":"westcon_overlap","label":"Solape con Westcon","help":"Intersección de fabricantes detectados con la semilla de portfolio Westcon. No mide presión competitiva ni cuota.","clarify":True},
        {"id":"specializations","label":"Especialización tecnológica","help":"Áreas y competencias respaldadas por evidencia pública.","clarify":True},
        {"id":"services","label":"Servicios","help":"Servicios publicados por el mayorista: profesionales, gestionados u otros de valor añadido.","clarify":True},
        {"id":"capabilities","label":"Capacidades de valor","help":"Financiación, marketplace, formación, labs, PoC, staging o logística cuando existe evidencia pública.","clarify":True},
        {"id":"job_vendors","label":"Tecnologías en ofertas","help":"Fabricantes o tecnologías mencionados en vacantes del mayorista; señal de foco/skills, no prueba de ventas.","clarify":True},
        {"id":"job_profiles","label":"Perfiles buscados","help":"Familias de roles observadas en ofertas públicas. Una vacante no equivale a headcount efectivo.","clarify":True},
        {"id":"confidence","label":"Confianza","help":"Confianza agregada en la evidencia pública del perfil; no mide presión competitiva.","clarify":True},
        {"id":"last_verified","label":"Última verificación","help":"Fecha más reciente de evidencia utilizada en el perfil.","clarify":True}
    ],
    "trends": [
        {"id":"domain","label":"Área","help":"Dominio tecnológico al que se asocia la tendencia.","clarify":False},
        {"id":"observed","label":"Qué se observa","help":"Síntesis propia construida a partir de señales enlazadas; describe el fenómeno y no prescribe acciones.","clarify":True},
        {"id":"market_metrics","label":"Datos de mercado","help":"Métricas publicadas por las fuentes. Revisar fecha, geografía y metodología antes de compararlas.","clarify":True},
        {"id":"sources","label":"Señales principales","help":"Principales señales públicas usadas para sostener la tendencia.","clarify":True}
    ],
    "architectures": [
        {"id":"context","label":"Contexto","help":"Problema o contexto tecnológico que explica el mapa; es una síntesis descriptiva basada en evidencias enlazadas.","clarify":True},
        {"id":"layers","label":"Capas","help":"Mapa funcional propio. La asignación de fabricantes a capas no implica integración certificada.","clarify":True},
        {"id":"vendors","label":"Fabricantes","help":"Fabricantes usados para representar capacidades funcionales observadas en el mapa.","clarify":True},
        {"id":"integrations","label":"Integraciones","help":"Solo se presentan como integración cuando existe soporte explícito; el resto se considera encaje funcional.","clarify":True},
        {"id":"risks","label":"Cautelas","help":"Limitaciones o riesgos de interpretación del mapa arquitectónico.","clarify":True}
    ]
}


def build() -> dict[str, Any]:
    sources = merge_source_catalog()
    result = {
        "meta": {
            "version": "3.5.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "scope": "España + Portugal",
            "principle": "Inteligencia de negocio descriptiva limitada a Fabricantes, Integradores, Mayoristas competidores, Tendencias y Arquitecturas.",
            "traceability": "Cada campo visible conserva las fuentes que sostienen o contextualizan el dato; las síntesis propias se etiquetan como tales.",
            "source_count": len(sources),
        },
        "schemas": SCHEMAS,
        "manufacturers": build_manufacturers(),
        "integrators": build_ecosystem("integrator"),
        "distributors": build_ecosystem("distributor"),
        "trends": build_trends(),
        "architectures": build_architectures(),
        "source_catalog": sources,
    }
    return result


if __name__ == "__main__":
    data = build()
    write("data/v35/intelligence.json", data)
    write("data/v35/last_run.json", {
        "version": "3.5.0", "generated_at": data["meta"]["generated_at"], "status": "published",
        "manufacturers": len(data["manufacturers"]), "integrators": len(data["integrators"]),
        "distributors": len(data["distributors"]), "trends": len(data["trends"]),
        "architectures": len(data["architectures"]), "source_count": len(data["source_catalog"]),
    })
    print(json.dumps(load("data/v35/last_run.json", {}), ensure_ascii=False))
