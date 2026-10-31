# HF6_R20_CANDIDATE_PROMOTION_GATE
# HF6_R12_R2_ENTITY_BOUND_RESEARCH
# HF6_R5_REVENUE_RUNTIME
# HF6_ATOMIC_ITEM_PROVENANCE
"""Incremental public-web intelligence runner with durable learning."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..enrichment import merge_field
from ..knowledge_provenance import typed_evidence_sufficient, accrediting_evidence
from ..model import canonical
from ..provenance import evidence_for_item, evidence_for_relationship, infer_scope_from_text
from ..settings import RESEARCH_POLICY, RESEARCH_PROFILES, VERSION
from ..storage import atomic_write_json, prune_json_mapping, read_json
from .documents import Document, Link, parse_document, sitemap_urls
from .client_discovery import discover_official_site
from .extractors import (
    Candidate,
    evidence_snippet,
    extract_candidates,
    manufacturer_revenue_value_is_strict,
    revenue_value_is_strict,
)
from .planner import plan
from .query_discovery import discover as discover_search_sources
from .security import UnsafeUrl, validate_public_url
from .sources import PATH_FAMILY_HINTS, SourceSeed, family_from_url, relevant_families, seeds_for
from .state import ResearchState, now_iso
from .ted import fetch_notices, upsert_notices


USER_AGENT = (
    f"Westcon-Iberia-Decision-Intelligence/{VERSION} "
    "(public research; bounded; respectful; contact=repository-owner)"
)
MAX_RESPONSE_BYTES = int(RESEARCH_POLICY.get("max_response_bytes") or 3_000_000)
IGNORED_EXTERNAL_HOSTS = {
    "facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com",
    "youtube.com", "youtu.be", "tiktok.com", "google.com", "microsoft.com",
}
GENERIC_LINK_LABELS = {
    "home", "inicio", "início", "read more", "learn more", "saber mais", "ver más",
    "click here", "contact", "contacto", "privacy", "legal", "cookies", "login",
}

FINANCIAL_LINK_HINTS = (
    "investor", "investors", "investor relations", "financial", "financials",
    "annual report", "annual reports", "earnings", "results", "quarterly",
    "reports and filings", "filings", "revenue", "net sales",
    "resultados", "resultados financieros", "informacion financiera",
    "informação financeira", "relatorio", "relatório", "contas",
)


def _now_date() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _row_index(data: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    output = {}
    for section in (
        "manufacturers", "distributors", "integrators", "clients_public",
        "clients_private", "trends", "architectures",
    ):
        for row in data.get(section) or []:
            output[(section, canonical(row.get("name")))] = row
    return output


def _unsourced_value_queries(row: dict[str, Any], target_fields: list[str], limit: int = 3) -> list[str]:
    """Recover exact unsourced atomic claims as search leads, never as proof.

    Previously, only gap.target_values fed focused searches. Many preserved
    historical items have no target_values in their gap record; this extracts
    those existing claim values without treating them as verified.
    """
    entity = str(row.get("name") or "").strip()
    if not entity:
        return []
    output: list[str] = []
    seen: set[str] = set()
    for field_name in target_fields:
        field = (row.get("fields") or {}).get(field_name) or {}
        if not isinstance(field, dict):
            continue
        for item in field.get("items") or []:
            if not isinstance(item, dict):
                continue
            value = item.get("value")
            if not isinstance(value, str):
                continue
            value = value.strip()
            if not (3 <= len(value) <= 95) or canonical(value) == canonical(entity):
                continue
            if any(accrediting_evidence(ev) for ev in item.get("evidence") or [] if isinstance(ev, dict)):
                continue
            query = f'"{entity}" "{value}"'
            key = query.casefold()
            if key not in seen:
                seen.add(key)
                output.append(query)
                if len(output) >= limit:
                    return output
    return output


def _vendor_names(data: dict[str, Any]) -> list[str]:
    names = []
    for row in data.get("manufacturers") or []:
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        names.append(name)
        if "/" in name:
            names.extend(part.strip() for part in name.split("/") if part.strip())
    return sorted(set(names), key=len, reverse=True)


def _field_values(field: dict[str, Any] | None) -> set[str]:
    value = (field or {}).get("value")
    rows = value if isinstance(value, list) else ([] if value in (None, "", {}, []) else [value])
    return {canonical(item) for item in rows if canonical(item)}


def _count_populated_rows(data: dict[str, Any], section: str, field_id: str) -> int:
    total = 0
    for row in data.get(section) or []:
        field = (row.get("fields") or {}).get(field_id) or {}
        value = field.get("value")
        if value not in (None, "", [], {}):
            total += 1
    return total

def _field_evidence_keys(field: dict[str, Any] | None) -> set[tuple[str, str, str]]:
    return {
        (str(item.get("url") or ""), str(item.get("title") or ""), str(item.get("scope") or ""))
        for item in (field or {}).get("evidence") or []
        if isinstance(item, dict)
    }


def _document_from_cache(cached: dict[str, Any]) -> Document:
    return Document(
        url=str(cached.get("url") or ""),
        title=str(cached.get("title") or ""),
        text=str(cached.get("text") or ""),
        links=tuple(
            Link(str(link.get("url") or ""), str(link.get("label") or ""))
            for link in cached.get("links") or []
            if isinstance(link, dict)
        ),
        content_digest=str(cached.get("content_digest") or ""),
    )


class Fetcher:
    def __init__(
        self,
        *,
        profile: str,
        deadline: float,
        cache: dict[str, Any],
        state: ResearchState,
        stats: dict[str, Any],
    ):
        self.profile = RESEARCH_PROFILES[profile]
        self.deadline = deadline
        self.cache = cache
        self.state = state
        self.stats = stats
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept-Language": "es,pt;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml,text/xml,text/plain;q=0.8,*/*;q=0.2",
        })
        # ResearchState handles backoff across sources/runs. HTTP-level retries
        # can sleep on Retry-After beyond the supervisor deadline and lose work.
        retry = Retry(
            total=0,
            connect=0,
            read=0,
            status=0,
            backoff_factor=0.55,
            status_forcelist=(408, 425, 429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "HEAD", "POST"}),
            respect_retry_after_header=True,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry, pool_connections=12, pool_maxsize=12))
        self.session.mount("http://", HTTPAdapter(max_retries=retry, pool_connections=6, pool_maxsize=6))

    def fetch(self, seed: SourceSeed) -> tuple[Document | None, bool, int, str]:
        try:
            url = validate_public_url(seed.url)
        except UnsafeUrl as exc:
            return None, False, 0, f"unsafe-url: {exc}"
        if not self.state.domain_available(url):
            self.stats["circuit_skips"] += 1
            return None, False, 0, "domain-circuit-open"

        key = hashlib.sha256(url.encode("utf-8")).hexdigest()
        cached = self.cache.get(key)
        if (
            isinstance(cached, dict)
            and cached.get("ok")
            and time.time() - float(cached.get("ts") or 0) < self.profile.cache_ttl_s
        ):
            self.stats["cache_hits"] += 1
            return _document_from_cache(cached), True, int(cached.get("status") or 200), ""

        remaining = self.deadline - time.monotonic()
        if remaining <= 3:
            return None, False, 0, "deadline"
        timeout = max(2.0, min(float(self.profile.request_timeout_s), remaining - 1))
        self.stats["fetch_attempts"] += 1
        try:
            with self.session.get(url, timeout=(min(4.0, timeout), timeout), allow_redirects=True, stream=True) as response:
                status = int(response.status_code)
                response.raise_for_status()
                validate_public_url(response.url)
                content_type = response.headers.get("content-type", "").casefold()
                if not any(kind in content_type for kind in ("html", "xml", "text", "xhtml", "rss", "atom")):
                    self.state.record_domain(url, ok=False, status=status)
                    return None, False, status, f"unsupported-content-type:{content_type[:80]}"
                declared_size = int(response.headers.get("content-length") or 0)
                if declared_size > MAX_RESPONSE_BYTES:
                    self.state.record_domain(url, ok=False, status=status)
                    return None, False, status, "response-too-large"
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_content(65_536):
                    if time.monotonic() >= self.deadline - 1:
                        return None, False, status, "deadline"
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > MAX_RESPONSE_BYTES:
                        self.state.record_domain(url, ok=False, status=status)
                        return None, False, status, "response-too-large"
                    chunks.append(chunk)
                body = b"".join(chunks)
                digest = hashlib.sha256(body).hexdigest()
                raw = _decode_http_body(body, response)
                document = parse_document(raw, response.url, digest)
                self.cache[key] = {
                    "ok": True,
                    "url": document.url,
                    "title": document.title,
                    "text": document.text,
                    "links": [asdict(link) for link in document.links],
                    "content_digest": document.content_digest,
                    "content_type": content_type,
                    "status": status,
                    "ts": time.time(),
                }
                return document, False, status, ""
        except (requests.RequestException, UnsafeUrl, UnicodeError, ValueError) as exc:
            self.state.record_domain(url, ok=False, status=getattr(getattr(exc, "response", None), "status_code", 0) or 0)
            return None, False, 0, f"{type(exc).__name__}: {exc}"[:240]


ANALYST_SOURCE_NAMES = (
    "gartner", "forrester", "idc", "omdia", "canalys", "isg", "gigaom", "451 research",
)


def _merge_source_seeds(*groups: list[SourceSeed]) -> list[SourceSeed]:
    output = []
    seen = set()
    for group in groups:
        for seed in group:
            key = (seed.url, seed.family)
            if key in seen:
                continue
            seen.add(key)
            output.append(seed)
    return output


def _revalidation_source_seeds(target: dict[str, Any]) -> list[SourceSeed]:
    output = []
    fallback_family = next(iter(target.get("families") or []), "official")
    for raw in target.get("revalidation_seeds") or []:
        if not isinstance(raw, dict):
            continue
        url = str(raw.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            continue
        official = bool(raw.get("official"))
        output.append(SourceSeed(
            url=url,
            family=family_from_url(url, fallback_family),
            official=official,
            source_grade="A" if official else str(raw.get("source_grade") or "B"),
            source_type="official-domain-revalidated" if official else "public-web-revalidated",
            source_name=str(raw.get("source_name") or target.get("entity") or "Fuente pública"),
        ))
    return output


def _dimension_matches(section: str, dims: list[str]) -> bool:
    if not dims:
        return True
    wanted = {canonical(value) for value in dims if value}
    aliases = {
        "clients_public": {"clients public", "clients", "public clients", "procurement"},
        "clients_private": {"clients private", "clients", "private clients"},
        "manufacturers": {"manufacturers", "vendors"},
        "distributors": {"distributors", "distribution"},
        "integrators": {"integrators", "system integrators", "partners"},
        "trends": {"trends", "market", "analyst"},
        "architectures": {"architectures", "technology", "analyst"},
    }
    return bool(wanted & aliases.get(section, {canonical(section)}))



def _host_entity_owned(url: str, entity: str) -> bool:
    # Safe hostname/entity matching:
    # - short names (SIA/IBM/EY) need exact hostname-label token match;
    # - long anchors may occur inside compound labels;
    # - joined multi-token entity names such as 'Grupo ICA' -> 'grupoica'
    #   are accepted only when the joined token is at least 5 characters.
    hostname = (urlparse(url).hostname or "").casefold()
    labels = [
        canonical(label)
        for label in hostname.split(".")
        if label and label.casefold() != "www"
    ]
    label_words = {
        word
        for label in labels
        for word in label.split()
        if word
    }

    anchors = _entity_anchor_tokens(entity)
    for anchor in anchors[:4]:
        if anchor in label_words:
            return True
        if len(anchor) >= 4 and any(anchor in label for label in labels):
            return True

    entity_tokens = [
        token
        for token in canonical(entity).split()
        if token
    ]
    joined = "".join(entity_tokens)
    if len(entity_tokens) >= 2 and len(joined) >= 5:
        if any(joined == label or joined in label for label in labels):
            return True

    return False
def _seed_binding(
    url: str,
    entity: str,
    *,
    source_type: str = "",
    source_name: str = "",
) -> str:
    path = canonical(urlparse(url).path)
    if _host_entity_owned(url, entity):
        return "entity-owned"

    path_relationship_hints = {
        "partner", "partners", "alliance", "alliances", "locator",
        "directory", "reseller", "resellers", "distributor", "distributors",
        "integrator", "integrators", "system integrator", "msp", "mssp",
        "service provider", "award", "awards", "customer case", "case study",
        "customer success", "strategic agreement",
    }
    relationship_source_type_hints = {
        "partner directory", "partners directory", "vendor partner directory",
        "partner locator", "reseller locator", "distributor locator",
        "integrator locator", "alliance directory", "alliances directory",
        "customer case", "customer success", "case study",
        "strategic agreement",
    }
    source_type_key = canonical(source_type)

    if any(hint in path for hint in path_relationship_hints):
        return "relationship-source"
    if any(hint in source_type_key for hint in relationship_source_type_hints):
        return "relationship-source"
    if "revalidated" in source_type_key:
        return "relationship-source"

    return "discovery-only"

def _filter_entity_seeds(
    seeds: list[SourceSeed],
    entity: str,
    section: str,
) -> list[SourceSeed]:
    if section in {"trends", "architectures"}:
        return seeds

    output = []
    for seed in seeds:
        binding = _seed_binding(
            seed.url,
            entity,
            source_type=seed.source_type,
            source_name=seed.source_name,
        )
        if (
            binding in {"entity-owned", "relationship-source"}
            or str(seed.source_type or "").startswith("search-discovery:")
        ):
            output.append(seed)
    return output


def _catalog_source_seeds(
    data: dict[str, Any],
    section: str,
    fields: list[str],
    entity: str,
    limit: int = 14,
) -> list[SourceSeed]:
    wanted = relevant_families(fields)
    output = []

    for raw in data.get("source_catalog") or []:
        if not isinstance(raw, dict):
            continue

        url = str(raw.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            continue

        dims = raw.get("dimensions") or []
        if isinstance(dims, str):
            dims = [dims]

        name = str(raw.get("name") or "")
        cls = str(raw.get("class") or raw.get("source_type") or "")
        blob = f"{name} {cls} {url}".casefold()
        analyst = any(token in blob for token in ANALYST_SOURCE_NAMES)
        family = "analyst" if analyst else family_from_url(url, "official")

        if family not in wanted and not (
            section in {"trends", "architectures"} and analyst
        ):
            continue
        if not _dimension_matches(section, list(dims)) and not analyst:
            continue

        binding = _seed_binding(
            url,
            entity,
            source_type=cls,
            source_name=name,
        )

        if (
            section not in {"trends", "architectures"}
            and binding == "discovery-only"
        ):
            continue

        official = "official" in cls.casefold() or "vendor-" in cls.casefold()
        output.append(SourceSeed(
            url=url,
            family=family,
            official=official,
            source_grade="B" if analyst else ("A" if official else "B"),
            source_type=cls or ("analyst-open-source" if analyst else "public-web"),
            source_name=name or "Fuente pública",
        ))

        if len(output) >= limit:
            break

    return output


def _financial_entry_seed(seeds: list[SourceSeed], entity: str) -> SourceSeed | None:
    """Start financial discovery from one already trusted entity-owned official host."""
    for seed in seeds:
        if not seed.official or not _host_entity_owned(seed.url, entity):
            continue
        parsed = urlparse(seed.url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        return SourceSeed(
            f"{parsed.scheme}://{parsed.netloc}/",
            "financial",
            True,
            "A",
            "official-financial-entry",
            seed.source_name or entity,
        )
    return None

def _decode_http_body(body: bytes, response: Any) -> str:
    if body.startswith(b"\xef\xbb\xbf"):
        return body.decode("utf-8-sig", errors="strict")
    if body.startswith((b"\xff\xfe", b"\xfe\xff")):
        return body.decode("utf-16", errors="strict")

    headers = getattr(response, "headers", {}) or {}
    content_type = str(headers.get("Content-Type") or "")
    match = re.search(
        r"charset\s*=\s*[\"']?([^;\s\"']+)",
        content_type,
        flags=re.I,
    )
    explicit = match.group(1).strip() if match else ""

    tried = set()

    def attempt(encoding: str):
        key = str(encoding or "").strip().casefold()
        if not key or key in tried:
            return None
        tried.add(key)
        try:
            return body.decode(encoding, errors="strict")
        except (UnicodeDecodeError, LookupError):
            return None

    if explicit:
        decoded = attempt(explicit)
        if decoded is not None:
            return decoded

    decoded = attempt("utf-8")
    if decoded is not None:
        return decoded

    response_encoding = str(getattr(response, "encoding", "") or "")
    decoded = attempt(response_encoding)
    if decoded is not None:
        return decoded

    for fallback in ("cp1252", "latin-1"):
        decoded = attempt(fallback)
        if decoded is not None:
            return decoded

    return body.decode("utf-8", errors="replace")


def _target_match(value: Any, text: str) -> bool:
    wanted = canonical(value)
    hay = canonical(text)
    if not wanted or len(wanted) > 180:
        return False
    if len(wanted) <= 4:
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(wanted)}(?![a-z0-9])", hay))
    return wanted in hay


def _entity_anchor_tokens(entity: str) -> list[str]:
    value = canonical(entity)
    if not value:
        return []
    stop = {
        "sociedad", "servicios", "service", "services", "empresa",
        "grupo", "group", "corporation", "corporacion", "general",
        "direccion", "direcao", "consejeria", "ministerio",
        "ayuntamiento", "municipio", "fundacion", "instituto", "agencia",
        "entidade", "entidad", "publica", "publico", "public", "sa", "sl",
        "spa", "ltd", "limited", "inc", "gmbh", "epe", "ip",
    }
    tokens = [
        token for token in re.findall(r"[a-z0-9]+", value)
        if token not in stop and (len(token) >= 4 or len(value) <= 4)
    ]
    return sorted(set(tokens), key=lambda x: (-len(x), x))


def _term_positions(term: str, text: str) -> list[int]:
    if not term:
        return []
    if len(term) <= 4:
        pattern = rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])"
    else:
        pattern = re.escape(term)
    return [m.start() for m in re.finditer(pattern, text)]


def _semantic_window(text: str, left: int, right: int, radius: int = 260) -> str:
    lo = max(0, min(left, right) - radius)
    hi = min(len(text), max(left, right) + radius)
    return text[lo:hi]


def _near_taxonomy_heading(
    body: str,
    target_positions: list[int],
    headings: tuple[str, ...],
    *,
    before: int = 360,
    after: int = 100,
) -> bool:
    for pos in target_positions:
        lo = max(0, pos - before)
        hi = min(len(body), pos + after)
        window = body[lo:hi]
        if any(heading in window for heading in headings):
            return True
    return False


def _field_context_ok(
    field_id: str,
    window: str,
    *,
    entity_owned: bool,
) -> bool:
    field = str(field_id or "").casefold()


    if field in {"hiring_signals", "job_profiles", "job_vendors"}:
        cues = (
            "job", "jobs", "career", "careers", "vacan", "position",
            "role", "hiring", "empleo", "empleos", "puesto", "puestos",
            "oferta", "ofertas", "talento", "contrat", "recruit",
        )
        return entity_owned or any(cue in window for cue in cues)

    if field == "revenue":
        cues = (
            "revenue", "net sales", "annual sales", "turnover",
            "facturacion", "facturación", "ingresos", "ventas",
            "faturacao", "faturação", "receita",
            "volume de negocios", "volume de negócios",
        )
        return any(cue in window for cue in cues)
    if field in {"capabilities", "services"}:
        cues = (
            "we offer", "we provide", "we deliver",
            "our services", "our solutions", "our capabilities",
            "offers", "provides", "delivers",
            "ofrecemos", "ofrece", "proporciona", "prestamos",
            "nuestros servicios", "nuestras soluciones",
            "servicios", "servicos", "solutions", "solucoes", "capabilities",
            "nossos servicos", "nossas solucoes",
            "managed services", "consulting services",
        )
        return any(cue in window for cue in cues)

    if field == "specializations":
        cues = (
            "specialist", "specialized", "specialised", "specialization",
            "specialisation", "expertise", "certified", "certification",
            "especialista", "especializado", "especializada",
            "especializacion", "especialización", "experiencia",
            "competencia", "acreditacion", "acreditación",
        )
        return any(cue in window for cue in cues)

    if field == "verticals":
        cues = (
            "industries", "industry", "sectors", "sector",
            "sectores", "industrias", "markets", "mercados",
            "verticals", "verticales",
        )
        return any(cue in window for cue in cues)

    if field in {"competitors", "competitor_vendor_overlap"}:
        cues = (
            "competitor", "competitors", "competition", "alternative",
            "alternatives", "versus", " vs ", "compare", "comparison",
            "competidor", "competidores", "alternativa", "comparativa",
        )
        return any(cue in window for cue in cues)

    if field in {"technology_signals", "westcon_area"}:
        cues = (
            "technology", "cloud", "security", "network", "data center",
            "datacenter", "observability", "identity", "automation", "ai",
            "tecnologia", "tecnología", "nube", "seguridad", "red",
            "infraestructura", "licitacion", "licitación", "contrato",
            "project", "proyecto", "deploy", "desplieg",
        )
        return entity_owned or any(cue in window for cue in cues)

    if field == "public_cases":
        cues = (
            "case study", "customer story", "customer success",
            "caso de exito", "caso de éxito", "cliente",
            "project", "proyecto", "deploy", "desplieg",
        )
        return any(cue in window for cue in cues)

    cues = (
        " is ", " are ", " has ", " have ", " offers ", " provides ",
        " partner ", " uses ", " deploys ", " selected ", " announced ",
        " es ", " son ", " ofrece ", " dispone ", " utiliza ",
        " despliega ", " seleccion", " anuncio", " anunció",
    )
    padded = f" {window} "
    return any(cue in padded for cue in cues)


def _explicit_self_identification(
    entity: str,
    target: str,
    body: str,
) -> bool:
    entity_key = canonical(entity)
    anchors = _entity_anchor_tokens(entity)
    subject_terms = [entity_key] + anchors[:3]

    target_variants = {target}
    if target == "service provider":
        target_variants.update({
            "managed service provider",
            "managed security service provider",
            "solution provider",
            "mssp",
            "msp",
        })

    copulas = (
        " is a ", " is an ", " are a ", " are an ",
        " es un ", " es una ", " somos ", " se define como ",
        " acts as ", " operates as ", " recognized as ", " recognised as ",
    )

    for subject in subject_terms:
        if not subject:
            continue
        for spos in _term_positions(subject, body):
            lo = max(0, spos - 120)
            hi = min(len(body), spos + 500)
            window = f" {body[lo:hi]} "
            if not any(copula in window for copula in copulas):
                continue
            if any(_target_match(variant, window) for variant in target_variants):
                return True

    return False


def _subject_value_match(
    entity: str,
    value: Any,
    document: Document,
    field_id: str = "",
) -> bool:
    target = canonical(value)
    if not target or not _target_match(value, document.text):
        return False

    title = canonical(document.title or "")
    body = canonical(document.text or "")
    entity_key = canonical(entity)
    anchors = _entity_anchor_tokens(entity)
    entity_owned = _host_entity_owned(document.url, entity)

    target_positions = _term_positions(target, body)
    if not target_positions:
        return False

    field = str(field_id or "").casefold()

    # Revenue value validity belongs here: this function owns `value`.
    # _field_context_ok() is only a local textual-context classifier.
    if field == "revenue" and not revenue_value_is_strict(str(value or "")):
        return False

    if field in {"hiring_signals", "job_profiles", "job_vendors"}:
        if entity_owned and entity_key and entity_key in title:
            return True

    if entity_owned:
        if field == "revenue":
            for pos in target_positions:
                window = _semantic_window(body, pos, pos, radius=240)
                if _field_context_ok("revenue", window, entity_owned=True):
                    return True
        if field in {"services", "capabilities"}:
            headings = (
                "services", "servicios", "servicos", "solutions", "soluciones",
                "solucoes", "capabilities", "capacidades", "portfolio", "oferta",
            )
            if _near_taxonomy_heading(body, target_positions, headings):
                if target != "service provider":
                    return True

        if field == "verticals":
            headings = (
                "industries", "sectors", "sectores", "industrias",
                "markets", "mercados", "verticals", "verticales",
            )
            if _near_taxonomy_heading(body, target_positions, headings):
                return True

        if field == "specializations":
            headings = (
                "specializations", "specialisations", "especializaciones",
                "expertise", "certifications", "certificaciones",
                "competencias",
            )
            if _near_taxonomy_heading(body, target_positions, headings):
                return True

    anchor_terms = []
    if entity_key:
        anchor_terms.append(entity_key)
    anchor_terms.extend(anchors[:4])

    anchor_positions = []
    for anchor in anchor_terms:
        anchor_positions.extend(_term_positions(anchor, body))

    identity_targets = {
        "service provider", "managed service provider", "msp", "mssp",
        "reseller", "distributor", "integrator", "system integrator",
    }
    if field in {"capabilities", "services", "specializations"} and target in identity_targets:
        if _explicit_self_identification(entity, target, body):
            return True
        if entity_owned:
            first_person = (
                "we are a service provider", "we are an msp", "we are an mssp",
                "somos un proveedor de servicios",
                "somos proveedor de servicios",
            )
            if any(phrase in body for phrase in first_person):
                return True
        return False

    for a in anchor_positions:
        for t in target_positions:
            if abs(a - t) > 700:
                continue
            window = _semantic_window(body, a, t, radius=220)
            if _field_context_ok(
                field_id,
                window,
                entity_owned=entity_owned,
            ):
                return True

    if entity_owned and target in title and entity_key in title:
        if _field_context_ok(
            field_id,
            title,
            entity_owned=True,
        ):
            return True

    if not field_id:
        for a in anchor_positions:
            for t in target_positions:
                if abs(a - t) <= 700:
                    window = _semantic_window(body, a, t, radius=220)
                    if any(cue in window for cue in (
                        "partner", "integrator", "integrates", "integra",
                        "delivers", "provides", "offers", "uses",
                        "authorized", "authorised",
                    )):
                        return True
        if entity_owned and entity_key in title:
            return True

    return False


def _exact_historical_candidate(
    document: Document,
    wanted: list[Any],
    official: bool,
    entity: str,
    field_id: str,
) -> Candidate | None:
    matched = [
        value for value in wanted
        if _subject_value_match(
            entity,
            value,
            document,
            field_id=field_id,
        )
    ]
    if not matched:
        return None
    labels = [str(value) for value in matched]
    return Candidate(
        tuple(labels),
        "fact",
        0.90 if official else 0.76,
        evidence_snippet(document.text, labels),
        tuple(labels),
    )


SEMANTICALLY_BOUND_WEB_FIELDS = {
    "capabilities": "capabilities",
    "services": "services",
    "technology_domains": "capabilities",
    "differential_capabilities": "services",
    "specializations": "specializations",
    "verticals": "verticals",
    "vendor_relations": "vendor_relations",
    "identified_vendors": "identified_vendors",
    "job_vendors": "job_vendors",
    "technology_signals": "technology_signals",
    "job_profiles": "job_profiles",
    "hiring_signals": "hiring_signals",
}


def _semantic_candidate_filter(
    candidates: dict[str, Candidate],
    target: dict[str, Any],
    document: Document,
) -> dict[str, Candidate]:
    entity = str(target.get("entity") or "")
    entity_owned = _host_entity_owned(document.url, entity)
    output: dict[str, Candidate] = {}

    direct_owned_observations = {
        "vendor_relations", "identified_vendors", "job_vendors",
        "technology_signals", "job_profiles", "hiring_signals",
    }

    for field_id, candidate in candidates.items():
        semantic_field = SEMANTICALLY_BOUND_WEB_FIELDS.get(field_id)
        if not semantic_field:
            output[field_id] = candidate
            continue

        kept_values: list[Any] = []
        kept_terms: list[str] = []

        for index, value in enumerate(candidate.values):
            term = (
                candidate.matched_terms[index]
                if index < len(candidate.matched_terms)
                else str(value)
            )
            probe = term or str(value)

            if (
                entity_owned
                and semantic_field in direct_owned_observations
                and _target_match(probe, document.text)
            ):
                valid = True
            else:
                valid = _subject_value_match(
                    entity,
                    probe,
                    document,
                    field_id=semantic_field,
                )

            if not valid:
                continue

            kept_values.append(value)
            kept_terms.append(term)

        if not kept_values:
            continue

        output[field_id] = Candidate(
            tuple(kept_values),
            candidate.claim_type,
            candidate.confidence,
            evidence_snippet(document.text, kept_terms),
            tuple(kept_terms),
        )

    return output


def _focus_candidates(
    candidates: dict[str, Candidate],
    target: dict[str, Any],
    document: Document,
    official: bool,
) -> dict[str, Candidate]:
    output = _semantic_candidate_filter(dict(candidates), target, document)

    revenue_candidate = output.get("revenue")
    if revenue_candidate is not None:
        validator = (
            manufacturer_revenue_value_is_strict
            if target.get("section") == "manufacturers"
            else revenue_value_is_strict
        )
        kept_values: list[Any] = []
        kept_terms: list[str] = []
        for index, value in enumerate(revenue_candidate.values):
            term = (
                revenue_candidate.matched_terms[index]
                if index < len(revenue_candidate.matched_terms)
                else str(value)
            )
            if validator(str(value)) and _subject_value_match(
                str(target.get("entity") or ""),
                value,
                document,
                field_id="revenue",
            ):
                kept_values.append(value)
                kept_terms.append(term)
        if kept_values:
            output["revenue"] = Candidate(
                tuple(kept_values),
                revenue_candidate.claim_type,
                revenue_candidate.confidence,
                evidence_snippet(document.text, kept_terms),
                tuple(kept_terms),
            )
        else:
            output.pop("revenue", None)

    target_map = target.get("target_values") or {}
    if not isinstance(target_map, dict) or not target_map:
        return output

    strict_claim_support = bool(
        {"historical-revalidation", "evidence-support"}
        & set(target.get("gap_kinds") or [])
    )
    for field_id, wanted in target_map.items():
        if not wanted:
            continue
        if strict_claim_support:
            exact = _exact_historical_candidate(
                document,
                list(wanted),
                official,
                str(target.get("entity") or ""),
                field_id,
            )
            if exact is not None:
                output[field_id] = exact
            else:
                output.pop(field_id, None)
            continue

        candidate = output.get(field_id)
        if candidate is None:
            continue
        wanted_keys = {canonical(value) for value in wanted}
        pairs = []
        for index, value in enumerate(candidate.values):
            if canonical(value) not in wanted_keys:
                continue
            term = (
                candidate.matched_terms[index]
                if index < len(candidate.matched_terms)
                else str(value)
            )
            pairs.append((value, term))

        if pairs:
            kept_values = tuple(value for value, _term in pairs)
            kept_terms = tuple(term for _value, term in pairs)
            output[field_id] = Candidate(
                kept_values,
                candidate.claim_type,
                candidate.confidence,
                evidence_snippet(document.text, kept_terms),
                kept_terms,
            )
        else:
            output.pop(field_id, None)

    return output

def _evidence(
    seed: SourceSeed,
    document: Document,
    field_id: str,
    candidate: Candidate,
    entity: str,
    scope: str,
    *,
    item_value: Any | None = None,
    snippet: str | None = None,
    matched_terms: list[str] | tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    description = snippet if snippet is not None else candidate.snippet
    explicit_scope = infer_scope_from_text(
        " ".join((document.title or "", description or "", document.url or ""))
    )
    return [{
        "source": urlparse(document.url).netloc.removeprefix("www.") or seed.source_name or entity,
        "source_catalog_name": seed.source_name or "",
        "researched_entity": entity,
        "source_binding": (
            "atomic-item"
            if item_value is not None
            else _seed_binding(
                document.url,
                entity,
                source_type=seed.source_type,
                source_name=seed.source_name,
            )
        ),
        "title": document.title or f"Página pública · {seed.family}",
        "url": document.url,
        "date": _now_date(),
        "description": description,
        "scope": explicit_scope,
        "scope_provenance": "explicit-text" if explicit_scope != "GLOBAL" else "unspecified",
        "research_target_scope": scope or "GLOBAL",
        "source_grade": "A" if seed.official else seed.source_grade or "B",
        "source_type": seed.source_type,
        "official": seed.official,
        "classification": "public",
        "retrieved_at": _now_date(),
        "freshness_status": "current",
        "method": f"web-evidence:{seed.family}",
        "content_digest": document.content_digest,
        "matched_terms": list(matched_terms if matched_terms is not None else candidate.matched_terms),
        "field": field_id,
        "item_value": item_value if item_value is not None else "",
        "item_key": canonical(item_value) if item_value is not None else "",
        "atomic": item_value is not None,
        "revalidation": "historical-source-refetched" if "revalidated" in seed.source_type else "",
    }]


def _candidate_items(
    seed: SourceSeed,
    document: Document,
    field_id: str,
    candidate: Candidate,
    entity: str,
    target_scope: str,
) -> list[dict[str, Any]]:
    """Create one local evidence object per extracted value."""
    items: list[dict[str, Any]] = []
    for index, value in enumerate(candidate.values):
        term = (
            candidate.matched_terms[index]
            if index < len(candidate.matched_terms)
            else str(value)
        )
        snippet = evidence_snippet(document.text, (term, str(value)), radius=140)
        evidence = _evidence(
            seed,
            document,
            field_id,
            candidate,
            entity,
            target_scope,
            item_value=value,
            snippet=snippet,
            matched_terms=(term,),
        )
        items.append({
            "value": value,
            "evidence": evidence,
            "confidence": candidate.confidence,
            "claim_type": candidate.claim_type,
            "assertion_status": (
                "SEÑAL"
                if candidate.claim_type == "signal"
                else "CONFIRMADO"
                if candidate.confidence >= 0.8
                else "PROBABLE"
            ),
        })
    return items

_RELATION_PROMOTION_FIELDS = frozenset({
    "vendor_relations", "distributors", "integrators",
    "westcon_overlap", "competitor_vendor_overlap",
})


def _promotable_candidate_items(
    items: list[dict[str, Any]],
    *,
    entity: str,
    field_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Separate extracted candidates from facts that may enter canonical data.

    A candidate is promotable only when it has typed accrediting evidence and that
    evidence survives the same exact owner/field/value binding used later by
    normalization, preservation and quality. Rejected candidates remain research
    telemetry; they never mutate ``intelligence.json``.
    """
    promoted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    relation_field = field_id in _RELATION_PROMOTION_FIELDS

    for raw in items:
        if not isinstance(raw, dict):
            continue
        value = raw.get("value")
        evidence_rows = [
            ev for ev in (raw.get("evidence") or [])
            if isinstance(ev, dict)
        ]
        # Research-generated evidence carries authoritative atomic metadata.
        # Do not allow fuzzy source-text matching to repair a malformed candidate
        # before it reaches canonical state.
        exact_rows = [
            ev for ev in evidence_rows
            if ev.get("atomic") is True
            and canonical(ev.get("item_value")) == canonical(value)
            and canonical(ev.get("researched_entity")) == canonical(entity)
            and (not str(ev.get("field") or "") or str(ev.get("field")) == field_id)
        ]
        if not exact_rows:
            rejected.append({
                "value": value,
                "reason": "research-binding-metadata-failed",
            })
            continue
        sufficient = [
            ev for ev in exact_rows
            if typed_evidence_sufficient(ev)
        ]
        if not sufficient:
            rejected.append({
                "value": value,
                "reason": "typed-evidence-insufficient",
            })
            continue

        if relation_field:
            bound = evidence_for_relationship(sufficient, entity, value)
        else:
            bound = evidence_for_item(
                sufficient,
                entity,
                value,
                field_id=field_id,
            )
        if not bound:
            rejected.append({
                "value": value,
                "reason": "atomic-binding-failed",
            })
            continue

        item = dict(raw)
        item["evidence"] = bound
        promoted.append(item)

    return promoted, rejected

def _same_host(url_a: str, url_b: str) -> bool:
    return urlparse(url_a).netloc.casefold().removeprefix("www.") == urlparse(url_b).netloc.casefold().removeprefix("www.")


def _link_is_relevant(link: Link, families: set[str]) -> bool:
    path = urlparse(link.url).path.casefold()
    return any(
        family in families and any(hint in path for hint in PATH_FAMILY_HINTS.get(family, ()))
        for family in families
    )


def _financial_link_is_relevant(link: Link) -> bool:
    parsed = urlparse(link.url)
    path = canonical(parsed.path)
    label = canonical(link.label or "")
    blob = f"{path} {label}"
    if parsed.path.casefold().endswith((".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".zip")):
        return False
    return any(canonical(hint) in blob for hint in FINANCIAL_LINK_HINTS)


def _trusted_external_financial_link(
    link: Link,
    document: Document,
    *,
    entity: str,
    seed: SourceSeed,
) -> bool:
    if not seed.official:
        return False
    if not _host_entity_owned(document.url, entity):
        return False
    target_host = (urlparse(link.url).hostname or "").casefold().removeprefix("www.")
    if not target_host or target_host in IGNORED_EXTERNAL_HOSTS:
        return False
    return _financial_link_is_relevant(link)

def _record_external_candidates(
    queue: dict[str, Any],
    document: Document,
    *,
    entity: str,
    family: str,
) -> None:
    if family not in {"partners", "cases"}:
        return
    source_host = urlparse(document.url).netloc.casefold().removeprefix("www.")
    for link in document.links:
        target_host = urlparse(link.url).netloc.casefold().removeprefix("www.")
        label = re.sub(r"\s+", " ", link.label).strip()
        if not target_host or target_host == source_host or target_host in IGNORED_EXTERNAL_HOSTS:
            continue
        if len(label) < 3 or len(label) > 100 or canonical(label) in GENERIC_LINK_LABELS:
            continue
        if not re.search(r"[A-Za-zÀ-ÿ]", label):
            continue
        key = hashlib.sha1(f"{canonical(label)}|{target_host}".encode("utf-8")).hexdigest()[:20]
        item = queue.setdefault(key, {
            "candidate_name": label,
            "target_host": target_host,
            "target_url": link.url,
            "family": family,
            "sightings": [],
            "status": "candidate",
        })
        sighting = {"source_entity": entity, "source_url": document.url, "seen_at": _now_date()}
        signature = (entity, document.url)
        existing = {(row.get("source_entity"), row.get("source_url")) for row in item.get("sightings") or []}
        if signature not in existing:
            item.setdefault("sightings", []).append(sighting)
        distinct_entities = {row.get("source_entity") for row in item.get("sightings") or []}
        item["corroboration_count"] = len(distinct_entities)
        item["status"] = "corroborated-candidate" if len(distinct_entities) >= 2 else "candidate"


def _checkpoint(
    data: dict[str, Any],
    cache: dict[str, Any],
    state: ResearchState,
    discovery: dict[str, Any],
    stats: dict[str, Any],
    active_gap_ids: set[str],
) -> None:
    atomic_write_json("data/current/intelligence.json", data, pretty=False)
    atomic_write_json("data/current/research_cache.json", cache)
    atomic_write_json("data/current/research_state.json", state.export(active_gap_ids))
    atomic_write_json("data/current/discovery_queue.json", {
        "version": VERSION,
        "updated_at": now_iso(),
        "candidates": discovery,
    })
    ledger = {
        key: value
        for key, value in stats.items()
        if key not in {"results", "families", "candidate_rejections"}
    }
    # Keep full-run aggregates before retaining only bounded diagnostic windows.
    # Release gates must never infer the run total from the last diagnostic rows.
    result_rows = [row for row in stats["results"] if isinstance(row, dict)]
    ledger["result_rows_total"] = len(result_rows)
    ledger["accepted_result_rows_total"] = sum(
        int(row.get("accepted") or 0) for row in result_rows
    )
    ledger["results_truncated"] = len(result_rows) > 300
    ledger["results"] = result_rows[-300:]
    rejected_rows = [
        row for row in stats.get("candidate_rejections") or []
        if isinstance(row, dict)
    ]
    ledger["candidate_rejection_rows_total"] = len(rejected_rows)
    ledger["candidate_rejections_truncated"] = len(rejected_rows) > 500
    ledger["candidate_rejections"] = rejected_rows[-500:]
    atomic_write_json("data/current/research_ledger.json", ledger)


def run(
    profile: str = "daily",
    max_runtime: int = 600,
    max_tasks: int | None = None,
    *,
    include_gap_kinds: set[str] | None = None,
) -> dict[str, Any]:
    profile_config = RESEARCH_PROFILES[profile]
    started = time.monotonic()
    deadline = started + max(20, int(max_runtime))
    data = read_json("data/current/intelligence.json")
    from ..public_recovery import recover_newer_public
    recover_newer_public(data)
    gaps = read_json("data/current/research_gaps.json")
    learning = read_json("data/current/research_learning.json", {"version": VERSION, "families": {}})
    cache = read_json("data/current/research_cache.json", {})
    research_state = ResearchState(read_json("data/current/research_state.json", {}))
    discovery_raw = read_json("data/current/discovery_queue.json", {})
    discovery = discovery_raw.get("candidates") if isinstance(discovery_raw, dict) else {}
    if not isinstance(discovery, dict):
        discovery = {}
    targets = plan(
        gaps,
        learning,
        profile,
        state=research_state,
        max_tasks=max_tasks,
        include_gap_kinds=include_gap_kinds,
    )
    # All gaps may be in exponential cooldown simultaneously. A zero-target
    # Daily must not silently report success while making no research attempts.
    # Rotate a small rescue batch across the eligible entity pool; canonical
    # evidence gates, URL security, watchdog and preservation still apply.
    rescue_targets = 0
    if profile == "daily" and not targets:
        candidate_pool = plan(
            gaps, learning, profile, state=None,
            max_tasks=240, include_gap_kinds=include_gap_kinds,
        )
        if candidate_pool:
            offset = (datetime.now(timezone.utc).timetuple().tm_yday * 13) % len(candidate_pool)
            rotated = candidate_pool[offset:] + candidate_pool[:offset]
            targets = rotated[:12]
            rescue_targets = len(targets)
    index = _row_index(data)
    vendor_names = _vendor_names(data)
    active_gap_ids = {str(gap.get("id")) for gap in gaps.get("gaps") or [] if gap.get("id")}
    gap_by_id = {str(gap.get("id")): gap for gap in gaps.get("gaps") or [] if gap.get("id")}

    stats: dict[str, Any] = {
        "version": VERSION,
        "profile": profile,
        "started_at": now_iso(),
        "planned_entities": len(targets),
        "rescue_targets_after_cooldown": rescue_targets,
        "fetch_attempts": 0,
        "fetch_successes": 0,
        "pages_relevant": 0,
        "candidate_evidences": 0,
        "candidate_values_seen": 0,
        "candidate_values_promoted": 0,
        "candidate_values_rejected": 0,
        "candidate_fields_rejected": 0,
        "candidate_rejections": [],
        "accepted_evidences": 0,
        "fields_enriched": 0,
        "values_added": 0,
        "entities_added": 0,
        "cache_hits": 0,
        "circuit_skips": 0,
        "unsafe_url_rejections": 0,
        "official_sites_discovered": 0,
        "financial_links_discovered": 0,
        "query_discovery_targets": 0,
        "search_queries_attempted": 0,
        "search_queries_succeeded": 0,
        "search_provider_failures": 0,
        "search_urls_discovered": 0,
        "unsourced_value_queries": 0,
        "manufacturer_revenue_rows_before": _count_populated_rows(data, "manufacturers", "revenue"),
        "manufacturer_revenue_acceptances": 0,
        "stop_reason": "complete",
        "families": defaultdict(lambda: defaultdict(int)),
        "results": [],
    }
    # Measure the actual contribution of archived source leads independently from
    # HTTP successes or candidate promotions. These counters do not close gaps.
    stats["historical_lead_targets_planned"] = sum(
        bool(any(seed.get("historical_lead") for seed in t.get("revalidation_seeds") or []
                 if isinstance(seed, dict))) for t in targets
    )
    stats["historical_lead_urls_planned"] = sum(
        sum(bool(seed.get("historical_lead")) for seed in t.get("revalidation_seeds") or []
            if isinstance(seed, dict)) for t in targets
    )
    stats["historical_lead_urls_attempted"] = 0
    stats["historical_lead_evidences_accepted"] = 0
    fetcher = Fetcher(profile=profile, deadline=deadline, cache=cache, state=research_state, stats=stats)
    pages_since_checkpoint = 0
    next_heartbeat = started + 25

    # Structured public procurement is both higher precision and a genuine growth path.
    if include_gap_kinds is None and deadline - time.monotonic() > profile_config.request_timeout_s + 3:
        try:
            structured_growth_defaults = {"daily": 24, "deep": 100, "exhaustive": 220}
            structured_growth_limits = RESEARCH_POLICY.get("structured_growth_limits") or {}
            structured_growth_budget = max(
                0, int(structured_growth_limits.get(profile, structured_growth_defaults[profile]))
            )
            stats["structured_entity_budget"] = structured_growth_budget
            notices = fetch_notices(
                fetcher.session,
                lookback_days=profile_config.ted_lookback_days,
                timeout_s=profile_config.request_timeout_s,
                limit=structured_growth_budget,
            )
            structured_added = upsert_notices(data, notices)
            stats["entities_added"] += structured_added
            stats["structured_entities_added"] = structured_added
            stats["structured_notices"] = len(notices)
            index = _row_index(data)
        except requests.RequestException as exc:
            stats["structured_ted_status"] = f"degraded:{type(exc).__name__}"

    for target in targets:
        if "derivation-support" in set(target.get("gap_kinds") or []):
            continue
        if time.monotonic() >= deadline - 4:
            stats["stop_reason"] = "deadline"
            break
        row = index.get((target["section"], canonical(target["entity"])))
        if not row:
            continue
        exact_unsourced_queries = _unsourced_value_queries(row, target["fields"])
        if exact_unsourced_queries:
            target["query_hints"] = list(dict.fromkeys(
                exact_unsourced_queries + list(target.get("query_hints") or [])
            ))[:16]
            stats["unsourced_value_queries"] += len(exact_unsourced_queries)
        seeds = _merge_source_seeds(
            _revalidation_source_seeds(target),
            seeds_for(row, target["fields"], target=target),
            _catalog_source_seeds(data, target["section"], target["fields"], target["entity"]),
        )
        seeds = _filter_entity_seeds(
            seeds,
            target["entity"],
            target["section"],
        )
        if (
            "revenue" in (target.get("fields") or [])
            and target["section"] in {"manufacturers", "distributors"}
        ):
            financial_entry = _financial_entry_seed(seeds, target["entity"])
            financial_seeds = [seed for seed in seeds if seed.family == "financial"]
            other_seeds = [seed for seed in seeds if seed.family != "financial"]
            seeds = _merge_source_seeds(
                [financial_entry] if financial_entry else [],
                financial_seeds,
                other_seeds,
            )
        needs_official_discovery = (
            target["section"] not in {"trends", "architectures"}
            and (
                not seeds
                or (
                    bool({"historical-revalidation", "evidence-support"} & set(target.get("gap_kinds") or []))
                    and not any(seed.official for seed in seeds)
                )
            )
        )
        if needs_official_discovery:
            remaining = min(float(profile_config.request_timeout_s), deadline - time.monotonic() - 2)
            if remaining >= 3.0:
                discovered = discover_official_site(fetcher.session, target["entity"], timeout_s=remaining)
                if discovered:
                    seeds = [discovered]
                    stats["official_sites_discovered"] += 1
        # Query discovery closes the blind spot between generated query hints and
        # the URL-only crawler. Search results are discovery leads, never evidence.
        query_policy = RESEARCH_POLICY.get("query_discovery") or {}
        query_budgets = query_policy.get("budgets") or {}
        query_budget = query_budgets.get(profile) or {}
        can_query_discover = (
            bool(query_policy.get("enabled", True))
            and bool(target.get("query_hints"))
            and stats["query_discovery_targets"] < int(query_budget.get("max_entities") or 0)
            and time.monotonic() < deadline - max(5.0, float(profile_config.request_timeout_s))
        )
        if can_query_discover:
            fallback_family = next(iter(target.get("families") or []), "official")
            discovered, query_stats = discover_search_sources(
                fetcher.session,
                target.get("query_hints") or [],
                fallback_family=fallback_family,
                providers=query_policy.get("providers") or ["bing_rss", "duckduckgo_html"],
                timeout_s=min(float(profile_config.request_timeout_s), max(2.5, deadline - time.monotonic() - 3)),
                max_queries=int(query_budget.get("queries_per_entity") or 0),
                results_per_query=int(query_budget.get("results_per_query") or 4),
            )
            stats["query_discovery_targets"] += 1
            stats["search_queries_attempted"] += int(query_stats.get("queries_attempted") or 0)
            stats["search_queries_succeeded"] += int(query_stats.get("queries_succeeded") or 0)
            stats["search_provider_failures"] += int(query_stats.get("provider_failures") or 0)
            stats["search_urls_discovered"] += int(query_stats.get("urls_discovered") or 0)
            # A discovered page is official only when its host is demonstrably owned
            # by the researched entity. Everything else remains grade-C discovery.
            discovered = [
                SourceSeed(
                    seed.url,
                    seed.family,
                    True,
                    "A",
                    "search-discovery:official-owned-host",
                    target["entity"],
                )
                if _host_entity_owned(seed.url, target["entity"])
                else seed
                for seed in discovered
            ]
            seeds = _merge_source_seeds(seeds, discovered)
            seeds = _filter_entity_seeds(seeds, target["entity"], target["section"])

        if not seeds:
            for gap_id in target["gap_ids"]:
                research_state.record_gap(gap_id, accepted=0, error="no-seed-source")
            continue

        archived_urls = {
            str(item.get("url") or "") for item in target.get("revalidation_seeds") or []
            if isinstance(item, dict) and item.get("historical_lead")
        }
        queue = list(seeds)
        seen: set[tuple[str, str]] = set()
        pages = 0
        accepted_by_field: defaultdict[str, int] = defaultdict(int)
        wanted_families = relevant_families(target["fields"]) | set(target.get("source_families") or [])
        scope = str(((row.get("fields") or {}).get("scope") or {}).get("value") or "GLOBAL")

        while queue and pages < profile_config.pages_per_entity and time.monotonic() < deadline - 3:
            seed = queue.pop(0)
            seed_key = (seed.url, seed.family)
            if seed_key in seen:
                continue
            seen.add(seed_key)
            from_history = seed.url in archived_urls
            if from_history:
                stats["historical_lead_urls_attempted"] += 1
            document, cached, status, error = fetcher.fetch(seed)
            family_stats = stats["families"][f"{target['section']}:{seed.family}"]
            family_stats["attempts"] += 1
            if document is None:
                if error.startswith("unsafe-url"):
                    stats["unsafe_url_rejections"] += 1
                stats["results"].append({
                    "section": target["section"],
                    "entity": target["entity"],
                    "url": seed.url,
                    "family": seed.family,
                    "status": status,
                    "error": error,
                    "accepted": 0,
                })
                continue

            stats["fetch_successes"] += 1
            family_stats["fetch_successes"] += 1
            pages += 1
            pages_since_checkpoint += 1
            candidates = extract_candidates(
                target["section"],
                seed.family,
                document,
                vendor_names,
                official=seed.official,
            )
            candidates = _focus_candidates(
                candidates, target, document, seed.official
            )
            relevant = bool(candidates)
            if relevant:
                stats["pages_relevant"] += 1
                family_stats["pages_relevant"] += 1
            accepted_here = 0

            for field_id, candidate in candidates.items():
                if profile == "daily" and field_id not in target["fields"]:
                    continue
                stats["candidate_evidences"] += 1
                family_stats["candidate_evidence"] += 1
                old_field = row.get("fields", {}).get(field_id)
                before_values = _field_values(old_field)
                before_evidence = _field_evidence_keys(old_field)
                raw_items = _candidate_items(
                    seed, document, field_id, candidate, target["entity"], scope
                )
                stats["candidate_values_seen"] += len(raw_items)
                items, rejected = _promotable_candidate_items(
                    raw_items,
                    entity=target["entity"],
                    field_id=field_id,
                )
                stats["candidate_values_promoted"] += len(items)
                stats["candidate_values_rejected"] += len(rejected)
                if rejected:
                    family_stats["candidate_rejected"] += len(rejected)
                    for decision in rejected:
                        stats["candidate_rejections"].append({
                            "section": target["section"],
                            "entity": target["entity"],
                            "field": field_id,
                            "value": decision.get("value"),
                            "reason": decision.get("reason"),
                            "url": document.url,
                            "family": seed.family,
                        })
                if not items:
                    stats["candidate_fields_rejected"] += 1
                    continue
                evidence = [
                    ev
                    for item in items
                    for ev in (item.get("evidence") or [])
                ]
                row.setdefault("fields", {})[field_id] = merge_field(old_field, {
                    "value": [item.get("value") for item in items],
                    "items": items,
                    "evidence": evidence,
                    "confidence": candidate.confidence,
                    "claim_type": candidate.claim_type,
                    "assertion_status": "SEÑAL" if candidate.claim_type == "signal" else "CONFIRMADO" if candidate.confidence >= 0.8 else "PROBABLE",
                    "qualifier": (
                        "Facturación: concepto financiero, importe/moneda y periodo deben aparecer juntos; "
                        "en fabricantes se rechazan cifras de canal, región, segmento, mercado o terceros. "
                        if field_id == "revenue"
                        else
                        "Extracción automática conservadora con fragmento y huella del documento. "
                        "Las señales de empleo no prueban por sí solas una relación comercial o un despliegue."
                    ),
                })
                new_field = row["fields"][field_id]
                values_added = len(_field_values(new_field) - before_values)
                evidence_added = len(_field_evidence_keys(new_field) - before_evidence)
                if values_added or evidence_added:
                    accepted_here += 1
                    accepted_by_field[field_id] += 1
                    stats["accepted_evidences"] += 1
                    if from_history:
                        stats["historical_lead_evidences_accepted"] += 1
                    stats["fields_enriched"] += 1
                    stats["values_added"] += values_added
                    family_stats["accepted_evidence"] += 1
                    if target["section"] == "manufacturers" and field_id == "revenue":
                        stats["manufacturer_revenue_acceptances"] += 1

            fetcher.state.record_domain(document.url, ok=True, relevant=relevant, accepted=accepted_here, status=status)
            if include_gap_kinds is None:
                _record_external_candidates(discovery, document, entity=target["entity"], family=seed.family)
            stats["results"].append({
                "section": target["section"],
                "entity": target["entity"],
                "url": document.url,
                "family": seed.family,
                "cached": cached,
                "relevant": relevant,
                "accepted": accepted_here,
                "status": status,
            })

            # Sitemaps and real links drive discovery. Financial research additionally starts from
            # the trusted official page and can follow an explicit Investor Relations/results link
            # even when that official link moves to an investor subdomain or dedicated corporate host.
            discovered_urls = sitemap_urls(document.text) if seed.url.casefold().endswith(("sitemap.xml", "sitemap_index.xml")) else []
            for url in discovered_urls[:250]:
                family = family_from_url(url)
                if family in wanted_families and (url, family) not in seen:
                    queue.append(SourceSeed(url, family, seed.official, seed.source_grade, seed.source_type, seed.source_name))
            follow_links = (
                profile != "daily"
                or relevant
                or (seed.family == "financial" and "revenue" in (target.get("fields") or []))
            )
            if follow_links:
                for link in document.links:
                    hinted_financial = "financial" in wanted_families and _financial_link_is_relevant(link)
                    family = "financial" if hinted_financial else family_from_url(link.url)
                    same_host = _same_host(link.url, document.url)
                    trusted_external_financial = (
                        hinted_financial
                        and _trusted_external_financial_link(
                            link,
                            document,
                            entity=target["entity"],
                            seed=seed,
                        )
                    )
                    if (
                        (same_host or trusted_external_financial)
                        and family in wanted_families
                        and (hinted_financial or _link_is_relevant(link, wanted_families))
                        and (link.url, family) not in seen
                    ):
                        linked_type = (
                            "official-linked-financial"
                            if trusted_external_financial and not same_host
                            else seed.source_type
                        )
                        queue.append(SourceSeed(
                            link.url,
                            family,
                            seed.official,
                            seed.source_grade,
                            linked_type,
                            seed.source_name,
                        ))
                        if hinted_financial:
                            stats["financial_links_discovered"] += 1

            if pages_since_checkpoint >= profile_config.checkpoint_every:
                _checkpoint(data, cache, research_state, discovery, stats, active_gap_ids)
                pages_since_checkpoint = 0
            if time.monotonic() >= next_heartbeat:
                print(
                    f"research heartbeat: {profile} · {round(time.monotonic()-started)}s · "
                    f"{stats['fetch_attempts']} fetch · {stats['accepted_evidences']} accepted",
                    flush=True,
                )
                next_heartbeat = time.monotonic() + 25

        for gap_id in target["gap_ids"]:
            field_id = str((gap_by_id.get(gap_id) or {}).get("field") or "")
            research_state.record_gap(gap_id, accepted=accepted_by_field[field_id])

    families_output = {}
    for key, row_stats in stats["families"].items():
        current = (learning.setdefault("families", {}).setdefault(key, {}))
        for metric in (
            "attempts", "fetch_successes", "pages_relevant",
            "candidate_evidence", "accepted_evidence", "candidate_rejected",
        ):
            current[metric] = int(current.get(metric) or 0) + int(row_stats.get(metric) or 0)
        current["fetch_success_rate"] = round(current["fetch_successes"] / max(1, current["attempts"]), 4)
        current["evidence_yield"] = round(current["accepted_evidence"] / max(1, current["pages_relevant"]), 4)
        families_output[key] = dict(row_stats)

    learning["version"] = VERSION
    learning["updated_at"] = now_iso()
    learning["policy"] = "Prioritize accepted evidence and gap closure; transport success is never intelligence success."
    stats["families"] = families_output
    stats["accepted_evidence_per_fetch_attempt"] = round(
        stats["accepted_evidences"] / max(1, stats["fetch_attempts"]), 4
    )
    stats["candidate_acceptance_rate"] = round(
        stats["accepted_evidences"] / max(1, stats["candidate_evidences"]), 4
    )
    stats["candidate_value_promotion_rate"] = round(
        stats["candidate_values_promoted"] / max(1, stats["candidate_values_seen"]), 4
    )
    stats["values_per_accepted_evidence"] = round(
        stats["values_added"] / max(1, stats["accepted_evidences"]), 4
    )
    stats["growth_pressure_ratio"] = round(
        stats["entities_added"] / max(1, stats["values_added"]), 4
    )
    stats["manufacturer_revenue_rows_after"] = _count_populated_rows(
        data, "manufacturers", "revenue"
    )
    stats["manufacturer_revenue_rows_added"] = max(
        0,
        stats["manufacturer_revenue_rows_after"] - stats["manufacturer_revenue_rows_before"],
    )
    stats["elapsed_s"] = round(time.monotonic() - started, 2)
    stats["finished_at"] = now_iso()
    cache = prune_json_mapping(cache, limit=1_600, timestamp_key="ts")
    _checkpoint(data, cache, research_state, discovery, stats, active_gap_ids)
    atomic_write_json("data/current/research_learning.json", learning)
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=sorted(RESEARCH_PROFILES), default="daily")
    parser.add_argument("--max-runtime", type=int, default=600)
    parser.add_argument("--max-tasks", type=int)
    arguments = parser.parse_args()
    try:
        result = run(arguments.profile, max_runtime=arguments.max_runtime, max_tasks=arguments.max_tasks)
    except Exception as exc:
        print(f"research fatal: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        raise
    print(json.dumps({
        key: value for key, value in result.items()
        if key not in {"results", "candidate_rejections"}
    }, ensure_ascii=False))
