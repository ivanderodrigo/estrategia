"""Evidence-first source navigation and claim-specific URL discovery.

A source lead is never a confirmed assertion. This module changes only the
order in which publicly accessible documents are fetched and searched. Every
extracted fact still needs the normal entity/field/atomic-provenance gates.
"""
from __future__ import annotations

import re
from collections import defaultdict
from urllib.parse import urlsplit

from ..model import canonical
from .documents import Document
from .sources import SourceSeed, family_from_url, relevant_families

_NAVIGATION = {
    "partners": ("fabricantes", "marcas", "nuestras marcas", "nossas marcas",
                 "vendors", "our vendors", "brands", "our brands", "linecard",
                 "line card", "partners", "parceiros", "alianzas", "alliances",
                 "fabricantes y socios", "technology partners"),
    "services": ("servicios", "servicos", "services", "solutions", "soluciones",
                 "solucoes", "managed services", "servicios gestionados"),
    "cases": ("casos de exito", "casos de éxito", "case studies", "customer stories",
              "clientes", "success stories", "casos de sucesso"),
    "careers": ("empleo", "emprego", "jobs", "careers", "carreiras", "trabaja con nosotros"),
    "financial": ("investor relations", "investors", "financial results",
                  "resultados financieros", "relatorios e contas", "annual reports"),
    "technology": ("products", "productos", "produtos", "plataformas", "technologies"),
    "news": ("noticias", "notícias", "newsroom", "press releases", "actualidad"),
    "procurement": ("contratacion", "contratação", "licitaciones", "adjudicaciones",
                    "concursos", "procurement", "tenders"),
}
_STRONG_VENDOR = ("fabricantes", "marcas", "vendors", "brands", "linecard",
                  "line card", "portfolio", "parceiros", "partners")
_EXCLUDED_PATH = re.compile(
    r"(?:/|^)(?:login|signin|register|cart|checkout|privacy|cookies|terms|"
    r"account|subscribe|newsletter|contact|contacto)(?:/|$)", re.I,
)


def _label_family(label: str, path: str, wanted: set[str]) -> tuple[str, int] | None:
    normalized = canonical(label)
    canonical_path = canonical(path.replace("-", " ").replace("_", " "))
    for family, phrases in _NAVIGATION.items():
        if family not in wanted:
            continue
        for phrase in phrases:
            phrase = canonical(phrase)
            if (phrase in normalized or phrase in canonical_path):
                # A link to a named first-party catalogue beats a generic menu.
                strength = 0 if family == "partners" and any(
                    canonical(word) in normalized or canonical(word) in canonical_path
                    for word in _STRONG_VENDOR
                ) else 1
                return family, strength
    return None


def precise_navigation(
    document: Document,
    origin: SourceSeed,
    fields: list[str],
    *,
    limit: int = 5,
) -> list[SourceSeed]:
    """Follow explicit internal section menus, even on non-extractable homepages.

    Daily previously required a page to produce a candidate BEFORE following its
    Fabricantes/Vendors/Services link: the relevant catalogue was never reached.
    A linked page is only an entry point, not proof of any vendor relationship.
    """
    if limit <= 0 or not origin.official:
        return []
    wanted = relevant_families(fields)
    wanted.discard("official")  # Generic home links are not evidence routes.
    host = (urlsplit(document.url).hostname or "").casefold().removeprefix("www.")
    source_path = urlsplit(document.url).path.rstrip("/")
    candidates: dict[str, tuple[int, SourceSeed]] = {}
    for link in document.links:
        parsed = urlsplit(link.url)
        if (parsed.scheme not in {"https", "http"}
                or (parsed.hostname or "").casefold().removeprefix("www.") != host
                or not parsed.path or parsed.path.rstrip("/") == source_path
                or _EXCLUDED_PATH.search(parsed.path)
                or parsed.path.lower().endswith((".pdf", ".zip", ".jpg", ".png", ".doc", ".docx"))):
            continue
        matched = _label_family(str(link.label or ""), parsed.path, wanted)
        if not matched:
            continue
        family, strength = matched
        # Avoid multiplying near-identical tracking query URLs.
        url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
        if not url:
            continue
        seed = SourceSeed(
            url=url,
            family=family,
            official=True,
            source_grade="A",
            source_type="official-explicit-navigation",
            source_name=origin.source_name,
        )
        key = url.casefold()
        # Prefer the specific catalogue path to a generic partner page.
        rank = strength * 10 + min(9, len(parsed.path.split("/")))
        if key not in candidates or rank < candidates[key][0]:
            candidates[key] = (rank, seed)
    return [item[1] for item in sorted(candidates.values(), key=lambda row: (row[0], row[1].url))[:limit]]


def prioritize_sources(seeds: list[SourceSeed], target: dict) -> list[SourceSeed]:
    """Reserve scarce pages for exact citations and first-party directories.

    Do not spend all six Daily pages on guessed routes, site maps and generic
    corporate homepages while a documented claim or catalogue URL is waiting.
    """
    fields = set(target.get("fields") or [])
    want_vendors = bool(fields & {"vendor_relations", "competitor_vendor_overlap", "westcon_overlap"})
    want_financial = "revenue" in fields
    ranked = []
    for order, seed in enumerate(seeds):
        parsed = urlsplit(seed.url)
        path = parsed.path.casefold().rstrip("/")
        source_type = str(seed.source_type or "").casefold()
        if want_vendors and source_type == "official-linecard-discovery-lead":
            priority = 0
        elif "revalidat" in source_type or "historical" in source_type:
            priority = 1
        elif want_financial and seed.family == "financial" and seed.official:
            priority = 2
        elif source_type == "official-explicit-navigation":
            priority = 2
        elif source_type == "official-domain":
            # The expanded routes are only guesses: an actual documented
            # homepage is more useful because its links reveal real paths.
            priority = 9 if "sitemap" in path or "robots.txt" in path else 7
        elif seed.official and path and "sitemap" not in path:
            priority = 3
        elif seed.official and path in {"", "/"}:
            priority = 4
        elif "search-discovery" in source_type and path and path != "/":
            priority = 5
        elif "search-discovery" in source_type:
            priority = 6
        elif path.endswith(("sitemap.xml", "robots.txt", "sitemap_index.xml")):
            priority = 9
        else:
            priority = 8
        ranked.append((priority, order, seed))
    # Same URL with multiple guessed families is still one HTTP document. Keep
    # the most relevant family and avoid burning the per-entity page allowance.
    chosen = {}
    for priority, order, seed in sorted(ranked):
        key = seed.url.casefold().rstrip("/")
        if key not in chosen:
            chosen[key] = seed
    return list(chosen.values())


def precise_claim_queries(
    target: dict,
    seeds: list[SourceSeed],
    *,
    rotation: int = 0,
    limit: int = 4,
) -> list[str]:
    """Search unsupported *exact* values inside known official source domains.

    Historical values are search hypotheses, not verified facts. Domain limits
    restrict search discovery; only fetched documents can accredit a claim.
    """
    if limit <= 0:
        return []
    entity = str(target.get("entity") or "").strip()
    if not entity:
        return []
    official_hosts: list[str] = []
    for seed in seeds:
        if not seed.official:
            continue
        host = (urlsplit(seed.url).hostname or "").casefold().removeprefix("www.")
        if host and host not in official_hosts:
            official_hosts.append(host)
    if not official_hosts:
        return []
    items: list[tuple[str, str]] = []
    for field, values in (target.get("target_values_by_field") or target.get("target_values") or {}).items():
        for raw in values or []:
            value = " ".join(str(raw).split()).strip('"')
            if (not 4 <= len(value) <= 85 or len(value.split()) > 10
                    or canonical(value) in {"unknown", "por investigar", "no disponible", "si", "no"}
                    or value.casefold() == entity.casefold()):
                continue
            items.append((str(field), value))
    if not items:
        return []
    # Rotate fields across runs rather than citing the same first pending claim.
    shift = rotation % len(items)
    items = items[shift:] + items[:shift]
    output = []
    for field, value in items:
        for host in official_hosts[:2]:
            query = f'"{entity}" "{value}" site:{host}'
            if query not in output:
                output.append(query)
            if len(output) >= limit:
                return output
    return output
