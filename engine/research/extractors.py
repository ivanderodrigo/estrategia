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


def extract_candidates(
    section: str,
    family: str,
    document: Document,
    vendor_names: Iterable[str],
    *,
    official: bool,
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
            add("vendor_relations", vendors, vendor_terms)
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
    elif section == "trends":
        if family in {"analyst", "news", "official", "technology"}:
            add("market_players", vendors, vendor_terms, confidence=0.68 if not official else 0.80)
    elif section == "architectures" and family in {"analyst", "technology", "official"}:
        add("vendors", vendors, vendor_terms, claim="interpretation", confidence=0.68)

    return candidates
