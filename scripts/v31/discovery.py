from __future__ import annotations

import json
import os
import random
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, FIRST_COMPLETED, wait
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Tuple

from .source_learning import LearningStore
from .taxonomy import classify_record, procurement_anchor_score

UA = "Westcon-Iberia-Decision-Intelligence/3.1.5 public-research"


def _http_json(url: str, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def _http_text(url: str, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def google_news(query: str, country="ES", lang="es", limit=12, timeout=8):
    ceid = f"{country}:{lang}"
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": query, "hl": lang, "gl": country, "ceid": ceid}
    )
    xml = _http_text(url, timeout=timeout)
    root = ET.fromstring(xml)
    out = []
    for item in root.findall(".//item")[:limit]:
        source_node = item.find("source")
        out.append({
            "title": item.findtext("title") or "",
            "url": item.findtext("link") or "",
            "published_at": item.findtext("pubDate") or "",
            "source": source_node.text if source_node is not None and source_node.text else "Google News RSS",
            "discovery_provider": "google_news_rss",
            "query": query,
        })
    return out


def gdelt(query: str, limit=12, timeout=8):
    params = {
        "query": query,
        "mode": "ArtList",
        "maxrecords": str(limit),
        "format": "json",
        "sort": "HybridRel",
    }
    url = "https://api.gdeltproject.org/api/v2/doc/doc?" + urllib.parse.urlencode(params)
    data = _http_json(url, timeout=timeout)
    out = []
    for a in data.get("articles", [])[:limit]:
        out.append({
            "title": a.get("title", ""),
            "url": a.get("url", ""),
            "published_at": a.get("seendate", ""),
            "source": a.get("domain", "GDELT"),
            "language": a.get("language"),
            "discovery_provider": "gdelt",
            "query": query,
        })
    return out


def brave(query: str, limit=10, timeout=8):
    key = os.getenv("BRAVE_SEARCH_API_KEY")
    if not key:
        return []
    url = "https://api.search.brave.com/res/v1/web/search?" + urllib.parse.urlencode(
        {"q": query, "count": min(limit, 20)}
    )
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "X-Subscription-Token": key, "User-Agent": UA},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8", errors="replace"))
    return [
        {
            "title": x.get("title", ""),
            "url": x.get("url", ""),
            "summary": x.get("description", ""),
            "source": "Brave Search",
            "discovery_provider": "brave",
            "query": query,
        }
        for x in data.get("web", {}).get("results", [])[:limit]
    ]


# Query variants are intentionally compact. v3.1.1 used long whitespace-separated
# keyword chains which many providers interpreted as an implicit AND, causing valid
# calls to return zero rows.
DIMENSION_QUERY_VARIANTS = {
    "distribution": [
        "distributor OR mayorista OR distribuidor",
        '"channel partner" OR distribution OR distribución',
    ],
    "certification": [
        "certification OR certified OR certificación",
        'specialization OR especialización OR "partner level"',
    ],
    "customers": [
        '"case study" OR customer OR cliente',
        '"customer story" OR referencia OR "caso de éxito"',
    ],
    "procurement": [
        "tender OR procurement OR licitación OR adjudicación",
        '"contract award" OR contrato OR expediente',
    ],
    "services": [
        '"managed services" OR MSSP OR MSP',
        '"professional services" OR SOC OR NOC',
    ],
    "ma": [
        "acquisition OR merger OR adquisición OR fusión",
        "partnership OR alliance OR alianza OR acuerdo",
    ],
    "hiring": [
        "hiring OR careers OR vacancies OR empleo",
        "engineer OR security OR cloud OR network",
    ],
    "awards": [
        "award OR awards OR premio OR reconocimiento",
        '"partner of the year" OR winner OR galardón',
    ],
    "competitive": [
        "competitor OR competition OR competencia",
        "migration OR replacement OR displacement OR sustitución",
    ],
}


def _clean_alias(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "").strip(" -–—/|")
    return value


def _entity_aliases(entity_name: str) -> List[str]:
    """Generate conservative aliases for Iberian entity naming conventions."""
    raw = _clean_alias(entity_name)
    if not raw:
        return []
    aliases = [raw]
    # Multi-brand seed such as "V-Valley / Esprinet".
    for part in re.split(r"\s*/\s*|\s*\|\s*", raw):
        part = _clean_alias(part)
        if part:
            aliases.append(part)
    # Geographic suffixes often disappear from headlines.
    for a in list(aliases):
        stripped = re.sub(r"\s+(Spain|Portugal|Iberia|España|España y Portugal)$", "", a, flags=re.I).strip()
        if stripped and stripped != a:
            aliases.append(stripped)
    # Hyphenated brand families are often written with spaces.
    for a in list(aliases):
        spaced = _clean_alias(re.sub(r"[-–—]", " ", a))
        if spaced and spaced != a:
            aliases.append(spaced)
    # Westcon-Comstor is frequently referenced as either brand independently.
    if raw.lower() in {"westcon-comstor", "westcon comstor"}:
        aliases.extend(["Westcon", "Comstor"])

    out = []
    seen = set()
    for a in aliases:
        key = a.casefold()
        if len(a) < 3 or key in seen:
            continue
        seen.add(key)
        out.append(a)
    # Prefer the most specific names first.
    out.sort(key=len, reverse=True)
    return out


def _search_entity(entity_name: str) -> str:
    aliases = _entity_aliases(entity_name)
    if not aliases:
        return entity_name
    # Avoid searching a slash-combined or geography-suffixed seed when a cleaner
    # brand alias exists. Keep specificity by choosing the longest alias that has
    # no slash and no trailing country marker.
    cleaned = [a for a in aliases if "/" not in a and not re.search(r"\s+(Spain|Portugal|Iberia|España)$", a, re.I)]
    if cleaned:
        return cleaned[0]
    return aliases[0]


def make_query(entity: str, dimension: str, domains: List[str] | None = None, variant: int = 0, country: str | None = None, freshness_days: int | None = None) -> str:
    search_entity = _search_entity(entity)
    variants = DIMENSION_QUERY_VARIANTS.get(dimension, [dimension])
    clause = variants[variant % len(variants)]
    query = f'"{search_entity}" ({clause})'
    country = (country or "").upper().strip()
    if country == "PT" and "portugal" not in search_entity.casefold():
        query += " Portugal"
    elif country == "ES" and not re.search(r"\b(spain|españa)\b", search_entity, re.I):
        query += " (Spain OR España)"
    elif country == "IBERIA":
        query += " (Iberia OR Spain OR España OR Portugal)"
    # Keep daily discovery biased toward current intelligence.  Google News accepts
    # normal search operators; an absolute after: date is safer than relying on a
    # provider-specific relative-time syntax.  The quality layer still verifies the
    # publication date independently, so this is only a discovery hint.
    if freshness_days and freshness_days > 0:
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=int(freshness_days))).date().isoformat()
        query += f" after:{cutoff}"
    domains = [d.strip() for d in (domains or []) if d and d.strip()]
    if domains:
        query += " (" + " OR ".join(f"site:{d}" for d in domains[:2]) + ")"
    return query


def _entity_key(ent: Dict[str, Any]) -> Tuple[str, str, str]:
    return (
        str(ent.get("entity_type") or "vendor"),
        str(ent.get("country") or "IBERIA"),
        str(ent.get("name") or "").strip().lower(),
    )


def _dedupe_entities(entities: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    seen = set()
    for ent in entities:
        if not isinstance(ent, dict) or not ent.get("name"):
            continue
        key = _entity_key(ent)
        if key in seen:
            continue
        seen.add(key)
        out.append(ent)
    return out


def _source_matches(src: Dict[str, Any], ent: Dict[str, Any], dimension: str) -> bool:
    if src.get("enabled", True) is False or src.get("category") == "discovery":
        return False
    et = str(ent.get("entity_type") or "vendor")
    country = str(ent.get("country") or "IBERIA")
    allowed_types = set(src.get("entity_types") or ["all"])
    if et not in allowed_types and "all" not in allowed_types:
        return False
    dims = set(src.get("dimensions") or ["all"])
    if dimension not in dims and "all" not in dims:
        return False
    countries = set(src.get("countries") or ["GLOBAL"])
    if country not in countries and "GLOBAL" not in countries and "IBERIA" not in countries:
        return False
    return True


def _source_affinity(src: Dict[str, Any], ent: Dict[str, Any], learning: LearningStore) -> float:
    score = float(src.get("authority", 0.5)) * learning.get(str(src.get("id"))).priority()
    name = str(ent.get("name") or "").strip().lower()
    for seeded in src.get("seed_entities") or []:
        if str(seeded.get("name") or "").strip().lower() == name:
            score *= 2.4
            break
    category = str(src.get("category") or "")
    if category in {"vendor", "integrator", "distributor", "official", "security", "channel"}:
        score *= 1.12
    score *= random.uniform(0.96, 1.04)
    return score


def _norm_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").casefold()).strip()


def _is_relevant(row: Dict[str, Any], entity_name: str) -> bool:
    """Result must mention a canonical entity name or a conservative alias."""
    hay = _norm_text(" ".join(str(row.get(k) or "") for k in ("title", "summary", "source", "url")))
    if not hay:
        return False
    for alias in _entity_aliases(entity_name):
        needle = _norm_text(alias)
        if not needle:
            continue
        if len(needle) <= 5:
            if re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", hay, flags=re.I):
                return True
        elif needle in hay:
            return True
    return False


COUNTRY_HINTS = {
    "PT": ("portugal", "portuguese", "portugues", "português", "lisboa", "lisbon", "porto", ".pt", "jornal de negocios", "jornal de negócios", "observador", "expresso", "eco", "sapo", "silicon portugal", "pcguia"),
    "ES": ("spain", "españa", "espana", "spanish", "madrid", "barcelona", ".es", "expansion", "expansión", "el economista", "computing españa", "revista byte", "red seguridad"),
}
OTHER_GEO_HINTS = {
    "PT": ("brasil", "brazil", ".br", "mexico", "méxico", "argentina", "colombia", "chile"),
    "ES": ("brasil", "brazil", ".br", "mexico", "méxico", "argentina", "colombia", "chile", "portugal"),
}

DIMENSION_PATTERNS = {
    "distribution": (
        "distribution agreement", "acuerdo de distribución", "acuerdo de distribucion", "acordo de distribuição", "acordo de distribuicao",
        "global distributor", "distribuidor global", "selected as distributor", "seleccionado como distribuidor", "nombrado distribuidor",
    ),
    "certification": (
        "certified", "certification", "certificación", "certificacion", "certificação", "certificacao", "accreditation", "acreditación", "acreditacion",
        "gold partner", "platinum partner", "premier partner", "elite partner", "partner level", "certified partner",
    ),
    "customers": (
        "case study", "customer story", "success story", "caso de éxito", "caso de exito", "caso de sucesso",
        "customer", "cliente", "referencia", "implementa", "implemented", "deploys", "deployed", "despliega",
        "adopta", "adopts", "selecciona", "selected", "escolhe", "aposta em", "com soluções da", "com solucoes da", "con soluciones de", "de la mano de",
    ),
    "procurement": (
        "tender", "procurement", "licitación", "licitacion", "adjudicación", "adjudicacion", "adjudicatario",
        "contract award", "award notice", "expediente", "pliego", "contracting authority", "cpv", "concurso público", "concurso publico",
    ),
    "services": (
        "managed services", "managed service", "servicios gestionados", "serviços geridos", "professional services", "servicios profesionales", "serviços profissionais",
        "mssp", "msp", "soc", "noc", "as-a-service", "onesoc", "new practice", "nueva práctica", "nueva practica", "nova prática", "nova pratica",
        "áreas de especialización", "areas de especializacion", "áreas de especialização", "areas de especializacao",
    ),
    "ma": (
        "acquisition", "acquires", "acquired", "merger", "merges", "adquisición", "adquisicion", "fusión", "fusion", "fusão", "fusao",
        "acuerda la compra de", "acorda a compra de", "takeover", "buyout",
    ),
    "hiring": (
        "hiring", "vacancy", "vacancies", "job opening", "careers", "nuevo ceo", "novo ceo", "new ceo", "nuevo director", "nueva directora",
        "novo diretor", "nova diretora", "nuevo head", "novo head", "new head", "nuevo cmo", "nova cmo", "new cmo", "nombra a", "nomeia",
        "al frente del área", "al frente del area", "à frente da área", "a frente da area",
    ),
    "awards": (
        "award", "awards", "premio", "prémio", "premios", "prémios", "winner", "finalist", "vencedor", "galardón", "galardon", "reconocimiento",
        "partner of the year", "distributor of the year", "distribuidor del año", "distribuidor do ano", "digital awards",
    ),
    "competitive": (
        "competitor", "competition", "competencia", "market share", "cuota de mercado", "quota de mercado", "replacement", "replaces", "sustitución", "sustitucion",
        "migration", "migración", "migracion", "displacement", "rival", "plan estratégico", "plan estrategico", "strategic plan", "plano estratégico", "plano estrategico",
        "revenue target", "objetivo de ingresos", "growth target", "reestructura", "reorganiza", "posicionamiento", "posicionamento", "informe", "report", "barómetro", "barometro",
    ),
}

CLASS_TO_DIMENSION = {
    "procurement_award": "procurement",
    "tender": "procurement",
    "contract": "procurement",
    "certification": "certification",
    "distribution_agreement": "distribution",
    "ma_activity": "ma",
    "leadership_change": "hiring",
    "hiring_signal": "hiring",
    "customer_reference": "customers",
    "customer_award": "awards",
    "vendor_award": "awards",
    "partner_award": "awards",
    "industry_award": "awards",
    "partnership": "competitive",
    "strategy_growth": "competitive",
    "market_signal": "competitive",
    "analyst_signal": "competitive",
    "service_launch": "services",
    "product_release": "services",
    "capability_change": "services",
}

ALLOWED_DIMENSIONS = {
    "vendor": {"distribution", "certification", "customers", "procurement", "ma", "competitive", "services", "awards"},
    "distributor": {"distribution", "services", "ma", "hiring", "competitive", "customers", "awards", "procurement"},
    "integrator": {"certification", "customers", "procurement", "services", "hiring", "awards", "ma", "competitive"},
}


def _quality_blob(row: Dict[str, Any]) -> str:
    text = " | ".join(str(row.get(k) or "") for k in ("title", "summary", "source", "url"))
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text.casefold()).strip()


def _content_blob(row: Dict[str, Any]) -> str:
    """Geography and event semantics should be driven by content, not publisher domain."""
    text = " | ".join(str(row.get(k) or "") for k in ("title", "summary"))
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text.casefold()).strip()


def _geo_relevant(row: Dict[str, Any], ent: Dict[str, Any]) -> bool:
    country = str(ent.get("country") or "IBERIA").upper()
    blob = _quality_blob(row)
    content = _content_blob(row)
    entity_name = _norm_text(str(ent.get("name") or ""))

    if country in {"PT", "ES"}:
        if entity_name and entity_name in blob:
            return True
        if any(h in blob for h in COUNTRY_HINTS[country]):
            return True
        if any(h in blob for h in OTHER_GEO_HINTS[country]):
            return False
        return False

    if country == "IBERIA":
        # Explicitly non-Iberian regional news is not useful unless the content is global.
        foreign = ("latin america", "america latina", "américa latina", "brasil", "brazil", "chile", "mexico", "méxico", "argentina", "colombia")
        global_anchor = ("global", "worldwide", "mundial", "europe", "europa", "iberia", "spain", "españa", "portugal")
        if any(x in content for x in foreign) and not any(x in content for x in global_anchor):
            return False
        return True

    if country == "GLOBAL":
        # Keep global developments and Iberian/European relevance, but drop clearly regional
        # LATAM-only stories from the main Westcon Iberia signal stream.
        foreign = ("latin america", "america latina", "américa latina", "brasil", "brazil", "chile", "mexico", "méxico", "argentina", "colombia", "caribbean", "caribe")
        global_anchor = ("global", "worldwide", "mundial", "europe", "europa", "iberia", "spain", "españa", "portugal", "emea")
        if any(x in content for x in foreign) and not any(x in content for x in global_anchor):
            return False
        return True

    return True


def _published_datetime(value: str):
    value = (value or "").strip()
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(value[:20], fmt).replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return None


def _fresh_enough(row: Dict[str, Any], profile: str) -> bool:
    dt = _published_datetime(str(row.get("published_at") or ""))
    if dt is None:
        row["freshness_band"] = "unknown"
        row["is_current_signal"] = False
        return True
    age_days = max(0, (datetime.now(timezone.utc) - dt).days)
    max_age = {"daily": 550, "weekly": 1095, "monthly": 1825}.get(profile, 730)
    current_window = {"daily": 90, "weekly": 180, "monthly": 550}.get(profile, 180)
    row["age_days"] = age_days
    row["is_current_signal"] = age_days <= current_window
    row["freshness_band"] = "current" if row["is_current_signal"] else "historical_context"
    return age_days <= max_age


def _pattern_hit(blob: str, pattern: str) -> bool:
    p = unicodedata.normalize("NFKD", str(pattern or ""))
    p = "".join(c for c in p if not unicodedata.combining(c))
    p = re.sub(r"\s+", " ", p.casefold()).strip()
    if len(p) <= 4 and " " not in p:
        return re.search(rf"(?<!\w){re.escape(p)}(?!\w)", blob) is not None
    return p in blob


def _dimension_scores(row: Dict[str, Any]) -> Dict[str, int]:
    blob = _content_blob(row)
    scores = {}
    for dim, patterns in DIMENSION_PATTERNS.items():
        score = 0
        for p in patterns:
            if _pattern_hit(blob, p):
                score += 2 if " " in p else 1
        scores[dim] = score
    return scores


def _semantic_dimension(row: Dict[str, Any], requested_dim: str, entity_type: str):
    """Classify the signal independently from the search query that found it."""
    result = classify_record(row)
    mapped = CLASS_TO_DIMENSION.get(result.classification)
    allowed = ALLOWED_DIMENSIONS.get(entity_type, set(DIMENSION_PATTERNS))

    # Procurement is deliberately strict: never infer it from the query alone.
    if requested_dim == "procurement" or mapped == "procurement":
        if result.classification in {"procurement_award", "tender", "contract"} and procurement_anchor_score(row) >= 0.62:
            return "procurement", result
        if requested_dim == "procurement":
            # A procurement search can still surface another useful event; try normal scoring below.
            mapped = None

    if mapped in allowed and mapped != "procurement":
        return mapped, result

    scores = _dimension_scores(row)
    ranked = sorted(((score, dim) for dim, score in scores.items() if dim in allowed and dim != "procurement"), reverse=True)
    if ranked and ranked[0][0] >= 2:
        return ranked[0][1], result

    # The requested dimension is only trusted when the content itself has at least one strong cue.
    if requested_dim in allowed and scores.get(requested_dim, 0) >= 2:
        return requested_dim, result
    return None, result


def _award_program_owned_by_entity(row: Dict[str, Any], ent: Dict[str, Any], classification: str) -> bool:
    if classification not in {"industry_award", "partner_award", "vendor_award", "customer_award"}:
        return False
    title = _content_blob(row)
    if not any(k in title for k in ("award", "premio", "prémio")):
        return False
    aliases = [_norm_text(a) for a in _entity_aliases(str(ent.get("name") or ""))]
    # Example: "finalistas do Axians Portugal Digital Awards" describes an awards programme
    # run by the entity, not an award won by the entity.
    if any(a and a in title and re.search(rf"{re.escape(a)}.{{0,45}}(awards?|premios?|premios?)", title) for a in aliases):
        if any(k in title for k in ("finalistas", "finalists", "candidatos", "nominees")):
            return True
    return False


def _third_party_certification(row: Dict[str, Any], classification: str) -> bool:
    if classification != "certification":
        return False
    title = _content_blob(row)
    learners = ("estudiantes", "students", "alumnos", "alumnas", "campus 42", "formacion para obtener", "formación para obtener")
    return any(x in title for x in learners)


def _secondary_people_move(row: Dict[str, Any], ent: Dict[str, Any], classification: str) -> bool:
    """Drop headlines whose real subject is another company and only mention a move to the entity.

    Example found in live QA: a Renault CEO appointment headline merely said that the
    predecessor had left *for Indra*.  That is context, not a sufficiently specific
    Indra hiring/leadership event for the strategic signal stream.
    """
    if classification not in {"leadership_change", "hiring_signal"}:
        return False
    title = _content_blob(row)
    aliases = [_norm_text(a) for a in _entity_aliases(str(ent.get("name") or ""))]
    if not aliases:
        return False
    # Spanish/Portuguese/English secondary-move constructions without a role at the target.
    secondary = ("tras la marcha de", "despues de la marcha de", "después de la marcha de", "apos a saida de", "após a saída de", "after the departure of")
    if any(x in title for x in secondary) and any(a and re.search(rf"(?:a|para|to)\s+{re.escape(a)}(?:\b|$)", title) for a in aliases):
        role_near_target = any(re.search(rf"(?:ceo|director|directora|head|president|presidente|manager).{{0,45}}{re.escape(a)}|{re.escape(a)}.{{0,45}}(?:ceo|director|directora|head|president|presidente|manager)", title) for a in aliases)
        return not role_near_target
    return False


def _strategic_relevance(row: Dict[str, Any]) -> float:
    base = float(row.get("classification_confidence") or 0.5)
    auth = float(row.get("authority_score") or 0.5)
    freshness = 1.0 if row.get("is_current_signal") else 0.68
    return round(min(1.0, 0.50 * base + 0.25 * auth + 0.25 * freshness), 3)


def _quality_filter(row: Dict[str, Any], task: Dict[str, Any], profile: str):
    if not _is_relevant(row, str(task["ent"].get("name") or "")):
        return None, "entity_relevance"
    if not _geo_relevant(row, task["ent"]):
        return None, "geo_relevance"
    if not _fresh_enough(row, profile):
        return None, "stale"
    dim, classification = _semantic_dimension(row, task["dim"], str(task["ent"].get("entity_type") or "vendor"))
    if dim is None:
        return None, "semantic_mismatch"
    if _award_program_owned_by_entity(row, task["ent"], classification.classification):
        return None, "owned_awards_program"
    if _third_party_certification(row, classification.classification):
        return None, "third_party_certification"
    if _secondary_people_move(row, task["ent"], classification.classification):
        return None, "secondary_people_move"
    row["search_dimension"] = task["dim"]
    row["dimension"] = dim
    row["classification"] = classification.classification
    row["event_type"] = classification.classification
    row["classification_confidence"] = round(classification.confidence, 3)
    row["classification_reason"] = classification.reason
    row["procurement_anchor_score"] = round(classification.procurement_anchor_score, 3)
    row["semantic_reclassified"] = dim != task["dim"]
    row["authority_score"] = float(task.get("authority", row.get("authority_score") or 0.5))
    row["strategic_relevance_score"] = _strategic_relevance(row)
    return row, None


def sanitize_signal(row: Dict[str, Any], profile: str = "daily"):
    """Revalidate stored rows so false positives do not persist across releases."""
    ent = {
        "name": row.get("entity_name"),
        "entity_type": row.get("entity_type") or "vendor",
        "country": row.get("country") or "IBERIA",
    }
    requested = str(row.get("search_dimension") or row.get("dimension") or "competitive")
    task = {"ent": ent, "dim": requested}
    clone = dict(row)
    cleaned, reason = _quality_filter(clone, task, profile)
    return cleaned, reason


def _provider_for_ent(provider: str, query: str, ent: Dict[str, Any], timeout: int):
    if provider == "gdelt":
        return gdelt(query, limit=8, timeout=timeout)
    if provider == "brave":
        return brave(query, limit=8, timeout=timeout)
    country = "PT" if ent.get("country") == "PT" else "ES"
    lang = "pt" if country == "PT" else "es"
    return google_news(query, country=country, lang=lang, limit=8, timeout=timeout)


def _profile_limits(profile: str):
    # v3.1.5: Google News latency in real Iberian runs was ~28s even with a 7s
    # socket timeout.  More workers + continuous refill increases coverage without
    # relaxing semantic quality.  Daily avoids slow site-restricted searches; direct
    # source connectors belong in v3.2.
    return {
        "daily": {"target_sources": 0, "providers": 2, "workers": 8, "timeout": 6, "freshness_days": 120},
        "weekly": {"target_sources": 2, "providers": 2, "workers": 8, "timeout": 8, "freshness_days": 365},
        "monthly": {"target_sources": 4, "providers": 3, "workers": 10, "timeout": 9, "freshness_days": 1095},
    }.get(profile, {"target_sources": 1, "providers": 2, "workers": 6, "timeout": 8, "freshness_days": 365})


def _dimension_order(ent: Dict[str, Any], dimensions_by_type: Dict[str, List[str]]) -> List[str]:
    et = str(ent.get("entity_type") or "vendor")
    return dimensions_by_type.get(et, ["customers", "competitive"])


def _fair_gaps(entities: List[Dict[str, Any]], dimensions_by_type: Dict[str, List[str]]):
    """One dimension per entity before any entity receives its second dimension."""
    dim_lists = [(ent, _dimension_order(ent, dimensions_by_type)) for ent in entities]
    max_dims = max((len(dims) for _, dims in dim_lists), default=0)
    out = []
    for dim_index in range(max_dims):
        for ent, dims in dim_lists:
            if dim_index < len(dims):
                out.append((ent, dims[dim_index]))
    return out


def _run_task(task, timeout):
    started = time.monotonic()
    # GDELT is best-effort in v3.1.4. A degraded free endpoint must never consume
    # a large fraction of the research budget.
    effective_timeout = min(timeout, 4) if task.get("provider") == "gdelt" else timeout
    try:
        rows = _provider_for_ent(task["provider"], task["query"], task["ent"], effective_timeout)
        return task, rows, None, (time.monotonic() - started) * 1000
    except Exception as exc:
        return task, None, exc, (time.monotonic() - started) * 1000


def adaptive_discover(
    registry: Iterable[Dict[str, Any]],
    entities: Iterable[Dict[str, Any]],
    learning: LearningStore,
    *,
    seconds=60,
    profile="daily",
):
    deadline = time.monotonic() + max(1, seconds)
    # High-impact dimensions first. Fairness still gives each entity one gap before
    # any entity receives a second, but the first pass is now more strategic.
    dimensions_by_type = {
        "vendor": ["distribution", "ma", "competitive", "services", "certification", "customers", "procurement"],
        "distributor": ["distribution", "ma", "services", "competitive", "customers", "hiring", "procurement"],
        "integrator": ["ma", "services", "certification", "customers", "competitive", "procurement", "hiring", "awards"],
    }
    registry = [s for s in registry if isinstance(s, dict) and s.get("id")]
    entities = _dedupe_entities(entities)
    limits = _profile_limits(profile)

    discovery_defs = [s for s in registry if s.get("category") == "discovery" and s.get("enabled", True) is not False]
    preferred = ["google_news_rss", "gdelt"]
    if os.getenv("BRAVE_SEARCH_API_KEY"):
        preferred.append("brave")
    available = {str(s.get("provider") or "") for s in discovery_defs}
    provider_ids = [p for p in preferred if p in available]
    if not provider_ids:
        provider_ids = ["google_news_rss", "gdelt"]
    provider_ids = provider_ids[: limits["providers"]]

    gap_pairs = _fair_gaps(entities, dimensions_by_type)
    gaps = []
    tasks_by_gap = defaultdict(list)
    gap_meta = {}
    for gap_index, (ent, dim) in enumerate(gap_pairs):
        et = str(ent.get("entity_type") or "vendor")
        gap_id = f"{et}|{ent.get('country','IBERIA')}|{str(ent.get('name') or '').lower()}|{dim}"
        gaps.append(gap_id)
        gap_meta[gap_id] = {"entity": ent, "dimension": dim}

        # Google News is the reliable discovery transport in v3.1.5.  GDELT is
        # health-probed only once per run while its public endpoint is timing out; it
        # must not consume one task slot for every knowledge gap.
        if "google_news_rss" in provider_ids:
            tasks_by_gap[gap_id].append({
                "gap_id": gap_id,
                "ent": ent,
                "dim": dim,
                "provider": "google_news_rss",
                "query": make_query(str(ent.get("name") or ""), dim, variant=gap_index, country=str(ent.get("country") or "IBERIA"), freshness_days=limits.get("freshness_days")),
                "source_id": "discovery:google_news_rss",
                "target_source_id": None,
                "authority": 0.58,
            })
        if "brave" in provider_ids:
            tasks_by_gap[gap_id].append({
                "gap_id": gap_id,
                "ent": ent,
                "dim": dim,
                "provider": "brave",
                "query": make_query(str(ent.get("name") or ""), dim, variant=gap_index + 1, country=str(ent.get("country") or "IBERIA"), freshness_days=limits.get("freshness_days")),
                "source_id": "discovery:brave",
                "target_source_id": None,
                "authority": 0.62,
            })

        targets = [s for s in registry if _source_matches(s, ent, dim) and s.get("domains")]
        targets.sort(key=lambda s: _source_affinity(s, ent, learning), reverse=True)
        for target_index, src in enumerate(targets[: limits["target_sources"]]):
            tasks_by_gap[gap_id].append({
                "gap_id": gap_id,
                "ent": ent,
                "dim": dim,
                "provider": "google_news_rss",
                "query": make_query(
                    str(ent.get("name") or ""), dim, list(src.get("domains") or []), variant=gap_index + target_index + 1, country=str(ent.get("country") or "IBERIA"), freshness_days=limits.get("freshness_days")
                ),
                "source_id": str(src.get("id")),
                "target_source_id": str(src.get("id")),
                "authority": float(src.get("authority", 0.5)),
            })

    # One task per gap per round. Because gaps are dimension-major across entities and
    # providers are rotated per gap, even a 2-3 minute run gets broad entity/provider coverage.
    tasks = []
    max_rounds = max((len(v) for v in tasks_by_gap.values()), default=0)
    for round_no in range(max_rounds):
        for gap_id in gaps:
            q = tasks_by_gap[gap_id]
            if round_no < len(q):
                tasks.append(q[round_no])

    # One non-blocking GDELT health probe per run. If it recovers, v3.2 can promote
    # it again; while degraded it no longer halves first-round coverage.
    if "gdelt" in provider_ids and gaps:
        probe_gap = gaps[0]
        meta = gap_meta[probe_gap]
        ent = meta["entity"]
        dim = meta["dimension"]
        tasks.insert(0, {
            "gap_id": probe_gap,
            "ent": ent,
            "dim": dim,
            "provider": "gdelt",
            "query": make_query(str(ent.get("name") or ""), dim, variant=0, country=str(ent.get("country") or "IBERIA"), freshness_days=limits.get("freshness_days")),
            "source_id": "discovery:gdelt",
            "target_source_id": None,
            "authority": 0.62,
            "health_probe": True,
        })

    signals: List[Dict[str, Any]] = []
    seen_urls = set()
    provider_failure_streak = defaultdict(int)
    provider_circuit_open = set()
    coverage = {g: {"attempted": 0, "successful_calls": 0, "signals": 0, "errors": set()} for g in gaps}
    provider_stats = defaultdict(lambda: {
        "attempted": 0,
        "successful": 0,
        "failed": 0,
        "raw_rows": 0,
        "accepted_rows": 0,
        "relevance_rejected": 0,
        "geo_rejected": 0,
        "stale_rejected": 0,
        "semantic_rejected": 0,
        "semantic_reclassified": 0,
        "current_accepted_rows": 0,
        "historical_accepted_rows": 0,
        "owned_awards_rejected": 0,
        "third_party_cert_rejected": 0,
        "secondary_people_move_rejected": 0,
        "duplicates": 0,
        "empty_success": 0,
        "latency_ms_total": 0.0,
    })
    attempted_tasks = 0
    completed_tasks = 0

    def process_result(task, rows, error, latency_ms):
        nonlocal attempted_tasks, completed_tasks
        gap_id = task["gap_id"]
        provider = task["provider"]
        attempted_tasks += 1
        coverage[gap_id]["attempted"] += 1
        provider_stats[provider]["attempted"] += 1
        provider_stats[provider]["latency_ms_total"] += latency_ms

        if error is not None or rows is None:
            provider_failure_streak[provider] += 1
            provider_stats[provider]["failed"] += 1
            err_name = type(error).__name__ if error else "provider_failure"
            detail = ""
            if error is not None:
                code = getattr(error, "code", None)
                reason = getattr(error, "reason", None)
                if code:
                    detail = f":http_{code}"
                elif reason:
                    detail = f":{str(reason)[:60]}"
            err_token = f"{provider}:{err_name}{detail}"
            coverage[gap_id]["errors"].add(err_token)
            provider_stats[provider]["last_error"] = err_token
            learning.update(task["source_id"], failed=True, authority=task["authority"], latency_ms=latency_ms)
            threshold = 1 if provider == "gdelt" else 4
            if provider_failure_streak[provider] >= threshold:
                provider_circuit_open.add(provider)
            return

        completed_tasks += 1
        provider_failure_streak[provider] = 0
        provider_stats[provider]["successful"] += 1
        coverage[gap_id]["successful_calls"] += 1
        provider_stats[provider]["raw_rows"] += len(rows)
        if not rows:
            provider_stats[provider]["empty_success"] += 1

        useful = False
        for row in rows:
            url = str(row.get("url") or "").strip()
            if not url:
                provider_stats[provider]["relevance_rejected"] += 1
                continue
            if url in seen_urls:
                provider_stats[provider]["duplicates"] += 1
                continue
            cleaned, reject_reason = _quality_filter(row, task, profile)
            if cleaned is None:
                if reject_reason == "entity_relevance":
                    provider_stats[provider]["relevance_rejected"] += 1
                elif reject_reason == "geo_relevance":
                    provider_stats[provider]["geo_rejected"] += 1
                elif reject_reason == "stale":
                    provider_stats[provider]["stale_rejected"] += 1
                elif reject_reason == "owned_awards_program":
                    provider_stats[provider]["owned_awards_rejected"] += 1
                elif reject_reason == "third_party_certification":
                    provider_stats[provider]["third_party_cert_rejected"] += 1
                elif reject_reason == "secondary_people_move":
                    provider_stats[provider]["secondary_people_move_rejected"] += 1
                else:
                    provider_stats[provider]["semantic_rejected"] += 1
                continue
            row = cleaned
            seen_urls.add(url)
            row.update({
                "entity_name": task["ent"].get("name"),
                "entity_type": task["ent"].get("entity_type"),
                "country": task["ent"].get("country", "IBERIA"),
                "source_registry_id": task["source_id"],
                "target_source_id": task["target_source_id"],
                "authority_score": task["authority"],
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "research_profile": profile,
            })
            if row.get("semantic_reclassified"):
                provider_stats[provider]["semantic_reclassified"] += 1
            signals.append(row)
            coverage[gap_id]["signals"] += 1
            provider_stats[provider]["accepted_rows"] += 1
            if row.get("is_current_signal"):
                provider_stats[provider]["current_accepted_rows"] += 1
            else:
                provider_stats[provider]["historical_accepted_rows"] += 1
            useful = True
        learning.update(task["source_id"], useful=useful, authority=task["authority"], latency_ms=latency_ms)

    # Bounded parallelism with continuous refill. v3.1.4 used batch barriers: one
    # slow Google News request held the whole batch, yielding only 18 calls in a
    # 167-second real run. Here a free worker immediately receives the next task.
    workers = max(1, int(limits["workers"]))
    timeout = max(3, int(limits["timeout"]))
    cursor = 0
    executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="v315-discovery")
    pending = {}

    def submit_next():
        nonlocal cursor
        while cursor < len(tasks) and time.monotonic() < deadline:
            task = tasks[cursor]
            cursor += 1
            if task["provider"] in provider_circuit_open:
                coverage[task["gap_id"]]["errors"].add(f"{task['provider']}:circuit_open")
                continue
            fut = executor.submit(_run_task, task, timeout)
            pending[fut] = task
            return True
        return False

    try:
        while len(pending) < workers and submit_next():
            pass
        while pending and time.monotonic() < deadline:
            remaining = max(0.05, min(1.0, deadline - time.monotonic()))
            done, _ = wait(tuple(pending), timeout=remaining, return_when=FIRST_COMPLETED)
            if not done:
                continue
            for fut in done:
                pending.pop(fut, None)
                task, rows, error, latency_ms = fut.result()
                process_result(task, rows, error, latency_ms)
                if time.monotonic() < deadline:
                    submit_next()
        # Results already completed at the deadline are still valuable. Do not wait
        # for new work, and cancel any futures that never started.
        for fut in list(pending):
            if fut.done():
                pending.pop(fut, None)
                task, rows, error, latency_ms = fut.result()
                process_result(task, rows, error, latency_ms)
            else:
                fut.cancel()
    finally:
        executor.shutdown(wait=True, cancel_futures=True)

    debt = []
    for gap_id in gaps:
        meta = gap_meta[gap_id]
        c = coverage[gap_id]
        planned = len(tasks_by_gap[gap_id])
        if c["signals"] > 0:
            continue
        if c["attempted"] == 0:
            reason = "runtime_budget"
        elif c["successful_calls"] == 0:
            reason = "provider_failure"
        elif c["attempted"] < planned:
            reason = "partial_coverage_no_signal"
        else:
            reason = "no_signal"
        debt.append({
            "entity": meta["entity"].get("name"),
            "entity_type": meta["entity"].get("entity_type"),
            "country": meta["entity"].get("country", "IBERIA"),
            "dimension": meta["dimension"],
            "reason": reason,
            "attempted": c["attempted"],
            "successful_calls": c["successful_calls"],
            "planned": planned,
            "errors": sorted(c["errors"])[:4],
        })

    # Collapse syndication/near-duplicate headlines while retaining corroborating origins.
    def event_key(row):
        title = _norm_text(str(row.get("title") or ""))
        # Google News commonly appends " - Publisher". Strip it for event identity.
        title = re.sub(r"\s+-\s+[^-]{2,80}$", "", title).strip()
        title = re.sub(r"[^a-z0-9áéíóúüñçãõàâêô ]+", " ", title)
        title = re.sub(r"\s+", " ", title).strip()
        return (str(row.get("entity_name") or "").casefold(), str(row.get("dimension") or ""), title[:190])

    event_buckets = defaultdict(list)
    for row in signals:
        event_buckets[event_key(row)].append(row)
    collapsed = []
    for rows in event_buckets.values():
        rows.sort(key=lambda r: (float(r.get("authority_score") or 0), bool(r.get("is_current_signal"))), reverse=True)
        primary = dict(rows[0])
        origins = sorted({str(r.get("source") or r.get("discovery_provider") or "") for r in rows if (r.get("source") or r.get("discovery_provider"))})
        urls = sorted({str(r.get("url") or "") for r in rows if r.get("url")})
        primary["corroborating_sources"] = origins
        primary["corroborating_urls"] = urls[:8]
        primary["corroboration_count"] = len(origins)
        primary["corroboration_score"] = round(min(1.0, 0.45 + 0.18 * max(0, len(origins) - 1)), 3)
        primary["source_diversity_score"] = round(min(1.0, 0.40 + 0.15 * len(origins)), 3)
        collapsed.append(primary)
        if len(origins) >= 2:
            learning.update(
                primary.get("source_registry_id", "unknown"),
                corroborating=True,
                authority=primary.get("authority_score", 0.5),
                count_attempt=False,
            )
    signals = collapsed

    provider_payload = {}
    for name, st in provider_stats.items():
        d = dict(st)
        attempts = max(1, int(d["attempted"]))
        d["avg_latency_ms"] = round(float(d.pop("latency_ms_total", 0.0)) / attempts, 1)
        provider_payload[name] = d

    stats = {
        "entities": len(entities),
        "gaps": len(gaps),
        "planned_tasks": len(tasks),
        "attempted_tasks": attempted_tasks,
        "completed_tasks": completed_tasks,
        "new_signals": len(signals),
        "current_signals": sum(1 for r in signals if r.get("is_current_signal")),
        "historical_context_signals": sum(1 for r in signals if not r.get("is_current_signal")),
        "covered_gaps": sum(1 for g in gaps if coverage[g]["signals"] > 0),
        "debt_gaps": len(debt),
        "provider_circuits_open": sorted(provider_circuit_open),
        "providers": provider_payload,
    }
    return signals, debt, stats
