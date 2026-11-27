"""Strict provenance gate for published distributor/integrator vendor claims.

An official page is not automatically proof of every manufacturer in the
company's linecard. The public green badge needs an item-bound, atomic source.
The historical source archive is separate and never discarded by this gate.
"""
from __future__ import annotations

from typing import Any

from .knowledge_provenance import accrediting_evidence
from .model import canonical


VENDOR_RELATION_FIELDS = frozenset({
    "vendor_relations", "manufacturer_relations", "vendor_partnerships",
    "linecard_remainder", "westcon_overlap", "competitor_vendor_overlap",
})
_EXACT_BINDINGS = frozenset({"claim-specific", "atomic-item"})


def exact_vendor_source(evidence: dict[str, Any], field_name: str, value: str) -> bool:
    """Require an accredited atomic citation for *this* field and vendor."""
    return (
        isinstance(evidence, dict)
        and accrediting_evidence(evidence)
        and evidence.get("atomic") is True
        and str(evidence.get("source_binding") or "").casefold() in _EXACT_BINDINGS
        and str(evidence.get("field") or "") == field_name
        and bool(canonical(value))
        and canonical(evidence.get("item_value")) == canonical(value)
    )
