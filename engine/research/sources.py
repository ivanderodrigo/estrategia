"""Evidence-aware source registry and route discovery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urlparse

from .planner import FAMILY_BY_FIELD


@dataclass(frozen=True)
class SourceSeed:
    url: str
    family: str
    official: bool
    source_grade: str
    source_type: str
    source_name: str


ROUTES = {
    "official": ("/", "/sitemap.xml", "/robots.txt"),
    "partners": ("/partners", "/parceiros", "/alianzas", "/vendors", "/fabricantes", "/marcas", "/portfolio", "/line-card", "/sitemap.xml"),
    "services": ("/services", "/servicios", "/servicos", "/solutions", "/soluciones", "/solucoes", "/cybersecurity", "/cloud", "/sitemap.xml"),
    "cases": ("/customers", "/clientes", "/case-studies", "/casos", "/projects", "/proyectos", "/industrias", "/sitemap.xml"),
    "careers": ("/careers", "/jobs", "/empleo", "/talent", "/carreiras", "/emprego", "/sitemap.xml"),
    "technology": (
        "/technology", "/tecnologia", "/digital", "/transformacion-digital", "/transformacao-digital",
        "/solutions", "/soluciones", "/solucoes", "/services", "/servicios", "/servicos",
        "/cybersecurity", "/ciberseguridad", "/security", "/seguridad", "/seguranca",
        "/networking", "/redes", "/connectivity", "/cloud", "/data", "/ai",
        "/innovation", "/innovacion", "/inovacao", "/it", "/ict", "/sitemap.xml",
    ),
    "financial": ("/investors", "/investor-relations", "/annual-report", "/resultados", "/relatorio-e-contas", "/sitemap.xml"),
    "news": ("/news", "/noticias", "/insights", "/press", "/actualidad", "/feed", "/rss", "/sitemap.xml"),
    "analyst": ("/analyst", "/reports", "/resources", "/research", "/sitemap.xml"),
    "signals": ("/news", "/careers", "/projects", "/sitemap.xml"),
    "procurement": ("/contratacion", "/procurement", "/concursos", "/sitemap.xml"),
}

PATH_FAMILY_HINTS = {
    "partners": ("partner", "vendor", "fabric", "marca", "portfolio", "line-card", "parceir", "alian"),
    "careers": ("career", "job", "emple", "emprego", "talent", "oportun"),
    "cases": ("case", "caso", "customer", "client", "project", "industr", "sector"),
    "services": ("service", "servic", "solu", "cyber", "cloud", "network"),
    "technology": ("technolog", "tecnolog", "digital", "cyber", "security", "segur", "network", "red", "cloud", "data", "ai", "automat", "observab", "identity", "identid", "innovation", "inovacao", "innovacion"),
    "financial": ("invest", "annual", "result", "relatorio", "report"),
    "news": ("news", "press", "notic", "insight", "feed", "rss"),
    "analyst": ("analyst", "research", "report", "resource"),
}


def family_from_url(url: str, fallback: str = "official") -> str:
    path = urlparse(url).path.casefold()
    for family, hints in PATH_FAMILY_HINTS.items():
        if any(hint in path for hint in hints):
            return family
    return fallback


def relevant_families(fields: Iterable[str]) -> set[str]:
    return {FAMILY_BY_FIELD.get(field, "official") for field in fields} | {"official"}


def _iter_evidence(row: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for evidence in row.get("evidence") or []:
        if isinstance(evidence, dict):
            yield evidence
    for field in (row.get("fields") or {}).values():
        for evidence in field.get("evidence") or []:
            if isinstance(evidence, dict):
                yield evidence
        for item in field.get("items") or []:
            if isinstance(item, dict):
                for evidence in item.get("evidence") or []:
                    if isinstance(evidence, dict):
                        yield evidence


def seeds_for(row: dict[str, Any], fields: Iterable[str]) -> list[SourceSeed]:
    families = relevant_families(fields)
    found: dict[tuple[str, str], SourceSeed] = {}
    for evidence in _iter_evidence(row):
        url = str(evidence.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            continue
        source_type = str(evidence.get("source_type") or evidence.get("type") or "public-web")
        grade = str(evidence.get("source_grade") or "C")
        official = evidence.get("official") is True or "official" in source_type.casefold()
        family = family_from_url(url)
        seed = SourceSeed(
            url=url,
            family=family,
            official=official,
            source_grade=grade,
            source_type=source_type,
            source_name=str(evidence.get("source") or row.get("name") or "Fuente pública"),
        )
        found.setdefault((url, family), seed)

        if official:
            parsed = urlparse(url)
            base = f"{parsed.scheme}://{parsed.netloc}"
            for wanted in families:
                for route in ROUTES.get(wanted, ROUTES["official"]):
                    routed = SourceSeed(
                        url=base + route,
                        family=wanted,
                        official=True,
                        source_grade="A",
                        source_type="official-domain",
                        source_name=str(row.get("name") or seed.source_name),
                    )
                    found.setdefault((routed.url, wanted), routed)

    ordered = sorted(
        found.values(),
        key=lambda item: (
            item.family not in families,
            not item.official,
            item.source_grade[:1] not in {"A", "B"},
            item.url,
        ),
    )
    return ordered
