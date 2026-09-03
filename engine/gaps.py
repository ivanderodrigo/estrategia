"""Strict, stateful gap accounting for every declared public field."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Mapping
from urllib.parse import urlparse

from .settings import SECTIONS, VERSION
from .gap_intelligence import enrich_gap_report
from .knowledge_provenance import accrediting_evidence, provenance_kind, typed_evidence_sufficient
from .relationship_revalidation import relationship_revalidation_debt


PLACEHOLDERS = {
    "", "-", "--", "—", "n/d", "nd", "pendiente", "pendiente de evidencia",
    "por investigar", "en investigacion", "en investigación",
}
IDENTITY_FIELDS = {"scope", "domain", "entity_type", "notice_id", "source_portal", "index_universe"}


def norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().casefold())


def has_value(value: Any) -> bool:
    if value is None or value is False or value == [] or value == {}:
        return False
    return not isinstance(value, str) or norm(value) not in PLACEHOLDERS


def evidence_rows(field: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = [row for row in field.get("evidence") or [] if isinstance(row, Mapping)]
    for item in field.get("items") or []:
        if isinstance(item, Mapping):
            rows.extend(row for row in item.get("evidence") or [] if isinstance(row, Mapping))
    return rows


def complete_evidence(evidence: Mapping[str, Any]) -> bool:
    # A public URL is valid evidence, but a typed primary Westcon/user document is too.
    # LEGACY_UNRESOLVED is visible provenance but never sufficient to close a gap.
    return typed_evidence_sufficient(evidence)


def evidence_sufficient(field: Mapping[str, Any]) -> bool:
    if not has_value(field.get("value")):
        return False
    rows = [row for row in evidence_rows(field) if complete_evidence(row)]
    if not rows:
        return False
    claim_type = str(field.get("claim_type") or "fact")
    if claim_type in {"signal", "interpretation"} and not field.get("assertion_status"):
        return False
    official = any(
        row.get("official") is True
        or str(row.get("source_grade") or "").startswith("A")
        or "official" in str(row.get("source_type") or row.get("type") or "").casefold()
        for row in rows
    )
    independent = {
        (
            str(row.get("source") or "").casefold(),
            urlparse(str(row.get("url") or "")).netloc.casefold().removeprefix("www."),
        )
        for row in rows
    }
    return official or len(independent) >= 2


HISTORICAL_KINDS = {
    "HISTORICAL_RECOVERED", "ARCHIVE_RECOVERED", "ARCHIVE_CORROBORATION",
    "REPORT_CORROBORATION", "LEGACY_UNRESOLVED",
}

DERIVED_SUPPORT_FIELDS = {
    ("clients_public", "westcon_fit"): {
        "claim_class": "DERIVED_FACT",
        "rule": "client signals/needs ∩ supported Westcon portfolio/capabilities",
        "dependency_fields": ["technology_signals"],
    },
    ("clients_private", "westcon_fit"): {
        "claim_class": "DERIVED_FACT",
        "rule": "client signals/needs ∩ supported Westcon portfolio/capabilities",
        "dependency_fields": ["technology_signals"],
    },
    ("clients_public", "westcon_area"): {
        "claim_class": "INTERNAL_CLASSIFICATION",
        "rule": "supported client technology signals → Westcon area taxonomy",
        "dependency_fields": ["technology_signals"],
    },
    ("clients_private", "westcon_area"): {
        "claim_class": "INTERNAL_CLASSIFICATION",
        "rule": "supported client technology signals → Westcon area taxonomy",
        "dependency_fields": ["technology_signals"],
    },
    ("trends", "westcon_vendors"): {
        "claim_class": "DERIVED_FACT",
        "rule": "supported trend/vendor evidence ∩ supported Westcon portfolio",
        "dependency_fields": ["market_players"],
    },
}


def _claim_policy(section: str, field_id: str, column: Mapping[str, Any] | None = None) -> dict[str, Any]:
    value = DERIVED_SUPPORT_FIELDS.get((section, field_id))
    declared_class = str((column or {}).get("claim_class") or "")
    if value is None and declared_class in {"DERIVED_FACT", "INTERNAL_CLASSIFICATION"}:
        value = {
            "claim_class": declared_class,
            "rule": str((column or {}).get("derivation_rule") or "derived from supported canonical inputs"),
            "dependency_fields": list((column or {}).get("dependency_fields") or []),
        }
    if value:
        return {
            "claim_class": value["claim_class"],
            "rule": value["rule"],
            "dependency_fields": list(value["dependency_fields"]),
            "gap_kind": "derivation-support",
            "research_mode": "derive-from-supported-inputs",
        }
    return {
        "claim_class": "EXTERNAL_FACT",
        "rule": "direct support required",
        "dependency_fields": [],
        "gap_kind": "evidence-support",
        "research_mode": "public-source-verification",
    }


def _historical_rows(rows: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [row for row in rows if provenance_kind(row) in HISTORICAL_KINDS]


def _internal_hint_rows(rows: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [
        row for row in rows
        if provenance_kind(row) in HISTORICAL_KINDS | {"RESEARCH_SEED", "WESTCON_DOCUMENT"}
    ]


def _current_public_rows(rows: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [
        row for row in rows
        if provenance_kind(row) not in HISTORICAL_KINDS
        and str(row.get("url") or "").startswith(("http://", "https://"))
        and accrediting_evidence(row)
    ]


def _support_rows(rows: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    # HF7: external facts are accredited only by current public evidence.
    return _current_public_rows(rows)


def _target_values(value: Any) -> list[Any]:
    if value in (None, "", [], {}):
        return []
    return list(value) if isinstance(value, list) else [value]


def _revalidation_seeds(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output = []
    seen = set()
    for ev in rows:
        url = str(ev.get("url") or "").strip()
        if not url.startswith(("http://", "https://")) or url in seen:
            continue
        seen.add(url)
        output.append({
            "url": url,
            "official": bool(ev.get("official")),
            "source_grade": str(ev.get("source_grade") or "B"),
            "source_name": str(ev.get("source") or ev.get("title") or "Fuente histórica"),
        })
    return output


def _append_support_gaps(
    public: Mapping[str, Any],
    gaps: list[dict[str, Any]],
    missing: Counter[tuple[str, str]],
    critical: Counter[str],
    states: Counter[str],
    state_gaps: Mapping[str, Any],
) -> tuple[int, int, int]:
    evidence_added = 0
    derivation_added = 0
    historical_added = 0
    existing = {str(gap.get("id") or "") for gap in gaps}

    for section in SECTIONS:
        schema_rows = (public.get("schemas") or {}).get(section, [])
        schema = {
            column.get("id"): column
            for column in schema_rows
            if column.get("id")
        }

        for row in public.get(section) or []:
            fields = row.get("fields") or {}
            # IMPORTANT r3: union(schema, actual populated fields).
            # This fixes orphan claims such as TD SYNNEX verticals that existed
            # in intelligence but were absent from the section schema.
            field_ids = list(dict.fromkeys(
                list(schema.keys()) + list(fields.keys())
            ))

            for field_id in field_ids:
                field = fields.get(field_id) or {}
                if not isinstance(field, Mapping) or not has_value(field.get("value")):
                    continue

                column = schema.get(field_id) or {
                    "id": field_id,
                    "label": field_id,
                    "decision_required": False,
                }
                if column.get("virtual"):
                    continue
                policy = _claim_policy(section, field_id, column)
                targets = []
                items = [
                    item for item in field.get("items") or []
                    if isinstance(item, Mapping)
                ]

                if items:
                    for item in items:
                        if not has_value(item.get("value")):
                            continue
                        rows = [
                            ev for ev in item.get("evidence") or []
                            if isinstance(ev, Mapping)
                        ]
                        if _support_rows(rows):
                            continue
                        targets.append(("item", item.get("value"), _internal_hint_rows(rows)))
                else:
                    rows = [
                        ev for ev in field.get("evidence") or []
                        if isinstance(ev, Mapping)
                    ]
                    if not _support_rows(rows):
                        targets.append(("field", field.get("value"), _internal_hint_rows(rows)))

                for level, value, historical in targets:
                    signature = hashlib.sha1(
                        json.dumps(
                            value,
                            ensure_ascii=False,
                            sort_keys=True,
                            default=str,
                        ).encode("utf-8")
                    ).hexdigest()[:12]
                    effective_gap_kind = (
                        "public-validation"
                        if policy["gap_kind"] == "evidence-support" and bool(historical)
                        else policy["gap_kind"]
                    )
                    gap_id = (
                        f"{section}:{norm(row.get('name'))}:{field_id}:"
                        f"{effective_gap_kind}:{signature}"
                    )
                    if gap_id in existing:
                        continue
                    existing.add(gap_id)

                    history = state_gaps.get(gap_id) or {}
                    priority = 1 if column.get("decision_required") else 2
                    has_historical = bool(historical)
                    is_derived = policy["gap_kind"] == "derivation-support"

                    gaps.append({
                        "id": gap_id,
                        "section": section,
                        "entity": row.get("name"),
                        "entity_id": row.get("id"),
                        "field": field_id,
                        "country_context": _scope(row),
                        "research_state": (
                            "Pendiente de validación pública"
                            if effective_gap_kind == "public-validation"
                            else "Por investigar"
                        ),
                        "priority": priority,
                        "reason": (
                            "conclusión interna preservada; requiere derivación trazable "
                            "desde inputs sustentados"
                            if is_derived else
                            "hecho externo preservado como pista interna/histórica; requiere fuente pública actual"
                        ),
                        "gap_kind": effective_gap_kind,
                        "claim_class": policy["claim_class"],
                        "research_mode": policy["research_mode"],
                        "support_requirement": (
                            "TRACEABLE_DERIVATION_FROM_SUPPORTED_INPUTS"
                            if is_derived else
                            "CURRENT_PUBLIC_ONLY"
                        ),
                        "target_level": level,
                        "target_values": _target_values(value),
                        "preserve_value": True,
                        "historical_lineage_present": has_historical,
                        "revalidation_seeds": (
                            [] if is_derived else _revalidation_seeds(historical)
                        ),
                        "derivation_rule": policy["rule"],
                        "dependency_fields": policy["dependency_fields"],
                        "attempts_completed": int(history.get("attempts") or 0),
                        "accepted_evidences": int(history.get("accepted") or 0),
                        "consecutive_no_yield": int(history.get("consecutive_no_yield") or 0),
                        "next_pass": int(history.get("next_pass") or 1),
                        "next_due_at": history.get("next_due_at"),
                        "last_attempt_at": history.get("last_attempt_at"),
                        "last_error": history.get("last_error") or "",
                        "close_policy": (
                            "Conservar el valor y cerrarlo solo cuando exista una derivación "
                            "reproducible desde inputs con soporte final."
                            if is_derived else
                            "Conservar el valor/pista y cerrarlo solo cuando el mismo dato quede "
                            "sustentado por una fuente pública actual."
                        ),
                        "strategy_profile": (
                            "traceable-derived-support"
                            if is_derived else
                            "evidence-support-public-verification"
                        ),
                        "retry_policy": "persistent-backoff-with-circuit-breaker",
                    })
                    states[(
                        "Pendiente de validación pública"
                        if effective_gap_kind == "public-validation"
                        else "Por investigar"
                    )] += 1
                    missing[(section, field_id)] += 1
                    critical[section] += int(priority == 1)
                    historical_added += int(has_historical)
                    if is_derived:
                        derivation_added += 1
                    else:
                        evidence_added += 1

    return evidence_added, derivation_added, historical_added

def _scope(row: Mapping[str, Any]) -> str:
    value = (((row.get("fields") or {}).get("scope") or {}).get("value"))
    return " / ".join(map(str, value)) if isinstance(value, list) else str(value or "ES / PT")


def _semantic_gap_value(value: Any) -> str:
    if isinstance(value, str):
        return "text:" + norm(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))


def _append_registry_validation_gaps(
    public: Mapping[str, Any],
    gaps: list[dict[str, Any]],
    missing: Counter[tuple[str, str]],
    critical: Counter[str],
    states: Counter[str],
    state_gaps: Mapping[str, Any],
) -> int:
    """Make surviving registry-only research clues actionable without treating them as proof.

    Most seeds stay attached to their field/item and are already handled by
    ``_append_support_gaps``. This pass covers clues preserved in HF8's internal registry when a
    canonical build detached their presentation metadata. It never recreates a missing value.
    """
    existing_targets: set[tuple[str, str, str, str]] = set()
    for gap in gaps:
        for value in gap.get("target_values") or []:
            existing_targets.add((
                str(gap.get("section") or ""),
                norm(gap.get("entity") or ""),
                str(gap.get("field") or ""),
                _semantic_gap_value(value),
            ))

    added = 0
    for record in public.get("research_seed_registry") or []:
        if not isinstance(record, Mapping):
            continue
        section = str(record.get("section") or "")
        field_id = str(record.get("field") or "")
        value = record.get("value")
        if section not in SECTIONS or not field_id or value in (None, "", [], {}):
            continue
        wanted_entity = norm(record.get("entity") or record.get("entity_key") or "")
        row = next((
            candidate for candidate in public.get(section) or []
            if isinstance(candidate, Mapping)
            and wanted_entity in {
                norm(candidate.get("name") or ""), norm(candidate.get("id") or "")
            }
        ), None)
        if not isinstance(row, Mapping):
            continue
        field = ((row.get("fields") or {}).get(field_id) or {})
        if not isinstance(field, Mapping):
            continue

        raw = field.get("value")
        values = raw if isinstance(raw, list) else ([] if raw in (None, "", [], {}) else [raw])
        actual = next((candidate for candidate in values if _semantic_gap_value(candidate) == _semantic_gap_value(value)), None)
        if actual is None:
            continue

        rows: list[Mapping[str, Any]] = []
        if isinstance(raw, list):
            item = next((
                item for item in field.get("items") or []
                if isinstance(item, Mapping) and _semantic_gap_value(item.get("value")) == _semantic_gap_value(actual)
            ), None)
            if isinstance(item, Mapping):
                rows.extend(ev for ev in item.get("evidence") or [] if isinstance(ev, Mapping))
            else:
                rows.extend(ev for ev in field.get("evidence") or [] if isinstance(ev, Mapping))
        else:
            rows.extend(ev for ev in field.get("evidence") or [] if isinstance(ev, Mapping))
        if _support_rows(rows):
            continue

        entity_name = str(row.get("name") or row.get("id") or record.get("entity") or "")
        target_key = (section, norm(entity_name), field_id, _semantic_gap_value(actual))
        if target_key in existing_targets:
            continue
        signature = hashlib.sha1(_semantic_gap_value(actual).encode("utf-8")).hexdigest()[:12]
        gap_id = f"{section}:{norm(entity_name)}:{field_id}:public-validation-registry:{signature}"
        history = state_gaps.get(gap_id) or {}
        schema_column = next((
            column for column in ((public.get("schemas") or {}).get(section) or [])
            if isinstance(column, Mapping) and str(column.get("id") or "") == field_id
        ), {})
        priority = 1 if schema_column.get("decision_required") else 2
        gaps.append({
            "id": gap_id,
            "section": section,
            "entity": entity_name,
            "entity_id": row.get("id"),
            "field": field_id,
            "country_context": _scope(row),
            "research_state": "Pendiente de validación pública",
            "priority": priority,
            "reason": "pista histórica/interna preservada en memoria; requiere fuente pública actual",
            "gap_kind": "public-validation",
            "claim_class": "EXTERNAL_FACT",
            "research_mode": "public-source-verification",
            "support_requirement": "CURRENT_PUBLIC_ONLY",
            "target_level": "registry",
            "target_values": [actual],
            "preserve_value": True,
            "historical_lineage_present": True,
            "revalidation_seeds": [],
            "derivation_rule": "direct support required",
            "dependency_fields": [],
            "attempts_completed": int(history.get("attempts") or 0),
            "accepted_evidences": int(history.get("accepted") or 0),
            "consecutive_no_yield": int(history.get("consecutive_no_yield") or 0),
            "next_pass": int(history.get("next_pass") or 1),
            "next_due_at": history.get("next_due_at"),
            "last_attempt_at": history.get("last_attempt_at"),
            "last_error": history.get("last_error") or "",
            "close_policy": "Conservar la pista y cerrar solo cuando el mismo dato tenga evidencia pública actual.",
            "strategy_profile": "evidence-support-public-verification",
            "retry_policy": "persistent-backoff-with-circuit-breaker",
            "seed_registry": True,
        })
        existing_targets.add(target_key)
        states["Pendiente de validación pública"] += 1
        missing[(section, field_id)] += 1
        critical[section] += int(priority == 1)
        added += 1
    return added


def validate_gap_state_contract(report: Mapping[str, Any]) -> list[str]:
    """Validate HF8's richer open-gap states before legacy quality compatibility mapping."""
    errors: list[str] = []
    allowed = {"Por investigar", "Pendiente de validación pública"}
    for gap in report.get("gaps") or []:
        if not isinstance(gap, Mapping):
            errors.append("gap no estructurado")
            continue
        state = str(gap.get("research_state") or "")
        kind = str(gap.get("gap_kind") or "")
        if state not in allowed:
            errors.append(f"estado abierto no permitido: {state or '<vacío>'}")
            continue
        if kind == "public-validation" and state != "Pendiente de validación pública":
            errors.append(f"public-validation con estado incompatible: {gap.get('id')}")
        if kind != "public-validation" and state == "Pendiente de validación pública":
            errors.append(f"estado de validación pública usado fuera de public-validation: {gap.get('id')}")
    declared_public = int(report.get("public_validation_gaps") or 0)
    actual_public = sum(1 for gap in report.get("gaps") or [] if isinstance(gap, Mapping) and gap.get("gap_kind") == "public-validation")
    if declared_public != actual_public:
        errors.append(f"contador public_validation_gaps inconsistente: {declared_public}!={actual_public}")
    return errors


def build_gaps(
    public: Mapping[str, Any],
    version: str = VERSION,
    research_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    state_gaps = ((research_state or {}).get("gaps") or {}) if isinstance(research_state, Mapping) else {}
    gaps: list[dict[str, Any]] = []
    missing: Counter[tuple[str, str]] = Counter()
    critical: Counter[str] = Counter()
    states: Counter[str] = Counter()
    expected: Counter[str] = Counter()
    populated: Counter[str] = Counter()

    for section in SECTIONS:
        schema = {
            column.get("id"): column
            for column in (public.get("schemas") or {}).get(section, [])
            if column.get("id")
        }
        for row in public.get(section) or []:
            fields = row.get("fields") or {}
            for field_id, column in schema.items():
                if column.get("virtual"):
                    continue
                expected[section] += 1
                field = fields.get(field_id) or {}
                value_ok = has_value(field.get("value"))
                populated[section] += int(value_ok)
                if value_ok and evidence_sufficient(field):
                    continue

                # Populated claims are audited atomically below. Keeping a second
                # field-level gap would double-count the same research debt and,
                # for derived claims, could accidentally route it to web research.
                if value_ok:
                    continue

                reason = "valor pendiente" if not value_ok else "evidencia o trazabilidad insuficiente"
                priority = 1 if column.get("decision_required") else 2
                gap_id = f"{section}:{norm(row.get('name'))}:{field_id}"
                history = state_gaps.get(gap_id) or {}
                states["Por investigar"] += 1
                missing[(section, field_id)] += 1
                critical[section] += int(priority == 1)
                policy = _claim_policy(section, field_id, column)
                gap = {
                    "id": gap_id,
                    "section": section,
                    "entity": row.get("name"),
                    "entity_id": row.get("id"),
                    "field": field_id,
                    "country_context": _scope(row),
                    "research_state": "Por investigar",
                    "priority": priority,
                    "reason": reason,
                    "gap_kind": policy["gap_kind"] if policy["gap_kind"] == "derivation-support" else "standard",
                    "claim_class": policy["claim_class"],
                    "research_mode": policy["research_mode"],
                    "derivation_rule": policy["rule"],
                    "dependency_fields": policy["dependency_fields"],
                    "attempts_completed": int(history.get("attempts") or 0),
                    "accepted_evidences": int(history.get("accepted") or 0),
                    "consecutive_no_yield": int(history.get("consecutive_no_yield") or 0),
                    "next_pass": int(history.get("next_pass") or 1),
                    "next_due_at": history.get("next_due_at"),
                    "last_attempt_at": history.get("last_attempt_at"),
                    "last_error": history.get("last_error") or "",
                    "close_policy": (
                        "Solo cerrar con valor y evidencia pública suficiente. "
                        "PPT/portfolio/histórico conservan la pista pero no acreditan el hecho; una señal no se convierte en hecho."
                    ),
                    "strategy_profile": "adaptive-source-cascade",
                    "retry_policy": "persistent-backoff-with-circuit-breaker",
                }
                gaps.append(gap)

    evidence_support_gaps, derivation_support_gaps, historical_revalidation_gaps = _append_support_gaps(
        public, gaps, missing, critical, states, state_gaps
    )
    research_seed_registry_gaps = _append_registry_validation_gaps(
        public, gaps, missing, critical, states, state_gaps
    )
    business_priority = enrich_gap_report(gaps, public)
    gaps.sort(key=lambda item: (
        {"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(str(item.get("priority_tier") or "P3"), 3),
        -float(item.get("priority_score") or 0),
        item["priority"], item["section"], norm(item["entity"]), item["field"]
    ))
    by_section = {section: sum(1 for gap in gaps if gap["section"] == section) for section in SECTIONS}
    coverage = {
        section: {
            "expected_fields": expected[section],
            "populated_fields": populated[section],
            "value_completeness_pct": round(populated[section] * 100 / max(1, expected[section]), 2),
            "open_gaps": by_section[section],
            "critical_gaps": critical[section],
        }
        for section in SECTIONS
    }
    return {
        "version": version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "definition": (
            "Todo campo declarado cuenta. Los hechos externos solo cierran con evidencia pública actual. "
            "PPT, portfolio e histórico se conservan como pistas internas y generan deuda de validación pública, no acreditación."
        ),
        "total_gaps": len(gaps),
        "historical_revalidation_gaps": historical_revalidation_gaps,
        "research_seed_registry_gaps": research_seed_registry_gaps,
        "evidence_support_gaps": evidence_support_gaps,
        "derivation_support_gaps": derivation_support_gaps,
        "support_model": "DIRECT_OR_TRACEABLE_DERIVATION",
        "support_rule": "CURRENT_PUBLIC_ONLY",
        "public_validation_gaps": sum(1 for gap in gaps if gap.get("gap_kind") == "public-validation"),
        "unknown_research_gaps": sum(1 for gap in gaps if gap.get("research_state") == "Por investigar"),
        "business_priority": business_priority,
        "critical_gaps": sum(critical.values()),
        "high_priority_gaps": sum(critical.values()),
        "by_section": by_section,
        "critical_by_section": dict(critical),
        "missing_by_field": {f"{section}.{field}": count for (section, field), count in missing.most_common()},
        "research_states": dict(states),
        "coverage": coverage,
        "engine": {
            "strategy_profile": "business-value-x-researchability",
            "priority_model": "P0-P3 with source playbooks and section fairness",
            "plan_storage": "normalized and generated on demand",
            "languages": ["es", "pt", "en"],
            "profiles": ["daily", "deep", "exhaustive"],
            "retries": "profile-aware exponential backoff",
            "circuit_breaker_failures": 5,
            "checkpointing": "atomic and durable",
            "incremental": True,
            "resume": True,
            "failure_isolation": "per-source and per-entity",
            "contradiction_policy": "signals never promote automatically to facts",
            "learning_state": "data/current/research_state.json",
            "ledger": "data/current/research_ledger.json",
        },
        "gaps": gaps,
        "relationship_revalidation_debt": relationship_revalidation_debt(state_gaps),
        "relationship_revalidation_debt_total": len(relationship_revalidation_debt(state_gaps)),
    }
