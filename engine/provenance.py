"""Atomic provenance policy.

A list item may only show evidence that supports that exact item. Relationship
evidence must bind both endpoints, textually or through exact atomic metadata.
Broad catalogues never support an arbitrary neighbour merely because they say
"vendors", "partners" or similar collection words.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from .model import canonical

GEOGRAPHIC_WORDS = {"spain", "espana", "portugal", "iberia", "iberica", "iberico"}
GENERIC_SUFFIXES = {"advanced", "solutions"}
NON_ACCREDITING_BINDINGS = {"discovery-only"}
ACCREDITING_ATOMIC_BINDINGS = {"claim-specific", "atomic-item", "entity-owned-item"}


def entity_aliases(raw: Any) -> set[str]:
    text = str(raw or "")
    candidates = {canonical(text)}
    candidates.update(canonical(part) for part in re.split(r"[/|]", text))
    candidates.update(canonical(part) for part in re.findall(r"\(([^)]+)\)", text))
    for candidate in tuple(candidates):
        words = candidate.split()
        for ignored in (GEOGRAPHIC_WORDS, GEOGRAPHIC_WORDS | GENERIC_SUFFIXES):
            reduced = " ".join(word for word in words if word not in ignored)
            if reduced:
                candidates.add(reduced)
    return {candidate for candidate in candidates if len(candidate) >= 2}


def _mentioned(blob: str, alias: str) -> bool:
    return f" {alias} " in f" {blob} "


def _matches_entity(raw: Any, entity: Any) -> bool:
    probe = canonical(raw)
    if not probe:
        return False
    return any(probe == alias or _mentioned(probe, alias) for alias in entity_aliases(entity))


def _evidence_blob(evidence: dict[str, Any]) -> str:
    return canonical(
        " ".join(
            str(evidence.get(key) or "")
            for key in (
                "source", "source_catalog_name", "title", "description", "url",
                "researched_entity", "item_value",
            )
        )
    )


def _dedupe(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for evidence in rows:
        if not isinstance(evidence, dict):
            continue
        key = (
            str(evidence.get("url") or ""),
            str(evidence.get("title") or ""),
            str(evidence.get("scope") or ""),
            canonical(evidence.get("item_value") or ""),
        )
        unique[key] = evidence
    return list(unique.values())


def evidence_for_item(
    evidence_rows: Iterable[dict[str, Any]],
    owner: Any,
    value: Any,
    *,
    field_id: str = "",
) -> list[dict[str, Any]]:
    """Keep only evidence that supports this exact owner / field / value."""
    owner_aliases = entity_aliases(owner)
    value_aliases = entity_aliases(value)
    chosen: list[dict[str, Any]] = []

    for evidence in evidence_rows:
        if not isinstance(evidence, dict):
            continue

        binding = str(evidence.get("source_binding") or "").strip().casefold()
        ev_field = str(evidence.get("field") or "")
        if field_id and ev_field and ev_field != field_id:
            continue

        item_value = evidence.get("item_value")
        researched_entity = evidence.get("researched_entity")
        item_match = bool(item_value) and _matches_entity(item_value, value)
        owner_meta_match = bool(researched_entity) and _matches_entity(researched_entity, owner)

        # Typed Westcon/internal documentary lineage is deliberately non-public,
        # but an already-atomic field/item association must survive normalization.
        # This preserves traceability without allowing it to accredit web claims.
        origin = str(evidence.get("provenance_origin") or "").strip().upper()
        source_type = str(evidence.get("source_type") or evidence.get("type") or "").strip().casefold()
        typed_document_atomic = (
            bool(field_id)
            and item_match
            and evidence.get("atomic") is True
            and (not ev_field or ev_field == field_id)
            and (
                origin in {"WESTCON_DOCUMENT", "WESTCON_DOCUMENT_CURRENT", "WESTCON_FIRST_PARTY_CURRENT"}
                or source_type in {"westcon-document", "internal-document", "user-provided", "curated-westcon"}
            )
        )
        if typed_document_atomic:
            chosen.append(evidence)
            continue

        if evidence.get("accrediting") is False:
            continue
        if binding in NON_ACCREDITING_BINDINGS:
            continue

        if item_match and owner_meta_match:
            chosen.append(evidence)
            continue
        if (
            item_match
            and binding in ACCREDITING_ATOMIC_BINDINGS
            and (not researched_entity or owner_meta_match)
        ):
            chosen.append(evidence)
            continue

        blob = _evidence_blob(evidence)
        owner_match = any(_mentioned(blob, alias) for alias in owner_aliases)
        value_match = any(_mentioned(blob, alias) for alias in value_aliases)

        if owner_match and value_match:
            chosen.append(evidence)
            continue

        # Owner can be implicit only for an entity-owned source. The exact item
        # must still be explicit in the source/snippet.
        if binding == "entity-owned" and value_match:
            chosen.append(evidence)

    return _dedupe(chosen)


def evidence_for_relationship(
    evidence_rows: Iterable[dict[str, Any]], owner: Any, value: Any
) -> list[dict[str, Any]]:
    """Strict endpoint binding shared by normalisation, graph, preservation and QA."""
    return evidence_for_item(evidence_rows, owner, value)


def infer_scope_from_text(text: Any) -> str:
    blob = f" {canonical(text)} "
    es = " spain " in blob or " espana " in blob
    pt = " portugal " in blob
    iberia = " iberia " in blob or " iberica " in blob or " iberico " in blob
    if iberia or (es and pt):
        return "IBERIA"
    if es:
        return "ES"
    if pt:
        return "PT"
    return "GLOBAL"


def evidence_scopes(evidence_rows: Iterable[dict[str, Any]]) -> list[str]:
    """Derive relationship geography from evidence, never from the entity row."""
    result: list[str] = []
    for evidence in evidence_rows:
        if not isinstance(evidence, dict):
            continue
        provenance = str(evidence.get("scope_provenance") or "").casefold()
        declared = str(evidence.get("scope") or "").upper()
        if provenance in {"explicit-text", "claim-specific", "curated-claim"} and declared in {
            "ES", "PT", "IBERIA", "GLOBAL"
        }:
            scope = declared
        else:
            scope = infer_scope_from_text(
                " ".join(
                    str(evidence.get(key) or "")
                    for key in ("title", "description", "url")
                )
            )
        if scope not in result:
            result.append(scope)
    non_global = [scope for scope in result if scope != "GLOBAL"]
    return non_global or ["GLOBAL"]
