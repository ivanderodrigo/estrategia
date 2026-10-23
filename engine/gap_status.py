"""Business-readable classification of research debt, without changing gate semantics.

Technical research_state remains unchanged for planner compatibility.
The public-facing status is separate, reasoned and auditable.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Mapping


def classify_gap(gap: Mapping[str, Any]) -> tuple[str, str]:
    kind = str(gap.get("gap_kind") or "")
    attempts = max(0, int(gap.get("attempts_completed") or 0))
    accepted = max(0, int(gap.get("accepted_evidences") or 0))
    historical = bool(gap.get("historical_lineage_present"))
    last_attempt = str(gap.get("last_attempt_at") or "").strip()
    last_error = str(gap.get("last_error") or "").strip()
    if kind == "derivation-support":
        return "derivation-pending", "Requiere calcularse desde datos acreditados; no corresponde buscarlo directamente en la web."
    if kind == "public-validation" or historical:
        return "historical-validation", "Existe una pista o valor histórico que requiere acreditación pública; no debe tratarse como dato vigente confirmado."
    if attempts > 0 and accepted == 0 and last_error:
        return "source-unavailable", "La última búsqueda no consiguió una fuente válida; se conserva el trabajo anterior."
    if attempts > 0 and accepted == 0:
        return "not-found", "No se ha encontrado soporte suficiente en los intentos registrados."
    if attempts > 0 and accepted > 0:
        return "insufficient-support", "Se recogieron evidencias, pero todavía no acreditan el dato requerido."
    if last_attempt:
        return "not-found", "Existe un intento registrado, sin información pública suficiente para cerrar el campo."
    return "not-researched", "Pendiente de una búsqueda documentada."


def annotate_public_states(gaps: list[dict[str, Any]]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    by_section: dict[str, Counter[str]] = {}
    for gap in gaps:
        state, reason = classify_gap(gap)
        gap["public_status"] = state
        gap["public_status_reason"] = reason
        section = str(gap.get("section") or "unknown")
        counts[state] += 1
        by_section.setdefault(section, Counter())[state] += 1
    return {
        "version": 1,
        "defined_at": datetime.now(timezone.utc).isoformat(),
        "total": len(gaps),
        "by_status": dict(sorted(counts.items())),
        "by_section": {k: dict(sorted(v.items())) for k, v in sorted(by_section.items())},
        "note": "Open research tasks, not missing cells. A field may produce multiple tasks. Completeness, integrity and freshness are different measures.",
    }
