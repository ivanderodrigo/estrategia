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
from ..model import canonical
from ..settings import RESEARCH_POLICY, RESEARCH_PROFILES, VERSION
from ..storage import atomic_write_json, prune_json_mapping, read_json
from .documents import Document, Link, parse_document, sitemap_urls
from .client_discovery import discover_official_site
from .extractors import Candidate, evidence_snippet, extract_candidates
from .planner import plan
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
        retry = Retry(
            total=self.profile.retries,
            connect=self.profile.retries,
            read=self.profile.retries,
            status=self.profile.retries,
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

    blob = canonical(f"{source_type} {source_name} {path}")
    relationship_hints = {
        "partner", "partners", "alliance", "alliances", "locator",
        "directory", "reseller", "resellers", "distributor", "distributors",
        "integrator", "integrators", "system integrator", "msp", "mssp",
        "service provider", "award", "awards", "customer case", "case study",
        "customer success", "strategic agreement",
    }
    if any(hint in blob for hint in relationship_hints):
        return "relationship-source"

    if "revalidated" in canonical(source_type):
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
        if binding in {"entity-owned", "relationship-source"}:
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

    if field in {"capabilities", "services"}:
        cues = (
            "we offer", "we provide", "we deliver",
            "our services", "our solutions", "our capabilities",
            "offers", "provides", "delivers",
            "ofrecemos", "ofrece", "proporciona", "prestamos",
            "nuestros servicios", "nuestras soluciones",
            "servicios", "solutions", "capabilities",
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

    if field in {"hiring_signals", "job_profiles", "job_vendors"}:
        if entity_owned and entity_key and entity_key in title:
            return True

    if entity_owned:
        if field in {"services", "capabilities"}:
            headings = (
                "services", "servicios", "solutions", "soluciones",
                "capabilities", "capacidades", "portfolio", "oferta",
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


def _focus_candidates(
    candidates: dict[str, Candidate],
    target: dict[str, Any],
    document: Document,
    official: bool,
) -> dict[str, Candidate]:
    target_map = target.get("target_values") or {}
    if not isinstance(target_map, dict) or not target_map:
        return candidates

    strict_claim_support = bool(
        {"historical-revalidation", "evidence-support"}
        & set(target.get("gap_kinds") or [])
    )
    output = dict(candidates)

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
        filtered = tuple(
            value for value in candidate.values
            if canonical(value) in wanted_keys
        )
        if filtered:
            output[field_id] = Candidate(
                filtered,
                candidate.claim_type,
                candidate.confidence,
                candidate.snippet,
                candidate.matched_terms,
            )

    return output


def _evidence(seed: SourceSeed, document: Document, field_id: str, candidate: Candidate, entity: str, scope: str) -> list[dict[str, Any]]:
    return [{
        "source": urlparse(document.url).netloc.removeprefix("www.") or seed.source_name or entity,
        "source_catalog_name": seed.source_name or "",
        "researched_entity": entity,
        "source_binding": _seed_binding(
            document.url,
            entity,
            source_type=seed.source_type,
            source_name=seed.source_name,
        ),
        "title": document.title or f"Página pública · {seed.family}",
        "url": document.url,
        "date": _now_date(),
        "description": candidate.snippet,
        "scope": scope or "GLOBAL",
        "source_grade": "A" if seed.official else seed.source_grade or "B",
        "source_type": seed.source_type,
        "official": seed.official,
        "classification": "public",
        "retrieved_at": _now_date(),
        "freshness_status": "current",
        "method": f"web-evidence:{seed.family}",
        "content_digest": document.content_digest,
        "matched_terms": list(candidate.matched_terms),
        "field": field_id,
        "revalidation": "historical-source-refetched" if "revalidated" in seed.source_type else "",
    }]


def _same_host(url_a: str, url_b: str) -> bool:
    return urlparse(url_a).netloc.casefold().removeprefix("www.") == urlparse(url_b).netloc.casefold().removeprefix("www.")


def _link_is_relevant(link: Link, families: set[str]) -> bool:
    path = urlparse(link.url).path.casefold()
    return any(
        family in families and any(hint in path for hint in PATH_FAMILY_HINTS.get(family, ()))
        for family in families
    )


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
    ledger = {key: value for key, value in stats.items() if key not in {"results", "families"}}
    ledger["results"] = stats["results"][-300:]
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
    index = _row_index(data)
    vendor_names = _vendor_names(data)
    active_gap_ids = {str(gap.get("id")) for gap in gaps.get("gaps") or [] if gap.get("id")}
    gap_by_id = {str(gap.get("id")): gap for gap in gaps.get("gaps") or [] if gap.get("id")}

    stats: dict[str, Any] = {
        "version": VERSION,
        "profile": profile,
        "started_at": now_iso(),
        "planned_entities": len(targets),
        "fetch_attempts": 0,
        "fetch_successes": 0,
        "pages_relevant": 0,
        "candidate_evidences": 0,
        "accepted_evidences": 0,
        "fields_enriched": 0,
        "values_added": 0,
        "entities_added": 0,
        "cache_hits": 0,
        "circuit_skips": 0,
        "unsafe_url_rejections": 0,
        "official_sites_discovered": 0,
        "stop_reason": "complete",
        "families": defaultdict(lambda: defaultdict(int)),
        "results": [],
    }
    fetcher = Fetcher(profile=profile, deadline=deadline, cache=cache, state=research_state, stats=stats)
    pages_since_checkpoint = 0
    next_heartbeat = started + 25

    # Structured public procurement is both higher precision and a genuine growth path.
    if include_gap_kinds is None and deadline - time.monotonic() > profile_config.request_timeout_s + 3:
        try:
            notices = fetch_notices(
                fetcher.session,
                lookback_days=profile_config.ted_lookback_days,
                timeout_s=profile_config.request_timeout_s,
                limit={"daily": 80, "deep": 150, "exhaustive": 250}[profile],
            )
            stats["entities_added"] += upsert_notices(data, notices)
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
        if not seeds:
            for gap_id in target["gap_ids"]:
                research_state.record_gap(gap_id, accepted=0, error="no-seed-source")
            continue

        queue = list(seeds)
        seen: set[str] = set()
        pages = 0
        accepted_by_field: defaultdict[str, int] = defaultdict(int)
        wanted_families = relevant_families(target["fields"]) | set(target.get("source_families") or [])
        scope = str(((row.get("fields") or {}).get("scope") or {}).get("value") or "GLOBAL")

        while queue and pages < profile_config.pages_per_entity and time.monotonic() < deadline - 3:
            seed = queue.pop(0)
            if seed.url in seen:
                continue
            seen.add(seed.url)
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
                evidence = _evidence(seed, document, field_id, candidate, target["entity"], scope)
                row.setdefault("fields", {})[field_id] = merge_field(old_field, {
                    "value": list(candidate.values),
                    "evidence": evidence,
                    "confidence": candidate.confidence,
                    "claim_type": candidate.claim_type,
                    "assertion_status": "SEÑAL" if candidate.claim_type == "signal" else "CONFIRMADO" if candidate.confidence >= 0.8 else "PROBABLE",
                    "qualifier": (
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
                    stats["fields_enriched"] += 1
                    stats["values_added"] += values_added
                    family_stats["accepted_evidence"] += 1

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

            # Sitemaps and relevant same-domain links replace invented 48-query claims with real discovery.
            discovered_urls = sitemap_urls(document.text) if seed.url.casefold().endswith(("sitemap.xml", "sitemap_index.xml")) else []
            for url in discovered_urls[:250]:
                family = family_from_url(url)
                if family in wanted_families and url not in seen:
                    queue.append(SourceSeed(url, family, seed.official, seed.source_grade, seed.source_type, seed.source_name))
            if profile != "daily" or relevant:
                for link in document.links:
                    family = family_from_url(link.url)
                    if (
                        _same_host(link.url, document.url)
                        and family in wanted_families
                        and _link_is_relevant(link, wanted_families)
                        and link.url not in seen
                    ):
                        queue.append(SourceSeed(link.url, family, seed.official, seed.source_grade, seed.source_type, seed.source_name))

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
        for metric in ("attempts", "fetch_successes", "pages_relevant", "candidate_evidence", "accepted_evidence"):
            current[metric] = int(current.get(metric) or 0) + int(row_stats.get(metric) or 0)
        current["fetch_success_rate"] = round(current["fetch_successes"] / max(1, current["attempts"]), 4)
        current["evidence_yield"] = round(current["accepted_evidence"] / max(1, current["pages_relevant"]), 4)
        families_output[key] = dict(row_stats)

    learning["version"] = VERSION
    learning["updated_at"] = now_iso()
    learning["policy"] = "Prioritize accepted evidence and gap closure; transport success is never intelligence success."
    stats["families"] = families_output
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
    print(json.dumps({key: value for key, value in result.items() if key != "results"}, ensure_ascii=False))
