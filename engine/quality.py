from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .model import canonical

VERSION = "3.20.0"
SECTIONS = ("manufacturers", "distributors", "integrators", "clients_public", "clients_private", "trends", "architectures")


def audit(data: dict[str, Any], graph: dict[str, Any], gaps: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    manufacturers = {canonical(r.get("name")) for r in data.get("manufacturers") or []}
    distributors = {canonical(r.get("name")) for r in data.get("distributors") or []}
    if canonical("Comstor") in distributors:
        errors.append("Comstor no puede clasificarse como mayorista competidor.")
    if canonical("Forescout") in manufacturers:
        errors.append("Forescout no debe figurar como fabricante Westcon.")
    overlap = manufacturers & distributors
    if overlap:
        errors.append("Fabricantes clasificados también como mayoristas: " + ", ".join(sorted(overlap)))

    # Canonical entity duplicates by section. Public procurement rows are opportunities, so notice_id disambiguates them.
    for section in SECTIONS:
        seen = Counter()
        for row in data.get(section) or []:
            if section == "clients_public":
                notice = str((((row.get("fields") or {}).get("notice_id") or {}).get("value")) or "")
                key = (canonical(row.get("name")), canonical(notice))
            else:
                key = canonical(row.get("name"))
            seen[key] += 1
        duplicates = [str(k) for k, n in seen.items() if n > 1]
        if duplicates:
            errors.append(f"Duplicados en {section}: {duplicates[:8]}")

    # Repeated vendors inside line cards and blank values masquerading as data.
    for section in ("distributors", "integrators"):
        for row in data.get(section) or []:
            field = ((row.get("fields") or {}).get("vendor_relations") or {})
            value = field.get("value")
            if isinstance(value, list):
                keys = [canonical(str(v).split(" · ", 1)[0]) for v in value if str(v).strip()]
                if len(keys) != len(set(keys)):
                    errors.append(f"Fabricante repetido en {section}/{row.get('name')}")

    # Graph invariants.
    relation_keys = []
    for rel in graph.get("relationships") or []:
        relation_keys.append((rel.get("entity_a_id"), rel.get("relation"), rel.get("entity_b_id")))
        evidence = rel.get("evidence") or []
        if not evidence:
            errors.append(f"Relación sin evidencia: {rel.get('id')}")
            continue
        for ev in evidence:
            url = str(ev.get("url") or "")
            if not url.startswith(("http://", "https://")):
                errors.append(f"Relación con evidencia sin URL válida: {rel.get('id')}")
    if len(relation_keys) != len(set(relation_keys)):
        errors.append("El grafo contiene aristas canónicas duplicadas.")

    # Public facts must have some provenance; open gaps remain explicitly active.
    for section in SECTIONS:
        schema = {c.get("id") for c in (data.get("schemas") or {}).get(section, []) if c.get("id")}
        for row in data.get(section) or []:
            for field_id, field in (row.get("fields") or {}).items():
                if field_id not in schema:
                    continue
                value = field.get("value")
                if value in (None, "", [], {}):
                    continue
                if isinstance(value, str) and value.strip() in {"-", "—", "--"}:
                    errors.append(f"Guion usado como pendiente: {section}/{row.get('name')}/{field_id}")
                ev = field.get("evidence") or []
                if not ev and field.get("claim_type") == "fact":
                    warnings.append(f"Dato factual sin evidencia directa: {section}/{row.get('name')}/{field_id}")

    if any(g.get("research_state") != "Por investigar" for g in gaps.get("gaps") or []):
        errors.append("Un gap abierto tiene un estado distinto de 'Por investigar'.")

    domains = set()
    for section in SECTIONS:
        for row in data.get(section) or []:
            for field in (row.get("fields") or {}).values():
                for ev in field.get("evidence") or []:
                    host = urlparse(str(ev.get("url") or "")).netloc.lower().removeprefix("www.")
                    if host:
                        domains.add(host)

    score = max(0, 100 - len(errors) * 8 - min(20, len(warnings)))
    return {
        "version": VERSION,
        "score": score,
        "errors": errors,
        "warnings": warnings,
        "checks": {
            "entities": sum(len(data.get(s) or []) for s in SECTIONS),
            "relationships": len(graph.get("relationships") or []),
            "gaps": int(gaps.get("total_gaps") or 0),
            "domains": len(domains),
        },
    }
