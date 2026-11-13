"""Review EVERY displayed historical claim against the current canonical dataset.

This is an atomic inventory, not a blanket accreditation. It records the
exact historical value, its old URLs, and whether an individual current
source has already passed normal typed-provenance rules. Unmatched claims
remain queued; old URL availability by itself never establishes truth.
"""
from __future__ import annotations

import json
from collections import Counter
from typing import Any

from .knowledge_provenance import accrediting_evidence
from .model import canonical
from .settings import SECTIONS
from .storage import json_bytes


def _existing_atomic_proof(field: dict[str, Any], value: Any) -> list[str]:
    raw_values = field.get("value")
    values = raw_values if isinstance(raw_values, list) else [raw_values]
    if not any(canonical(v) == canonical(value) for v in values):
        return []
    if isinstance(raw_values, list):
        match = next((item for item in field.get("items") or []
                      if canonical(item.get("value")) == canonical(value)), None)
        evidence = (match or {}).get("evidence") or []
    else:
        evidence = field.get("evidence") or []
    return list(dict.fromkeys(
        str(ev.get("url") or ev.get("document") or ev.get("document_id"))
        for ev in evidence if accrediting_evidence(ev)
        and ev.get("field") in (None, "", field.get("_audit_field_id"))
        and (ev.get("item_value") in (None, "") or canonical(ev["item_value"]) == canonical(value))
        and (ev.get("url") or ev.get("document") or ev.get("document_id"))
    ))


def audit_historical_claims(data: dict[str, Any], sidecars: dict[str, bytes],
                            generated_at: str) -> tuple[bytes, dict[str, Any]]:
    index = {
        section: {canonical(row.get("name")): row for row in data.get(section) or []
                  if isinstance(row, dict)}
        for section in SECTIONS
    }
    reviewed: list[dict[str, Any]] = []
    counts = Counter()
    for section in SECTIONS:
        raw = sidecars.get(f"data/public/historical/current/{section}.json")
        if not raw:
            continue
        payload = json.loads(raw)
        for entity, fields in (payload.get("entities") or {}).items():
            row = index.get(section, {}).get(canonical(entity))
            for field_id, records in fields.items():
                field = dict(((row or {}).get("fields") or {}).get(field_id) or {})
                field["_audit_field_id"] = field_id
                for record in records:
                    value = record.get("value")
                    proof = _existing_atomic_proof(field, value)
                    status = ("ACREDITADO_CON_FUENTE_ACTUAL" if proof
                              else "PENDIENTE_DE_CONTRASTAR_AFIRMACION")
                    counts[status] += 1
                    counts["reviewed_" + section] += 1
                    reviewed.append({
                        "section": section, "entity": (row or {}).get("name") or entity,
                        "field": field_id, "value": value,
                        "status": status,
                        "current_evidence_urls": proof[:5],
                        "historical_urls": list(record.get("urls") or []),
                    })
    output = {
        "generated_at": generated_at,
        "review_policy": "Atomic claim/value matching against accredited current evidence; historical URLs alone never confer accreditation.",
        "reviewed": len(reviewed),
        "accredited_existing": counts["ACREDITADO_CON_FUENTE_ACTUAL"],
        "pending_revalidation": counts["PENDIENTE_DE_CONTRASTAR_AFIRMACION"],
        "by_section": {sec: counts["reviewed_" + sec] for sec in SECTIONS},
        "claims": reviewed,
    }
    summary = {k: v for k, v in output.items() if k != "claims"}
    return json_bytes(output), summary
