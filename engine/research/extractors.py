"""Conservative, explainable extraction rules for public web documents."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from ..model import canonical
from .documents import Document


@dataclass(frozen=True)
class Candidate:
    values: tuple[str, ...]
    claim_type: str
    confidence: float
    snippet: str
    matched_terms: tuple[str, ...]


CAPABILITY_TERMS = {
    "SOC": ("security operations center", "security operation centre", "cybersoc", "soc as a service"),
    "NOC": ("network operations center", "network operation centre", "noc as a service"),
    "MSSP": ("mssp", "managed security service"),
    "Managed Services": ("managed services", "servicios gestionados", "serviços geridos"),
    "Cloud": ("cloud", "nube"),
    "Cybersecurity": ("cybersecurity", "ciberseguridad", "cibersegurança"),
    "Networking": ("networking", "redes", "conectividad", "connectivity"),
    "Data Center": ("data center", "datacenter"),
    "Observability": ("observability", "observabilidad", "observabilidade"),
    "Identity & Access": ("identity and access", "identity security", "identidad", "iam", "pam"),
    "Incident Response": ("incident response", "respuesta a incidentes", "resposta a incidentes", "dfir"),
    "Threat Intelligence": ("threat intelligence", "inteligencia de amenazas", "inteligência de ameaças"),
    "AI / Data": ("artificial intelligence", "inteligencia artificial", "inteligência artificial", "machine learning", "data platform"),
}

SERVICE_TERMS = {
    "Consultoría": ("consulting services", "consultoría", "consultoria"),
    "Servicios profesionales": ("professional services", "servicios profesionales", "serviços profissionais"),
    "Servicios gestionados": ("managed services", "servicios gestionados", "serviços geridos"),
    "Implementación / integración": ("implementation", "implementación", "implementação", "systems integration", "integração"),
    "Soporte": ("support services", "technical support", "soporte", "suporte"),
    "Formación": ("training", "academy", "formación", "formação"),
    "Financiación": ("financing", "leasing", "financiación", "financiamento"),
    "Marketplace / plataforma cloud": ("cloud marketplace", "marketplace", "cloud platform"),
    "Logística": ("logistics", "logística", "supply chain"),
}

JOB_PROFILE_TERMS = {
    "Solutions Architect": ("solutions architect", "solution architect", "arquitecto de soluciones", "arquiteto de soluções"),
    "Security Engineer / Analyst": ("security engineer", "security analyst", "analista de seguridad", "cybersecurity engineer"),
    "Cloud Engineer / Architect": ("cloud engineer", "cloud architect", "arquitecto cloud", "arquiteto cloud"),
    "Network Engineer": ("network engineer", "systems engineer networking", "ingeniero de redes", "engenheiro de redes"),
    "DevOps / Platform": ("devops", "platform engineer", "site reliability engineer"),
    "Presales": ("presales", "pre-sales", "preventa", "pré-venda"),
    "SOC / Detection & Response": ("soc analyst", "detection and response", "incident response analyst"),
    "Data / AI": ("data engineer", "data architect", "machine learning engineer", "ai engineer"),
}

VERTICAL_TERMS = {
    "Sector público": ("public sector", "administraciones públicas", "administrações públicas", "government"),
    "Sanidad": ("healthcare", "sanidad", "saúde", "hospital"),
    "Servicios financieros": ("financial services", "banca", "banking", "insurance", "seguros"),
    "Telecomunicaciones": ("telecommunications", "telecomunicaciones", "telecomunicações", "telco"),
    "Industria": ("manufacturing", "industria", "industry 4.0"),
    "Retail": ("retail", "gran consumo", "consumer goods"),
    "Energía": ("energy", "energía", "energia", "utilities"),
    "Educación": ("education", "educación", "educação", "university", "universidad"),
}


def competitors_in_text(text: str, entity: str, known_vendors: Iterable[str]) -> tuple[list[str], list[str]]:
    """Identify explicitly compared named vendors, never mere sector co-membership.

    A vendor must occur close to the researched entity with a direct comparative
    expression between the two names. Neither analyst rankings nor category
    membership alone establish competition. Discovery vocabulary is not evidence.
    """
    if not entity or not text:
        return [], []
    blob = canonical(text[:120_000])
    name = canonical(entity)
    owner_positions = list(re.finditer(r"(?<![a-z0-9])" + re.escape(name) + r"(?![a-z0-9])", blob))[:24]
    if not owner_positions:
        return [], []
    relation = re.compile(
        r"\b(?:competitor(?:s)?|competitive|compete(?:s|d)?|rival(?:s)?|"
        r"alternativ(?:e|es|a|as)|versus|vs|competidor(?:es)?|"
        r"compite(?:n)?|concorrent(?:e|es)?|comparativ[oa]|comparison|"
        r"compare(?:d|s)?|comparacion)\b"
    )
    found: list[str] = []
    for vendor in known_vendors:
        canonical_vendor = canonical(vendor)
        if len(canonical_vendor) < 3 or canonical_vendor == name or canonical_vendor in name:
            continue
        vendor_positions = list(re.finditer(
            r"(?<![a-z0-9])" + re.escape(canonical_vendor) + r"(?![a-z0-9])", blob
        ))[:24]
        accepted = False
        for left in owner_positions:
            for right in vendor_positions:
                distance = min(abs(left.start() - right.end()), abs(right.start() - left.end()))
                if distance > 340:
                    continue
                gap = blob[min(left.end(), right.end()):max(left.start(), right.start())]
                # Strictly require comparative language near the two parties.
                if relation.search(gap):
                    accepted = True
                    break
            if accepted:
                break
        if accepted:
            found.append(str(vendor))
    return list(dict.fromkeys(found))[:14], list(dict.fromkeys(found))[:14]


def _matches(text: str, dictionary: dict[str, Iterable[str]]) -> tuple[list[str], list[str]]:
    blob = f" {canonical(text)} "
    labels: list[str] = []
    terms_found: list[str] = []
    for label, terms in dictionary.items():
        matched = next((term for term in terms if f" {canonical(term)} " in blob or canonical(term) in blob), None)
        if matched:
            labels.append(label)
            terms_found.append(matched)
    return labels, terms_found


def vendors_in_text(text: str, vendor_names: Iterable[str]) -> tuple[list[str], list[str]]:
    blob = canonical(text)
    found: list[str] = []
    matched: list[str] = []
    for vendor in vendor_names:
        token = canonical(vendor)
        if len(token) < 3:
            continue
        if re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", blob):
            found.append(vendor)
            matched.append(vendor)
    return list(dict.fromkeys(found))[:100], matched[:100]



# HF5 strict revenue evidence
REVENUE_LABELS = (
    "total revenue", "consolidated revenue", "group revenue", "company revenue",
    "revenue", "net sales", "annual sales", "turnover",
    "facturación total", "facturacion total", "facturación", "facturacion",
    "importe neto de la cifra de negocios", "cifra de negocios",
    "ingresos totales", "ingresos anuales", "ingresos",
    "ventas netas", "ventas anuales", "ventas totales", "ventas",
    "faturação total", "faturacao total", "faturação", "faturacao",
    "receita total", "receita anual", "receita",
    "volume de negócios", "volume de negocios",
    "vendas líquidas", "vendas liquidas", "vendas anuais", "vendas totais",
)

_REVENUE_CUE_PATTERN = (
    r"\b(?:total\s+|annual\s+|consolidated\s+|group\s+|company\s+)?revenues?\b"
    r"|\bnet\s+sales\b|\bannual\s+sales\b|\bturnover\b"
    r"|\bimporte\s+neto\s+de\s+la\s+cifra\s+de\s+negocios\b"
    r"|\bcifra\s+de\s+negocios\b|\bfacturaci[oó]n(?:\s+total)?\b"
    r"|\bingresos(?:\s+(?:totales|anuales))?\b"
    r"|\bventas(?:\s+(?:netas|anuales|totales))?\b"
    r"|\bfatura[cç][aã]o(?:\s+total)?\b|\breceita(?:\s+(?:total|anual))?\b"
    r"|\bvolume\s+de\s+neg[oó]cios\b|\bvendas(?:\s+(?:l[ií]quidas|anuais|totais))?\b"
)
REVENUE_CUE_RE = re.compile(_REVENUE_CUE_PATTERN, re.I)

_REVENUE_NUMBER = r"(?:\d{1,3}(?:[.\s]\d{3})*(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"
_REVENUE_SCALE = (
    r"(?:mil\s+millones|mil\s+milh[oõ]es|millions|million|billions|billion|"
    r"millones|mill[oó]n|milh[oõ]es|milh[aã]o|bili[oõ]es|bili[aã]o|mn|bn|m|k)"
)
_REVENUE_CURRENCY = r"(?:euros?|dollars?|d[oó]lares?|libras?|US\$|USD|EUR|GBP|€|£|\$)"
REVENUE_MONEY_RE = re.compile(
    rf"(?:{_REVENUE_CURRENCY}\s*{_REVENUE_NUMBER}(?:\s*{_REVENUE_SCALE})?"
    rf"|{_REVENUE_NUMBER}(?:\s*{_REVENUE_SCALE})?\s*(?:de\s+)?{_REVENUE_CURRENCY})",
    re.I,
)
REVENUE_YEAR_RE = re.compile(r"\b(?:FY\s*)?20\d{2}\b", re.I)

_MANUFACTURER_PARTIAL_SCOPE_RE = re.compile(
    r"\b(?:channel|canal|partner|partners|spain|españa|portugal|iberia|emea|"
    r"europe|europa|segment|division|business\s+unit|unidad\s+de\s+negocio|"
    r"market|mercado|industry|industria)\b",
    re.I,
)
_MANUFACTURER_TOTAL_RE = re.compile(
    r"\b(?:total\s+revenue|consolidated\s+revenue|group\s+revenue|company\s+revenue|"
    r"net\s+sales|facturaci[oó]n\s+total|ingresos\s+totales|ventas\s+netas|"
    r"fatura[cç][aã]o\s+total|receita\s+total|vendas\s+l[ií]quidas)\b",
    re.I,
)


def _revenue_components(value: str) -> tuple[re.Match[str] | None, re.Match[str] | None, re.Match[str] | None]:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    cue = REVENUE_CUE_RE.search(text)
    money = REVENUE_MONEY_RE.search(text)
    year = REVENUE_YEAR_RE.search(text)
    return cue, money, year


def revenue_value_is_strict(value: str) -> bool:
    # Concept + amount/currency + period must belong to one compact observation.
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text or len(text) > 240:
        return False
    cue, money, year = _revenue_components(text)
    if not cue or not money or not year:
        return False
    distance = max(0, max(cue.start(), money.start()) - min(cue.end(), money.end()))
    if distance > 150:
        return False
    core_left = min(cue.start(), money.start())
    core_right = max(cue.end(), money.end())
    if year.end() < core_left - 100 or year.start() > core_right + 100:
        return False
    return True


def manufacturer_revenue_value_is_strict(value: str) -> bool:
    # Manufacturer revenue means company/group scale, not channel/region/segment revenue.
    if not revenue_value_is_strict(value):
        return False
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if _MANUFACTURER_PARTIAL_SCOPE_RE.search(text) and not _MANUFACTURER_TOTAL_RE.search(text):
        return False
    return True


def _compact_revenue_observation(
    text: str,
    cue: re.Match[str],
    money: re.Match[str],
    year: re.Match[str],
) -> str:
    left = min(cue.start(), money.start(), year.start())
    right = max(cue.end(), money.end(), year.end())
    start = max(0, left - 55)
    end = min(len(text), right + 55)

    for marker in (". ", "; ", " • ", " | ", "\n"):
        pos = text.rfind(marker, start, left)
        if pos >= 0:
            start = max(start, pos + len(marker))
    next_positions = [
        pos for marker in (". ", "; ", " • ", " | ", "\n")
        for pos in [text.find(marker, right, end)]
        if pos >= 0
    ]
    if next_positions:
        end = min(end, min(next_positions) + 1)

    value = text[start:end].strip(" ,;:|-")
    if len(value) > 220:
        start = max(0, left - 24)
        end = min(len(text), right + 24)
        value = text[start:end].strip(" ,;:|-")
    return value


def revenue_observations(text: str, *, global_only: bool = False) -> tuple[list[str], list[str]]:
    compact = re.sub(r"\s+", " ", text or "").strip()
    if not compact:
        return [], []

    values: list[str] = []
    terms: list[str] = []
    seen: set[str] = set()

    for cue in REVENUE_CUE_RE.finditer(compact):
        window_start = max(0, cue.start() - 120)
        window_end = min(len(compact), cue.end() + 190)
        local = compact[window_start:window_end]

        money_matches = list(REVENUE_MONEY_RE.finditer(local))
        year_matches = list(REVENUE_YEAR_RE.finditer(local))
        if not money_matches or not year_matches:
            continue

        cue_abs = cue.start()
        money_local = min(
            money_matches,
            key=lambda m: abs((window_start + m.start()) - cue_abs),
        )
        money_start = window_start + money_local.start()
        money_end = window_start + money_local.end()
        money = REVENUE_MONEY_RE.search(compact, money_start, money_end)
        if money is None:
            continue

        year_local = min(
            year_matches,
            key=lambda m: min(
                abs((window_start + m.start()) - cue.start()),
                abs((window_start + m.start()) - money.start()),
            ),
        )
        year_start = window_start + year_local.start()
        year_end = window_start + year_local.end()
        year = REVENUE_YEAR_RE.search(compact, year_start, year_end)
        if year is None:
            continue

        value = _compact_revenue_observation(compact, cue, money, year)
        validator = manufacturer_revenue_value_is_strict if global_only else revenue_value_is_strict
        if not validator(value):
            continue

        key = canonical(value)
        if key in seen:
            continue
        seen.add(key)
        values.append(value)
        terms.append(cue.group(0))
        if len(values) >= 3:
            break

    return values, terms


def evidence_snippet(text: str, terms: Iterable[str], *, radius: int = 180) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    lowered = canonical(compact)
    for term in terms:
        index = lowered.find(canonical(term))
        if index >= 0:
            start = max(0, index - radius)
            end = min(len(compact), index + len(str(term)) + radius)
            snippet = compact[start:end].strip()
            return ("…" if start else "") + snippet + ("…" if end < len(compact) else "")
    return compact[:360] + ("…" if len(compact) > 360 else "")



def _official_menu_brand_links(document: Document) -> list[str]:
    """Brands under an explicit first-party *Fabricantes/Vendors* navigation menu.

    Ajoomal, for example, publishes the catalogue as /bluecat/, /check-point/,
    etc. A bare vendor name on a news or solution page is not sufficient.
    Require multiple same-host links with labels matching their canonical slugs
    and labels in the contiguous vendor-menu region.
    """
    from urllib.parse import urlsplit

    text = document.text or ""
    menu_start = re.search(
        r"\b(?:fabricantes|nuestras marcas|nossos fabricantes|our vendors|"
        r"our brands|brands we distribute)\b", canonical(text[:7000]),
    )
    if not menu_start:
        return []
    # canonical() may change length due to accents. Only use it to find the
    # anchor; derive the navigation region from original text consistently.
    raw_match = re.search(
        r"(?i)\b(?:fabricantes|nuestras marcas|nossos fabricantes|"
        r"our vendors|our brands|brands we distribute)\b", text[:7000]
    )
    if not raw_match:
        return []
    region = text[raw_match.end(): raw_match.end()+1600]
    stop = re.search(r"(?i)\b(?:soluciones\s*(?:y|&)\s*servicios|"
                     r"solucoes\s*e\s*servicos|newsroom|noticias|"
                     r"servicios profesionales|eventos|careers)\b", region)
    if stop:
        region = region[:stop.start()]
    normalized_region = " " + canonical(region) + " "
    host = (urlsplit(document.url).hostname or "").lower().removeprefix("www.")
    excluded = {
        "fabricantes", "marcas", "brand", "brands", "vendors", "inicio",
        "home", "contacto", "contact", "newsletter", "soluciones", "servicios",
        "partners", "blog", "news", "noticias", "eventos", "securidad",
        "ciberseguridad", "cybersecurity", "cloud", "networking", "wifi",
        "backup", "hardware", "software", "casos de exito", "soporte",
    }
    labels: dict[str, str] = {}
    for link in document.links:
        url = urlsplit(link.url)
        if (url.scheme not in {"http", "https"} or
            (url.hostname or "").lower().removeprefix("www.") != host):
            continue
        label = " ".join(str(link.label or "").split()).strip()
        key = canonical(label)
        if (not 2 <= len(label) <= 48 or len(label.split()) > 5 or
            key in excluded or not re.search(r"[a-zA-Z]", label)):
            continue
        # Restrict to named menu entities, never unrelated site-wide links.
        if " "+key+" " not in normalized_region:
            continue
        slug = url.path.strip("/").split("/")[-1]
        slugkey = canonical(slug.replace("-", " ").replace("_", " "))
        if not slugkey or slugkey.replace(" ","") != key.replace(" ",""):
            continue
        labels.setdefault(key, label)
    return list(labels.values())[:150] if len(labels) >= 4 else []


def distributor_linecard_vendors(document: Document, vendor_names: Iterable[str]) -> tuple[list[str], list[str]]:
    """Extract named brands from explicit first-party reseller/distributor catalogues.

    The caller must require an *official entity-owned source*. These are
    DISCOVERY observations: the canonical relation provenance gate still verifies
    subject, vendor and field. Generic site footers and news co-mentions do not
    count as a linecard.
    """
    from urllib.parse import urlsplit

    path = canonical(urlsplit(document.url).path)
    title = canonical(document.title)
    labels = (
        "fabricantes", "marcas", "vendors", "brands", "line card",
        "linecard", "portfolio", "catalogo de marcas", "catalogo fabricantes",
        "nuestras marcas", "nossos fabricantes", "nossos parceiros",
    )
    owned_catalogue = any(label in path or label in title for label in labels)
    text = document.text or ""
    compact = canonical(text[:4500])
    heading = re.search(
        r"\b(nuestros fabricantes|nuestras marcas|marcas que distribuimos|"
        r"fabricantes que distribuimos|nossos fabricantes|as nossas marcas|"
        r"our vendors|our brands|vendor linecard|line card de fabricantes)\b",
        compact,
    )
    menu_brands = _official_menu_brand_links(document)
    # Some wholesalers list named brands in an explicit first-party distribution
    # paragraph on the product page rather than in a separate logo directory.
    # Extract only the text within that direct catalogue claim.
    statement = re.search(
        r"(?is)\b(?:mejores fabricantes del sector|fabricantes del sector):\s*"
        r"(.{12,1600}?)\s*,?\s*entre otros\b",
        text,
    )
    explicit_list = bool(
        statement and "distribuidores oficiales" in canonical(text[:12000])
    )
    if not owned_catalogue and not heading and not menu_brands and not explicit_list:
        return [], []
    body = (text[:70000] if owned_catalogue else
            statement.group(0) if explicit_list else text[:7000])
    known, terms = vendors_in_text(body, vendor_names)
    known_keys = {canonical(value) for value in known}
    for brand in menu_brands:
        key = canonical(brand)
        if key not in known_keys:
            known.append(brand)
            terms.append(brand)
            known_keys.add(key)
    # Official logo catalogues often contain more brands than a static
    # vocabulary. parse_document adds their img alt labels only on explicit
    # manufacturer/brand paths. Keep strong brand-like labels, not page UI.
    if (owned_catalogue or heading) and " Marcas y fabricantes: " in body:
        raw_labels = body.rsplit(" Marcas y fabricantes: ", 1)[1].split(" / ")
        excluded = {
            "home", "inicio", "busqueda", "buscar", "search", "cart",
            "email", "login", "linkedin", "twitter", "facebook", "youtube",
            "loading", "icon", "logo", "banner", "partner", "partners",
            "networking", "cloud", "cybersecurity", "ciberseguridad",
            "tecnologia", "technology", "productos", "productos y servicios",
            "ver mas", "leer mas", "contacto", "contact", "menu",
            "certified", "distribuidor", "fabricantes", "marcas",
        }
        for label in raw_labels[:1000]:
            brand = re.sub(r"(?i)^logo[\s_-]*(?:(?:de|da|of)[\s_-]+)?", "", label.strip())
            brand = brand.replace("_", " ")  # preserve legitimate brand hyphens (D-Link, TP-Link)
            brand = re.sub(r"(?i)\s+(?:logo|brand logo)$", "", brand).strip()
            key = canonical(brand)
            if (not 2 <= len(brand) <= 48 or len(brand.split()) > 5 or
                not re.search(r"[a-zA-Z]", brand) or key in excluded or
                any(word in key.split() for word in ("image", "imagen", "banner", "icono")) or
                re.fullmatch(r"\d+", brand)):
                continue
            if key not in {canonical(value) for value in known}:
                known.append(brand)
                terms.append(label.strip())
            if len(known) >= 1000:
                break

    # Spanish Ingram Micro vendor directory: a catalogue link carries
    # "Fabricante (número de productos)", never a contractual volume.
    url_path = urlsplit(document.url).path.casefold()
    if "/site/vendor/index" in url_path and "lista de fabricantes" in compact:
        host = (urlsplit(document.url).hostname or "").casefold()
        for link in document.links:
            match = re.fullmatch(r"\s*(.{2,48}?)\s*\((\d{1,7})\)\s*", link.label or "")
            if not match:
                continue
            linked = urlsplit(link.url)
            if ((linked.hostname or "").casefold() != host
                    or "/site/vendor/" not in linked.path.casefold()):
                continue
            brand = match.group(1).strip()
            key = canonical(brand)
            if key in {"fabricantes", "productos", "marcas"} or not re.search(r"[a-zA-Z]", brand):
                continue
            if key not in known_keys:
                known.append(brand)
                terms.append(link.label)
                known_keys.add(key)
            if len(known) >= 1000:
                break
    if explicit_list and statement:
        # Each comma-separated name is part of the stated manufacturer list;
        # never mine products, footers or generic text on the same page.
        listing = statement.group(1)
        entries = re.split(r"\s*,\s*|\s+y\s+(?=[A-ZÀ-Ú])", listing)
        for raw in entries[:200]:
            brand = " ".join(raw.split()).strip(".,;: ")
            key = canonical(brand)
            if (not 2 <= len(brand) <= 48 or len(brand.split()) > 5 or
                    not re.search(r"[a-zA-Z]", brand) or
                    key in {"entre otros", "fabricantes", "productos"}):
                continue
            if key not in known_keys:
                known.append(brand)
                terms.append(brand)
                known_keys.add(key)
    return known[:1000], terms[:1000]

def extract_candidates(
    section: str,
    family: str,
    document: Document,
    vendor_names: Iterable[str],
    *,
    official: bool,
    researched_entity: str = '',
) -> dict[str, Candidate]:
    text = document.text
    candidates: dict[str, Candidate] = {}
    base_fact = 0.84 if official else 0.69

    capabilities, cap_terms = _matches(text, CAPABILITY_TERMS)
    services, service_terms = _matches(text, SERVICE_TERMS)
    jobs, job_terms = _matches(text, JOB_PROFILE_TERMS)
    verticals, vertical_terms = _matches(text, VERTICAL_TERMS)
    vendors, vendor_terms = vendors_in_text(text, vendor_names)
    revenues, revenue_terms = revenue_observations(text, global_only=(section == "manufacturers"))
    competitors, competitor_terms = competitors_in_text(text, researched_entity, vendor_names) if section == 'manufacturers' else ([], [])

    def add(field: str, values: list[str], terms: list[str], claim: str = "fact", confidence: float | None = None) -> None:
        if not values:
            return
        candidates[field] = Candidate(
            tuple(values),
            claim,
            confidence if confidence is not None else (0.57 if claim == "signal" else base_fact),
            evidence_snippet(text, terms),
            tuple(terms),
        )

    if section in {"integrators", "distributors"}:
        if section == "distributors" and family in {"financial", "official"}:
            add("revenue", revenues, revenue_terms, confidence=0.90 if official else 0.74)
        if family == "partners":
            if official:
                listed, listed_terms = distributor_linecard_vendors(document, vendor_names)
                if listed:
                    add("vendor_relations", listed, listed_terms, confidence=0.90)
                else:
                    # Partner detail pages may evidence one particular relationship
                    # without publishing an entire catalogue.
                    add("vendor_relations", vendors, vendor_terms)
            else:
                add("vendor_relations", vendors, vendor_terms)
        elif official and family in {"official", "technology", "services"}:
            # First-party catalogues may be classified as generic or technical.
            listed, listed_terms = distributor_linecard_vendors(document, vendor_names)
            add("vendor_relations", listed, listed_terms, confidence=0.90)
        if family in {"services", "official"}:
            add("capabilities", capabilities, cap_terms)
            add("services", services, service_terms)
            add("technology_domains", capabilities, cap_terms, "interpretation", 0.68 if official else 0.60)
            if "Managed Services" in capabilities or "Servicios gestionados" in services:
                add("managed_services", ["Sí"], ["managed services"], confidence=base_fact)
            if section == "integrators" and "MSSP" in capabilities:
                add("msp_mssp", ["Sí"], ["mssp", "managed security service"], confidence=base_fact)
            if section == "distributors":
                add("differential_capabilities", services, service_terms)
                capability_columns = {
                    "training": ("Formación",),
                    "financing": ("Financiación",),
                    "logistics": ("Logística",),
                    "marketplace": ("Marketplace / plataforma cloud",),
                    "managed_services": ("Servicios gestionados",),
                }
                for field_id, labels in capability_columns.items():
                    present = [label for label in labels if label in services]
                    if present:
                        add(field_id, ["Sí"], present, confidence=base_fact)
        if family == "cases":
            add("verticals", verticals, vertical_terms)
            title = document.title.strip()
            if title and len(title) >= 12 and canonical(title) not in {"customers", "clientes", "case studies", "casos de exito"}:
                add("public_cases", [title], [title], confidence=0.72 if official else 0.62)
        if family == "careers":
            add("job_profiles", jobs, job_terms, "signal", 0.58)
            add("job_vendors", vendors, vendor_terms, "signal", 0.56)
    elif section in {"clients_private", "clients_public"}:
        if family in {"careers", "technology", "services", "official", "procurement", "news"}:
            add("technology_signals", capabilities, cap_terms, "signal", 0.57)
            add("technology_domains", capabilities, cap_terms, "interpretation", 0.57)
            add("identified_vendors", vendors, vendor_terms, "signal", 0.57)
            # r6: westcon_fit is internal/derived; public pages support\n            # inputs, not the fit conclusion itself.\n        if section == "clients_private" and family == "careers":
            add("hiring_signals", jobs, job_terms, "signal", 0.57)
    elif section == "manufacturers":
        if family in {"financial", "official"}:
            add("revenue", revenues, revenue_terms, confidence=0.92 if official else 0.76)
        if family in {"services", "official", "technology"}:
            add("capabilities", capabilities, cap_terms)
        if family in {"analyst", "news", "technology", "official", "cases"}:
            add("competitors", competitors, competitor_terms, confidence=0.83 if official else 0.76)
    elif section == "trends":
        if family in {"analyst", "news", "official", "technology"}:
            add("market_players", vendors, vendor_terms, confidence=0.68 if not official else 0.80)
    elif section == "architectures" and family in {"analyst", "technology", "official"}:
        add("vendors", vendors, vendor_terms, claim="interpretation", confidence=0.68)

    # Publish only item-specific articles that clearly name the researched entity.
    # All three sections share the same accredited news feed; landing pages do not
    # count as publications. Retrieval dates are never asserted as publish dates.
    if section in {"manufacturers", "distributors", "integrators", "clients_private", "clients_public", "trends", "architectures"} and family in {
        "news", "official", "partners", "technology", "cases", "services", "analyst",
    }:
        from urllib.parse import urlsplit
        path = urlsplit(document.url).path.casefold()
        title = (document.title or "").strip()
        is_article = bool(re.search(
            r"/(?:news|noticias?|actualidad|novidades|press|press-releases|"
            r"comunicados|announcements?|blog|insights|articles?|media|"
            r"newsroom|releases|research|reports|estudios|publicaciones|"
            r"artigos|sala-de-prensa|case-studies)/[^/?#]{7,}", path
        ) or re.search(r"/20\d\d/(?:0?[1-9]|1[012])/[a-z0-9-]{8,}",path))
        has_owner = (
            bool(researched_entity)
            and canonical(researched_entity) in canonical(title + " " + (text[:700] if text else ""))
        )
        if section in {"trends", "architectures"} and not has_owner:
            # Topic labels are editorial headings, not legal entity names.
            # Require a distinctive technical term in the specific article
            # title, not a generic category word occurring in a sidebar.
            stopped = {"technology", "tecnologia", "seguridad", "security",
                       "architecture", "arquitectura", "network", "networking",
                       "data", "cloud", "digital", "inteligencia", "artificial",
                       "infraestructura", "convergencia", "solutions"}
            anchors = [x for x in canonical(researched_entity).split()
                       if len(x)>=3 and x not in stopped]
            title_words = set(canonical(title).split())
            has_owner = any(word in title_words for word in anchors)
        if is_article and has_owner and 22 <= len(title) <= 180:
            add("recent_signals", [title], [title], claim="signal",
                confidence=0.82 if official else 0.70)

    return candidates
