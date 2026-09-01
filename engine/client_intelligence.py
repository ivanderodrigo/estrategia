"""Evidence-backed Westcon-area and portfolio mapping for client intelligence.

This module deliberately separates three things:
1. what a client source actually says;
2. the normalized Westcon technology area derived from that evidence; and
3. the portfolio vendors that have independently evidenced capability in that area.

A portfolio fit is therefore an interpretation backed by evidence from BOTH sides. It
never claims that the client uses the vendor or that a commercial opportunity exists.
"""

from __future__ import annotations

import re
from collections import defaultdict
from copy import deepcopy
from typing import Any, Iterable

from .enrichment import itemized_field
from .model import canonical


AREA_TERMS: dict[str, tuple[str, ...]] = {
    "Networking": (
        "network", "networking", "red", "redes", "connectivity", "conectividad",
        "wifi", "wi fi", "wireless", "switching", "routing", "router", "campus",
        "sd wan", "sd-wan", "edge networking", "branch networking", "cloud networking",
        "network segmentation", "segmentacion de red", "segmentação de rede",
    ),
    "Cybersecurity": (
        "cybersecurity", "ciberseguridad", "ciberseguranca", "security", "seguridad",
        "seguranca", "firewall", "sase", "sse", "zero trust", "xdr", "edr", "mdr",
        "soc", "threat", "amenaza", "ameaca", "incident response", "api security",
        "application security", "devsecops", "endpoint security", "cloud security",
        "ot security", "ot it security", "industrial security", "industrial cyber",
        "data protection", "proteccion de datos", "protecao de dados", "email security",
    ),
    "Cloud": (
        "cloud", "nube", "aws", "azure", "multi cloud", "multicloud", "hybrid cloud",
        "cloud platform", "cloud platforms", "cloud infrastructure", "cloud native",
    ),
    "Data Center": (
        "data center", "datacenter", "centro de datos", "centro de dados", "compute",
        "storage", "virtualization", "virtualizacion", "virtualizacao", "hyperconverged",
        "hci", "infrastructure", "infraestructura", "infraestrutura",
    ),
    "Observability": (
        "observability", "observabilidad", "observabilidade", "monitoring", "telemetry",
        "telemetria", "apm", "application performance", "sre", "site reliability",
    ),
    "Identity & Access": (
        "identity", "identidad", "identidade", "iam", "pam", "identity security",
        "identity and access", "access management", "gestion de acceso", "gestao de acesso",
    ),
    "AI / Data": (
        "artificial intelligence", "inteligencia artificial", "inteligencia artificial",
        "machine learning", " ai ", "data platform", "data platforms", "data analytics",
        "data / analytics", "analytics", "analitica", "analitica", "data engineer",
        "data engineering", "data governance", "data lake", "data fabric",
    ),
    "Automation": (
        "automation", "automatizacion", "automacao", "orchestration", "orquestacion",
        "orquestracao", "network automation", "devops", "platform engineer",
        "platform engineering", "infrastructure as code", "iac",
    ),
}

CLIENT_SIGNAL_FIELDS: dict[str, tuple[str, ...]] = {
    "clients_public": (
        "request_or_need", "opportunity_area", "technology_signals", "opportunity_notes",
    ),
    "clients_private": (
        "technology_signals", "hiring_signals", "opportunity_notes", "renewal_window",
    ),
}

MANUFACTURER_CAPABILITY_FIELDS = ("domain", "capabilities")


def _usable_evidence(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        url = str(raw.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            continue
        key = (url, str(raw.get("title") or ""), str(raw.get("scope") or ""))
        if key in seen:
            continue
        seen.add(key)
        output.append(deepcopy(raw))
    return output


def _evidence_strength(rows: Iterable[dict[str, Any]]) -> float:
    evidence = _usable_evidence(rows)
    if not evidence:
        return 0.0
    if any(
        item.get("official") is True
        or str(item.get("source_grade") or "").startswith("A")
        or "official" in str(item.get("source_type") or item.get("type") or "").casefold()
        for item in evidence
    ):
        return 0.78
    independent = {
        canonical(item.get("source") or item.get("url") or item.get("title"))
        for item in evidence
        if canonical(item.get("source") or item.get("url") or item.get("title"))
    }
    return 0.70 if len(independent) >= 2 else 0.64


def _signals_from_field(field: dict[str, Any] | None) -> list[tuple[str, list[dict[str, Any]]]]:
    """Return values with their most specific usable evidence.

    Legacy v4 fields sometimes have evidence at field level while their list items lost
    the pointer. For *deriving a broad area* we may use that field evidence, because it
    is explicitly attached to the whole field. We do not mutate the legacy item or
    pretend that this is atomic evidence for the raw list item.
    """

    field = field or {}
    value = field.get("value")
    field_evidence = _usable_evidence(field.get("evidence") or [])
    if isinstance(value, list):
        item_map = {
            canonical(item.get("value")): item
            for item in field.get("items") or []
            if isinstance(item, dict) and canonical(item.get("value"))
        }
        output: list[tuple[str, list[dict[str, Any]]]] = []
        for raw in value:
            if isinstance(raw, dict):
                continue
            text = str(raw or "").strip()
            if not text:
                continue
            item = item_map.get(canonical(text)) or {}
            specific = _usable_evidence(item.get("evidence") or [])
            # For multi-value fields, never treat field-wide evidence as if it proved
            # an individual item. This is the exact provenance bug v4.0.1 hardens.
            if specific:
                output.append((text, specific))
        return output
    text = str(value or "").strip()
    return [(text, field_evidence)] if text else []


def _detect_areas(text: str) -> list[str]:
    blob = f" {canonical(text)} "
    output: list[str] = []
    for area, terms in AREA_TERMS.items():
        for term in terms:
            token = canonical(term)
            if not token:
                continue
            if f" {token} " in blob or token in blob:
                output.append(area)
                break
    return output


def _schema_column(field_id: str) -> dict[str, Any]:
    if field_id == "westcon_area":
        return {
            "id": "westcon_area",
            "label": "Área Westcon",
            "help": (
                "Área tecnológica Westcon derivada exclusivamente de necesidades o señales públicas "
                "trazables del cliente. Es una clasificación funcional, no una oportunidad comercial confirmada."
            ),
            "clarify": True,
            "decision_required": True,
            "expected": True,
            "empty_mode": "research",
        }
    return {
        "id": "westcon_fit",
        "label": "Fabricantes Westcon relacionados",
        "help": (
            "Mapa funcional entre necesidades/señales evidenciadas del cliente y capacidades igualmente "
            "evidenciadas de fabricantes del portfolio Westcon. No prueba uso actual, adjudicación ni relación comercial."
        ),
        "clarify": True,
        "decision_required": True,
        "expected": True,
        "empty_mode": "research",
    }


def _ensure_client_schema(data: dict[str, Any], section: str) -> None:
    schema = (data.setdefault("schemas", {}).setdefault(section, []))
    by_id = {str(item.get("id")): item for item in schema if isinstance(item, dict)}
    for field_id in ("westcon_area", "westcon_fit"):
        wanted = _schema_column(field_id)
        current = by_id.get(field_id)
        if current is None:
            # Put the client-specific intelligence next to the observable technology fields.
            insert_at = next(
                (index + 1 for index, item in enumerate(schema) if item.get("id") in {"opportunity_area", "technology_signals"}),
                len(schema),
            )
            schema.insert(insert_at, wanted)
        else:
            current.update(wanted)


def _manufacturer_area_index(data: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()
    for row in data.get("manufacturers") or []:
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        for field_id in MANUFACTURER_CAPABILITY_FIELDS:
            field = (row.get("fields") or {}).get(field_id) or {}
            for text, evidence in _signals_from_field(field):
                if not evidence:
                    continue
                for area in _detect_areas(text):
                    key = (canonical(name), area)
                    if key in seen:
                        # Merge additional capability evidence into the existing row.
                        existing = next(item for item in index[area] if canonical(item["name"]) == canonical(name))
                        existing["evidence"] = _usable_evidence(existing.get("evidence", []) + evidence)
                        continue
                    seen.add(key)
                    index[area].append({"name": name, "evidence": evidence, "source_field": field_id, "scope": _scope_set(row)})
    return index


def _scope_set(row: dict[str, Any]) -> set[str]:
    raw = ((row.get("fields") or {}).get("scope") or {}).get("value")
    text = " ".join(map(str, raw)) if isinstance(raw, list) else str(raw or "")
    blob = canonical(text)
    scopes: set[str] = set()
    if any(token in blob for token in ("iberia", "es + pt", "es/pt", "spain + portugal")):
        return {"ES", "PT"}
    if re.search(r"(^|[^a-z])es([^a-z]|$)", blob) or "espana" in blob or "spain" in blob:
        scopes.add("ES")
    if re.search(r"(^|[^a-z])pt([^a-z]|$)", blob) or "portugal" in blob:
        scopes.add("PT")
    return scopes


def _scope_compatible(client: set[str], vendor: set[str]) -> bool:
    # Missing scope is treated as unknown rather than exclusion; an explicit mismatch is
    # never mapped. This prevents Portugal-only portfolio entries leaking into ES accounts.
    return not client or not vendor or bool(client & vendor)


def _portfolio_names(data: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for row in data.get("manufacturers") or []:
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        names.append(name)
        if "/" in name:
            names.extend(part.strip() for part in name.split("/") if part.strip())
    return sorted(set(names), key=len, reverse=True)


def _mentioned_portfolio_vendors(text: str, portfolio_names: Iterable[str]) -> list[str]:
    blob = canonical(text)
    found: list[str] = []
    for name in portfolio_names:
        token = canonical(name)
        if len(token) < 3:
            continue
        if re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", blob):
            found.append(name)
    return list(dict.fromkeys(found))


def _manufacturer_evidence_by_name(data: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for row in data.get("manufacturers") or []:
        evidence: list[dict[str, Any]] = []
        for field_id in MANUFACTURER_CAPABILITY_FIELDS:
            field = (row.get("fields") or {}).get(field_id) or {}
            evidence.extend(_usable_evidence(field.get("evidence") or []))
            for item in field.get("items") or []:
                if isinstance(item, dict):
                    evidence.extend(_usable_evidence(item.get("evidence") or []))
        result[canonical(row.get("name"))] = _usable_evidence(evidence)
    return result


def derive_client_intelligence(data: dict[str, Any]) -> dict[str, Any]:
    """Derive evidence-backed Westcon area and vendor fit for public/private clients."""

    for section in CLIENT_SIGNAL_FIELDS:
        _ensure_client_schema(data, section)

    manufacturer_index = _manufacturer_area_index(data)
    manufacturer_evidence = _manufacturer_evidence_by_name(data)
    manufacturer_scopes = {canonical(row.get("name")): _scope_set(row) for row in data.get("manufacturers") or []}
    portfolio_names = _portfolio_names(data)
    canonical_portfolio = {canonical(name): name for name in portfolio_names}
    # Prefer the canonical manufacturer row name for split aliases.
    for row in data.get("manufacturers") or []:
        canonical_portfolio[canonical(row.get("name"))] = str(row.get("name") or "")
        if "/" in str(row.get("name") or ""):
            for part in str(row.get("name") or "").split("/"):
                canonical_portfolio[canonical(part)] = str(row.get("name") or "")

    for section, source_fields in CLIENT_SIGNAL_FIELDS.items():
        for row in data.get(section) or []:
            fields = row.setdefault("fields", {})
            client_scope = _scope_set(row)
            area_evidence: dict[str, list[dict[str, Any]]] = defaultdict(list)
            source_material: list[tuple[str, list[dict[str, Any]]]] = []

            for field_id in source_fields:
                field = fields.get(field_id) or {}
                for text, evidence in _signals_from_field(field):
                    if not text or not evidence:
                        continue
                    source_material.append((text, evidence))
                    for area in _detect_areas(text):
                        area_evidence[area].extend(evidence)
                    evidence_text = " ".join(
                        " ".join(str(ev.get(k) or "") for k in ("title", "description", "matched_terms"))
                        for ev in evidence
                    )
                    for area in _detect_areas(evidence_text):
                        area_evidence[area].extend(evidence)

                # Field-level provenance may legitimately describe the whole field even
                # when old list items lost their atomic pointer. Derive only from words
                # actually present in the evidence itself, never from an unsupported item.
                field_evidence = _usable_evidence(field.get("evidence") or [])
                evidence_text = " ".join(
                    " ".join(str(ev.get(k) or "") for k in ("title", "description", "matched_terms"))
                    for ev in field_evidence
                )
                if evidence_text:
                    source_material.append((evidence_text, field_evidence))
                    for area in _detect_areas(evidence_text):
                        area_evidence[area].extend(field_evidence)

            if area_evidence:
                area_rows = []
                for area in AREA_TERMS:
                    evidence = _usable_evidence(area_evidence.get(area) or [])
                    if not evidence:
                        continue
                    area_rows.append({
                        "value": area,
                        "evidence": evidence,
                        "confidence": _evidence_strength(evidence),
                    })
                fields["westcon_area"] = itemized_field(
                    area_rows,
                    confidence=0.68,
                    claim_type="interpretation",
                    assertion_status="DERIVADO",
                    qualifier=(
                        "Taxonomía Westcon derivada de señales/necesidades públicas del cliente. "
                        "No presupone presupuesto, proyecto ni oportunidad comercial activa."
                    ),
                )
            else:
                # Never preserve an old inferred area without a traceable basis.
                fields.pop("westcon_area", None)

            fits: dict[str, dict[str, Any]] = {}

            # 1) Explicit portfolio-vendor mentions in client evidence rank highest.
            for text, client_evidence in source_material:
                evidence_blob = text + " " + " ".join(
                    " ".join(str(ev.get(k) or "") for k in ("title", "description", "matched_terms"))
                    for ev in client_evidence
                )
                for mentioned in _mentioned_portfolio_vendors(evidence_blob, portfolio_names):
                    canonical_name = canonical_portfolio.get(canonical(mentioned), mentioned)
                    key = canonical(canonical_name)
                    if not _scope_compatible(client_scope, manufacturer_scopes.get(key) or set()):
                        continue
                    item = fits.setdefault(key, {
                        "name": canonical_name,
                        "score": 100,
                        "evidence": [],
                        "areas": set(),
                        "direct": True,
                    })
                    item["score"] = max(item["score"], 100)
                    item["direct"] = True
                    item["evidence"].extend(client_evidence)
                    item["evidence"].extend(manufacturer_evidence.get(key) or [])

            # 2) Functional fit requires evidence from the client side AND manufacturer side.
            for area, client_rows in area_evidence.items():
                client_evidence = _usable_evidence(client_rows)
                if not client_evidence:
                    continue
                for manufacturer in manufacturer_index.get(area) or []:
                    name = manufacturer["name"]
                    key = canonical(name)
                    if not _scope_compatible(client_scope, manufacturer.get("scope") or set()):
                        continue
                    item = fits.setdefault(key, {
                        "name": name,
                        "score": 0,
                        "evidence": [],
                        "areas": set(),
                        "direct": False,
                    })
                    if area not in item["areas"]:
                        item["score"] += 10
                        item["areas"].add(area)
                    item["evidence"].extend(client_evidence)
                    item["evidence"].extend(manufacturer.get("evidence") or [])

            ranked = sorted(
                fits.values(),
                key=lambda item: (
                    not item.get("direct"),
                    -int(item.get("score") or 0),
                    -len(_usable_evidence(item.get("evidence") or [])),
                    canonical(item.get("name")),
                ),
            )[:8]

            fit_rows = []
            for item in ranked:
                evidence = _usable_evidence(item.get("evidence") or [])
                if not evidence:
                    continue
                confidence = 0.76 if item.get("direct") else min(0.72, max(0.62, _evidence_strength(evidence) - 0.04))
                areas = sorted(item.get("areas") or [])
                fit_rows.append({
                    "value": item["name"],
                    "evidence": evidence,
                    "confidence": confidence,
                    "qualifier": (
                        "Mención explícita del fabricante en evidencia del cliente; se muestra como señal, no como prueba de compra/uso."
                        if item.get("direct")
                        else "Encaje funcional por " + (", ".join(areas) if areas else "capacidad")
                        + "; combina evidencia del cliente y del fabricante y no prueba uso actual ni oportunidad comercial."
                    ),
                })

            if fit_rows:
                fields["westcon_fit"] = itemized_field(
                    fit_rows,
                    confidence=0.66,
                    claim_type="interpretation",
                    assertion_status="DERIVADO",
                    qualifier=(
                        "Mapa funcional basado en evidencia de necesidad/señal del cliente y evidencia independiente "
                        "de capacidad del fabricante. No equivale a implantación, adjudicación o relación comercial."
                    ),
                )
            else:
                # Remove legacy speculative mappings rather than publishing a vendor with no
                # atomic source behind that exact item.
                fields.pop("westcon_fit", None)

    return data
