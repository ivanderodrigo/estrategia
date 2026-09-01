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
        if family == "partners":
            add("vendor_relations", vendors, vendor_terms)
        if family in {"services", "official"}:
            add("capabilities", capabilities, cap_terms)
            add("services", services, service_terms)
            if section == "distributors":
                add("differential_capabilities", services, service_terms)
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
            add("westcon_fit", vendors, vendor_terms, "interpretation", 0.70 if official else 0.62)
        if section == "clients_private" and family == "careers":
            add("hiring_signals", jobs, job_terms, "signal", 0.57)
    elif section == "manufacturers" and family in {"services", "official", "technology"}:
        add("capabilities", capabilities, cap_terms)
    elif section == "trends":
        if family in {"analyst", "news", "official", "technology"}:
            add("market_players", vendors, vendor_terms, confidence=0.68 if not official else 0.80)
    elif section == "architectures" and family in {"analyst", "technology", "official"}:
        add("vendors", vendors, vendor_terms, claim="interpretation", confidence=0.68)

    return candidates
