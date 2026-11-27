"""Recover literal technology demand from independently verified TED titles.

This is *not* web search or a prediction of a buyer's installed technology.
The only eligible input is an original, buyer-bound TED Search API procedure
title already accredited under ``evidenced_needs``. Every new claim retains
the exact notice URL, owner, field, item and matching text. Vague IT titles
deliberately remain unresolved.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from engine.enrichment import merge_field
from engine.knowledge_provenance import typed_evidence_sufficient
from engine.model import canonical


@dataclass(frozen=True)
class TitleRule:
    signal: str
    domain: str
    pattern: str


# Terms have to be explicit in the title. Do not use generic "red" (redes
# sociales), "seguridad" (seguridad física) or "IA" (ordinary syllables).
# Patterns run on unicode-normalised canonical text and require word borders.
TITLE_RULES = (
    TitleRule("SASE", "Cybersecurity", r"\bsase\b"),
    TitleRule("SSE", "Cybersecurity", r"\bsse\b"),
    TitleRule("Zero Trust", "Cybersecurity", r"\bzero trust\b"),
    TitleRule("Ciberseguridad", "Cybersecurity", r"\b(?:ciberseguridad|ciberseguranca|cybersecurity)\b"),
    TitleRule("Firewall", "Cybersecurity", r"\bfirewalls?\b"),
    TitleRule("SOC", "Cybersecurity", r"\bsoc\b"),
    TitleRule("Seguridad perimetral", "Cybersecurity", r"\bseguridad perimetral\b"),
    TitleRule("Observabilidad", "Observability", r"\b(?:observabilidad|observabilidade|observability)\b"),
    TitleRule("Inteligencia artificial", "AI / Data", r"\b(?:inteligencia artificial|inteligencia artificial|intel ligencia artificial|artificial intelligence)\b"),
    TitleRule("IA generativa", "AI / Data", r"\b(?:generative ai|inteligencia artificial generativa|llm|large language models?)\b"),
    TitleRule("Analítica de datos", "AI / Data", r"\b(?:data analytics|data & analytics|business intelligence|analitica de datos)\b"),
    TitleRule("SD-WAN", "Networking", r"\bsd wan\b"),
    TitleRule("Wi-Fi", "Networking", r"\b(?:wi fi|wlan)\b"),
    TitleRule("Redes de comunicaciones", "Networking", r"\b(?:infraestructura de (?:red|rede|xarxa)|infraestruturas? de rede|red de area local|redes de comunicaciones|equipos de comunicaciones|equipamentos? de rede|networking|switches|switching|routing)\b"),
    TitleRule("Cloud", "Cloud", r"\b(?:cloud|nube|nuvem|multicloud|hiperescalar(?:es)?|hyperscalers?)\b"),
    TitleRule("SaaS", "Cloud", r"\b(?:saas|software como servicio|software as a service)\b"),
    TitleRule("Microsoft 365", "Cloud", r"\b(?:microsoft|ms)\s*365\b"),
    TitleRule("Microsoft Azure", "Cloud", r"\b(?:microsoft|ms)\s*azure\b"),
    TitleRule("Oracle OCI", "Cloud", r"\boracle\s+oci\b"),
    TitleRule("AWS", "Cloud", r"\b(?:amazon web services|aws)\b"),
    TitleRule("Servidores", "Data Center", r"\b(?:servidores|servidor(?:es)?|servers?)\b"),
    TitleRule("Virtualización", "Data Center", r"\b(?:virtualizacion|virtualizacao|virtualization)\b"),
    TitleRule("Almacenamiento", "Data Center", r"\b(?:almacenamiento|armazenamento|storage)\b"),
    TitleRule("Backup", "Data Center", r"\b(?:backup|backups|copias? de seguridad|copia de seguranca)\b"),
    TitleRule("Centro de datos", "Data Center", r"\b(?:data centers?|centro de (?:proceso de )?datos|centro de dados|cpds?)\b"),
    TitleRule("IAM", "Identity & Access", r"\b(?:iam|pam|mfa|sso|gestion de identidades|gestao de identidades|identity management)\b"),
    TitleRule("RPA", "Automation", r"\b(?:rpa|robotic process automation)\b"),
    TitleRule("Microsoft Teams", "UC / CX", r"\bmicrosoft teams\b"),
    TitleRule("Contact center", "UC / CX", r"\b(?:contact center|contact centre|ccaas)\b"),
)

VENDOR_RULES: tuple[tuple[str, str], ...] = (
    ("Microsoft", r"\bmicrosoft\b"), ("Oracle", r"\boracle\b"),
    ("VMware", r"\bvmware\b"), ("Citrix", r"\bcitrix\b"),
    ("NVIDIA", r"\bnvidia\b"), ("Cisco", r"\bcisco\b"),
    ("Fortinet", r"\bfortinet\b"), ("Palo Alto Networks", r"\bpalo alto networks\b"),
    ("CrowdStrike", r"\bcrowdstrike\b"), ("Zscaler", r"\bzscaler\b"),
    ("SAP", r"\bsap\b"), ("Adobe", r"\badobe\b"),
    ("Autodesk", r"\bautodesk\b"), ("IBM", r"\bibm\b"),
    ("Liferay", r"\bliferay\b"), ("ServiceNow", r"\bservicenow\b"),
    ("Check Point", r"\bcheck point\b"), ("HPE", r"\bhpe\b"),
    ("Dell", r"\bdell\b"), ("Lenovo", r"\blenovo\b"),
    ("Salesforce", r"\bsalesforce\b"), ("Okta", r"\bokta\b"),
    ("F5", r"\bf5\b"), ("Juniper", r"\bjuniper\b"),
    ("Ruckus", r"\bruckus\b"), ("Dynatrace", r"\bdynatrace\b"),
    ("Splunk", r"\bsplunk\b"), ("Huawei", r"\bhuawei\b"),
    ("Sophos", r"\bsophos\b"), ("NetApp", r"\bnetapp\b"),
    ("Pure Storage", r"\bpure storage\b"),
)

_PUBLICATION = re.compile(r"^[0-9]{1,8}-20[0-9]{2}$")
_TED_URL = re.compile(r"^https://ted\.europa\.eu/en/notice/-/detail/([0-9]{1,8}-20[0-9]{2})$")


def literal_claims(title: str) -> list[tuple[str, str, str, str]]:
    """Return (field, literal-derived value, exact matched words, rule)."""
    normalized = canonical(title)
    output: list[tuple[str, str, str, str]] = []
    domains: dict[str, str] = {}
    for rule in TITLE_RULES:
        found = re.search(rule.pattern, normalized)
        if not found:
            continue
        output.append(("technology_signals", rule.signal, found.group(), rule.pattern))
        domains.setdefault(rule.domain, found.group())
    for domain, match in domains.items():
        output.append(("technology_domains", domain, match, "title-domain-taxonomy-v1"))
    for vendor, pattern in VENDOR_RULES:
        found = re.search(pattern, normalized)
        if found:
            output.append(("identified_vendors", vendor, found.group(), pattern))
    return output


def _eligible_title_evidence(row: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Only exact buyer-bound API titles, never arbitrary search snippets."""
    owner = str(row.get("name") or "")
    fields = row.get("fields") or {}
    notices = (fields.get("notice_id") or {}).get("value") or []
    notices = notices if isinstance(notices, list) else [notices]
    valid_numbers = {str(number) for number in notices if _PUBLICATION.fullmatch(str(number))}
    result = []
    for item in (fields.get("evidenced_needs") or {}).get("items") or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("value") or "").strip()
        if not title:
            continue
        for ev in item.get("evidence") or []:
            if not isinstance(ev, dict):
                continue
            match = _TED_URL.fullmatch(str(ev.get("url") or ""))
            if not match or match.group(1) not in valid_numbers:
                continue
            if not (
                ev.get("official") is True
                and ev.get("source_type") == "official-procurement-api"
                and ev.get("method") == "ted-exact-procedure"
                and ev.get("source_binding") == "claim-specific"
                and ev.get("atomic") is True
                and ev.get("field") == "evidenced_needs"
                and canonical(ev.get("researched_entity")) == canonical(owner)
                and ev.get("item_value") == title
                and typed_evidence_sufficient(ev)
            ):
                continue
            result.append((title, ev))
    return result


def recover_verified_title_signals(row: dict[str, Any], *, checked_date: str) -> Counter[str]:
    """Enrich buyer fields only from existing official procedure-title evidence.

    Return new atomic claim counts by field. Safe to run repeatedly.
    """
    fields = row.setdefault("fields", {})
    accepted: Counter[str] = Counter()
    for title, source in _eligible_title_evidence(row):
        for field_id, value, matched, rule in literal_claims(title):
            field = fields.get(field_id) or {}
            old_items = [item for item in field.get("items") or [] if isinstance(item, dict)]
            if any(canonical(item.get("value")) == canonical(value)
                   and any(ev.get("method") == "ted-literal-title-v1"
                           and ev.get("url") == source["url"]
                           and ev.get("field") == field_id
                           and ev.get("item_value") == value
                           for ev in item.get("evidence") or [] if isinstance(ev, dict))
                   for item in old_items):
                continue
            evidence = dict(source)
            evidence.update({
                "date": source["date"], "retrieved_at": checked_date,
                "title": source["title"],
                "description": (
                    f"{row['name']} · TED {source['url'].rsplit('/', 1)[-1]} · "
                    f"título literal: {title} · término: {matched}. "
                    "Tecnología o fabricante mencionado en licitación; "
                    "no demuestra uso, compra ni adjudicación."
                ),
                "method": "ted-literal-title-v1",
                "extraction_rule": rule,
                "source_binding": "claim-specific",
                "researched_entity": row["name"],
                "field": field_id,
                "item_value": value,
                "matched_terms": [matched],
                "atomic": True,
                "accrediting": True,
            })
            interpreted = field_id == "technology_domains"
            is_signal = field_id == "technology_signals"
            spec = {
                "value": [value],
                "items": [{"value": value, "evidence": [evidence],
                           "confidence": 0.68 if interpreted else 0.59 if is_signal else 0.92,
                           "claim_type": "interpretation" if interpreted else "signal" if is_signal else "fact",
                           "assertion_status": "DERIVADO" if interpreted else "SEÑAL" if is_signal else "CONFIRMADO"}],
                "confidence": 0.68 if interpreted else 0.59 if is_signal else 0.92,
                "claim_type": "interpretation" if interpreted else "signal" if is_signal else "fact",
                "assertion_status": "DERIVADO" if interpreted else "SEÑAL" if is_signal else "CONFIRMADO",
                "qualifier": (
                    "Clasificación temática reproducible del título oficial TED; no equivale a despliegue."
                    if interpreted else
                    "Mención explícita en una contratación oficial; no implica que esté implantado."
                ),
            }
            fields[field_id] = merge_field(field, spec)
            accepted[field_id] += 1
    return accepted


def derive_verified_westcon_areas(row: dict[str, Any], *, checked_date: str) -> Counter[str]:
    """Certify ONLY the functional area implied by an exact TED title term.

    This is a reproducible internal classification, not evidence of Westcon
    engagement or an open commercial opportunity. No manufacturer fit is
    inferred. The source title, literal match, and exact classification rule
    travel together with every derived area.
    """
    fields = row.setdefault("fields", {})
    accepted: Counter[str] = Counter()
    for title, source in _eligible_title_evidence(row):
        for field_id, area, matched, rule in literal_claims(title):
            if field_id != "technology_domains":
                continue
            field = fields.get("westcon_area") or {}
            previous = [item for item in field.get("items") or [] if isinstance(item, dict)]
            if any(canonical(item.get("value")) == canonical(area)
                   and any(ev.get("method") == "ted-title-area-derivation-v1"
                           and ev.get("url") == source["url"]
                           and ev.get("field") == "westcon_area"
                           and ev.get("item_value") == area
                           for ev in item.get("evidence") or [] if isinstance(ev, dict))
                   for item in previous):
                continue
            proof = dict(source)
            proof.update({
                "retrieved_at": checked_date,
                "description": (
                    f"{row['name']} · {source['url'].rsplit('/', 1)[-1]} · "
                    f"título oficial «{title}» · término exacto «{matched}» "
                    f"clasificado como área funcional Westcon «{area}». "
                    "No prueba implantación ni oportunidad adjudicable."
                ),
                "method": "ted-title-area-derivation-v1",
                "derivation_rule": "official-TED-title ∩ TITLE_RULES.domain",
                "derivation_rule_id": rule,
                "derived_from_field": "evidenced_needs",
                "derived_from_value": title,
                "source_binding": "claim-specific",
                "researched_entity": row["name"],
                "field": "westcon_area",
                "item_value": area,
                "matched_terms": [matched],
                "atomic": True,
                "accrediting": True,
            })
            fields["westcon_area"] = merge_field(field, {
                "value": [area],
                "items": [{"value": area, "evidence": [proof],
                           "confidence": 0.68, "claim_type": "interpretation",
                           "assertion_status": "DERIVADO"}],
                "confidence": 0.68,
                "claim_type": "interpretation",
                "assertion_status": "DERIVADO",
                "qualifier": ("Clasificación funcional reproducible de una necesidad publicada "
                              "en TED, sin afirmar uso ni relación comercial con Westcon."),
            })
            accepted["westcon_area"] += 1
    return accepted
