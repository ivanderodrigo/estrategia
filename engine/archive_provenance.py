"""Historical archive provenance archaeology for Westcon Decision Intelligence v4.0.3.

This module is intentionally conservative:
- it never imports historical values into the current dataset;
- it only attaches historical evidence when the current value matches exactly;
- entity-level/report hints are marked as corroboration and cannot close a gap;
- archive provenance is persisted in a registry so GitHub Actions can reuse it later
  without access to the original local ZIP archive collection.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

from .knowledge_provenance import dedupe_evidence, provenance_kind, typed_evidence_sufficient
from .model import canonical

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config/current/archive_provenance_registry.json"
LINEAGE_PATH = ROOT / "data/current/provenance_lineage.json"

SECTIONS = (
    "manufacturers", "distributors", "integrators", "clients_public",
    "clients_private", "trends", "architectures",
)

SECTION_ALIASES = {
    "manufacturers": {
        "manufacturers", "fabricantes", "vendors", "vendor", "portfolio", "portfolio_vendors",
    },
    "distributors": {
        "distributors", "mayoristas", "wholesalers", "distribution", "competitor_distributors",
    },
    "integrators": {
        "integrators", "integradores", "partners", "ecosystem", "channel_partners", "resellers",
    },
    "clients_public": {
        "clients_public", "public_clients", "clientes_publicos", "public_sector", "procurement_clients",
    },
    "clients_private": {
        "clients_private", "private_clients", "clientes_privados", "accounts", "large_accounts",
    },
    "trends": {"trends", "tendencias", "technology_trends", "market_trends"},
    "architectures": {"architectures", "arquitecturas", "architecture", "reference_architectures"},
}

FIELD_GROUPS = {
    "domain": {"domain", "area", "technology_area", "area_tecnologica", "technology_domain"},
    "capabilities": {"capabilities", "capacidades", "capability", "technology_capabilities"},
    "competitors": {"competitors", "peers", "competidores", "competitors_peers"},
    "distributors": {"distributors", "mayoristas", "alternative_distributors", "mayoristas_alternativos"},
    "integrators": {"integrators", "partners_integrators", "partners", "integradores", "partners_integradores"},
    "vendor_relations": {"vendor_relations", "vendors", "manufacturers", "fabricantes", "linecard", "fabricantes_linecard"},
    "westcon_overlap": {"westcon_overlap", "overlap", "solape", "solape_con_westcon"},
    "competitor_vendor_overlap": {"competitor_vendor_overlap", "other_vendors", "fabricantes_competidores"},
    "services": {"services", "servicios", "service_capabilities"},
    "specializations": {"specializations", "especializaciones", "specialization", "especializacion_tecnologica"},
    "differential_capabilities": {"differential_capabilities", "capacidades_diferenciales", "capacidades_de_valor"},
    "revenue": {"revenue", "facturacion", "turnover", "sales"},
    "roles": {"roles", "partner_type", "tipo_de_partner"},
    "certifications": {"certifications", "certificaciones", "certificaciones_especializaciones", "specializations_certifications"},
    "scope": {"scope", "country", "geography", "ambito", "pais"},
    "technology_signals": {"technology_signals", "signals", "senales_tecnologicas", "technology", "technologies"},
    "hiring_signals": {"hiring_signals", "jobs", "employment_signals", "senales_empleo"},
    "westcon_area": {"westcon_area", "area_westcon", "opportunity_area", "area_oportunidad"},
    "westcon_fit": {"westcon_fit", "westcon_vendors_fit", "fabricantes_westcon_relacionados", "encaje_fabricantes"},
    "market_size_growth": {"market_size_growth", "market_growth", "mercado_crecimiento", "market_size", "market"},
    "horizon": {"horizon", "horizonte", "time_horizon"},
    "drivers": {"drivers", "growth_drivers", "motores_crecimiento", "motores_de_crecimiento"},
    "demand": {"demand", "market_demand", "demanda", "demanda_mercado", "que_esta_demandando_el_mercado"},
    "market_players": {"market_players", "players", "actors", "actores", "panorama_fabricantes"},
    "westcon_vendors": {"westcon_vendors", "fabricantes_westcon", "fabricantes_westcon_relacionados"},
    "evolution": {"evolution", "evolucion", "trajectory"},
    "iberia_context": {"iberia_context", "contexto_iberia", "iberia"},
    "what_is_happening": {"what_is_happening", "que_esta_ocurriendo", "summary", "descripcion"},
    "layers": {"layers", "capas", "architecture_layers"},
    "vendors": {"vendors", "fabricantes", "architecture_vendors"},
    "request_or_need": {"request_or_need", "need", "necesidad", "peticion", "request"},
    "opportunity_area": {"opportunity_area", "area", "area_oportunidad"},
    "amount": {"amount", "importe", "monto", "budget"},
    "deadline": {"deadline", "fecha", "date", "closing_date"},
}
FIELD_ALIAS_LOOKUP = {
    canonical(alias): target
    for target, aliases in FIELD_GROUPS.items()
    for alias in aliases | {target}
}

EVIDENCE_KEYS = ("evidence", "evidences", "sources", "source_rows", "references", "refs", "provenance")
NAME_KEYS = ("name", "entity", "company", "vendor", "manufacturer", "partner", "title", "label")
VALUE_KEYS = ("value", "values", "data")

PRIMARY_HINTS = ("primary", "official", "regulator", "open-data", "open_data", "procurement", "vendor-own", "manufacturer-own", "partner-locator", "partner-directory")
SECONDARY_HINTS = ("secondary", "analyst", "industry-research", "industry_research", "media", "press", "specialist")
DISCOVERY_HINTS = ("discovery", "search", "aggregator", "job", "career")

NON_SUFFICIENT_ORIGINS = {"ARCHIVE_CORROBORATION", "REPORT_CORROBORATION", "DISCOVERY_ONLY"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _has_value(value: Any) -> bool:
    return value not in (None, "", [], {})


def _value_key(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except TypeError:
        return str(value)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_value_key(value).encode("utf-8")).hexdigest()[:24]


def _section_name(raw: Any) -> str | None:
    key = canonical(raw)
    for target, aliases in SECTION_ALIASES.items():
        if key in {canonical(x) for x in aliases}:
            return target
    return None


def _field_name(raw: Any) -> str:
    key = canonical(raw)
    return FIELD_ALIAS_LOOKUP.get(key, key.replace(" ", "_"))


def _entity_name(row: Mapping[str, Any]) -> str:
    for key in NAME_KEYS:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _entity_aliases(name: str) -> set[str]:
    result = {canonical(name)} if name else set()
    for part in re.split(r"[/|]", name):
        token = canonical(part)
        if len(token) >= 3:
            result.add(token)
    simplified = re.sub(r"\b(sa|sl|s l|s a|plc|ltd|limited|inc|corp|corporation|group|grupo)\b", "", canonical(name)).strip()
    if len(simplified) >= 3:
        result.add(simplified)
    return {x for x in result if x}


def _archive_version(name: str) -> str:
    match = re.search(r"(?i)(?:^|[^a-z0-9])v?(\d+)\.(\d+)(?:\.(\d+))?([a-z]?)(?:[^a-z0-9]|$)", name)
    if not match:
        return name
    major, minor, patch, suffix = match.groups()
    return f"{int(major)}.{int(minor)}.{int(patch or 0)}{suffix or ''}"


def _version_sort_key(label: str) -> tuple[int, int, int, int, str]:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)([a-z]?)", label)
    if not match:
        return (-1, -1, -1, -1, label.casefold())
    major, minor, patch, suffix = match.groups()
    suffix_rank = 0 if not suffix else ord(suffix.casefold()) - 96
    return (int(major), int(minor), int(patch), suffix_rank, label.casefold())


def _is_business_intelligence_name(name: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_")
    return "westcon_iberia_business_intelligence" in normalized


def _is_candidate_archive(path: Path) -> bool:
    if path.suffix.casefold() != ".zip":
        return False
    # v4.0.3 r2 deliberately uses the Business Intelligence family as the
    # high-confidence historical corpus. Decision Intelligence / Strategy Studio
    # snapshots remain available for a later fallback pass over unresolved items.
    return _is_business_intelligence_name(path.name)


def discover_archives(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    rows = [path for path in directory.glob("*.zip") if _is_candidate_archive(path)]
    rows.sort(key=lambda p: (_version_sort_key(_archive_version(p.name)), p.name.casefold()))
    return rows


def _decode_json(raw: bytes) -> Any | None:
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return json.loads(raw.decode(encoding))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    return None


def _normalize_url(value: Any) -> str:
    text = str(value or "").strip()
    return text if text.startswith(("http://", "https://")) else ""


def _domain_name(url: str) -> str:
    try:
        host = urlparse(url).hostname or ""
    except ValueError:
        host = ""
    return host.removeprefix("www.") or "Fuente histórica"


def _pick(mapping: Mapping[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        value = mapping.get(key)
        if _has_value(value):
            return value
    return None


def _normalize_evidence(raw: Any, *, archive: str, version: str, member: str, match_mode: str, origin: str = "ARCHIVE_RECOVERED") -> dict[str, Any] | None:
    if isinstance(raw, str):
        url = _normalize_url(raw)
        if not url:
            return None
        item: dict[str, Any] = {"url": url, "source": _domain_name(url), "title": _domain_name(url)}
    elif isinstance(raw, Mapping):
        nested = raw.get("source") if isinstance(raw.get("source"), Mapping) else None
        merged = dict(nested or {})
        merged.update(dict(raw))
        url = _normalize_url(_pick(merged, ("url", "href", "link", "source_url", "sourceUrl")))
        source = _pick(merged, ("source_name", "publisher", "provider", "site", "domain"))
        if not source and isinstance(merged.get("source"), str):
            source = merged.get("source")
        title = _pick(merged, ("title", "headline", "name", "label", "source_title"))
        date = _pick(merged, ("date", "published_at", "publication_date", "observed_at", "retrieved_at", "fetched_at", "timestamp"))
        description = _pick(merged, ("description", "snippet", "summary", "context", "note", "text"))
        item = {
            "url": url,
            "source": str(source or (_domain_name(url) if url else "Fuente histórica")).strip(),
            "title": str(title or source or (_domain_name(url) if url else "Evidencia histórica")).strip(),
        }
        if date:
            item["date"] = str(date)
        if description:
            item["description"] = str(description)
        for key in ("official", "source_grade", "grade", "country", "scope", "method", "freshness_status", "age_days", "revalidation", "type", "source_type", "class", "classification", "confidence"):
            if _has_value(merged.get(key)):
                item[key] = deepcopy(merged.get(key))
    else:
        return None
    if not item.get("url") and not item.get("source"):
        return None
    item.setdefault(
        "description",
        "Evidencia recuperada de un snapshot histórico donde estaba asociada al mismo valor exacto de la misma entidad/campo."
        if origin == "ARCHIVE_RECOVERED"
        else "Corroboración histórica de contexto; no se considera evidencia atómica suficiente por sí sola.",
    )
    item["provenance_origin"] = origin
    item["historical_archive"] = archive
    item["historical_version"] = version
    item["historical_path"] = member
    item["match_mode"] = match_mode
    item["method"] = item.get("method") or ("archive-exact-provenance-recovery" if origin == "ARCHIVE_RECOVERED" else "archive-context-corroboration")
    return item


def _evidence_rows(node: Any, *, archive: str, version: str, member: str, match_mode: str, origin: str = "ARCHIVE_RECOVERED") -> list[dict[str, Any]]:
    candidates: list[Any] = []
    if isinstance(node, Mapping):
        for key in EVIDENCE_KEYS:
            value = node.get(key)
            if isinstance(value, list):
                candidates.extend(value)
            elif _has_value(value):
                candidates.append(value)
        # Some historical models stored a single source directly on the field.
        if _normalize_url(node.get("url")) and not candidates:
            candidates.append(node)
    elif isinstance(node, list):
        candidates.extend(node)
    rows = []
    for raw in candidates:
        normalized = _normalize_evidence(raw, archive=archive, version=version, member=member, match_mode=match_mode, origin=origin)
        if normalized:
            rows.append(normalized)
    return dedupe_evidence(rows)


def _field_value(field: Any) -> Any:
    if isinstance(field, Mapping):
        for key in VALUE_KEYS:
            if key in field and _has_value(field.get(key)):
                return field.get(key)
        # A raw direct field mapping with no wrapper is not considered a scalar value.
        return None
    return field


def _field_items(field: Any) -> list[Mapping[str, Any]]:
    if not isinstance(field, Mapping):
        return []
    for key in ("items", "elements", "entries", "rows"):
        value = field.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, Mapping)]
    return []


def _row_fields(row: Mapping[str, Any]) -> Iterator[tuple[str, Any]]:
    fields = row.get("fields")
    if isinstance(fields, Mapping):
        for field_id, field in fields.items():
            yield str(field_id), field
        return
    ignored = set(NAME_KEYS) | {"id", "key", "type", "kind", "category", "section", "evidence", "evidences", "sources", "source_catalog", "analytics", "meta"}
    for key, value in row.items():
        if key in ignored:
            continue
        if isinstance(value, Mapping) and any(k in value for k in VALUE_KEYS + EVIDENCE_KEYS):
            yield str(key), value


def _iter_section_rows(node: Any, path: str = "$") -> Iterator[tuple[str, Mapping[str, Any], str]]:
    if isinstance(node, Mapping):
        for key, value in node.items():
            section = _section_name(key)
            child_path = f"{path}.{key}"
            if section and isinstance(value, list):
                for index, row in enumerate(value):
                    if isinstance(row, Mapping) and _entity_name(row):
                        yield section, row, f"{child_path}[{index}]"
            elif section and isinstance(value, Mapping):
                for name, row in value.items():
                    if isinstance(row, Mapping):
                        enriched = dict(row)
                        enriched.setdefault("name", str(name))
                        if _entity_name(enriched):
                            yield section, enriched, f"{child_path}.{name}"
            yield from _iter_section_rows(value, child_path)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _iter_section_rows(value, f"{path}[{index}]")


def _iter_source_registry(node: Any, path: str = "$") -> Iterator[tuple[Mapping[str, Any], str]]:
    if isinstance(node, Mapping):
        url = _normalize_url(_pick(node, ("url", "href", "link", "source_url")))
        classification = _pick(node, ("class", "type", "source_type", "classification", "authority", "tier"))
        if url and classification:
            yield node, path
        for key, value in node.items():
            yield from _iter_source_registry(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _iter_source_registry(value, f"{path}[{index}]")


def _classification_origin(value: Any) -> tuple[str, str]:
    blob = canonical(value)
    if any(canonical(hint) in blob for hint in PRIMARY_HINTS):
        return "PUBLIC_PRIMARY", "historical-primary"
    if any(canonical(hint) in blob for hint in SECONDARY_HINTS):
        return "PUBLIC_SECONDARY", "historical-secondary"
    if any(canonical(hint) in blob for hint in DISCOVERY_HINTS):
        return "DISCOVERY_ONLY", "historical-discovery"
    return "UNKNOWN", str(value or "historical-unknown")


@dataclass
class Target:
    section: str
    entity: str
    entity_aliases: set[str]
    field_id: str
    field_alias: str
    value_key: str
    value_hash: str
    item_value_key: str | None = None
    item_value_hash: str | None = None
    kind: str = "field"

    @property
    def key(self) -> str:
        suffix = f"/item/{self.item_value_hash}" if self.item_value_hash else ""
        return f"{self.section}/{canonical(self.entity)}/{self.field_id}/{self.value_hash}{suffix}"


def _needs_recovery(evidence: Iterable[Mapping[str, Any]]) -> bool:
    rows = [row for row in evidence if isinstance(row, Mapping)]
    if not rows:
        return True
    if not any(typed_evidence_sufficient(row) for row in rows):
        return True
    return any(provenance_kind(row) == "UNKNOWN" for row in rows)


def build_targets(data: Mapping[str, Any], alias_config: Mapping[str, Any] | None = None) -> dict[str, Target]:
    aliases_cfg = alias_config or {}
    targets: dict[str, Target] = {}
    for section in SECTIONS:
        for row in data.get(section) or []:
            if not isinstance(row, Mapping):
                continue
            entity = str(row.get("name") or "").strip()
            if not entity:
                continue
            aliases = _entity_aliases(entity)
            for target_name, raw_aliases in aliases_cfg.items():
                if canonical(target_name) in aliases:
                    for alias in raw_aliases if isinstance(raw_aliases, list) else [raw_aliases]:
                        aliases |= _entity_aliases(str(alias))
            for field_id, field in (row.get("fields") or {}).items():
                if not isinstance(field, Mapping) or not _has_value(field.get("value")):
                    continue
                field_alias = _field_name(field_id)
                value_key = _value_key(field.get("value"))
                if _needs_recovery(field.get("evidence") or []):
                    target = Target(section, entity, set(aliases), str(field_id), field_alias, value_key, _stable_hash(field.get("value")))
                    targets[target.key] = target
                for item in field.get("items") or []:
                    if not isinstance(item, Mapping) or not _has_value(item.get("value")):
                        continue
                    if not _needs_recovery(item.get("evidence") or []):
                        continue
                    target = Target(
                        section, entity, set(aliases), str(field_id), field_alias, value_key, _stable_hash(field.get("value")),
                        _value_key(item.get("value")), _stable_hash(item.get("value")), "item",
                    )
                    targets[target.key] = target
    return targets


def _target_indexes(targets: Mapping[str, Target]) -> tuple[dict[tuple[str, str], list[Target]], dict[tuple[str, str, str, str], list[Target]], dict[tuple[str, str, str], list[Target]]]:
    by_entity: dict[tuple[str, str], list[Target]] = {}
    by_exact: dict[tuple[str, str, str, str], list[Target]] = {}
    by_unique_value: dict[tuple[str, str, str], list[Target]] = {}
    for target in targets.values():
        for alias in target.entity_aliases:
            by_entity.setdefault((target.section, alias), []).append(target)
            value_key = target.item_value_key if target.kind == "item" else target.value_key
            by_exact.setdefault((target.section, alias, target.field_alias, value_key or ""), []).append(target)
            by_unique_value.setdefault((target.section, alias, value_key or ""), []).append(target)
    return by_entity, by_exact, by_unique_value


def _history_observation(lineage: dict[str, Any], target: Target, *, archive: str, version: str, member: str, has_atomic: bool, has_context: bool, match_mode: str) -> None:
    item = lineage.setdefault(target.key, {
        "section": target.section, "entity": target.entity, "field": target.field_id,
        "value_hash": target.value_hash, "item_value_hash": target.item_value_hash,
        "observations": [],
    })
    key = (archive, member, match_mode)
    if any((x.get("archive"), x.get("member"), x.get("match_mode")) == key for x in item["observations"]):
        return
    item["observations"].append({
        "archive": archive, "version": version, "member": member,
        "atomic_evidence": bool(has_atomic), "context_evidence": bool(has_context), "match_mode": match_mode,
    })


def _add_match(matches: dict[str, dict[str, Any]], target: Target, evidence: Iterable[Mapping[str, Any]], *, mode: str, archive: str, version: str, member: str, historical_confidence: Any = None) -> None:
    rows = dedupe_evidence(evidence)
    if not rows:
        return
    entry = matches.setdefault(target.key, {
        "section": target.section, "entity": target.entity, "field": target.field_id,
        "field_alias": target.field_alias, "value_hash": target.value_hash,
        "item_value_hash": target.item_value_hash, "evidence": [], "match_modes": [], "origins": [],
    })
    entry["evidence"] = dedupe_evidence(list(entry.get("evidence") or []) + rows)
    mode_row = {"mode": mode, "archive": archive, "version": version, "member": member}
    if historical_confidence not in (None, ""):
        mode_row["historical_confidence"] = historical_confidence
    if mode_row not in entry["match_modes"]:
        entry["match_modes"].append(mode_row)
    entry["origins"] = sorted({str(ev.get("provenance_origin") or "") for ev in entry["evidence"] if ev.get("provenance_origin")})


def _process_historical_row(
    section: str,
    row: Mapping[str, Any],
    *, archive: str, version: str, member: str,
    by_exact: Mapping[tuple[str, str, str, str], list[Target]],
    by_unique_value: Mapping[tuple[str, str, str], list[Target]],
    matches: dict[str, dict[str, Any]], lineage: dict[str, Any], stats: dict[str, int],
) -> None:
    hist_entity = _entity_name(row)
    aliases = _entity_aliases(hist_entity)
    if not aliases:
        return
    row_context = _evidence_rows(row, archive=archive, version=version, member=member, match_mode="entity-context", origin="ARCHIVE_CORROBORATION")
    for raw_field_id, field in _row_fields(row):
        hist_value = _field_value(field)
        hist_alias = _field_name(raw_field_id)
        if _has_value(hist_value):
            value_key = _value_key(hist_value)
            candidate_targets: list[Target] = []
            for alias in aliases:
                candidate_targets.extend(by_exact.get((section, alias, hist_alias, value_key), []))
            candidate_targets = list({t.key: t for t in candidate_targets if t.kind == "field"}.values())
            mode = "entity-field-value-exact"
            if not candidate_targets:
                unique_candidates: dict[str, Target] = {}
                for alias in aliases:
                    rows = by_unique_value.get((section, alias, value_key), [])
                    for target in rows:
                        if target.kind == "field":
                            unique_candidates[target.key] = target
                if len(unique_candidates) == 1:
                    candidate_targets = list(unique_candidates.values())
                    mode = "entity-unique-value-exact"
            if candidate_targets:
                atomic = _evidence_rows(field, archive=archive, version=version, member=member, match_mode=mode, origin="ARCHIVE_RECOVERED")
                hist_conf = field.get("confidence") if isinstance(field, Mapping) else None
                for target in candidate_targets:
                    _history_observation(lineage, target, archive=archive, version=version, member=member, has_atomic=bool(atomic), has_context=bool(row_context), match_mode=mode)
                    if atomic:
                        _add_match(matches, target, atomic, mode=mode, archive=archive, version=version, member=member, historical_confidence=hist_conf)
                        stats["field_matches"] += 1
                    elif row_context:
                        _add_match(matches, target, row_context, mode="entity-context-corroboration", archive=archive, version=version, member=member, historical_confidence=hist_conf)
                        stats["context_matches"] += 1
        # Atomic item matching is preferred for list-valued fields.
        for hist_item in _field_items(field):
            hist_item_value = hist_item.get("value")
            if not _has_value(hist_item_value):
                continue
            item_key = _value_key(hist_item_value)
            candidates = []
            for alias in aliases:
                candidates.extend(by_exact.get((section, alias, hist_alias, item_key), []))
            candidates = list({t.key: t for t in candidates if t.kind == "item"}.values())
            mode = "entity-field-item-exact"
            if not candidates:
                unique_candidates: dict[str, Target] = {}
                for alias in aliases:
                    for target in by_unique_value.get((section, alias, item_key), []):
                        if target.kind == "item":
                            unique_candidates[target.key] = target
                if len(unique_candidates) == 1:
                    candidates = list(unique_candidates.values())
                    mode = "entity-unique-item-exact"
            if not candidates:
                continue
            atomic = _evidence_rows(hist_item, archive=archive, version=version, member=member, match_mode=mode, origin="ARCHIVE_RECOVERED")
            # Some old structures stored one field-level source for a one-item field.
            if not atomic and len(_field_items(field)) == 1:
                atomic = _evidence_rows(field, archive=archive, version=version, member=member, match_mode=mode, origin="ARCHIVE_RECOVERED")
            hist_conf = hist_item.get("confidence")
            for target in candidates:
                _history_observation(lineage, target, archive=archive, version=version, member=member, has_atomic=bool(atomic), has_context=bool(row_context), match_mode=mode)
                if atomic:
                    _add_match(matches, target, atomic, mode=mode, archive=archive, version=version, member=member, historical_confidence=hist_conf)
                    stats["item_matches"] += 1
                elif row_context:
                    _add_match(matches, target, row_context, mode="entity-context-corroboration", archive=archive, version=version, member=member, historical_confidence=hist_conf)
                    stats["context_matches"] += 1


def _scan_json_document(
    document: Any, *, archive: str, version: str, member: str,
    by_exact: Mapping[tuple[str, str, str, str], list[Target]],
    by_unique_value: Mapping[tuple[str, str, str], list[Target]],
    matches: dict[str, dict[str, Any]], lineage: dict[str, Any], classifications: dict[str, dict[str, Any]],
    name_classifications: dict[str, dict[str, Any]], stats: dict[str, int],
) -> None:
    stats["json_documents"] += 1
    for section, row, _json_path in _iter_section_rows(document):
        stats["historical_rows"] += 1
        _process_historical_row(
            section, row, archive=archive, version=version, member=member,
            by_exact=by_exact, by_unique_value=by_unique_value,
            matches=matches, lineage=lineage, stats=stats,
        )
    for source_row, source_path in _iter_source_registry(document):
        url = _normalize_url(_pick(source_row, ("url", "href", "link", "source_url")))
        if not url:
            continue
        raw_class = _pick(source_row, ("class", "type", "source_type", "classification", "authority", "tier"))
        origin, source_type = _classification_origin(raw_class)
        candidate = {
            "url": url,
            "provenance_origin": origin,
            "source_type": source_type,
            "historical_archive": archive,
            "historical_version": version,
            "historical_path": f"{member}:{source_path}",
            "historical_class": raw_class,
        }
        previous = classifications.get(url)
        rank = {"PUBLIC_PRIMARY": 3, "PUBLIC_SECONDARY": 2, "DISCOVERY_ONLY": 1, "UNKNOWN": 0}
        if previous is None or rank.get(origin, 0) > rank.get(str(previous.get("provenance_origin")), 0):
            classifications[url] = candidate
        source_name = str(_pick(source_row, ("name", "source", "title", "publisher", "provider")) or "").strip()
        name_key = canonical(source_name)
        if name_key:
            named = dict(candidate)
            named["historical_source_name"] = source_name
            existing_named = name_classifications.get(name_key)
            if existing_named is None:
                name_classifications[name_key] = named
            elif existing_named.get("provenance_origin") != origin:
                # Ambiguous source names are retained as UNKNOWN rather than guessed.
                name_classifications[name_key] = {"provenance_origin": "UNKNOWN", "ambiguous": True, "historical_source_name": source_name}
        stats["source_registry_rows"] += 1


def _scan_zip_handle(
    zf: zipfile.ZipFile, *, archive_name: str, version: str, depth: int,
    by_exact: Mapping[tuple[str, str, str, str], list[Target]],
    by_unique_value: Mapping[tuple[str, str, str], list[Target]],
    matches: dict[str, dict[str, Any]], lineage: dict[str, Any], classifications: dict[str, dict[str, Any]],
    name_classifications: dict[str, dict[str, Any]], stats: dict[str, int],
) -> None:
    if depth > 2:
        return
    for info in zf.infolist():
        if info.is_dir() or info.file_size <= 0 or info.file_size > 120_000_000:
            continue
        member = info.filename.replace("\\", "/")
        lower = member.casefold()
        if lower.endswith(".json"):
            try:
                payload = zf.read(info)
            except (OSError, RuntimeError, zipfile.BadZipFile):
                continue
            document = _decode_json(payload)
            if document is not None:
                _scan_json_document(
                    document, archive=archive_name, version=version, member=member,
                    by_exact=by_exact, by_unique_value=by_unique_value,
                    matches=matches, lineage=lineage, classifications=classifications, name_classifications=name_classifications, stats=stats,
                )
        elif lower.endswith(".zip") and info.file_size <= 80_000_000:
            try:
                nested = zf.read(info)
            except (OSError, RuntimeError, zipfile.BadZipFile):
                continue
            stats["nested_archives"] += 1
            _scan_zip_bytes(
                nested, archive_name=f"{archive_name}::{member}", version=version, depth=depth + 1,
                by_exact=by_exact, by_unique_value=by_unique_value,
                matches=matches, lineage=lineage, classifications=classifications, name_classifications=name_classifications, stats=stats,
            )


def _scan_zip_bytes(
    raw: bytes, *, archive_name: str, version: str, depth: int,
    by_exact: Mapping[tuple[str, str, str, str], list[Target]],
    by_unique_value: Mapping[tuple[str, str, str], list[Target]],
    matches: dict[str, dict[str, Any]], lineage: dict[str, Any], classifications: dict[str, dict[str, Any]],
    name_classifications: dict[str, dict[str, Any]], stats: dict[str, int],
) -> None:
    if depth > 2:
        return
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            _scan_zip_handle(
                zf, archive_name=archive_name, version=version, depth=depth,
                by_exact=by_exact, by_unique_value=by_unique_value,
                matches=matches, lineage=lineage, classifications=classifications, name_classifications=name_classifications, stats=stats,
            )
    except zipfile.BadZipFile:
        return

def _pptx_text_and_links(path: Path) -> Iterator[tuple[int, str, list[str]]]:
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        return
    with zf:
        slide_names = sorted(
            [name for name in zf.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)],
            key=lambda x: int(re.search(r"slide(\d+)\.xml", x).group(1)),
        )
        for slide_name in slide_names:
            number = int(re.search(r"slide(\d+)\.xml", slide_name).group(1))
            try:
                root = ET.fromstring(zf.read(slide_name))
            except (ET.ParseError, KeyError):
                continue
            text = " ".join((node.text or "") for node in root.iter() if node.tag.endswith("}t") and (node.text or "").strip())
            rel_name = slide_name.replace("ppt/slides/", "ppt/slides/_rels/") + ".rels"
            links: list[str] = []
            if rel_name in zf.namelist():
                try:
                    rel_root = ET.fromstring(zf.read(rel_name))
                    for rel in rel_root.iter():
                        target = rel.attrib.get("Target", "")
                        if rel.attrib.get("TargetMode") == "External" and target.startswith(("http://", "https://")):
                            links.append(target)
                except ET.ParseError:
                    pass
            yield number, text, list(dict.fromkeys(links))


def _report_corroboration(directory: Path, targets: Mapping[str, Target], matches: dict[str, dict[str, Any]], lineage: dict[str, Any], stats: dict[str, int]) -> None:
    # Report exports are contextual fallback only. They never close a gap.
    report_targets = [target for target in targets.values() if target.kind == "item" and target.item_value_key]
    for path in sorted(directory.glob("*.pptx")):
        if not _is_business_intelligence_name(path.name):
            continue
        version = _archive_version(path.name)
        for slide_no, text, links in _pptx_text_and_links(path):
            blob = canonical(text)
            if not blob:
                continue
            for target in report_targets:
                entity_token = canonical(target.entity)
                try:
                    item_text = json.loads(target.item_value_key or '""')
                except json.JSONDecodeError:
                    item_text = target.item_value_key or ""
                if isinstance(item_text, (dict, list)):
                    continue
                value_token = canonical(item_text)
                if len(value_token) < 3 or entity_token not in blob or value_token not in blob:
                    continue
                sources_match = re.search(r"(?i)fuentes?\s*[:·-]\s*(.{0,500})", text)
                source_names = sources_match.group(1).strip() if sources_match else ""
                evidence = {
                    "source": f"Informe histórico Westcon · {version}",
                    "title": f"{path.name} · diapositiva {slide_no}",
                    "url": links[0] if links else "",
                    "description": (
                        "El informe histórico contiene la misma entidad y el mismo valor. "
                        "Se conserva como corroboración de contexto, no como evidencia atómica suficiente."
                        + (f" Fuentes mostradas en la diapositiva: {source_names}" if source_names else "")
                    ),
                    "provenance_origin": "REPORT_CORROBORATION",
                    "historical_report": path.name,
                    "historical_version": version,
                    "slide": slide_no,
                    "source_names": source_names,
                    "method": "historical-report-corroboration",
                }
                _add_match(matches, target, [evidence], mode="report-exact-text-corroboration", archive=path.name, version=version, member=f"slide-{slide_no}")
                _history_observation(lineage, target, archive=path.name, version=version, member=f"slide-{slide_no}", has_atomic=False, has_context=True, match_mode="report-exact-text-corroboration")
                stats["report_corroborations"] += 1


def _summarize_lineage(lineage: dict[str, Any]) -> None:
    semver = re.compile(r"^\d+\.\d+\.\d+[a-z]?$", re.I)
    for item in lineage.values():
        observations = list(item.get("observations") or [])
        observations.sort(key=lambda x: (_version_sort_key(str(x.get("version") or "")), str(x.get("archive") or "")))
        item["observations"] = observations
        known = [x for x in observations if semver.match(str(x.get("version") or ""))]
        unknown = [x for x in observations if x not in known]
        basis = known or observations
        if basis:
            item["first_seen"] = basis[0].get("version")
            item["latest_seen"] = basis[-1].get("version")
            with_atomic = [x for x in basis if x.get("atomic_evidence")]
            item["last_with_atomic_evidence"] = with_atomic[-1].get("version") if with_atomic else None
            first_without = next((x for x in basis if not x.get("atomic_evidence")), None)
            item["first_seen_without_atomic_evidence"] = first_without.get("version") if first_without else None
        item["unversioned_snapshots"] = [x.get("archive") for x in unknown]


def build_archive_registry(
    data: Mapping[str, Any], archives_dir: Path,
    *, alias_config: Mapping[str, Any] | None = None, include_reports: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    targets = build_targets(data, alias_config)
    _by_entity, by_exact, by_unique_value = _target_indexes(targets)
    matches: dict[str, dict[str, Any]] = {}
    lineage: dict[str, Any] = {}
    classifications: dict[str, dict[str, Any]] = {}
    name_classifications: dict[str, dict[str, Any]] = {}
    stats = {
        "targets": len(targets), "archives_found": 0, "archives_scanned": 0, "archive_errors": 0,
        "json_documents": 0, "historical_rows": 0, "nested_archives": 0,
        "field_matches": 0, "item_matches": 0, "context_matches": 0,
        "source_registry_rows": 0, "report_corroborations": 0,
    }
    archives = discover_archives(archives_dir)
    stats["archives_found"] = len(archives)
    archive_rows = []
    for path in archives:
        version = _archive_version(path.name)
        archive_rows.append({"file": path.name, "version": version, "bytes": path.stat().st_size})
        try:
            with zipfile.ZipFile(path) as zf:
                _scan_zip_handle(
                    zf, archive_name=path.name, version=version, depth=0,
                    by_exact=by_exact, by_unique_value=by_unique_value,
                    matches=matches, lineage=lineage, classifications=classifications, name_classifications=name_classifications, stats=stats,
                )
            stats["archives_scanned"] += 1
        except (OSError, RuntimeError, zipfile.BadZipFile):
            stats["archive_errors"] += 1
    if include_reports:
        _report_corroboration(archives_dir, targets, matches, lineage, stats)
    _summarize_lineage(lineage)
    registry = {
        "version": "4.0.3",
        "generated_at": _now(),
        "policy": "Business Intelligence corpus only; exact-value historical provenance; never import historical values",
        "archive_directory_name": archives_dir.name,
        "archives": archive_rows,
        "matches": list(matches.values()),
        "url_classifications": classifications,
        "source_name_classifications": name_classifications,
        "stats": stats,
    }
    lineage_doc = {
        "version": "4.0.3",
        "generated_at": _now(),
        "targets": lineage,
        "stats": {
            "targets_observed": len(lineage),
            "targets_with_atomic_history": sum(1 for row in lineage.values() if row.get("last_with_atomic_evidence")),
        },
    }
    return registry, lineage_doc


def load_archive_registry(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path else REGISTRY_PATH
    if not target.exists():
        return {"version": "4.0.3", "matches": [], "url_classifications": {}, "stats": {}}
    try:
        return json.loads(target.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {"version": "4.0.3", "matches": [], "url_classifications": {}, "stats": {}}


def _current_index(data: Mapping[str, Any]) -> dict[tuple[str, str], Mapping[str, Any]]:
    result: dict[tuple[str, str], Mapping[str, Any]] = {}
    for section in SECTIONS:
        for row in data.get(section) or []:
            if not isinstance(row, Mapping):
                continue
            name = str(row.get("name") or "")
            for alias in _entity_aliases(name):
                result[(section, alias)] = row
    return result


def _remove_legacy_if_sufficient(container: dict[str, Any]) -> bool:
    evidence = [row for row in container.get("evidence") or [] if isinstance(row, Mapping)]
    if not any(typed_evidence_sufficient(row) for row in evidence):
        return False
    filtered = [dict(row) for row in evidence if provenance_kind(row) != "LEGACY_UNRESOLVED"]
    if len(filtered) != len(evidence):
        container["evidence"] = dedupe_evidence(filtered)
    # Clear only v4.0.2 legacy-forced decorations; normalization can rebuild presentation metadata.
    if "Origen histórico conservado" in str(container.get("confidence_reason") or "") or "histórico preservado" in str(container.get("qualifier") or "").casefold():
        for key in ("confidence", "confidence_band", "fact_confidence", "interpretation_confidence", "action_risk", "evidence_level", "evidence_color", "confidence_reason", "qualifier"):
            container.pop(key, None)
    return True


def _classify_unknown_evidence(
    container: dict[str, Any], classifications: Mapping[str, Any], name_classifications: Mapping[str, Any]
) -> int:
    changed = 0
    rows = container.get("evidence") or []
    if not isinstance(rows, list):
        return 0
    for evidence in rows:
        if not isinstance(evidence, dict) or provenance_kind(evidence) != "UNKNOWN":
            continue
        url = _normalize_url(evidence.get("url"))
        classification = classifications.get(url) if url else None
        if not isinstance(classification, Mapping):
            source_key = canonical(evidence.get("source") or evidence.get("title") or "")
            classification = name_classifications.get(source_key) if source_key else None
        if not isinstance(classification, Mapping) or classification.get("ambiguous"):
            continue
        origin = str(classification.get("provenance_origin") or "UNKNOWN")
        if origin == "UNKNOWN":
            continue
        evidence["provenance_origin"] = origin
        evidence.setdefault("source_type", classification.get("source_type"))
        evidence["historical_source_classification"] = classification.get("historical_class")
        evidence["historical_archive"] = classification.get("historical_archive")
        evidence["historical_version"] = classification.get("historical_version")
        evidence["historical_path"] = classification.get("historical_path")
        changed += 1
    return changed


def apply_archive_provenance(data: dict[str, Any], registry: Mapping[str, Any] | None = None) -> dict[str, int]:
    """Apply a prebuilt archive registry without ever mutating current values."""
    registry = registry or load_archive_registry()
    stats = {
        "field_evidence_added": 0, "item_evidence_added": 0, "legacy_resolved": 0,
        "unknown_classified": 0, "registry_matches_checked": 0, "value_guard_skips": 0,
    }
    index = _current_index(data)
    classifications = registry.get("url_classifications") or {}
    name_classifications = registry.get("source_name_classifications") or {}
    for section in SECTIONS:
        for row in data.get(section) or []:
            if not isinstance(row, dict):
                continue
            for field in (row.get("fields") or {}).values():
                if not isinstance(field, dict):
                    continue
                stats["unknown_classified"] += _classify_unknown_evidence(field, classifications, name_classifications)
                for item in field.get("items") or []:
                    if isinstance(item, dict):
                        stats["unknown_classified"] += _classify_unknown_evidence(item, classifications, name_classifications)
    for match in registry.get("matches") or []:
        if not isinstance(match, Mapping):
            continue
        stats["registry_matches_checked"] += 1
        section = str(match.get("section") or "")
        entity = str(match.get("entity") or "")
        row = None
        for alias in _entity_aliases(entity):
            row = index.get((section, alias))
            if row is not None:
                break
        if not isinstance(row, dict):
            continue
        field_id = str(match.get("field") or "")
        field = ((row.get("fields") or {}).get(field_id) or {})
        if not isinstance(field, dict) or not _has_value(field.get("value")):
            continue
        if _stable_hash(field.get("value")) != str(match.get("value_hash") or ""):
            stats["value_guard_skips"] += 1
            continue
        evidence = [dict(ev) for ev in match.get("evidence") or [] if isinstance(ev, Mapping)]
        item_hash = match.get("item_value_hash")
        if item_hash:
            target_item = None
            for item in field.get("items") or []:
                if isinstance(item, dict) and _has_value(item.get("value")) and _stable_hash(item.get("value")) == item_hash:
                    target_item = item
                    break
            if target_item is None:
                stats["value_guard_skips"] += 1
                continue
            before = len(target_item.get("evidence") or [])
            target_item["evidence"] = dedupe_evidence(list(target_item.get("evidence") or []) + evidence)
            stats["item_evidence_added"] += max(0, len(target_item["evidence"]) - before)
            if _remove_legacy_if_sufficient(target_item):
                stats["legacy_resolved"] += 1
        else:
            before = len(field.get("evidence") or [])
            field["evidence"] = dedupe_evidence(list(field.get("evidence") or []) + evidence)
            stats["field_evidence_added"] += max(0, len(field["evidence"]) - before)
            if _remove_legacy_if_sufficient(field):
                stats["legacy_resolved"] += 1
    return stats


def archive_registry_summary(registry: Mapping[str, Any] | None = None) -> dict[str, Any]:
    registry = registry or load_archive_registry()
    matches = [row for row in registry.get("matches") or [] if isinstance(row, Mapping)]
    evidence = [ev for row in matches for ev in row.get("evidence") or [] if isinstance(ev, Mapping)]
    return {
        "policy": registry.get("policy") or "exact-value historical archive provenance",
        "archives_scanned": int((registry.get("stats") or {}).get("archives_scanned") or 0),
        "historical_matches": len(matches),
        "archive_evidences": len(evidence),
        "archive_atomic_evidences": sum(1 for ev in evidence if provenance_kind(ev) == "ARCHIVE_RECOVERED"),
        "archive_context_corroborations": sum(1 for ev in evidence if provenance_kind(ev) in NON_SUFFICIENT_ORIGINS),
        "url_classifications": len(registry.get("url_classifications") or {}),
        "source_name_classifications": len(registry.get("source_name_classifications") or {}),
        "generated_at": registry.get("generated_at"),
    }
