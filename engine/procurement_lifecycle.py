"""Public-tender lifecycle, separate from historical contract intelligence.

Keep expired tender evidence in the canonical store for traceability; only
exclude it from the active opportunity projection. Never guess a deadline.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any


CLOSED_STATUSES = ("closed", "expired", "cancelled", "canceled", "awarded",
                   "adjudicado", "adjudicada", "desierto", "anulado", "anulada",
                   "encerrado", "adjudicado", "cancelado")


def deadline_date(raw: Any) -> date | None:
    if isinstance(raw, (list, tuple)):
        raw = raw[0] if raw else None
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        if len(text) >= 10 and text[4] == "-" and text[7] == "-":
            return date.fromisoformat(text[:10])
        if "/" in text:
            return datetime.strptime(text[:10], "%d/%m/%Y").date()
    except (ValueError, TypeError):
        return None
    return None


def public_tender_active(row: dict[str, Any], today: date | None = None) -> bool:
    fields = row.get("fields") or {}
    stamp = deadline_date((fields.get("milestone_date") or {}).get("value"))
    status = str((fields.get("procurement_stage") or {}).get("value") or "").casefold()
    if any(term in status for term in CLOSED_STATUSES):
        return False
    today = today or datetime.now(timezone.utc).date()
    return stamp is None or stamp >= today


def is_identified_tender(row: dict[str, Any]) -> bool:
    """A public client is NOT a procurement notice without an exact notice ID."""
    fields = row.get("fields") or {}
    value = (fields.get("notice_id") or {}).get("value")
    if isinstance(value, list):
        value = next((item for item in value if isinstance(item, str) and item.strip()), "")
    raw = str(value or "").strip()
    return bool(raw and raw.casefold() not in {
        "por investigar", "pendiente", "n/d", "nd", "sin datos",
        "no disponible", "desconocido", "—", "-", "none",
    })


def tender_lifecycle_report(data: dict[str, Any], today: date | None = None) -> dict[str, int]:
    today = today or datetime.now(timezone.utc).date()
    public_rows = data.get("clients_public") or []
    rows = [row for row in public_rows if is_identified_tender(row)]
    active = [row for row in rows if public_tender_active(row, today)]
    return {
        "total_public_rows": len(public_rows),
        "non_notice_public_rows": len(public_rows) - len(rows),
        "total_retained": len(rows),
        "currently_active_or_date_unknown": len(active),
        "closed_or_deadline_expired": len(rows) - len(active),
        "date_unknown": sum(
            deadline_date(((r.get("fields") or {}).get("milestone_date") or {}).get("value")) is None
            for r in active
        ),
    }
