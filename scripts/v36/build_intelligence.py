#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import defaultdict, Counter
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
    """Publish only Westcon portfolio vendors as rows.

    Competitors stay attached to the relevant Westcon manufacturer, with their
    own evidence. This keeps the page aligned with the user's mental model:
    Westcon vendors are the subjects; the external market is context.
    """
    base = load("data/vendor_intelligence.json", {})
    v31 = load("data/v31/entity_intelligence.json", {})
    relationships = load("data/v34/relationships.json", {})
    current = base.get("vendors", []) or []

    alias = {
        "akamai": "akamai / noname", "noname security": "akamai / noname", "cradlepoint": "ericsson cradlepoint",
        "stratus technologies": "stratus / penguin solutions", "penguin solutions": "stratus / penguin solutions",
    }
    canonical = lambda value: alias.get(norm(value), norm(value))
    v31_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in v31.get("vendors", []) or []:
        v31_by_name[canonical(row.get("name"))].append(row)

    int_by_vendor: dict[str, list[dict[str, Any]]] = defaultdict(list)
    dist_by_vendor: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rel in relationships.get("integrator_vendor", []) or []:
        if rel.get("status") in {"CONFIRMED", "PROBABLE"}:
            int_by_vendor[canonical(rel.get("vendor"))].append(rel)
    for rel in relationships.get("distributor_vendor", []) or []:
        if rel.get("status") in {"CONFIRMED", "PROBABLE"}:
            dist_by_vendor[canonical(rel.get("vendor"))].append(rel)

    portfolio_src = internal_evidence(
        "Westcon España – Presentación Corporativa FY2027",
        "Se usa para identificar el portfolio y su cobertura Iberia. La información competitiva procede de fuentes públicas enlazadas."
    )
    rows: list[dict[str, Any]] = []
    for vendor in current:
        name = vendor.get("name")
        key = canonical(name)
        v31_rows = v31_by_name.get(key, [])
        public_evidence = dedupe_evidence([ev for r in v31_rows for ev in (r.get("evidence", []) or [])], 16)
        analyst = [evidence(x) for x in vendor.get("analystSignals", []) or []]
        channel = [
            evidence({"source": x.get("name"), "title": x.get("evidence") or f"Distribución de {name}", "url": x.get("url"), "date": None, "confidence": x.get("confidence"), "classification": "distribution"})
            for x in vendor.get("channelCompetitors", []) or []
        ]
        int_rels = int_by_vendor.get(key, [])
        dist_rels = dist_by_vendor.get(key, [])

        # All externally supported competitors/peers are retained against the
        # Westcon vendor. No external manufacturer becomes a standalone row.
        competitor_evidence: list[dict[str, Any]] = []
        competitors: list[str] = []
        for signal in vendor.get("analystSignals", []) or []:
            ev = evidence(signal)
            for peer in signal.get("peers", []) or []:
                competitors.append(str(peer))
                if ev:
                    competitor_evidence.append(ev)
        market_competitors = vendor.get("marketCompetitors", []) or []
        # A competitor is published only when at least one public evidence item
        # explicitly mentions that competitor. This keeps traceability at the
        # value level rather than attaching a generic evidence bundle.
        for peer in market_competitors:
            peer_evs = []
            for ev in public_evidence:
                blob = norm(f"{ev.get('title','')} {ev.get('note','')} {ev.get('source','')}")
                if norm(peer) and norm(peer) in blob:
                    peer_evs.append(ev)
            if peer_evs:
                competitors.append(str(peer))
                competitor_evidence.extend(peer_evs)
        competitor_evidence = dedupe_evidence(competitor_evidence, 12)

        dist_values: list[str] = []
        dist_evs: list[dict[str, Any]] = []
        for x in vendor.get("channelCompetitors", []) or []:
            if x.get("name") and "westcon" not in norm(x.get("name")):
                dist_values.append(f"{x.get('name')} · {x.get('country') or '—'}")
            ev = evidence({"source": x.get("name"), "title": x.get("evidence"), "url": x.get("url"), "confidence": x.get("confidence"), "classification": "distribution"})
            if ev:
                dist_evs.append(ev)
        for rel in dist_rels:
            dist = rel.get("distributor")
            if dist and "westcon" not in norm(dist):
                dist_values.append(f"{dist} · {(rel.get('geography') or {}).get('scope') or '—'} · {rel.get('status_label') or rel.get('status')}")
                dist_evs.extend(rel_evidence(rel))

        int_values: list[str] = []
        int_evs: list[dict[str, Any]] = []
        for rel in int_rels:
            int_values.append(f"{rel.get('integrator')} · {(rel.get('geography') or {}).get('scope') or '—'} · {rel.get('status_label') or rel.get('status')}")
            int_evs.extend(rel_evidence(rel))

        analyst_values = [f"{x.get('analyst')}: {x.get('title')}" for x in vendor.get("analystSignals", []) or []]
        latest_public = sorted(public_evidence, key=lambda x: str(x.get("date") or ""), reverse=True)[:5]
        fields = {
            "scope": field(" / ".join(vendor.get("countries", []) or []), [portfolio_src]) if vendor.get("countries") else None,
            "domain": field(vendor.get("domain"), [portfolio_src]),
            "capabilities": field(vendor.get("capabilities", []), [portfolio_src]),
            "competitors": field(uniq(competitors), competitor_evidence, qualifier="Competidores/peers procedentes de comparativas públicas, señales de analistas y evidencia competitiva. No implica ranking propio ni cuota."),
            "distributors": field(uniq(dist_values), dist_evs, qualifier="Mayoristas alternativos detectados públicamente por país. Ausencia de dato no implica exclusividad."),
            "integrators": field(uniq(int_values), int_evs, qualifier="Partners/integradores relacionados con evidencia pública. El motor amplía este universo continuamente desde locators, premios, casos, portales de partners y empleo."),
            "analyst_signals": field(analyst_values, analyst, qualifier="Señales públicas de Gartner, IDC, Forrester u otras firmas; no se reconstruye contenido de pago."),
            "recent_signals": field([x.get("title") for x in latest_public if x.get("title")], latest_public, qualifier="Señales públicas recientes asociadas al fabricante."),
        }
        identity_evidence = dedupe_evidence([portfolio_src, *analyst, *public_evidence], 10)
        rows.append({"id": f"mfr-{re.sub('[^a-z0-9]+','-',norm(name))}", "name": name, "evidence": identity_evidence or [portfolio_src], "fields": {k: v for k, v in fields.items() if v}})
    return sorted(rows, key=lambda r: norm(r.get("name")))

def _entity_key(value: Any) -> str:
    text = norm(value)
    # Country suffixes are frequently introduced by vendor award pages and
    # should not create duplicate companies in the Iberia table.
    text = re.sub(r"\b(spain|espana|portugal|iberia)\b$", "", text).strip()
    aliases = {
        "telefonica": "telefonica tech",
        "logicalis spain": "logicalis",
        "ntt": "ntt data",
        "axians espana": "axians",
        "axians portugal": "axians",
    }
    return aliases.get(text, text)


def _signal_evidence(signal: Mapping[str, Any]) -> dict[str, Any] | None:
    if not signal.get("url"):
        return None
    return evidence({
        "source": signal.get("source") or signal.get("vendor") or "Fuente pública",
        "title": signal.get("signal") or signal.get("title") or f"Relación pública {signal.get('name') or ''} · {signal.get('vendor') or ''}",
        "url": signal.get("url"),
        "date": signal.get("date"),
        "confidence": signal.get("confidence"),
        "classification": signal.get("proofType") or signal.get("classification") or "partner-signal",
    })


def build_ecosystem(kind: str) -> list[dict[str, Any]]:
    entities_doc = load("data/v34/entities.json", {})
    relationships = load("data/v34/relationships.json", {})
    motion_doc = load("data/v34/ecosystem_motion_intelligence.json", {})
    research = load("data/research.latest.json", {})
    v33 = load("data/v33/ecosystem_profiles.json", {})
    discovered = load("data/discovered_entities.json", {})
    portfolio_names = {norm(x.get("name")) for x in load("data/vendor_intelligence.json", {}).get("vendors", []) or []}

    collection = "integrators" if kind == "integrator" else "distributors"
    primary_rows = entities_doc.get(collection, []) or []
    profile_rows = v33.get(collection, []) or []
    rel_index_raw = relationship_index(relationships, "integrator_vendor" if kind == "integrator" else "distributor_vendor")
    rel_index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entity_name, values in rel_index_raw.items():
        rel_index[_entity_key(entity_name)].extend(values)
    motion = {_entity_key(x.get("entity")): x for x in motion_doc.get("entities", []) or []}

    # Merge every public layer by canonical entity. In v3.6 the integrator
    # table is intentionally not limited to a static curated list.
    merged: dict[str, dict[str, Any]] = {}
    for raw in [*primary_rows, *profile_rows]:
        name = raw.get("name")
        key = _entity_key(name)
        if not key:
            continue
        item = merged.setdefault(key, {"name": name, "rows": [], "signals": [], "discovered": []})
        item["rows"].append(raw)
        if len(str(name or "")) < len(str(item.get("name") or "")):
            item["name"] = name

    signal_rows = research.get("integratorSignals" if kind == "integrator" else "channelSignals", []) or []
    if kind == "integrator":
        signal_rows = [*signal_rows, *(load("config/v36/curated_integrator_relations.json", {}).get("relations", []) or [])]
    for sig in signal_rows:
        name = sig.get("name") if kind == "integrator" else sig.get("distributor")
        vendor = sig.get("vendor")
        if kind == "integrator" and norm(vendor) not in portfolio_names:
            continue
        if not name:
            continue
        key = _entity_key(name)
        item = merged.setdefault(key, {"name": name, "rows": [], "signals": [], "discovered": []})
        item["signals"].append(sig)

    for cand in discovered.get(collection, []) or []:
        if kind == "integrator" and not any(norm(v) in portfolio_names for v in (cand.get("vendors") or [])):
            continue
        name = cand.get("name")
        if not name:
            continue
        key = _entity_key(name)
        item = merged.setdefault(key, {"name": name, "rows": [], "signals": [], "discovered": []})
        item["discovered"].append(cand)

    rows: list[dict[str, Any]] = []
    for key, item in merged.items():
        name = item.get("name")
        if kind == "distributor" and "westcon" in norm(name):
            continue
        source_rows = item.get("rows") or []
        base_row = source_rows[0] if source_rows else {}
        rels = rel_index.get(key, [])
        m = motion.get(key, {})
        confirmed = [r for r in rels if r.get("status") == "CONFIRMED" and (kind != "integrator" or norm(r.get("vendor")) in portfolio_names)]
        probable = [r for r in rels if r.get("status") == "PROBABLE" and (kind != "integrator" or norm(r.get("vendor")) in portfolio_names)]

        relation_values = [f"{r.get('vendor')} · Confirmada · {(r.get('geography') or {}).get('scope') or '—'}" for r in confirmed]
        relation_values += [f"{r.get('vendor')} · Probable · {(r.get('geography') or {}).get('scope') or '—'}" for r in probable]
        relation_evs = [ev for r in (confirmed + probable) for ev in rel_evidence(r)]
        roles: list[str] = []
        for sig in item.get("signals") or []:
            ev = _signal_evidence(sig)
            # Signals from jobs do not establish a partnership. Only explicit
            # vendor/partner proof or already curated public relationships do.
            proof = norm(sig.get("proofType") or sig.get("classification"))
            relation_proof = any(token in proof for token in ("partner", "award", "directory", "case", "integrator", "reseller", "mssp")) or sig.get("status") == "curated-public"
            if relation_proof and sig.get("vendor"):
                scope = sig.get("country") or "—"
                relation_values.append(f"{sig.get('vendor')} · Evidencia pública · {scope}")
                if ev:
                    relation_evs.append(ev)
            if sig.get("role"):
                roles.append(str(sig.get("role")))

        # If this is an integrator, it must have at least one supported relation
        # to a Westcon vendor. This keeps discovery broad without turning the
        # table into a generic list of IT companies.
        relation_values = uniq(relation_values)
        relation_evs = dedupe_evidence(relation_evs, 16)
        if kind == "integrator" and (not relation_values or not relation_evs):
            continue

        generic = dedupe_evidence([ev for r in source_rows for ev in (r.get("evidence", []) or [])], 12)
        for cand in item.get("discovered") or []:
            for url in cand.get("sourceUrls", []) or []:
                generic.append({"source": "Descubrimiento público", "title": f"Evidencia de ecosistema · {cand.get('name')}", "url": url, "date": cand.get("lastSeenAt"), "type": "discovery-candidate"})
        generic = dedupe_evidence(generic, 12)

        talent_signals = m.get("talent_signals", []) or []
        job_vendors = [f"{x.get('vendor')} · {x.get('signals')} señal(es)" for x in (m.get("manufacturers_in_job_profiles", []) or [])]
        job_profiles = [f"{x.get('family')} · {x.get('signals')} señal(es)" for x in (m.get("profiles_sought", []) or [])]

        def collect_list(*keys: str) -> list[Any]:
            vals: list[Any] = []
            for r in source_rows:
                for k in keys:
                    vals.extend(r.get(k, []) or [])
            return uniq(vals)

        services = collect_list("managed_services", "services")
        specializations = collect_list("specializations", "competencies")
        verticals = collect_list("verticals")
        public_cases = collect_list("customers_public_cases")
        scopes = uniq([r.get("scope") for r in source_rows if r.get("scope")] + [s.get("country") for s in item.get("signals", []) if s.get("country")])
        capabilities: list[str] = []
        for r in source_rows:
            for attr, label in (("soc","SOC"),("noc","NOC"),("mssp","MSSP"),("msp","MSP"),("professional_services","Servicios profesionales"),("financing","Financiación"),("marketplace","Marketplace"),("cloud_marketplace","Marketplace cloud"),("training_enablement","Formación / enablement"),("labs_demos","Labs / demos"),("poc","PoC"),("staging_configuration","Staging / configuración"),("logistics","Logística")):
                if r.get(attr):
                    capabilities.append(label)
        capabilities = uniq(capabilities)

        all_entity_evidence = dedupe_evidence([*generic, *relation_evs, *talent_signals], 16)
        fields = {
            "scope": field(" / ".join(str(x) for x in scopes), all_entity_evidence),
            "roles": field(uniq(roles), relation_evs, qualifier="Rol descrito por la evidencia pública: integrador, reseller, MSP, MSSP, service provider, etc. No es una clasificación comercial propia."),
            "vendor_relations": field(relation_values, relation_evs, qualifier="Solo relaciones con fabricantes Westcon soportadas por evidencia pública. Empleo nunca crea una relación por sí solo."),
            "specializations": field(specializations, all_entity_evidence, qualifier="Solo señales explícitas; no se infieren certificaciones por afinidad tecnológica."),
            "services": field(services, all_entity_evidence),
            "capabilities": field(capabilities, all_entity_evidence),
            "verticals": field(verticals, all_entity_evidence, qualifier="Sectores con actividad/casos públicos; no representa toda la cartera."),
            "public_cases": field(public_cases, all_entity_evidence, qualifier="Casos públicos detectados; no representa la base completa de clientes."),
            "job_vendors": field(job_vendors, talent_signals, qualifier="Menciones de fabricantes/certificaciones en vacantes: señal de skills, nunca prueba de partnership ni ventas."),
            "job_profiles": field(job_profiles, talent_signals, qualifier="Familias de perfiles demandadas en portales/ATS públicos; una vacante no equivale a headcount efectivo."),
        }
        if kind == "distributor":
            overlap = uniq([x for r in source_rows for x in (r.get("westcon_overlap", []) or [])])
            fields["westcon_overlap"] = field(overlap, [*relation_evs, internal_evidence("Westcon España – Presentación Corporativa FY2027", "El solape se calcula contra el portfolio aportado.")], qualifier="Intersección de linecard público con portfolio Westcon; no mide cuota ni presión competitiva.")

        published_fields = {k: v for k, v in fields.items() if v}
        identity_evidence = dedupe_evidence([*all_entity_evidence, *[ev for f in published_fields.values() for ev in (f.get("evidence") or [])]], 10)
        if not identity_evidence:
            continue
        rows.append({"id": base_row.get("entity_id") or f"{kind}-{re.sub('[^a-z0-9]+','-',key)}", "name": name, "evidence": identity_evidence, "fields": published_fields})
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



def signal_theme_ids(signal: Mapping[str, Any]) -> set[str]:
    """Map a market/analyst signal to themes without broad keyword spillover.

    Explicit theme tags always win. Untagged legacy signals are mapped by
    narrow research-title patterns so, for example, a SASE metric cannot appear
    in AI Security merely because its text contains the word security.
    """
    explicit={str(x) for x in (signal.get("themes") or []) if x}
    if explicit:
        return explicit
    title=norm(f"{signal.get('title','')} {signal.get('label','')}")
    mapping: list[tuple[list[str], set[str]]] = [
        (["emea it market 2026", "gasto ia emea"], {"ai-infra","agentic-automation"}),
        (["european ciso priorities"], {"ai-security","secops","cloud-security","sovereignty"}),
        (["european tech market forecast", "gasto tecnologico europa"], {"ai-infra","cloud-security","sovereignty"}),
        (["predictions 2026: infrastructure & operations", "sase vendors"], {"sase","secure-lan","network-aiops","naas"}),
        (["global sovereignty forecast", "soberania media"], {"sovereignty","cloud-security","data-security"}),
        (["forecast analysis: information security"], {"ai-security","secops"}),
        (["ai platforms and models market", "plataformas/modelos ia"], {"ai-infra","agentic-automation"}),
        (["ai cloud market", "cloud ia 2030"], {"ai-infra","sovereignty"}),
        (["magic quadrant for sase"], {"sase"}),
        (["wired and wireless lan"], {"secure-lan","network-aiops","naas"}),
        (["cps protection"], {"ot"}),
        (["endpoint protection"], {"secops"}),
        (["endpoint management"], {"identity","secops"}),
        (["access management"], {"identity"}),
        (["network detection and response"], {"secops","observability"}),
        (["strategic cloud platform"], {"cloud-security","sovereignty","ai-infra"}),
        (["cloud ai infrastructure"], {"ai-infra"}),
        (["robotic process automation"], {"agentic-automation"}),
        (["web application and api protection"], {"cloud-security","data-security"}),
        (["observability"], {"observability"}),
    ]
    out:set[str]=set()
    for needles,themes in mapping:
        if any(n in title for n in needles): out.update(themes)
    return out

def build_trends() -> list[dict[str, Any]]:
    base = load("data/base.json", {})
    vendors = load("data/vendor_intelligence.json", {})
    research = load("data/research.latest.json", {})
    enrich = load("config/v36/trend_enrichment.json", {})
    enrich_themes = enrich.get("themes", {}) or {}

    market_signals: list[dict[str, Any]] = []
    market_signals.extend(vendors.get("marketSignals", []) or [])
    market_signals.extend([x for x in (research.get("analystSignals", []) or []) if x.get("url")])
    for signal in enrich.get("public_signals", []) or []:
        market_signals.append({**signal, "analyst": signal.get("source"), "label": signal.get("title")})
    for vendor in vendors.get("vendors", []) or []:
        for signal in vendor.get("analystSignals", []) or []:
            if signal.get("url"):
                market_signals.append({**signal, "label": signal.get("title"), "detail": signal.get("summary"), "vendor": vendor.get("name")})

    # Local public signals are useful for Iberia context but only when they
    # actually mention the trend topic.
    local_evidence = [x for x in (research.get("evidence", []) or []) if x.get("url") and (x.get("country") in {"ES","PT","IBERIA"} or any(t in norm(x.get("scope")) for t in ("spain","portugal","iberia","espana")))]
    portfolio_src = internal_evidence("Westcon España – Presentación Corporativa FY2027", "Se usa solo para identificar qué fabricantes del portfolio tienen capacidades relacionadas con la tendencia.")

    rows: list[dict[str, Any]] = []
    for theme in base.get("themes", []) or []:
        tid = theme.get("id")
        cfg = enrich_themes.get(tid, {}) or {}
        keywords = TREND_KEYWORDS.get(tid, [norm(theme.get("name"))])
        matched: list[dict[str, Any]] = []
        for signal in market_signals:
            if tid in signal_theme_ids(signal):
                matched.append(signal)
        evs = dedupe_evidence(matched, 14)
        if not evs:
            continue

        metrics: list[str] = []
        for signal in matched:
            metric = signal.get("metric")
            label = signal.get("label") or signal.get("title")
            if metric and label:
                metrics.append(f"{metric} · {label}")
        metrics = uniq(metrics)

        # Actor list is descriptive: vendors explicitly named in source
        # material or cited as peers. It is not a homemade ranking.
        market_players: list[str] = []
        player_evidence: list[dict[str, Any]] = []
        for signal in matched:
            ev = evidence(signal)
            if signal.get("vendor"):
                market_players.append(str(signal.get("vendor")))
                if ev: player_evidence.append(ev)
            for peer in [*(signal.get("peers", []) or []), *(signal.get("players", []) or [])]:
                market_players.append(str(peer))
                if ev: player_evidence.append(ev)
        market_players = uniq(market_players)
        player_evidence = dedupe_evidence(player_evidence, 12)

        # Iberia-specific observations are extracted only from local evidence;
        # no market share or country claim is inferred from global research.
        local_matched: list[dict[str, Any]] = []
        for signal in local_evidence:
            blob = norm(f"{signal.get('title','')} {signal.get('snippet','')} {signal.get('query','')}")
            if any(norm(k) in blob for k in keywords):
                local_matched.append(signal)
        local_evs = dedupe_evidence(local_matched, 6)
        local_summary = [x.get("title") for x in local_matched[:5] if x.get("title")]

        westcon_vendors = cfg.get("westcon_vendors", []) or []
        westcon_sources = [portfolio_src, *[ev for ev in evs if any(norm(v) in norm(f"{ev.get('title','')} {ev.get('source','')}") for v in westcon_vendors)]]

        fields = {
            "domain": field(theme.get("domain"), evs),
            "observed": field(cfg.get("observed") or theme.get("why"), evs, qualifier="Síntesis descriptiva propia construida a partir de las fuentes enlazadas."),
            "market_metrics": field(metrics, matched, qualifier="Tamaños, porcentajes y previsiones tal como aparecen en fuentes públicas. Cada cifra conserva fecha y fuente; no se mezclan metodologías como si fueran una única serie."),
            "horizon": field(cfg.get("horizon"), evs, qualifier="Horizonte temporal descriptivo de las señales disponibles."),
            "drivers": field(cfg.get("drivers", []), evs, qualifier="Factores recurrentes observados en las fuentes que explican la evolución de la tendencia."),
            "buyer_priorities": field(cfg.get("buyer_priorities", []), evs, qualifier="Prioridades de compra/arquitectura observadas en analistas y fuentes sectoriales."),
            "market_players": field(market_players, player_evidence, qualifier="Panorama de fabricantes y actores citados explícitamente por analistas/fuentes o como peers. Solo se identifica liderazgo cuando la fuente lo afirma; no es un ranking propio."),
            "westcon_vendors": field(westcon_vendors, westcon_sources, qualifier="Fabricantes Westcon con capacidades relacionadas; indica presencia funcional en el portfolio."),
            "evolution": field(cfg.get("evolution"), evs, qualifier="Lectura descriptiva de cómo está cambiando el área según las señales enlazadas."),
            "iberia_context": field(local_summary, local_evs, qualifier="Señales específicamente vinculadas a España, Portugal o Iberia. Ausencia de esta sección significa que no se ha encontrado evidencia local suficiente."),
            "sources": field([f"{x.get('source') or x.get('analyst')} · {x.get('title') or x.get('label')}" for x in matched[:10]], matched),
        }
        rows.append({"id": tid, "name": theme.get("name"), "evidence": evs, "fields": {k: v for k, v in fields.items() if v}})
    return rows

def build_architectures() -> list[dict[str, Any]]:
    """Build analyst/standards-led architecture maps with explicit vendor roles.

    v3.5 inherited an automated domain-matching architecture generator. v3.6
    deliberately does not use it because domain affinity can produce nonsense
    mappings (for example, placing UiPath in an Identity layer). The framework
    is defined first; Westcon vendors are then mapped only where an explicit
    capability supports the role.
    """
    doc = load("config/v36/architecture_frameworks.json", {})
    portfolio = {norm(x.get("name")): x for x in load("data/vendor_intelligence.json", {}).get("vendors", []) or []}
    portfolio_src = internal_evidence("Westcon España – Presentación Corporativa FY2027", "Se usa para comprobar que el fabricante forma parte del portfolio y para sus capacidades declaradas de alto nivel.")
    rows: list[dict[str, Any]] = []
    for arch in doc.get("frameworks", []) or []:
        basis = dedupe_evidence(arch.get("basis", []) or [], 10)
        if not basis:
            continue
        layers: list[dict[str, Any]] = []
        mapped_vendors: list[str] = []
        for layer in arch.get("layers", []) or []:
            allowed: list[str] = []
            for vendor_name in layer.get("vendors", []) or []:
                if norm(vendor_name) in portfolio:
                    allowed.append(vendor_name)
                    mapped_vendors.append(vendor_name)
            if not allowed:
                continue
            layers.append({
                "layer": layer.get("name"),
                "vendors": allowed,
                "note": layer.get("reason") or "Encaje funcional por capacidad declarada; no implica integración certificada."
            })
        layer_sources = [*basis, portfolio_src]
        fields = {
            "context": field(arch.get("context"), basis, qualifier="Contexto arquitectónico basado en analistas/estándares, no una propuesta comercial."),
            "analyst_basis": field([f"{x.get('source')} · {x.get('title')}" for x in arch.get("basis", []) or []], basis, qualifier="Referencias usadas para definir la estructura funcional de la arquitectura."),
            "principles": field(arch.get("principles", []) or [], basis, qualifier="Principios de diseño derivados/sintetizados desde las referencias enlazadas."),
            "layers": field(layers, layer_sources, qualifier="El marco funcional se define primero y después se mapea el portfolio por capacidad explícita. Coexistencia en una capa no significa integración certificada."),
            "vendors": field(uniq(mapped_vendors), layer_sources, qualifier="Solo fabricantes Westcon con una capacidad declarada que encaja en alguna capa del marco."),
            "limits": field(arch.get("limits", []) or [], basis, qualifier="Límites de interpretación para evitar asociaciones forzadas o inferencias de integración."),
        }
        rows.append({"id": arch.get("id"), "name": arch.get("title"), "evidence": basis, "fields": {k: v for k, v in fields.items() if v}})
    return rows

def merge_source_catalog() -> list[dict[str, Any]]:
    current = load("data/v34/source_catalog.json", {}).get("sources", []) or []
    additions = load("config/v35/source_additions.json", {}).get("sources", []) or []
    additions_v36 = load("config/v36/source_additions.json", {}).get("sources", []) or []
    rows: dict[str, dict[str, Any]] = {}
    for raw in [*current, *additions, *additions_v36]:
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
        {"id":"scope","label":"Cobertura Westcon","help":"Países en los que el fabricante forma parte del portfolio Westcon aportado. No describe toda su presencia comercial.","clarify":True},
        {"id":"domain","label":"Área tecnológica","help":"Área tecnológica principal usada para ordenar la inteligencia del fabricante.","clarify":True},
        {"id":"capabilities","label":"Capacidades","help":"Capacidades tecnológicas documentadas para el fabricante.","clarify":True},
        {"id":"competitors","label":"Competidores / peers","help":"Todos los competidores o peers encontrados en comparativas y señales públicas trazables. No es un ranking propio ni implica igualdad de cuota.","clarify":True},
        {"id":"distributors","label":"Mayoristas alternativos","help":"Mayoristas/distribuidores relacionados públicamente con el fabricante. Ausencia de datos no implica exclusividad.","clarify":True},
        {"id":"integrators","label":"Partners / integradores","help":"Partners, integradores, instaladores, MSP/MSSP y otros socios encontrados con evidencia pública. El universo se amplía automáticamente.","clarify":True},
        {"id":"analyst_signals","label":"Analistas","help":"Señales públicas de Gartner, IDC, Forrester y otras firmas. No se reconstruye contenido de pago.","clarify":True},
        {"id":"recent_signals","label":"Señales recientes","help":"Noticias, cambios y otras evidencias públicas recientes asociadas al fabricante.","clarify":True}
    ],
    "integrators": [
        {"id":"scope","label":"Ámbito","help":"Geografía explícitamente respaldada por las fuentes; no se asigna España/Portugal sin evidencia.","clarify":True},
        {"id":"roles","label":"Tipo de partner","help":"Clasificación observable: integrador, instalador, reseller/VAR, MSP, MSSP, service provider, consultoría, partner certificado u otros roles publicados.","clarify":True},
        {"id":"vendor_relations","label":"Fabricantes Westcon relacionados","help":"Relaciones con fabricantes del portfolio Westcon respaldadas por directorios, páginas de partner, premios, casos, certificaciones u otras fuentes públicas. Una oferta de empleo por sí sola no prueba relación.","clarify":True},
        {"id":"specializations","label":"Certificaciones / especializaciones","help":"Especializaciones y certificaciones explícitas; nunca inferidas solo por una vacante o una tecnología mencionada.","clarify":True},
        {"id":"services","label":"Servicios","help":"Servicios profesionales, gestionados, implantación, soporte u otros servicios publicados por la entidad.","clarify":True},
        {"id":"capabilities","label":"Capacidades operativas","help":"SOC, NOC, MSP, MSSP, integración, instalación u otras capacidades cuando existe evidencia pública.","clarify":True},
        {"id":"verticals","label":"Verticales","help":"Sectores respaldados por casos o información pública; no representa toda la cartera de clientes.","clarify":True},
        {"id":"public_cases","label":"Casos / clientes públicos","help":"Referencias públicas trazables; no equivale a la base total de clientes.","clarify":True},
        {"id":"job_vendors","label":"Tecnologías en empleo","help":"Fabricantes, productos o certificaciones observados en vacantes. Sirven como señal de capacidades demandadas, nunca como prueba aislada de partnership o ventas.","clarify":True},
        {"id":"job_profiles","label":"Perfiles buscados","help":"Familias de puestos observadas en portales de empleo y ATS públicos. Una vacante no equivale a headcount efectivo.","clarify":True}
    ],
    "distributors": [
        {"id":"scope","label":"Ámbito","help":"Geografía explícitamente respaldada por evidencia.","clarify":True},
        {"id":"vendor_relations","label":"Fabricantes / linecard","help":"Relaciones de distribución confirmadas o probables por fuente pública; puede no representar el linecard completo.","clarify":True},
        {"id":"westcon_overlap","label":"Solape con Westcon","help":"Fabricantes del portfolio Westcon también detectados en el mayorista competidor. No mide presión competitiva ni cuota.","clarify":True},
        {"id":"specializations","label":"Especialización tecnológica","help":"Áreas y competencias respaldadas por evidencia pública.","clarify":True},
        {"id":"services","label":"Servicios","help":"Servicios profesionales, gestionados u otros servicios de valor añadido publicados por el mayorista.","clarify":True},
        {"id":"capabilities","label":"Capacidades de valor","help":"Financiación, marketplace, formación, labs, PoC, staging, logística u otras capacidades cuando existe evidencia.","clarify":True},
        {"id":"job_vendors","label":"Tecnologías en empleo","help":"Fabricantes o tecnologías mencionados en vacantes del mayorista; señal de foco/skills, no prueba de ventas.","clarify":True},
        {"id":"job_profiles","label":"Perfiles buscados","help":"Familias de roles observadas en ofertas públicas.","clarify":True}
    ],
    "trends": [
        {"id":"domain","label":"Área","help":"Dominio tecnológico al que se asocia la tendencia.","clarify":False},
        {"id":"observed","label":"Qué está ocurriendo","help":"Síntesis descriptiva basada exclusivamente en las fuentes enlazadas.","clarify":True},
        {"id":"market_metrics","label":"Mercado / crecimiento","help":"Tamaños, crecimientos y previsiones tal como los publican las fuentes. Fecha, geografía y metodología pueden diferir.","clarify":True},
        {"id":"horizon","label":"Horizonte","help":"Horizonte temporal que aparece de forma consistente en las señales disponibles.","clarify":True},
        {"id":"drivers","label":"Motores de crecimiento","help":"Factores observados en analistas y fuentes sectoriales que explican la evolución del área.","clarify":True},
        {"id":"buyer_priorities","label":"Qué está demandando el mercado","help":"Prioridades de compra/arquitectura observadas en fuentes sectoriales.","clarify":True},
        {"id":"market_players","label":"Panorama de fabricantes","help":"Fabricantes o actores nombrados explícitamente por las fuentes o como peers. Solo se identifica liderazgo cuando una fuente lo clasifica así; no es un ranking propio.","clarify":True},
        {"id":"westcon_vendors","label":"Fabricantes Westcon relacionados","help":"Fabricantes del portfolio con capacidades funcionalmente relacionadas con la tendencia; la relación es descriptiva.","clarify":True},
        {"id":"evolution","label":"Evolución","help":"Lectura descriptiva de cómo está cambiando el área según las señales enlazadas.","clarify":True},
        {"id":"iberia_context","label":"Iberia","help":"Señales específicamente vinculadas a España, Portugal o Iberia. Si no hay evidencia local suficiente, la columna desaparece.","clarify":True},
        {"id":"sources","label":"Señales principales","help":"Principales fuentes públicas utilizadas para sostener la ficha.","clarify":True}
    ],
    "architectures": [
        {"id":"context","label":"Contexto","help":"Problema y alcance de la arquitectura según analistas/estándares; es descriptivo, no una propuesta comercial.","clarify":True},
        {"id":"analyst_basis","label":"Base analítica","help":"Consultoras, estándares y referencias usadas para definir primero el marco funcional, antes de mapear fabricantes.","clarify":True},
        {"id":"principles","label":"Principios","help":"Principios arquitectónicos sintetizados desde las referencias enlazadas.","clarify":True},
        {"id":"layers","label":"Capas y encaje","help":"Capas funcionales definidas por arquitectura y fabricantes Westcon que encajan por capacidad explícita. Compartir capa no implica integración certificada.","clarify":True},
        {"id":"vendors","label":"Fabricantes Westcon","help":"Fabricantes del portfolio que tienen una capacidad explícita para alguna capa del marco.","clarify":True},
        {"id":"limits","label":"Límites / cautelas","help":"Límites de interpretación para evitar asociaciones forzadas. Si una capacidad es adyacente se identifica como tal.","clarify":True}
    ]
}


def build() -> dict[str, Any]:
    sources = merge_source_catalog()
    result = {
        "meta": {
            "version": "3.6.0",
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
    write("data/v36/intelligence.json", data)
    write("data/v36/last_run.json", {
        "version": "3.6.0", "generated_at": data["meta"]["generated_at"], "status": "published",
        "manufacturers": len(data["manufacturers"]), "integrators": len(data["integrators"]),
        "distributors": len(data["distributors"]), "trends": len(data["trends"]),
        "architectures": len(data["architectures"]), "source_count": len(data["source_catalog"]),
    })
    print(json.dumps(load("data/v36/last_run.json", {}), ensure_ascii=False))
