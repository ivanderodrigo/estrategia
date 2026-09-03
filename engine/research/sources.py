"""Evidence-aware source registry and route discovery with v4.2 gap playbooks."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping
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
    "partners": (
        "/partners", "/partner", "/partner-locator", "/find-a-partner", "/parceiros", "/alianzas",
        "/alliances", "/vendors", "/fabricantes", "/marcas", "/portfolio", "/line-card", "/sitemap.xml",
    ),
    "services": (
        "/services", "/servicios", "/servicos", "/solutions", "/soluciones", "/solucoes",
        "/cybersecurity", "/security", "/cloud", "/networking", "/managed-services", "/sitemap.xml",
    ),
    "cases": (
        "/customers", "/clientes", "/case-studies", "/customer-stories", "/casos", "/projects",
        "/proyectos", "/industrias", "/industries", "/success-stories", "/sitemap.xml",
    ),
    "careers": (
        "/careers", "/jobs", "/empleo", "/talent", "/carreiras", "/emprego", "/vacancies",
        "/open-positions", "/sitemap.xml",
    ),
    "technology": (
        "/technology", "/technologies", "/tecnologia", "/products", "/platform", "/solutions",
        "/services", "/architecture", "/architectures", "/sitemap.xml",
    ),
    "financial": (
        "/investors", "/investor-relations", "/annual-report", "/annual-reports", "/financial-results",
        "/resultados", "/relatorio-e-contas", "/reports", "/sitemap.xml",
    ),
    "news": (
        "/news", "/noticias", "/insights", "/press", "/press-releases", "/actualidad", "/feed", "/rss", "/sitemap.xml",
    ),
    "analyst": ("/analyst", "/reports", "/resources", "/research", "/market", "/sitemap.xml"),
    "signals": ("/news", "/careers", "/projects", "/roadmap", "/sitemap.xml"),
    "procurement": (
        "/contratacion", "/contratacion-publica", "/procurement", "/tenders", "/concursos", "/licitacoes",
        "/adjudicaciones", "/contracts", "/sitemap.xml",
    ),
}
PATH_FAMILY_HINTS = {
    "partners": ("partner", "vendor", "fabric", "marca", "portfolio", "line-card", "parceir", "alian", "alliance"),
    "careers": ("career", "job", "emple", "emprego", "talent", "oportun", "vacanc"),
    "cases": ("case", "caso", "customer", "client", "project", "industr", "sector", "success"),
    "services": ("service", "servic", "solu", "cyber", "cloud", "network", "managed"),
    "financial": ("invest", "annual", "result", "relatorio", "financial", "report"),
    "news": ("news", "press", "notic", "insight", "feed", "rss"),
    "analyst": ("analyst", "research", "report", "resource", "market"),
    "procurement": ("procurement", "tender", "contrat", "concurso", "licit", "adjudic"),
    "technology": ("technology", "technolog", "product", "platform", "architect"),
}


def family_from_url(url: str, fallback: str = "official") -> str:
    path = urlparse(url).path.casefold()
    for family, hints in PATH_FAMILY_HINTS.items():
        if any(hint in path for hint in hints):
            return family
    return fallback


PUBLIC_PROCUREMENT_FIELDS = {
    "notice_id", "request_or_need", "technology_signals", "identified_vendors",
    "identified_integrators", "known_architectures", "technology_domains",
    "estimated_amount", "milestone_date", "procurement_stage", "source_portal",
    "cpv_codes", "evidenced_needs", "opportunity_area",
}


def relevant_families(fields: Iterable[str], *, section: str = "") -> set[str]:
    fields = list(fields)
    families = {FAMILY_BY_FIELD.get(field, "official") for field in fields} | {"official"}
    if section == "clients_public" and any(field in PUBLIC_PROCUREMENT_FIELDS for field in fields):
        families.add("procurement")
    return families


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


def _gap_seed_hints(target: Mapping[str, Any] | None) -> Iterable[SourceSeed]:
    if not isinstance(target, Mapping):
        return []
    preferred = [str(value) for value in (target.get("source_families") or []) if str(value)]
    fallback_family = preferred[0] if preferred else "official"
    output: list[SourceSeed] = []
    for seed in target.get("revalidation_seeds") or []:
        if not isinstance(seed, Mapping):
            continue
        url = str(seed.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            continue
        family = family_from_url(url, fallback=fallback_family)
        output.append(SourceSeed(
            url=url,
            family=family,
            official=bool(seed.get("official")),
            source_grade=str(seed.get("source_grade") or "B"),
            source_type="historical-public-revalidation-seed",
            source_name=str(seed.get("source_name") or seed.get("source") or "Pista pública a revalidar"),
        ))
    return output


def seeds_for(
    row: dict[str, Any],
    fields: Iterable[str],
    *,
    target: Mapping[str, Any] | None = None,
) -> list[SourceSeed]:
    section = str((target or {}).get("section") or "") if isinstance(target, Mapping) else ""
    families = relevant_families(fields, section=section)
    if isinstance(target, Mapping):
        families.update(str(value) for value in (target.get("source_families") or []) if str(value))
    found: dict[tuple[str, str], SourceSeed] = {}

    # First: exact historical/public URLs attached to a pending validation claim.
    for seed in _gap_seed_hints(target):
        found.setdefault((seed.url, seed.family), seed)

    # Second: current evidence already known for the entity; official domains fan out to the
    # route families that are most appropriate for the open fields.
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
            item.source_type != "historical-public-revalidation-seed",
            item.family not in families,
            not item.official,
            item.source_grade[:1] not in {"A", "B"},
            item.url,
        ),
    )
    return ordered
