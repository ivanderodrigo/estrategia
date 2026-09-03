"""Claim/evidence support model for Westcon Decision Intelligence v4.2.2.

Policy:
- External facts require current public evidence.
- Current, claim-scoped Westcon first-party material may accredit Westcon-owned portfolio/capability/service facts.
- Historical Westcon deck/portfolio and recovered lineage are research hints only.
- Derived/internal Westcon conclusions are not searched literally on the web.
  They require traceable derivation from supported inputs.
- Historical/curated/inferred knowledge is preserved while support is pending.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping
import json

from .knowledge_provenance import accrediting_evidence, discovery_only, provenance_kind
from .settings import SECTIONS, VERSION

HISTORICAL_KINDS = {
    "HISTORICAL_RECOVERED",
    "ARCHIVE_RECOVERED",
    "ARCHIVE_CORROBORATION",
    "REPORT_CORROBORATION",
    "LEGACY_UNRESOLVED",
}
ANALYST_NAMES = (
    "gartner", "forrester", "idc", "omdia", "canalys", "isg",
    "gigaom", "451 research", "synergy research",
)

# Conservative list: only fields whose semantics are clearly Westcon-internal
# transformations are moved out of literal public-web verification.
DERIVED_FIELDS: dict[tuple[str, str], dict[str, Any]] = {
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


def claim_policy(section: str, field: str, column: Mapping[str, Any] | None = None) -> dict[str, Any]:
    policy = DERIVED_FIELDS.get((str(section), str(field)))
    declared_class = str((column or {}).get("claim_class") or "")
    if policy is None and declared_class in {"DERIVED_FACT", "INTERNAL_CLASSIFICATION"}:
        policy = {
            "claim_class": declared_class,
            "rule": str((column or {}).get("derivation_rule") or "derived from supported canonical inputs"),
            "dependency_fields": list((column or {}).get("dependency_fields") or []),
        }
    if policy:
        return {
            "claim_class": policy["claim_class"],
            "rule": policy["rule"],
            "dependency_fields": list(policy.get("dependency_fields") or []),
            "research_mode": "derive-from-supported-inputs",
        }
    return {
        "claim_class": "EXTERNAL_FACT",
        "rule": "direct support required",
        "dependency_fields": [],
        "research_mode": "public-source-verification",
    }


def _url(ev: Mapping[str, Any]) -> str:
    return str(ev.get("url") or "").strip()


def is_historical(ev: Mapping[str, Any]) -> bool:
    return provenance_kind(ev) in HISTORICAL_KINDS


def is_westcon_document(ev: Mapping[str, Any]) -> bool:
    return provenance_kind(ev) == "WESTCON_DOCUMENT"


def is_current_public(ev: Mapping[str, Any]) -> bool:
    return (
        not is_historical(ev)
        and not discovery_only(ev)
        and accrediting_evidence(ev)
        and _url(ev).startswith(("http://", "https://"))
    )


def is_current_westcon(ev: Mapping[str, Any]) -> bool:
    return (
        provenance_kind(ev) in {"WESTCON_DOCUMENT_CURRENT", "WESTCON_FIRST_PARTY_CURRENT"}
        and not discovery_only(ev)
        and accrediting_evidence(ev)
    )


def support_basis(rows: Iterable[Mapping[str, Any]]) -> str:
    evidence = [row for row in rows if isinstance(row, Mapping)]
    has_public = any(is_current_public(ev) for ev in evidence)
    has_westcon = any(is_current_westcon(ev) for ev in evidence)
    if has_public and has_westcon:
        return "WESTCON_AND_PUBLIC"
    if has_westcon:
        return "WESTCON_DOCUMENT_CURRENT"
    if has_public:
        return "CURRENT_PUBLIC"
    return "SEARCH_REQUIRED"


def _analyst(ev: Mapping[str, Any]) -> bool:
    blob = " ".join(
        str(ev.get(key) or "")
        for key in ("source", "title", "source_type", "classification", "url")
    ).casefold()
    return any(name in blob for name in ANALYST_NAMES)


def source_tier(ev: Mapping[str, Any]) -> str:
    kind = provenance_kind(ev)
    if kind in {"WESTCON_DOCUMENT_CURRENT", "WESTCON_FIRST_PARTY_CURRENT"}:
        return "A1"
    if kind in {"WESTCON_DOCUMENT", "RESEARCH_SEED"}:
        return "H"
    if is_historical(ev):
        return "H"
    if is_current_public(ev) and _analyst(ev):
        return "B"
    if is_current_public(ev):
        if ev.get("official") is True or str(ev.get("source_grade") or "").startswith("A"):
            return "A2"
        return "C"
    if kind == "CURATED":
        return "D"
    if kind == "INFERENCE":
        return "I"
    return "U"


def source_role(tier: str) -> str:
    return {
        "A1": "Fuente Westcon vigente",
        "A2": "Fuente primaria externa",
        "B": "Inteligencia especializada",
        "C": "Fuente pública secundaria",
        "D": "Curación interna no acreditativa",
        "I": "Inferencia no acreditativa",
        "H": "Histórico / linaje",
        "U": "Procedencia sin clasificar",
    }.get(tier, "Procedencia sin clasificar")


def _annotate(rows: Iterable[dict[str, Any]], basis: str) -> Counter[str]:
    stats: Counter[str] = Counter()
    for ev in rows:
        if not isinstance(ev, dict):
            continue
        tier = source_tier(ev)
        ev["intelligence_tier"] = tier
        ev["source_role"] = source_role(tier)
        stats[f"tier_{tier}"] += 1
        if tier == "H":
            stats["historical_total"] += 1
            if basis == "WESTCON_AND_PUBLIC":
                ev["revalidation_status"] = "supported-by-westcon-and-public"
                stats["historical_supported_westcon_and_public"] += 1
            elif basis == "CURRENT_PUBLIC":
                ev["revalidation_status"] = "supported-by-current-public"
                stats["historical_supported_public"] += 1
            elif basis == "WESTCON_DOCUMENT_CURRENT":
                ev["revalidation_status"] = "supported-by-current-westcon"
                stats["historical_supported_westcon"] += 1
            else:
                ev["revalidation_status"] = "support-pending"
                stats["historical_search_required"] += 1
    return stats


def _claim_key(
    section: str,
    entity: Any,
    field: str,
    level: str,
    value: Any,
) -> str:
    return json.dumps(
        [section, entity, field, level, value],
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )


def rationalize_sources(data: dict[str, Any]) -> dict[str, Any]:
    total: Counter[str] = Counter()
    target_stats: Counter[str] = Counter()
    unresolved: list[dict[str, Any]] = []
    unique_unresolved: dict[str, dict[str, Any]] = {}

    for section in SECTIONS:
        schema = {
            str(column.get("id")): column
            for column in (data.get("schemas") or {}).get(section, [])
            if isinstance(column, Mapping) and column.get("id")
        }
        for row in data.get(section) or []:
            if not isinstance(row, dict):
                continue

            row_evidence = [
                ev for ev in row.get("evidence") or []
                if isinstance(ev, dict)
            ]
            delta = _annotate(row_evidence, support_basis(row_evidence))
            total.update(delta)

            for field_id, field in (row.get("fields") or {}).items():
                if not isinstance(field, dict):
                    continue

                policy = claim_policy(section, field_id, schema.get(str(field_id)))
                items = [
                    item for item in field.get("items") or []
                    if isinstance(item, dict)
                    and item.get("value") not in (None, "", [], {})
                ]
                targets = (
                    [(item, "item") for item in items]
                    if items
                    else (
                        [(field, "field")]
                        if field.get("value") not in (None, "", [], {})
                        else []
                    )
                )

                for target, level in targets:
                    value = target.get("value")
                    evidence = [
                        ev for ev in target.get("evidence") or []
                        if isinstance(ev, dict)
                    ]
                    basis = support_basis(evidence)
                    delta = _annotate(evidence, basis)
                    total.update(delta)

                    target_stats["targets_total"] += 1
                    target_stats[f"claim_{policy['claim_class']}"] += 1

                    if basis != "SEARCH_REQUIRED":
                        target_stats["targets_direct_supported"] += 1
                        target_stats[f"supported_{basis}"] += 1
                        continue

                    target_stats["targets_support_pending_occurrences"] += 1
                    if policy["claim_class"] == "EXTERNAL_FACT":
                        target_stats["external_search_required_occurrences"] += 1
                        expected_gap_kind = "evidence-support"
                    else:
                        target_stats["derived_support_required_occurrences"] += 1
                        expected_gap_kind = "derivation-support"

                    record = {
                        "section": section,
                        "entity": row.get("name"),
                        "field": field_id,
                        "level": level,
                        "value": value,
                        "claim_class": policy["claim_class"],
                        "research_mode": policy["research_mode"],
                        "derivation_rule": policy["rule"],
                        "dependency_fields": policy["dependency_fields"],
                        "support_basis": "SEARCH_REQUIRED",
                        "expected_gap_kind": expected_gap_kind,
                        "preserve_value": True,
                    }
                    unresolved.append(record)
                    unique_unresolved.setdefault(
                        _claim_key(
                            section,
                            row.get("name"),
                            field_id,
                            level,
                            value,
                        ),
                        record,
                    )

    duplicate_occurrences = len(unresolved) - len(unique_unresolved)
    external_unique = sum(
        1 for row in unique_unresolved.values()
        if row["claim_class"] == "EXTERNAL_FACT"
    )
    derived_unique = len(unique_unresolved) - external_unique

    return {
        "version": VERSION,
        "model_revision": "r6-public-plus-current-westcon-first-party",
        "policy": (
            "Hechos externos: fuente pública actual. Hechos propiedad de Westcon sobre portfolio/capacidades: "
            "documentación o regla Westcon vigente y atómica. Histórico: pista no acreditativa. "
            "Conclusiones internas/derivadas: inputs sustentados + regla trazable."
        ),
        "support_rule": "CURRENT_PUBLIC_OR_CURRENT_WESTCON_OWNED_OR_TRACEABLE_DERIVATION",
        "targets_total": target_stats["targets_total"],
        "targets_direct_supported": target_stats["targets_direct_supported"],
        "targets_supported_westcon_only": target_stats["supported_WESTCON_DOCUMENT_CURRENT"],
        "targets_supported_public_only": target_stats["supported_CURRENT_PUBLIC"],
        "targets_supported_westcon_and_public": target_stats["supported_WESTCON_AND_PUBLIC"],
        "claim_classes": {
            "EXTERNAL_FACT": target_stats["claim_EXTERNAL_FACT"],
            "DERIVED_FACT": target_stats["claim_DERIVED_FACT"],
            "INTERNAL_CLASSIFICATION": target_stats["claim_INTERNAL_CLASSIFICATION"],
        },
        "support_pending_occurrences": len(unresolved),
        "support_pending_unique_claims": len(unique_unresolved),
        "duplicate_pending_occurrences": duplicate_occurrences,
        "external_search_required_occurrences": target_stats[
            "external_search_required_occurrences"
        ],
        "external_search_required_unique": external_unique,
        "derived_support_required_occurrences": target_stats[
            "derived_support_required_occurrences"
        ],
        "derived_support_required_unique": derived_unique,
        "historical_total": total["historical_total"],
        "historical_supported_westcon": total["historical_supported_westcon"],
        "historical_supported_public": total["historical_supported_public"],
        "historical_supported_westcon_and_public": total[
            "historical_supported_westcon_and_public"
        ],
        "historical_search_required": total["historical_search_required"],
        # Compatibility with r2 output.
        "targets_supported": target_stats["targets_direct_supported"],
        "targets_search_required": len(unresolved),
        "unsupported_targets": unresolved,
        "unsupported_unique_targets": list(unique_unresolved.values()),
    }
