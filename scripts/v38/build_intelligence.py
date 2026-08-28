#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import defaultdict, Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[2]
CONFIDENCE_POLICY = json.loads((ROOT / "config/v38/confidence_policy.json").read_text(encoding="utf-8"))
CONF_THRESHOLDS = CONFIDENCE_POLICY.get("thresholds", {"high": 0.80, "medium": 0.60, "low": 0.35})
PUBLISH_FLOOR = float(CONFIDENCE_POLICY.get("publish_floor", 0.35))


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
        "description": row.get("description") or row.get("snippet") or row.get("summary") or row.get("detail") or row.get("signal") or row.get("evidence"),
        "url": url,
        "date": row.get("date") or row.get("published") or row.get("last_verified") or row.get("collectedAt"),
        "confidence": row.get("confidence") if not isinstance(row.get("confidence"), dict) else row.get("confidence", {}).get("score"),
        "type": row.get("classification") or row.get("source_type") or row.get("kind") or row.get("proofType"),
        "method": row.get("method") or row.get("engine"),
        "source_grade": row.get("source_grade"),
        "country": row.get("country"),
        "scope": row.get("scope"),
    }
    value = {k:v for k,v in value.items() if v not in (None, "", [], {})}
    freshness = _freshness(value)
    value["freshness_status"] = freshness.get("status")
    if freshness.get("age_days") is not None:
        value["age_days"] = freshness.get("age_days")
    if freshness.get("revalidation_days") is not None:
        value["revalidation_days"] = freshness.get("revalidation_days")
    value["revalidation"] = freshness.get("revalidation")
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
        # Normalize freshness metadata even for evidence objects that were
        # already constructed upstream. This keeps every hover consistent.
        fresh = _freshness(item)
        item.setdefault("freshness_status", fresh.get("status"))
        if fresh.get("age_days") is not None:
            item.setdefault("age_days", fresh.get("age_days"))
        if fresh.get("revalidation_days") is not None:
            item.setdefault("revalidation_days", fresh.get("revalidation_days"))
        item.setdefault("revalidation", fresh.get("revalidation"))
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




def _parse_evidence_date(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw or raw.upper().startswith("FY"):
        return None
    raw = raw.replace("Z", "+00:00")
    for candidate in (raw, raw[:10]):
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            pass
    m = re.search(r"\b(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})\b", raw)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
        except Exception:
            return None
    return None


def _freshness(ev: Mapping[str, Any]) -> dict[str, Any]:
    parsed = _parse_evidence_date(ev.get("date"))
    if not parsed:
        return {"status": "unknown", "age_days": None, "revalidation": "Sin fecha normalizable; se mantiene en cola de sondeo cuando el campo lo requiere."}
    age = max(0, (datetime.now(timezone.utc) - parsed).days)
    blob = norm(" ".join(str(ev.get(k) or "") for k in ("type", "method", "source", "url")))
    volatile = any(x in blob for x in ("partner", "linecard", "job", "career", "award", "news", "case", "press"))
    limit = 240 if volatile else 365
    if age <= limit:
        status = "current"
        note = f"Evidencia dentro de ventana de revalidación ({limit} días)."
    elif age <= limit * 2:
        status = "aging"
        note = f"Evidencia envejecida; el motor prioriza revalidación automática (>{limit} días)."
    else:
        status = "stale"
        note = f"Evidencia antigua; se publica solo con cautela y el motor fuerza revalidación automática (>{limit*2} días)."
    return {"status": status, "age_days": age, "revalidation_days": limit, "revalidation": note}


def _freshness_penalty(sources: Iterable[Mapping[str, Any] | None]) -> float:
    rows = [x for x in sources if x]
    if not rows:
        return 0.0
    statuses = []
    for ev in rows:
        statuses.append(_freshness(ev).get("status"))
    if "current" in statuses or "unknown" in statuses:
        return 0.0
    if "aging" in statuses:
        return 0.06
    if statuses and all(x == "stale" for x in statuses):
        return 0.14
    return 0.0

def _score01(value: Any) -> float | None:
    if value in (None, "", False):
        return None
    try:
        score = float(value)
    except Exception:
        return None
    if score > 1:
        score /= 100.0
    return max(0.0, min(1.0, score))


def _evidence_base_score(ev: Mapping[str, Any]) -> float:
    explicit = _score01(ev.get("confidence"))
    if explicit is not None:
        return explicit
    blob = norm(" ".join(str(ev.get(k) or "") for k in ("type", "method", "source", "source_grade", "url")))
    if any(x in blob for x in ("user-provided", "official-partner-directory", "official-distributor-linecard", "official-partner-portal", "official-vendor", "partner-locator")):
        return 0.96
    if any(x in blob for x in ("primary", "company", "official", "gartner", "forrester", "idc", "omdia", "canalys", "dell'oro", "synergy research")):
        return 0.88
    if any(x in blob for x in ("case", "award", "press", "news", "specialized-media", "channel")):
        return 0.76
    if any(x in blob for x in ("job", "career", "ats", "employment", "vacan")):
        return 0.52
    if any(x in blob for x in ("aggregator", "discovery-candidate", "commoncrawl", "google news")):
        return 0.46
    return 0.66


def evidence_confidence(sources: Iterable[Mapping[str, Any] | None], explicit: float | int | None = None) -> float:
    exp = _score01(explicit)
    linked = dedupe_evidence(sources, 12)
    if not linked:
        return exp or 0.0
    scores = [_evidence_base_score(ev) for ev in linked]
    best = max(scores) if scores else 0.0
    independent = len({norm(ev.get("source") or ev.get("url") or ev.get("title")) for ev in linked if ev})
    corroboration = min(0.09, max(0, independent - 1) * 0.03)
    score = max(exp or 0.0, best) + corroboration
    score -= _freshness_penalty(linked)
    return round(max(0.0, min(0.99, score)), 3)


def confidence_band(score: float | int | None) -> str:
    score = _score01(score) or 0.0
    if score >= float(CONF_THRESHOLDS.get("high", .80)):
        return "high"
    if score >= float(CONF_THRESHOLDS.get("medium", .60)):
        return "medium"
    return "low"


def confidence_reason(score: float, sources: Iterable[Mapping[str, Any] | None]) -> str:
    linked = dedupe_evidence(sources, 8)
    band = confidence_band(score)
    official = any(any(t in norm(" ".join(str(ev.get(k) or "") for k in ("type","method","source","url"))) for t in ("official", "primary", "partner-locator", "partner-directory", "user-provided")) for ev in linked)
    freshness = [_freshness(ev).get("status") for ev in linked]
    suffix = ""
    if freshness and all(x == "stale" for x in freshness):
        suffix = " Evidencia antigua: revalidación automática prioritaria."
    elif "aging" in freshness and "current" not in freshness:
        suffix = " Evidencia envejecida: el motor la revalida automáticamente."
    if band == "high":
        base = "Confianza alta: evidencia oficial/primaria o corroboración pública suficientemente sólida." if official else "Confianza alta: varias evidencias públicas coherentes y trazables."
        return base + suffix
    if band == "medium":
        return "Confianza media: evidencia pública útil pero parcial, indirecta o todavía con corroboración limitada." + suffix
    return "Confianza baja: indicio trazable pendiente de corroboración adicional; no debe interpretarse como relación contractual confirmada." + suffix


def atomic_item(value: Any, sources: Iterable[Mapping[str, Any] | None], confidence: float | int | None = None, qualifier: str | None = None) -> dict[str, Any] | None:
    linked = dedupe_evidence(sources, 6)
    if not linked:
        return None
    score = evidence_confidence(linked, confidence)
    if score < PUBLISH_FLOOR:
        return None
    item = {
        "value": value,
        "confidence": score,
        "confidence_band": confidence_band(score),
        "confidence_reason": confidence_reason(score, linked),
        "evidence": linked,
    }
    if qualifier:
        item["qualifier"] = qualifier
    return item


def _match_value_sources(value: Any, linked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    needle = norm(value)
    # Relation values often include geography/status after a middle dot. The
    # entity/vendor part is the most useful matching token.
    head = norm(str(value).split("·", 1)[0])
    candidates = []
    for ev in linked:
        blob = norm(" ".join(str(ev.get(k) or "") for k in ("title", "description", "source", "type", "url")))
        if (needle and needle in blob) or (len(head) >= 3 and head in blob):
            candidates.append(ev)
    return candidates or linked


def field(value: Any, sources: Iterable[Mapping[str, Any] | None], confidence: float | int | None = None, qualifier: str | None = None, items: Iterable[Mapping[str, Any] | None] | None = None) -> dict[str, Any] | None:
    if value in (None, "", [], {}, False):
        return None
    linked = dedupe_evidence(sources, 12)
    if not linked:
        return None
    score = evidence_confidence(linked, confidence)
    if score < PUBLISH_FLOOR:
        return None
    result: dict[str, Any] = {
        "value": value,
        "evidence": linked,
        "confidence": score,
        "confidence_band": confidence_band(score),
        "confidence_reason": confidence_reason(score, linked),
    }
    if isinstance(value, list) and value and not (isinstance(value[0], dict) and value[0].get("layer")):
        atomic: list[dict[str, Any]] = []
        if items is not None:
            for raw in items:
                if raw:
                    atomic.append(dict(raw))
        else:
            for val in value:
                atom = atomic_item(val, _match_value_sources(val, linked), confidence, qualifier)
                if atom:
                    atomic.append(atom)
        if atomic:
            result["items"] = atomic
            result["value"] = [x.get("value") for x in atomic]
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


def _rel_fact_score(rel: Mapping[str, Any]) -> float:
    fc = rel.get("fact_confidence") or {}
    if isinstance(fc, Mapping):
        return _score01(fc.get("score")) or 0.0
    return _score01(fc) or 0.0


def build_manufacturers() -> list[dict[str, Any]]:
    """Publish only Westcon portfolio vendors as rows, with atomic evidence.

    v3.8 deliberately treats confidence as a display dimension rather than a
    binary gate. A datum can be shown from the publication floor upward, but
    every tag is bound to its own evidence and numerical confidence.
    """
    base = load("data/vendor_intelligence.json", {})
    v31 = load("data/v31/entity_intelligence.json", {})
    relationships = load("data/v34/relationships.json", {})
    curated_integrators = load("config/v38/curated_integrator_relations.json", {}).get("relations", []) or []
    curated_distributors = load("config/v38/curated_distributor_relations.json", {}).get("relations", []) or []
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
        if rel_evidence(rel) and _rel_fact_score(rel) >= PUBLISH_FLOOR:
            int_by_vendor[canonical(rel.get("vendor"))].append(rel)
    for rel in relationships.get("distributor_vendor", []) or []:
        if rel_evidence(rel) and _rel_fact_score(rel) >= PUBLISH_FLOOR:
            dist_by_vendor[canonical(rel.get("vendor"))].append(rel)
    for rel in curated_integrators:
        if rel.get("vendor") and rel.get("url"):
            int_by_vendor[canonical(rel.get("vendor"))].append({"_curated": True, **rel})
    for rel in curated_distributors:
        if rel.get("vendor") and rel.get("url"):
            dist_by_vendor[canonical(rel.get("vendor"))].append({"_curated": True, **rel})

    portfolio_src = internal_evidence(
        "Portfolio Westcon Iberia · regla operativa aportada",
        "España y Portugal comparten el portfolio base. Portugal incorpora además Proofpoint y Check Point."
    )
    rows: list[dict[str, Any]] = []
    for vendor in current:
        name = vendor.get("name")
        key = canonical(name)
        v31_rows = v31_by_name.get(key, [])
        public_evidence = dedupe_evidence([ev for r in v31_rows for ev in (r.get("evidence", []) or [])], 24)

        # Portfolio geography is a user-provided business rule, not inferred
        # from public websites.
        scope_value = "PT" if name in {"Proofpoint", "Check Point"} else "ES + PT"

        competitor_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for signal in vendor.get("analystSignals", []) or []:
            ev = evidence(signal)
            for peer in signal.get("peers", []) or []:
                if ev: competitor_map[str(peer)].append(ev)
        for peer in vendor.get("marketCompetitors", []) or []:
            for ev in public_evidence:
                blob = norm(f"{ev.get('title','')} {ev.get('description','')} {ev.get('note','')} {ev.get('source','')}")
                if norm(peer) and norm(peer) in blob:
                    competitor_map[str(peer)].append(ev)
        competitor_items = [atomic_item(peer, evs) for peer,evs in competitor_map.items()]
        competitor_items = [x for x in competitor_items if x]

        dist_items: list[dict[str, Any]] = []
        for x in vendor.get("channelCompetitors", []) or []:
            dist = x.get("name")
            if not dist or "westcon" in norm(dist):
                continue
            ev = evidence({"source": x.get("name"), "title": x.get("evidence") or f"Distribución de {name}", "url": x.get("url"), "date": x.get("date"), "confidence": x.get("confidence"), "classification": "distribution"})
            atom = atomic_item(f"{dist} · {x.get('country') or '—'}", [ev] if ev else [], x.get("confidence"), "Relación de distribución observada en fuente pública.")
            if atom: dist_items.append(atom)
        for rel in dist_by_vendor.get(key, []):
            if rel.get("_curated"):
                dist = rel.get("distributor")
                ev = _signal_evidence(rel)
                atom = atomic_item(f"{dist} · {rel.get('country') or rel.get('scope') or '—'}", [ev] if ev else [], rel.get("confidence"), "Fuente oficial/curada de linecard o distribución.")
            else:
                dist = rel.get("distributor")
                evs = rel_evidence(rel)
                atom = atomic_item(f"{dist} · {(rel.get('geography') or {}).get('scope') or '—'}", evs, _rel_fact_score(rel), rel.get("status_label") or rel.get("status"))
            if atom and dist and "westcon" not in norm(dist): dist_items.append(atom)
        # Deduplicate by displayed value, retaining the strongest evidence.
        dist_best: dict[str, dict[str, Any]] = {}
        for item in dist_items:
            k=norm(item.get("value")); prev=dist_best.get(k)
            if not prev or item.get("confidence",0)>prev.get("confidence",0): dist_best[k]=item
        dist_items=list(dist_best.values())

        int_items: list[dict[str, Any]] = []
        for rel in int_by_vendor.get(key, []):
            if rel.get("_curated"):
                partner = rel.get("name")
                ev = _signal_evidence(rel)
                atom = atomic_item(f"{partner} · {rel.get('country') or '—'} · {rel.get('role') or 'Partner'}", [ev] if ev else [], rel.get("confidence"), "Relación publicada/curada desde portal, premio, directorio o caso.")
            else:
                partner = rel.get("integrator")
                evs=rel_evidence(rel)
                atom=atomic_item(f"{partner} · {(rel.get('geography') or {}).get('scope') or '—'} · {rel.get('status_label') or rel.get('status')}", evs, _rel_fact_score(rel), "Relación con evidencia pública; el color refleja la solidez de la prueba.")
            if atom and partner: int_items.append(atom)
        int_best: dict[str,dict[str,Any]]={}
        for item in int_items:
            # canonical partner name is before first middle dot
            k=norm(str(item.get("value")).split("·",1)[0]); prev=int_best.get(k)
            if not prev or item.get("confidence",0)>prev.get("confidence",0): int_best[k]=item
        int_items=list(int_best.values())

        analyst_items=[]
        for x in vendor.get("analystSignals", []) or []:
            ev=evidence(x)
            atom=atomic_item(f"{x.get('analyst')}: {x.get('title')}", [ev] if ev else [], x.get("confidence"), "Señal pública de analista; no reconstruye contenido de pago.")
            if atom: analyst_items.append(atom)
        latest_public = sorted(public_evidence, key=lambda x: str(x.get("date") or ""), reverse=True)[:8]
        recent_items=[]
        for ev in latest_public:
            atom=atomic_item(ev.get("title"), [ev])
            if atom: recent_items.append(atom)

        fields = {
            "scope": field(scope_value, [portfolio_src], 0.99, qualifier="Cobertura de portfolio aportada por el usuario: portfolio base común ES/PT; Proofpoint y Check Point adicionales en Portugal."),
            "domain": field(vendor.get("domain"), [portfolio_src], 0.98),
            "capabilities": field(vendor.get("capabilities", []), [portfolio_src], 0.96),
            "competitors": field([x["value"] for x in competitor_items], [ev for x in competitor_items for ev in x.get("evidence",[])], items=competitor_items, qualifier="Competidores/peers procedentes de comparativas públicas. El color expresa confianza de la evidencia, no posición competitiva."),
            "distributors": field([x["value"] for x in dist_items], [ev for x in dist_items for ev in x.get("evidence",[])], items=dist_items, qualifier="Mayoristas alternativos detectados públicamente. Verde=alta, amarillo=media, rojo=baja; ausencia de dato no implica exclusividad."),
            "integrators": field([x["value"] for x in int_items], [ev for x in int_items for ev in x.get("evidence",[])], items=int_items, qualifier="Partners/integradores con evidencia pública. La confianza permite publicar indicios trazables sin presentarlos como hechos confirmados."),
            "analyst_signals": field([x["value"] for x in analyst_items], [ev for x in analyst_items for ev in x.get("evidence",[])], items=analyst_items, qualifier="Señales públicas de Gartner, IDC, Forrester y otras firmas; no se reconstruye contenido de pago."),
            "recent_signals": field([x["value"] for x in recent_items], [ev for x in recent_items for ev in x.get("evidence",[])], items=recent_items, qualifier="Señales públicas recientes asociadas al fabricante."),
        }
        identity_evidence = dedupe_evidence([portfolio_src, *public_evidence, *[ev for x in analyst_items for ev in x.get("evidence",[])]], 12)
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
    entity = signal.get("name") or signal.get("distributor") or signal.get("source") or "Entidad"
    vendor = signal.get("vendor") or "fabricante"
    return evidence({
        "source": signal.get("source") or vendor or "Fuente pública",
        "title": signal.get("title") or f"{entity} ↔ {vendor}",
        "description": signal.get("signal") or signal.get("description") or f"Relación pública entre {entity} y {vendor}.",
        "url": signal.get("url"),
        "date": signal.get("date"),
        "confidence": signal.get("confidence"),
        "classification": signal.get("proofType") or signal.get("classification") or "partner-signal",
        "method": signal.get("method") or "curated-public-correlation",
        "country": signal.get("country"),
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
        signal_rows = [*signal_rows, *(load("config/v38/curated_integrator_relations.json", {}).get("relations", []) or [])]
    else:
        signal_rows = [*signal_rows, *(load("config/v38/curated_distributor_relations.json", {}).get("relations", []) or [])]
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
        supported_rels=[]
        for r in rels:
            if kind == "integrator" and norm(r.get("vendor")) not in portfolio_names: continue
            evs=rel_evidence(r); score=_rel_fact_score(r)
            if evs and score >= PUBLISH_FLOOR: supported_rels.append(r)
        confirmed=[r for r in supported_rels if r.get("status")=="CONFIRMED"]
        probable=[r for r in supported_rels if r.get("status")=="PROBABLE"]
        indicative=[r for r in supported_rels if r.get("status") not in {"CONFIRMED","PROBABLE"}]
        relation_items=[]
        for r in [*confirmed,*probable,*indicative]:
            label={"CONFIRMED":"Confirmada","PROBABLE":"Probable"}.get(r.get("status"),"Indicio trazable")
            evs=rel_evidence(r); atom=atomic_item(f"{r.get('vendor')} · {label} · {(r.get('geography') or {}).get('scope') or '—'}",evs,_rel_fact_score(r),"Relación publicada según evidencia disponible; rojo indica indicio, no partnership confirmada.")
            if atom: relation_items.append(atom)
        relation_values=[x["value"] for x in relation_items]
        relation_evs=[ev for x in relation_items for ev in x.get("evidence",[])]
        roles: list[str] = []
        signal_specializations: list[str] = []
        signal_services: list[str] = []
        signal_verticals: list[str] = []
        signal_cases: list[str] = []
        signal_capabilities: list[str] = []
        signal_field_evidence: dict[str, list[dict[str, Any]]] = defaultdict(list)
        dimension_items: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for sig in item.get("signals") or []:
            ev = _signal_evidence(sig)
            # Signals from jobs do not establish a partnership. Only explicit
            # vendor/partner proof or already curated public relationships do.
            proof = norm(sig.get("proofType") or sig.get("classification"))
            relation_proof = any(token in proof for token in ("partner", "award", "directory", "case", "integrator", "reseller", "mssp", "distributor", "linecard")) or sig.get("status") == "curated-public"
            if relation_proof and sig.get("vendor"):
                scope=sig.get("country") or "—"
                atom=atomic_item(f"{sig.get('vendor')} · Evidencia pública · {scope}",[ev] if ev else [],sig.get("confidence"),"Relación respaldada por esta fuente concreta.")
                if atom:
                    relation_items.append(atom); relation_values.append(atom["value"]); relation_evs.extend(atom.get("evidence",[]))
            if sig.get("role"):
                roles.append(str(sig.get("role")))
                # v3.8: controlled semantic propagation. An explicitly published
                # role can support a probable service/capability at a LOWER
                # confidence than the underlying partnership. It never creates
                # a certification, customer case or vertical. The inference is
                # individually traceable and visually yellow/red.
                role_blob = norm(sig.get("role"))
                vendor_name = str(sig.get("vendor") or "").strip()
                base_conf = _score01(sig.get("confidence")) or 0.66
                inferred_conf = max(PUBLISH_FLOOR, min(0.74, round(base_conf * 0.76, 3)))
                if ev and vendor_name:
                    iev = dict(ev)
                    iev["confidence"] = inferred_conf
                    iev["method"] = "role-to-capability-inference-v3.8"
                    iev["description"] = (str(ev.get("description") or "") + " Inferencia controlada: el rol de partner publicado se traduce a una capacidad/servicio probable; no equivale a certificación ni a caso de cliente.").strip()
                    derived=[]
                    if "mssp" in role_blob:
                        derived += [("capabilities","MSSP"),("services",f"Servicios de seguridad gestionados · {vendor_name}")]
                    elif "msp" in role_blob or "managed service" in role_blob:
                        derived += [("capabilities","MSP"),("services",f"Servicios gestionados · {vendor_name}")]
                    if "integrat" in role_blob or "system integrator" in role_blob or "si" == role_blob.strip():
                        derived += [("capabilities","Integración"),("services",f"Integración de soluciones · {vendor_name}")]
                    if "install" in role_blob:
                        derived += [("capabilities","Instalación"),("services",f"Instalación / despliegue · {vendor_name}")]
                    if "reseller" in role_blob or "var" in role_blob or "revendedor" in role_blob:
                        derived += [("services",f"Suministro / reventa · {vendor_name}")]
                    if "service provider" in role_blob or "provider" in role_blob:
                        derived += [("capabilities","Service provider"),("services",f"Servicios asociados · {vendor_name}")]
                    for dim,val in derived:
                        atom=atomic_item(val,[iev],inferred_conf,"Inferencia controlada a partir del rol de partner explícitamente publicado. Se muestra con menor confianza que la relación original.")
                        if atom: dimension_items[dim].append(atom)
            # A single high-quality public source can support several explicit
            # dimensions (tier/specialization/services/vertical/case). Preserve
            # evidence independently for every populated dimension.
            for key_name, target in (("specializations", signal_specializations), ("services", signal_services), ("verticals", signal_verticals), ("public_cases", signal_cases), ("capabilities", signal_capabilities)):
                values = sig.get(key_name) or []
                if isinstance(values, str): values = [values]
                for value in values:
                    if value not in (None, ""):
                        target.append(str(value))
                        if ev:
                            signal_field_evidence[key_name].append(ev)
                            atom=atomic_item(str(value),[ev],sig.get("confidence"),f"Dato {key_name} extraído de esta evidencia concreta.")
                            if atom: dimension_items[key_name].append(atom)

        # If this is an integrator, it must have at least one supported relation
        # to a Westcon vendor. This keeps discovery broad without turning the
        # table into a generic list of IT companies.
        rb={}
        for atom in relation_items:
            k=norm(atom.get("value")); prev=rb.get(k)
            if not prev or atom.get("confidence",0)>prev.get("confidence",0): rb[k]=atom
        relation_items=list(rb.values()); relation_values=[x["value"] for x in relation_items]
        relation_evs=dedupe_evidence([ev for x in relation_items for ev in x.get("evidence",[])],24)
        if kind == "integrator" and (not relation_values or not relation_evs):
            continue

        generic = dedupe_evidence([ev for r in source_rows for ev in (r.get("evidence", []) or [])], 12)
        for cand in item.get("discovered") or []:
            for url in cand.get("sourceUrls", []) or []:
                generic.append({"source": "Descubrimiento público", "title": f"Evidencia de ecosistema · {cand.get('name')}", "url": url, "date": cand.get("lastSeenAt"), "type": "discovery-candidate"})
        generic = dedupe_evidence(generic, 12)

        scopes = uniq([r.get("scope") for r in source_rows if r.get("scope")] + [sig.get("country") for sig in item.get("signals",[]) if sig.get("country")])
        talent_signals = m.get("talent_signals", []) or []
        job_vendors = [f"{x.get('vendor')} · {x.get('signals')} señal(es)" for x in (m.get("manufacturers_in_job_profiles", []) or [])]
        job_profiles = [f"{x.get('family')} · {x.get('signals')} señal(es)" for x in (m.get("profiles_sought", []) or [])]
        if kind == "integrator":
            for x in (m.get("manufacturers_in_job_profiles", []) or []):
                vendor=x.get("vendor")
                if norm(vendor) not in portfolio_names: continue
                matching=[ev for ev in talent_signals if norm(vendor) in norm(f"{ev.get('title','')} {ev.get('description','')} {ev.get('source','')}")]
                if matching and not any(norm(str(v).split("·",1)[0])==norm(vendor) for v in relation_values):
                    atom=atomic_item(f"{vendor} · Indicio por empleo · {(scopes[0] if scopes else '—')}",matching,0.50,"Una vacante indica skills/uso tecnológico; NO prueba partnership, ventas ni certificación.")
                    if atom: relation_items.append(atom); relation_values.append(atom["value"]); relation_evs.extend(atom.get("evidence",[]))

        def add_row_items(dim: str, keys: tuple[str,...]):
            for r in source_rows:
                row_evs=dedupe_evidence(r.get("evidence",[]) or [],8)
                for k in keys:
                    vals=r.get(k,[]) or []
                    if isinstance(vals,str): vals=[vals]
                    for val in vals:
                        atom=atomic_item(str(val),row_evs,None,f"{dim} publicado en el perfil de la entidad y ligado a su evidencia de procedencia.")
                        if atom: dimension_items[dim].append(atom)
        add_row_items("services",("managed_services","services"))
        add_row_items("specializations",("specializations","competencies"))
        add_row_items("verticals",("verticals",))
        add_row_items("public_cases",("customers_public_cases",))
        cap_map=(("soc","SOC"),("noc","NOC"),("mssp","MSSP"),("msp","MSP"),("professional_services","Servicios profesionales"),("financing","Financiación"),("marketplace","Marketplace"),("cloud_marketplace","Marketplace cloud"),("training_enablement","Formación / enablement"),("labs_demos","Labs / demos"),("poc","PoC"),("staging_configuration","Staging / configuración"),("logistics","Logística"))
        for r in source_rows:
            row_evs=dedupe_evidence(r.get("evidence",[]) or [],8)
            for attr,label in cap_map:
                if r.get(attr):
                    atom=atomic_item(label,row_evs,None,"Capacidad operativa publicada en el perfil de la entidad.")
                    if atom: dimension_items["capabilities"].append(atom)
        def dedup_items(dim):
            best={}
            for atom in dimension_items.get(dim,[]):
                k=norm(atom.get("value")); prev=best.get(k)
                if not prev or atom.get("confidence",0)>prev.get("confidence",0): best[k]=atom
            return list(best.values())
        service_items=dedup_items("services"); specialization_items=dedup_items("specializations"); vertical_items=dedup_items("verticals"); case_items=dedup_items("public_cases"); capability_items=dedup_items("capabilities")
        services=[x["value"] for x in service_items]; specializations=[x["value"] for x in specialization_items]; verticals=[x["value"] for x in vertical_items]; public_cases=[x["value"] for x in case_items]; capabilities=[x["value"] for x in capability_items]
        all_entity_evidence = dedupe_evidence([*generic, *relation_evs, *talent_signals], 16)
        fields = {
            "scope": field(" / ".join(str(x) for x in scopes), all_entity_evidence),
            "roles": field(uniq(roles), relation_evs, qualifier="Rol descrito por la evidencia pública: integrador, reseller, MSP, MSSP, service provider, etc. No es una clasificación comercial propia."),
            "vendor_relations": field(relation_values, relation_evs, items=relation_items, qualifier="Relaciones confirmadas/probables e indicios trazables. Los indicios de empleo se muestran en rojo y nunca prueban partnership por sí solos."),
            "specializations": field(specializations, [ev for x in specialization_items for ev in x.get("evidence",[])], items=specialization_items, qualifier="Solo señales explícitas; no se infieren certificaciones por afinidad tecnológica."),
            "services": field(services, [ev for x in service_items for ev in x.get("evidence",[])], items=service_items),
            "capabilities": field(capabilities, [ev for x in capability_items for ev in x.get("evidence",[])], items=capability_items),
            "verticals": field(verticals, [ev for x in vertical_items for ev in x.get("evidence",[])], items=vertical_items, qualifier="Sectores con actividad/casos públicos; no representa toda la cartera."),
            "public_cases": field(public_cases, [ev for x in case_items for ev in x.get("evidence",[])], items=case_items, qualifier="Casos públicos detectados; no representa la base completa de clientes."),
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
    enrich = load("config/v38/trend_enrichment.json", {})
    trend_state = load("config/v38/trend_state.json", {})
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

    local_evidence = [x for x in (research.get("evidence", []) or []) if x.get("url") and (x.get("country") in {"ES","PT","IBERIA"} or any(t in norm(x.get("scope")) for t in ("spain","portugal","iberia","espana")))]
    portfolio_src = internal_evidence("Portfolio Westcon Iberia · regla operativa aportada", "Portfolio base común España/Portugal; Proofpoint y Check Point son adicionales en Portugal.")

    broad_metric_needles=("information security", "security worldwide", "emea it market", "european tech market", "global security market", "overall security market", "technology market")
    strict_metric_needles = {
        "ai-security": ("ai systems security", "aiss", "ai trism", "ai security"),
        "sase": ("sase", "secure access service edge"),
        "secops": ("secops", "security operations", "xdr", "mdr", "ctem"),
        "identity": ("identity", "access management", "iam", "itdr"),
        "data-security": ("data security", "dspm", "cryptograph", "post-quantum", "data protection"),
        "cloud-security": ("cloud security", "cnapp", "cloud-native security"),
        "network-aiops": ("network aiops", "autonomous network", "ai networking"),
        "secure-lan": ("secure lan", "wired and wireless lan", "campus network"),
        "naas": ("naas", "network as a service", "managed network services"),
        "ai-infra": ("ai infrastructure", "ai cloud", "gpu", "neocloud", "ai platforms and models"),
        "observability": ("observability",),
        "ot": ("ot security", "cps protection", "cyber-physical", "industrial security"),
        "services": ("managed services", "professional services", "it services", "consulting services"),
        "sovereignty": ("digital sovereignty", "sovereign cloud", "sovereignty"),
        "agentic-automation": ("agentic automation", "robotic process automation", "rpa", "automation market"),
    }
    display_names = {"ai-infra": "AI-ready Data Center / Fabric / Edge"}
    rows: list[dict[str, Any]] = []
    for theme in base.get("themes", []) or []:
        tid = theme.get("id")
        cfg = enrich_themes.get(tid, {}) or {}
        keywords = TREND_KEYWORDS.get(tid, [norm(theme.get("name"))])
        matched=[signal for signal in market_signals if tid in signal_theme_ids(signal)]
        evs=dedupe_evidence(matched,18)
        if not evs: continue

        specific_items=[]; adjacent_items=[]
        for signal in matched:
            metric=signal.get("metric"); label=signal.get("label") or signal.get("title")
            if not metric or not label: continue
            ev=evidence(signal)
            if not ev: continue
            atom=atomic_item(f"{metric} · {label}",[ev],signal.get("confidence"))
            if not atom: continue
            title=norm(label)
            explicit={str(x) for x in (signal.get("themes") or []) if x}
            specific_for={str(x) for x in (signal.get("specific_for") or []) if x}
            adjacent_for={str(x) for x in (signal.get("adjacent_for") or []) if x}
            scope=norm(signal.get("metric_scope"))
            if "secure lan" in title and "sase vendor" in title:
                is_specific = tid == "secure-lan"
            elif "ai observability" in title:
                is_specific = tid == "observability"
            elif tid in specific_for:
                is_specific=True
            elif tid in adjacent_for or scope == "adjacent":
                is_specific=False
            elif scope == "specific" and (not explicit or tid in explicit):
                is_specific=True
            else:
                # Legacy/untagged metrics only become specific when their own label
                # actually names this trend. Otherwise they are context, never the
                # size/growth of the trend itself.
                strict=strict_metric_needles.get(tid, ())
                direct_name=any(n in title for n in strict)
                broad=any(n in title for n in broad_metric_needles) or (explicit and len(explicit)>1)
                is_specific=direct_name and not broad
            (specific_items if is_specific else adjacent_items).append(atom)

        # Build an evidence-bound actor panorama from explicit actors/peers and from
        # competitors of Westcon vendors related to the trend. This expands coverage
        # without presenting inferred market leadership as fact.
        actor_best:dict[str,dict[str,Any]]={}
        def put_actor(name, srcs, confidence=None):
            if not name: return
            atom=atomic_item(str(name),srcs,confidence,"Actor citado o peer con evidencia pública; no implica liderazgo salvo que la fuente lo afirme.")
            if not atom: return
            k=norm(name); prev=actor_best.get(k)
            if not prev or atom.get("confidence",0)>prev.get("confidence",0): actor_best[k]=atom
        for signal in matched:
            ev=evidence(signal)
            explicit={str(x) for x in (signal.get("themes") or []) if x}
            specific_for={str(x) for x in (signal.get("specific_for") or []) if x}
            # Actors from broad/multi-theme context do not automatically become
            # members of this trend's vendor panorama. This prevents, e.g., an
            # automation vendor appearing as an AI-security market actor merely
            # because it was present in a broad AI market signal.
            direct_actor = tid in specific_for or len(explicit)==1 or (not explicit and tid in signal_theme_ids(signal) and any(n in norm(signal.get("title") or signal.get("label")) for n in strict_metric_needles.get(tid,())))
            if direct_actor and signal.get("vendor") and ev: put_actor(signal.get("vendor"),[ev],signal.get("confidence"))
            if direct_actor:
                for peer in [*(signal.get("peers",[]) or []),*(signal.get("players",[]) or [])]:
                    if ev: put_actor(peer,[ev],signal.get("confidence"))
        westcon_vendors=cfg.get("westcon_vendors",[]) or []
        for vendor in vendors.get("vendors",[]) or []:
            if vendor.get("name") not in westcon_vendors: continue
            for sig in vendor.get("analystSignals",[]) or []:
                ev=evidence(sig)
                if not ev or tid not in signal_theme_ids(sig): continue
                put_actor(vendor.get("name"),[ev],sig.get("confidence"))
                for peer in sig.get("peers",[]) or []: put_actor(peer,[ev],sig.get("confidence"))
        market_items=list(actor_best.values())

        local_matched=[]
        for signal in local_evidence:
            blob=norm(f"{signal.get('title','')} {signal.get('snippet','')} {signal.get('query','')}")
            if any(norm(k) in blob for k in keywords): local_matched.append(signal)
        local_items=[]
        for x in local_matched[:8]:
            ev=evidence(x); atom=atomic_item(x.get("title"),[ev] if ev else [],x.get("confidence"))
            if atom: local_items.append(atom)

        westcon_items=[]
        for name in westcon_vendors:
            supporting=[portfolio_src]
            supporting += [evidence(x) for x in matched if norm(name) in norm(f"{x.get('vendor','')} {x.get('title','')} {x.get('label','')} {x.get('detail','')}") and evidence(x)]
            atom=atomic_item(name,supporting,0.92 if len(supporting)>1 else 0.78,"Encaje funcional del portfolio con la tendencia; no equivale a liderazgo de mercado.")
            if atom: westcon_items.append(atom)

        def list_atoms(values, sources, confidence=.78, qualifier=None):
            out=[]
            for v in values or []:
                a=atomic_item(v,sources,confidence,qualifier)
                if a: out.append(a)
            return out
        driver_items=list_atoms(cfg.get("drivers",[]),evs,.78)
        buyer_items=list_atoms(cfg.get("buyer_priorities",[]),evs,.78)
        source_items=[]
        for x in matched[:12]:
            ev=evidence(x)
            a=atomic_item(f"{x.get('source') or x.get('analyst')}: {x.get('title') or x.get('label')}",[ev] if ev else [],x.get('confidence'))
            if a: source_items.append(a)

        no_specific="Sin cifra específica pública localizada todavía; se mantiene sondeo activo."
        no_local="Sin señal Iberia específica suficientemente sustentada todavía; se mantiene sondeo activo."
        status_src={"source":"Motor Westcon Intelligence v3.8","title":"Estado de cobertura de investigación","date":datetime.now(timezone.utc).date().isoformat(),"type":"research-status","confidence":0.72,"description":"Estado calculado sobre las fuentes consultadas; no afirma ausencia de mercado, solo ausencia de evidencia específica localizada."}
        if not specific_items: specific_items=[atomic_item(no_specific,[status_src],.72)]
        if not adjacent_items: adjacent_items=[atomic_item("Sin métrica adyacente necesaria/localizada para esta ficha.",[status_src],.72)]
        if not market_items: market_items=[atomic_item("Panorama específico en investigación; no se publica un ranking sin evidencia suficiente.",[status_src],.72)]
        if not local_items: local_items=[atomic_item(no_local,[status_src],.72)]
        specific_items=[x for x in specific_items if x]; adjacent_items=[x for x in adjacent_items if x]; market_items=[x for x in market_items if x]; local_items=[x for x in local_items if x]

        fields={
          "domain":field(theme.get("domain"),evs),
          "observed":field(cfg.get("observed") or theme.get("why"),evs,qualifier="Síntesis descriptiva propia construida a partir de las fuentes enlazadas."),
          "trend_market_metrics":field([x["value"] for x in specific_items],[ev for x in specific_items for ev in x.get("evidence",[])],items=specific_items,qualifier="Solo cifras específicas de esta tendencia. No se mezclan con mercados adyacentes."),
          "adjacent_market_metrics":field([x["value"] for x in adjacent_items],[ev for x in adjacent_items for ev in x.get("evidence",[])],items=adjacent_items,qualifier="Contexto de mercados más amplios o adyacentes; nunca se presenta como tamaño de la tendencia concreta."),
          "horizon":field(cfg.get("horizon") or "2026–2030",evs),
          "drivers":field([x["value"] for x in driver_items],[ev for x in driver_items for ev in x.get("evidence",[])],items=driver_items),
          "buyer_priorities":field([x["value"] for x in buyer_items],[ev for x in buyer_items for ev in x.get("evidence",[])],items=buyer_items),
          "market_players":field([x["value"] for x in market_items],[ev for x in market_items for ev in x.get("evidence",[])],items=market_items,qualifier="Actores citados o peers con evidencia. No es ranking propio."),
          "westcon_vendors":field([x["value"] for x in westcon_items],[ev for x in westcon_items for ev in x.get("evidence",[])],items=westcon_items,qualifier="Fabricantes Westcon con encaje funcional documentado; no implica liderazgo."),
          "evolution":field(cfg.get("evolution") or "Evolución en seguimiento continuo.",evs),
          "iberia_context":field([x["value"] for x in local_items],[ev for x in local_items for ev in x.get("evidence",[])],items=local_items),
          "sources":field([x["value"] for x in source_items],[ev for x in source_items for ev in x.get("evidence",[])],items=source_items),
        }
        analytics=(trend_state.get("themes",{}) or {}).get(tid,{})
        rows.append({"id":tid,"name":display_names.get(tid, theme.get("name")),"evidence":evs,"analytics":analytics,"fields":{k:v for k,v in fields.items() if v}})
    return rows

def build_architectures() -> list[dict[str, Any]]:
    """Build analyst/standards-led architecture maps with explicit vendor roles.

    The framework is defined first from analyst/standards evidence. Westcon
    vendors are mapped only when a declared capability supports the role. Each
    vendor label carries its own atomic provenance: the architecture basis plus
    the specific portfolio capability used for the mapping.
    """
    doc = load("config/v38/architecture_frameworks.json", {})
    portfolio = {norm(x.get("name")): x for x in load("data/vendor_intelligence.json", {}).get("vendors", []) or []}
    rows: list[dict[str, Any]] = []
    for arch in doc.get("frameworks", []) or []:
        basis = dedupe_evidence(arch.get("basis", []) or [], 10)
        if not basis:
            continue
        layers: list[dict[str, Any]] = []
        mapped_vendors: list[str] = []
        vendor_atoms_by_name: dict[str, dict[str, Any]] = {}
        for layer in arch.get("layers", []) or []:
            allowed: list[str] = []
            vendor_items: list[dict[str, Any]] = []
            for vendor_name in layer.get("vendors", []) or []:
                vendor = portfolio.get(norm(vendor_name))
                if not vendor:
                    continue
                allowed.append(vendor_name)
                mapped_vendors.append(vendor_name)
                capabilities = uniq(vendor.get("capabilities", []) or [])
                capability_text = ", ".join(capabilities) if capabilities else "capacidad de portfolio declarada"
                portfolio_ev = internal_evidence(
                    f"{vendor_name} · capacidades de portfolio Westcon FY27",
                    f"Capacidades declaradas: {capability_text}. Se usan únicamente para comprobar el encaje funcional en la capa «{layer.get('name')}»; no prueban integración certificada con otros fabricantes."
                )
                role_ev = {
                    "source": "Westcon Iberia Business Intelligence v3.8",
                    "title": f"Mapeo funcional · {vendor_name} → {layer.get('name')}",
                    "description": layer.get("reason") or "Encaje funcional por capacidad explícita.",
                    "date": datetime.now(timezone.utc).date().isoformat(),
                    "type": "analyst-led-synthesis",
                    "method": "framework-first capability mapping",
                    "confidence": 0.82,
                }
                # Keep the atomic evidence compact and intelligible: one source
                # for the vendor capability, one for the explicit mapping, and
                # up to two references defining the architectural layer.
                atom_sources = [portfolio_ev, role_ev, *basis[:2]]
                atom = atomic_item(
                    vendor_name,
                    atom_sources,
                    .82,
                    "Encaje funcional documentado. No implica integración certificada, liderazgo de mercado ni una decisión comercial."
                )
                if atom:
                    vendor_items.append(atom)
                    existing = vendor_atoms_by_name.get(norm(vendor_name))
                    if not existing or float(atom.get("confidence") or 0) > float(existing.get("confidence") or 0):
                        vendor_atoms_by_name[norm(vendor_name)] = atom
            if not allowed:
                continue
            layers.append({
                "layer": layer.get("name"),
                "vendors": allowed,
                "vendor_items": vendor_items,
                "note": layer.get("reason") or "Encaje funcional por capacidad declarada; no implica integración certificada."
            })
        layer_sources = basis
        vendor_items = [vendor_atoms_by_name[norm(v)] for v in uniq(mapped_vendors) if norm(v) in vendor_atoms_by_name]
        fields = {
            "context": field(arch.get("context"), basis, qualifier="Contexto arquitectónico basado en analistas/estándares, no una propuesta comercial."),
            "analyst_basis": field([f"{x.get('source')} · {x.get('title')}" for x in arch.get("basis", []) or []], basis, qualifier="Referencias usadas para definir la estructura funcional de la arquitectura."),
            "principles": field(arch.get("principles", []) or [], basis, qualifier="Principios de diseño derivados/sintetizados desde las referencias enlazadas."),
            "layers": field(layers, basis, qualifier="El marco funcional se define primero y después se mapea el portfolio por capacidad explícita. Cada fabricante conserva trazabilidad atómica. Coexistencia en una capa no significa integración certificada."),
            "vendors": field(
                [x.get("value") for x in vendor_items],
                [ev for x in vendor_items for ev in x.get("evidence", [])],
                items=vendor_items,
                qualifier="Solo fabricantes Westcon con una capacidad declarada que encaja en alguna capa del marco. Cada etiqueta identifica su evidencia concreta."
            ),
            "limits": field(arch.get("limits", []) or [], basis, qualifier="Límites de interpretación para evitar asociaciones forzadas o inferencias de integración."),
        }
        rows.append({"id": arch.get("id"), "name": arch.get("title"), "evidence": basis, "fields": {k: v for k, v in fields.items() if v}})
    return rows

def merge_source_catalog() -> list[dict[str, Any]]:
    current = load("data/v34/source_catalog.json", {}).get("sources", []) or []
    additions = load("config/v35/source_additions.json", {}).get("sources", []) or []
    additions_v36 = load("config/v36/source_additions.json", {}).get("sources", []) or []
    additions_v37 = load("config/v38/source_additions.json", {}).get("sources", []) or []
    rows: dict[str, dict[str, Any]] = {}
    for raw in [*current, *additions, *additions_v36, *additions_v37]:
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
        {"id":"trend_market_metrics","label":"Mercado específico / adopción / crecimiento","help":"Indicadores que describen directamente esta tendencia: tamaño/CAGR cuando existe y, si no, señales directas de adopción o formación del mercado. Nunca se mezclan aquí cifras de mercados más amplios.","clarify":True},
        {"id":"adjacent_market_metrics","label":"Mercado adyacente / contexto","help":"Cifras de mercados más amplios o relacionados que ayudan a contextualizar, pero NO son el tamaño de la tendencia concreta.","clarify":True},
        {"id":"horizon","label":"Horizonte","help":"Horizonte temporal que aparece de forma consistente en las señales disponibles.","clarify":True},
        {"id":"drivers","label":"Motores de crecimiento","help":"Factores observados en analistas y fuentes sectoriales que explican la evolución del área.","clarify":True},
        {"id":"buyer_priorities","label":"Qué está demandando el mercado","help":"Prioridades de compra/arquitectura observadas en fuentes sectoriales.","clarify":True},
        {"id":"market_players","label":"Panorama de fabricantes","help":"Fabricantes o actores nombrados explícitamente por las fuentes o como peers. Solo se identifica liderazgo cuando una fuente lo clasifica así; no es un ranking propio.","clarify":True},
        {"id":"westcon_vendors","label":"Fabricantes Westcon relacionados","help":"Fabricantes del portfolio con capacidades funcionalmente relacionadas con la tendencia; la relación es descriptiva.","clarify":True},
        {"id":"evolution","label":"Evolución","help":"Lectura descriptiva de cómo está cambiando el área según las señales enlazadas.","clarify":True},
        {"id":"iberia_context","label":"Iberia","help":"Señales específicamente vinculadas a España, Portugal o Iberia. Si no hay evidencia local suficiente, la ficha lo indica explícitamente y el motor mantiene el sondeo activo.","clarify":True},
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
            "version": "3.8.0",
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
    write("data/v38/intelligence.json", data)
    write("data/v38/last_run.json", {
        "version": "3.8.0", "generated_at": data["meta"]["generated_at"], "status": "published",
        "manufacturers": len(data["manufacturers"]), "integrators": len(data["integrators"]),
        "distributors": len(data["distributors"]), "trends": len(data["trends"]),
        "architectures": len(data["architectures"]), "source_count": len(data["source_catalog"]),
    })
    print(json.dumps(load("data/v38/last_run.json", {}), ensure_ascii=False))
