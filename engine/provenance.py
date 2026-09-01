"""Relationship-level provenance scoping.

The public UI must never answer a question about one list item with evidence belonging
to its neighbours.  This module is the single policy used by migration and graph build.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from .model import canonical


COLLECTION_MARKERS = (
    "catalog", "directorio", "directory", "line card", "linecard",
    "fabricantes", "marcas", "brands", "partners",
)
GEOGRAPHIC_WORDS = {"spain", "espana", "portugal", "iberia", "iberica", "iberico"}
GENERIC_SUFFIXES = {"advanced", "solutions"}


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


def evidence_for_relationship(
    evidence_rows: Iterable[dict[str, Any]], owner: Any, value: Any
) -> list[dict[str, Any]]:
    """Keep evidence that names both endpoints, or a scoped line-card source.

    Exact relationship assertions win over broad catalogues.  This is what makes a click
    on ``1Password → Ingram Micro`` show the 1Password assertion rather than every Ingram
    source carried by an old field.
    """

    owner_aliases = entity_aliases(owner)
    value_aliases = entity_aliases(value)
    exact: list[dict[str, Any]] = []
    collection: list[dict[str, Any]] = []
    for evidence in evidence_rows:
        if not isinstance(evidence, dict):
            continue
        blob = canonical(
            " ".join(
                str(evidence.get(key) or "")
                for key in ("source", "title", "description", "url")
            )
        )
        owner_match = any(_mentioned(blob, alias) for alias in owner_aliases)
        value_match = any(_mentioned(blob, alias) for alias in value_aliases)
        if owner_match and value_match:
            exact.append(evidence)
        elif (owner_match or value_match) and any(marker in blob for marker in COLLECTION_MARKERS):
            collection.append(evidence)

    chosen = exact or collection
    unique: dict[tuple[str, str, str], dict[str, Any]] = {}
    for evidence in chosen:
        key = (
            str(evidence.get("url") or ""),
            str(evidence.get("title") or ""),
            str(evidence.get("scope") or ""),
        )
        unique[key] = evidence
    return list(unique.values())
