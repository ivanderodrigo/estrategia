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
from .knowledge_provenance import provenance_kind, typed_evidence_sufficient
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


def _historical_rows(rows: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [row for row in rows if provenance_kind(row) in HISTORICAL_KINDS]


def _current_open_rows(rows: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [
        row for row in rows
        if provenance_kind(row) not in HISTORICAL_KINDS
        and str(row.get("url") or "").startswith(("http://", "https://"))
    ]


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


def _append_historical_revalidation_gaps(
    public: Mapping[str, Any],
    gaps: list[dict[str, Any]],
    missing: Counter[tuple[str, str]],
    critical: Counter[str],
    states: Counter[str],
    state_gaps: Mapping[str, Any],
) -> int:
    added = 0
    existing = {str(gap.get("id") or "") for gap in gaps}
    for section in SECTIONS:
        schema = {
            column.get("id"): column
            for column in (public.get("schemas") or {}).get(section, [])
            if column.get("id")
        }
        for row in public.get(section) or []:
            fields = row.get("fields") or {}
            for field_id, column in schema.items():
                field = fields.get(field_id) or {}
                if not isinstance(field, Mapping) or not has_value(field.get("value")):
                    continue
                item_rows = [item for item in field.get("items") or [] if isinstance(item, Mapping)]
                targets = []
                for item in item_rows:
                    rows = [ev for ev in item.get("evidence") or [] if isinstance(ev, Mapping)]
                    historical = _historical_rows(rows)
                    if historical and not _current_open_rows(rows):
                        targets.append(("item", item.get("value"), historical))
                field_rows = [ev for ev in field.get("evidence") or [] if isinstance(ev, Mapping)]
                field_historical = _historical_rows(field_rows)
                if field_historical and not _current_open_rows(field_rows) and not targets:
                    targets.append(("field", field.get("value"), field_historical))

                for level, value, historical in targets:
                    signature = hashlib.sha1(
                        json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
                    ).hexdigest()[:12]
                    gap_id = f"{section}:{norm(row.get('name'))}:{field_id}:h:{signature}"
                    if gap_id in existing:
                        continue
                    existing.add(gap_id)
                    history = state_gaps.get(gap_id) or {}
                    priority = 1 if column.get("decision_required") else 2
                    gaps.append({
                        "id": gap_id,
                        "section": section,
                        "entity": row.get("name"),
                        "entity_id": row.get("id"),
                        "field": field_id,
                        "country_context": _scope(row),
                        "research_state": "Por investigar",
                        "priority": priority,
                        "reason": "procedencia histórica pendiente de revalidación con fuente abierta actual",
                        "gap_kind": "historical-revalidation",
                        "target_level": level,
                        "target_values": _target_values(value),
                        "revalidation_seeds": _revalidation_seeds(historical),
                        "attempts_completed": int(history.get("attempts") or 0),
                        "accepted_evidences": int(history.get("accepted") or 0),
                        "consecutive_no_yield": int(history.get("consecutive_no_yield") or 0),
                        "next_pass": int(history.get("next_pass") or 1),
                        "next_due_at": history.get("next_due_at"),
                        "last_attempt_at": history.get("last_attempt_at"),
                        "last_error": history.get("last_error") or "",
                        "close_policy": (
                            "Una H solo se considera sustentada cuando una búsqueda actual encuentra "
                            "una fuente abierta pública para el mismo dato."
                        ),
                        "strategy_profile": "historical-open-source-revalidation",
                        "retry_policy": "persistent-backoff-with-circuit-breaker",
                    })
                    states["Por investigar"] += 1
                    missing[(section, field_id)] += 1
                    critical[section] += int(priority == 1)
                    added += 1
    return added


def _scope(row: Mapping[str, Any]) -> str:
    value = (((row.get("fields") or {}).get("scope") or {}).get("value"))
    return " / ".join(map(str, value)) if isinstance(value, list) else str(value or "ES / PT")


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
                expected[section] += 1
                field = fields.get(field_id) or {}
                value_ok = has_value(field.get("value"))
                populated[section] += int(value_ok)
                if value_ok and evidence_sufficient(field):
                    continue

                reason = "valor pendiente" if not value_ok else "evidencia o trazabilidad insuficiente"
                priority = 1 if column.get("decision_required") else 2
                gap_id = f"{section}:{norm(row.get('name'))}:{field_id}"
                history = state_gaps.get(gap_id) or {}
                states["Por investigar"] += 1
                missing[(section, field_id)] += 1
                critical[section] += int(priority == 1)
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
                    "attempts_completed": int(history.get("attempts") or 0),
                    "accepted_evidences": int(history.get("accepted") or 0),
                    "consecutive_no_yield": int(history.get("consecutive_no_yield") or 0),
                    "next_pass": int(history.get("next_pass") or 1),
                    "next_due_at": history.get("next_due_at"),
                    "last_attempt_at": history.get("last_attempt_at"),
                    "last_error": history.get("last_error") or "",
                    "close_policy": (
                        "Solo cerrar con valor y evidencia suficiente: web pública o documento tipado. "
                        "LEGACY_UNRESOLVED conserva el dato pero mantiene el gap abierto; una señal no se convierte en hecho."
                    ),
                    "strategy_profile": "adaptive-source-cascade",
                    "retry_policy": "persistent-backoff-with-circuit-breaker",
                }
                gaps.append(gap)

    historical_revalidation_gaps = _append_historical_revalidation_gaps(
        public, gaps, missing, critical, states, state_gaps
    )
    gaps.sort(key=lambda item: (item["priority"], item["section"], norm(item["entity"]), item["field"]))
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
            "Todo campo declarado cuenta. Un valor solo cierra el gap con evidencia tipada suficiente; "
            "toda procedencia H conserva el linaje pero exige búsqueda abierta actual para quedar sustentada."
        ),
        "total_gaps": len(gaps),
        "historical_revalidation_gaps": historical_revalidation_gaps,
        "critical_gaps": sum(critical.values()),
        "high_priority_gaps": sum(critical.values()),
        "by_section": by_section,
        "critical_by_section": dict(critical),
        "missing_by_field": {f"{section}.{field}": count for (section, field), count in missing.most_common()},
        "research_states": dict(states),
        "coverage": coverage,
        "engine": {
            "strategy_profile": "adaptive-source-cascade",
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
