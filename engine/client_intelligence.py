"""Additive Westcon-area and portfolio-fit intelligence for public/private clients."""
from __future__ import annotations

import re
from collections import defaultdict
from copy import deepcopy
from typing import Any, Iterable, Mapping

from .enrichment import itemized_field, merge_field
from .knowledge_provenance import dedupe_evidence, provenance_kind, typed_evidence_sufficient
from .model import canonical

AREA_TERMS: dict[str, tuple[str, ...]] = {
    "Networking": (
        "network", "networking", "red", "redes", "connectivity", "conectividad", "wifi", "wi fi",
        "wireless", "switching", "routing", "router", "campus", "sd wan", "sd-wan", "private 5g",
        "private lte", "ddi", "dns", "ipam", "mpls", "optical", "wlan",
    ),
    "Cybersecurity": (
        "cybersecurity", "ciberseguridad", "ciberseguranca", "security", "seguridad", "seguranca",
        "firewall", "sase", "sse", "zero trust", "xdr", "edr", "mdr", "soc", "threat", "amenaza",
        "incident response", "api security", "application security", "devsecops", "endpoint security",
        "cloud security", "ot security", "industrial security", "data protection", "email security",
        "waap", "waf", "ddos", "ctem", "ndr", "dlp", "ransomware",
    ),
    "Cloud": (
        "cloud", "nube", "aws", "azure", "multi cloud", "multicloud", "hybrid cloud", "cloud platform",
        "cloud infrastructure", "cloud native", "marketplace", "landing zone", "containers", "kubernetes",
    ),
    "Data Center": (
        "data center", "datacenter", "centro de datos", "centro de dados", "compute", "storage",
        "virtualization", "hci", "infrastructure", "infraestructura", "evpn", "vxlan", "dci", "hpc",
        "high availability", "alta disponibilidad", "edge",
    ),
    "Observability": (
        "observability", "observabilidad", "observabilidade", "monitoring", "telemetry", "telemetria", "apm",
        "application performance", "sre", "network visibility", "visibility", "monitorizacion",
    ),
    "Identity & Access": (
        "identity", "identidad", "identidade", "iam", "pam", "identity security", "access management",
        "gestion de acceso", "mfa", "sso", "ciam", "secrets", "password", "zero trust access",
    ),
    "AI / Data": (
        "artificial intelligence", "inteligencia artificial", "inteligencia artificial", "machine learning",
        "data platform", "data analytics", "analytics", "data engineering", "data governance", "data lake",
        "data fabric", "genai", "generative ai", "agentic ai", "ai platform", "openai",
    ),
    "Automation": (
        "automation", "automatizacion", "automacao", "orchestration", "orquestacion", "network automation",
        "devops", "platform engineering", "infrastructure as code", "rpa", "process mining", "workflow",
    ),
    "UC / CX": (
        "unified communications", "contact center", "contact centre", "ccaas", "ucaas", "teams phone",
        "voice", "voip", "customer experience", "omnichannel", "omnicanal", "collaboration", "colaboracion",
    ),
}

CLIENT_SIGNAL_FIELDS = {
    "clients_public": ("request_or_need", "opportunity_area", "technology_signals", "opportunity_notes"),
    "clients_private": ("technology_signals", "hiring_signals", "opportunity_notes", "renewal_window"),
}
MANUFACTURER_CAPABILITY_FIELDS = ("domain", "capabilities", "services", "specializations")


def _client_evidence(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        url = str(raw.get("url") or "")
        if url.startswith(("http://", "https://")) and provenance_kind(raw) != "LEGACY_UNRESOLVED":
            output.append(dict(raw))
    return dedupe_evidence(output)


def _manufacturer_evidence(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return dedupe_evidence(raw for raw in rows if isinstance(raw, Mapping) and typed_evidence_sufficient(raw))


def _detect_areas(text: str) -> list[str]:
    blob = f" {canonical(text)} "
    output = []
    for area, terms in AREA_TERMS.items():
        if any(canonical(term) and canonical(term) in blob for term in terms):
            output.append(area)
    return output


def _signals(field: Mapping[str, Any] | None, *, client_side: bool) -> list[tuple[str, list[dict[str, Any]]]]:
    field = field or {}
    evidence_filter = _client_evidence if client_side else _manufacturer_evidence
    field_evidence = evidence_filter(field.get("evidence") or [])
    value = field.get("value")
    if isinstance(value, list):
        item_map = {
            canonical(item.get("value")): item
            for item in field.get("items") or []
            if isinstance(item, Mapping) and canonical(item.get("value"))
        }
        output = []
        for raw in value:
            text = str(raw or "").strip()
            if not text:
                continue
            item = item_map.get(canonical(text)) or {}
            specific = evidence_filter(item.get("evidence") or [])
            if specific:
                output.append((text, specific))
            elif field_evidence:
                # Field evidence can support a scalar/list signal, but it is never used to assert a vendor relation.
                output.append((text, field_evidence))
        return output
    text = str(value or "").strip()
    return [(text, field_evidence)] if text and field_evidence else []


def _schema(field_id: str) -> dict[str, Any]:
    if field_id == "westcon_area":
        return {
            "id": "westcon_area", "label": "Área Westcon",
            "help": (
                "Clasificación funcional derivada de señales o necesidades trazables del cliente. "
                "No implica presupuesto, compra ni oportunidad comercial confirmada."
            ),
            "clarify": True, "decision_required": True, "expected": True, "empty_mode": "research",
        }
    return {
        "id": "westcon_fit", "label": "Fabricantes Westcon relacionados",
        "help": (
            "Mapa funcional entre señales del cliente y capacidades documentadas del portfolio Westcon. "
            "No prueba uso, compra, adjudicación ni relación comercial."
        ),
        "clarify": True, "decision_required": True, "expected": True, "empty_mode": "research",
    }


def _ensure_schema(data: dict[str, Any], section: str) -> None:
    schema = data.setdefault("schemas", {}).setdefault(section, [])
    by_id = {str(item.get("id")): item for item in schema if isinstance(item, dict)}
    for field_id in ("westcon_area", "westcon_fit"):
        wanted = _schema(field_id)
        current = by_id.get(field_id)
        if current is None:
            insert_at = next(
                (i + 1 for i, item in enumerate(schema) if item.get("id") in {"opportunity_area", "technology_signals"}),
                len(schema),
            )
            schema.insert(insert_at, wanted)
        else:
            current.update(wanted)


def _scope(row: Mapping[str, Any]) -> set[str]:
    raw = ((row.get("fields") or {}).get("scope") or {}).get("value")
    text = " ".join(map(str, raw)) if isinstance(raw, list) else str(raw or "")
    blob = canonical(text)
    if any(token in blob for token in ("iberia", "es pt", "spain portugal")):
        return {"ES", "PT"}
    output = set()
    if "espana" in blob or "spain" in blob or re.search(r"(^|[^a-z])es([^a-z]|$)", blob):
        output.add("ES")
    if "portugal" in blob or re.search(r"(^|[^a-z])pt([^a-z]|$)", blob):
        output.add("PT")
    return output


def _compatible(a: set[str], b: set[str]) -> bool:
    return not a or not b or bool(a & b)


def _manufacturer_index(data: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    index: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in data.get("manufacturers") or []:
        if not isinstance(row, Mapping):
            continue
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        by_area: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        for field_id in MANUFACTURER_CAPABILITY_FIELDS:
            field = ((row.get("fields") or {}).get(field_id) or {})
            if not isinstance(field, Mapping):
                continue
            values = field.get("value")
            blob = " ".join(map(str, values)) if isinstance(values, list) else str(values or "")
            evidence = _manufacturer_evidence(field.get("evidence") or [])
            if evidence:
                for area in _detect_areas(blob):
                    by_area[area].extend(evidence)
            for text, item_evidence in _signals(field, client_side=False):
                for area in _detect_areas(text):
                    by_area[area].extend(item_evidence)
        for area, evidence in by_area.items():
            clean = _manufacturer_evidence(evidence)
            if clean:
                index[area].append({"name": name, "evidence": clean, "scope": _scope(row)})
    return index


def _portfolio_names(data: Mapping[str, Any]) -> list[str]:
    names = []
    for row in data.get("manufacturers") or []:
        if not isinstance(row, Mapping):
            continue
        name = str(row.get("name") or "").strip()
        if name:
            names.append(name)
            if "/" in name:
                names.extend(part.strip() for part in name.split("/") if part.strip())
    return sorted(set(names), key=len, reverse=True)


def _mentioned(text: str, names: Iterable[str]) -> list[str]:
    blob = canonical(text)
    output = []
    for name in names:
        token = canonical(name)
        if len(token) >= 3 and re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", blob):
            output.append(name)
    return list(dict.fromkeys(output))


def derive_client_intelligence(data: dict[str, Any]) -> dict[str, Any]:
    """Enrich client rows additively; never delete a pre-existing client mapping."""
    for section in CLIENT_SIGNAL_FIELDS:
        _ensure_schema(data, section)

    manufacturer_index = _manufacturer_index(data)
    portfolio_names = _portfolio_names(data)
    canonical_names: dict[str, str] = {}
    manufacturer_evidence: dict[str, list[dict[str, Any]]] = {}
    manufacturer_scopes: dict[str, set[str]] = {}

    for row in data.get("manufacturers") or []:
        if not isinstance(row, Mapping):
            continue
        name = str(row.get("name") or "")
        key = canonical(name)
        canonical_names[key] = name
        manufacturer_scopes[key] = _scope(row)
        evidence: list[dict[str, Any]] = []
        for field_id in MANUFACTURER_CAPABILITY_FIELDS:
            field = ((row.get("fields") or {}).get(field_id) or {})
            if not isinstance(field, Mapping):
                continue
            evidence.extend(_manufacturer_evidence(field.get("evidence") or []))
            for item in field.get("items") or []:
                if isinstance(item, Mapping):
                    evidence.extend(_manufacturer_evidence(item.get("evidence") or []))
        manufacturer_evidence[key] = dedupe_evidence(evidence)
        if "/" in name:
            for part in name.split("/"):
                canonical_names[canonical(part)] = name

    for section, source_fields in CLIENT_SIGNAL_FIELDS.items():
        for row in data.get(section) or []:
            if not isinstance(row, dict):
                continue
            fields = row.setdefault("fields", {})
            client_scope = _scope(row)
            area_evidence: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
            source_material: list[tuple[str, list[dict[str, Any]]]] = []

            for field_id in source_fields:
                field = fields.get(field_id) or {}
                for text, evidence in _signals(field, client_side=True):
                    source_material.append((text, evidence))
                    for area in _detect_areas(text):
                        area_evidence[area].extend(evidence)
                    evidence_text = " ".join(
                        " ".join(str(ev.get(key) or "") for key in ("title", "description", "matched_terms"))
                        for ev in evidence
                    )
                    for area in _detect_areas(evidence_text):
                        area_evidence[area].extend(evidence)

            area_rows = []
            for area in AREA_TERMS:
                evidence = _client_evidence(area_evidence.get(area) or [])
                if evidence:
                    area_rows.append({"value": area, "evidence": evidence, "confidence": 0.72})
            if area_rows:
                derived = itemized_field(
                    area_rows, confidence=0.68, claim_type="interpretation", assertion_status="DERIVADO",
                    qualifier="Taxonomía Westcon derivada de señales/necesidades trazables del cliente.",
                )
                fields["westcon_area"] = merge_field(fields.get("westcon_area"), derived)

            fits: dict[str, dict[str, Any]] = {}
            # Preserve direct vendor mentions already extracted from client pages.
            existing_fit = fields.get("westcon_fit") or {}
            if isinstance(existing_fit, Mapping):
                item_map = {
                    canonical(item.get("value")): item
                    for item in existing_fit.get("items") or []
                    if isinstance(item, Mapping)
                }
                for raw_name in existing_fit.get("value") or []:
                    key = canonical(raw_name)
                    item = item_map.get(key) or {}
                    client_ev = _client_evidence(item.get("evidence") or [])
                    name = canonical_names.get(key, str(raw_name))
                    vendor_key = canonical(name)
                    vendor_ev = manufacturer_evidence.get(vendor_key) or []
                    if client_ev and vendor_ev and _compatible(client_scope, manufacturer_scopes.get(vendor_key) or set()):
                        fits[vendor_key] = {
                            "name": name, "score": 100, "evidence": client_ev + vendor_ev,
                            "areas": set(), "direct": True,
                        }

            for text, client_ev in source_material:
                evidence_text = text + " " + " ".join(str(ev.get("description") or "") for ev in client_ev)
                for raw_name in _mentioned(evidence_text, portfolio_names):
                    name = canonical_names.get(canonical(raw_name), raw_name)
                    key = canonical(name)
                    vendor_ev = manufacturer_evidence.get(key) or []
                    if not vendor_ev or not _compatible(client_scope, manufacturer_scopes.get(key) or set()):
                        continue
                    item = fits.setdefault(key, {"name": name, "score": 100, "evidence": [], "areas": set(), "direct": True})
                    item["score"] = 100
                    item["direct"] = True
                    item["evidence"].extend(client_ev)
                    item["evidence"].extend(vendor_ev)

            for area, client_rows in area_evidence.items():
                client_ev = _client_evidence(client_rows)
                if not client_ev:
                    continue
                for manufacturer in manufacturer_index.get(area) or []:
                    name = manufacturer["name"]
                    key = canonical(name)
                    if not _compatible(client_scope, manufacturer.get("scope") or set()):
                        continue
                    item = fits.setdefault(key, {"name": name, "score": 0, "evidence": [], "areas": set(), "direct": False})
                    if area not in item["areas"]:
                        item["score"] += 10
                        item["areas"].add(area)
                    item["evidence"].extend(client_ev)
                    item["evidence"].extend(manufacturer.get("evidence") or [])

            ranked = sorted(fits.values(), key=lambda item: (not item["direct"], -int(item["score"]), canonical(item["name"])))[:10]
            fit_rows = []
            for item in ranked:
                evidence = dedupe_evidence(item["evidence"])
                if not evidence:
                    continue
                areas = sorted(item["areas"])
                fit_rows.append({
                    "value": item["name"], "evidence": evidence,
                    "confidence": 0.76 if item["direct"] else 0.66,
                    "qualifier": (
                        "Mención explícita del fabricante en evidencia del cliente; no prueba compra o uso."
                        if item["direct"]
                        else "Encaje funcional por " + (", ".join(areas) if areas else "capacidad")
                        + "; combina evidencia del cliente y capacidad documentada del fabricante."
                    ),
                })
            if fit_rows:
                derived = itemized_field(
                    fit_rows, confidence=0.66, claim_type="interpretation", assertion_status="DERIVADO",
                    qualifier="Mapa funcional; no equivale a implantación, adjudicación ni relación comercial.",
                )
                fields["westcon_fit"] = merge_field(fields.get("westcon_fit"), derived)
    return data
