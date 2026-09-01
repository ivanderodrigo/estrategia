"""Source Intelligence Rationalization for Westcon Decision Intelligence v4.0.5."""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping

from .knowledge_provenance import provenance_kind
from .settings import SECTIONS

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


def _url(ev: Mapping[str, Any]) -> str:
    return str(ev.get("url") or "").strip()


def is_historical(ev: Mapping[str, Any]) -> bool:
    return provenance_kind(ev) in HISTORICAL_KINDS


def is_current_open(ev: Mapping[str, Any]) -> bool:
    return (not is_historical(ev)) and _url(ev).startswith(("http://", "https://"))


def _analyst(ev: Mapping[str, Any]) -> bool:
    blob = " ".join(
        str(ev.get(key) or "")
        for key in ("source", "title", "source_type", "classification", "url")
    ).casefold()
    return any(name in blob for name in ANALYST_NAMES)


def source_tier(ev: Mapping[str, Any]) -> str:
    kind = provenance_kind(ev)
    if kind == "WESTCON_DOCUMENT":
        return "A1"
    if is_historical(ev):
        return "H"
    if is_current_open(ev) and _analyst(ev):
        return "B"
    if is_current_open(ev):
        if ev.get("official") is True or str(ev.get("source_grade") or "").startswith("A"):
            return "A2"
        return "C"
    if kind == "CURATED":
        return "D"
    return "U"


def source_role(tier: str) -> str:
    return {
        "A1": "Fuente directa Westcon",
        "A2": "Fuente primaria externa",
        "B": "Inteligencia especializada",
        "C": "Fuente abierta secundaria",
        "D": "Curación interna",
        "H": "Histórico en revalidación",
        "U": "Procedencia sin clasificar",
    }.get(tier, "Procedencia sin clasificar")


def _current_open(rows: Iterable[Mapping[str, Any]]) -> bool:
    return any(is_current_open(ev) for ev in rows if isinstance(ev, Mapping))


def _annotate(rows: Iterable[dict[str, Any]], *, current_open_available: bool) -> Counter[str]:
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
            if current_open_available:
                ev["revalidation_status"] = "supported-by-current-open-source"
                stats["historical_supported_current_open"] += 1
            else:
                ev["revalidation_status"] = "search-required"
                stats["historical_search_required"] += 1
    return stats


def rationalize_sources(data: dict[str, Any]) -> dict[str, Any]:
    total: Counter[str] = Counter()
    by_section: dict[str, Counter[str]] = {section: Counter() for section in SECTIONS}
    unsupported: list[dict[str, Any]] = []

    for section in SECTIONS:
        for row in data.get(section) or []:
            if not isinstance(row, dict):
                continue
            row_evidence = [ev for ev in row.get("evidence") or [] if isinstance(ev, dict)]
            delta = _annotate(row_evidence, current_open_available=_current_open(row_evidence))
            total.update(delta)
            by_section[section].update(delta)

            for field_id, field in (row.get("fields") or {}).items():
                if not isinstance(field, dict):
                    continue
                field_evidence = [ev for ev in field.get("evidence") or [] if isinstance(ev, dict)]
                delta = _annotate(field_evidence, current_open_available=_current_open(field_evidence))
                total.update(delta)
                by_section[section].update(delta)
                if any(is_historical(ev) for ev in field_evidence) and not _current_open(field_evidence):
                    unsupported.append({
                        "section": section,
                        "entity": row.get("name"),
                        "field": field_id,
                        "level": "field",
                    })

                for item in field.get("items") or []:
                    if not isinstance(item, dict):
                        continue
                    evidence = [ev for ev in item.get("evidence") or [] if isinstance(ev, dict)]
                    delta = _annotate(evidence, current_open_available=_current_open(evidence))
                    total.update(delta)
                    by_section[section].update(delta)
                    if any(is_historical(ev) for ev in evidence) and not _current_open(evidence):
                        unsupported.append({
                            "section": section,
                            "entity": row.get("name"),
                            "field": field_id,
                            "level": "item",
                            "value": item.get("value"),
                        })

    return {
        "version": "4.0.5",
        "policy": (
            "A1 Westcon directa; A2 primaria externa; B inteligencia especializada; "
            "C abierta secundaria; H histórico solo para linaje y siempre sujeto a "
            "revalidación mediante búsqueda abierta actual."
        ),
        "tiers": {
            key.removeprefix("tier_"): value
            for key, value in total.items()
            if key.startswith("tier_")
        },
        "historical_total": total["historical_total"],
        "historical_supported_current_open": total["historical_supported_current_open"],
        "historical_search_required": total["historical_search_required"],
        "by_section": {
            section: {
                "historical_total": counts["historical_total"],
                "historical_supported_current_open": counts["historical_supported_current_open"],
                "historical_search_required": counts["historical_search_required"],
            }
            for section, counts in by_section.items()
        },
        "unsupported_targets": unsupported,
    }
