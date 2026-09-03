"""Evidence-quality confidence model.

Confidence is driven by the strongest relevant evidence, source quality,
freshness and contradictions. Repeated weak URLs never outweigh one clear
primary source simply by volume.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timezone
from statistics import median
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse

from .knowledge_provenance import provenance_kind, typed_evidence_sufficient
from .settings import SECTIONS


ANALYST_MARKERS = ("gartner", "forrester", "idc", "omdia", "canalys", "isg", "gigaom")


def _band(score: float) -> str:
    return "high" if score >= 0.80 else "medium" if score >= 0.60 else "low"


def _evidence_identity(ev: Mapping[str, Any]) -> str:
    kind = provenance_kind(ev)
    if kind == "WESTCON_DOCUMENT":
        return f"document:{ev.get('document_id') or ev.get('document') or ev.get('source')}"
    host = urlparse(str(ev.get("url") or "")).netloc.casefold().removeprefix("www.")
    return host or str(ev.get("source") or ev.get("title") or "").casefold()


def _is_analyst(ev: Mapping[str, Any]) -> bool:
    blob = " ".join(str(ev.get(key) or "") for key in ("source", "title", "url", "source_type")).casefold()
    return any(marker in blob for marker in ANALYST_MARKERS)


def _age_days(ev: Mapping[str, Any]) -> int | None:
    explicit = ev.get("age_days")
    if explicit not in (None, ""):
        try:
            return max(0, int(float(explicit)))
        except (TypeError, ValueError):
            pass
    raw = str(ev.get("retrieved_at") or ev.get("date") or "")[:10]
    try:
        return max(0, (date.today() - date.fromisoformat(raw)).days)
    except ValueError:
        return None


def _strength(ev: Mapping[str, Any]) -> tuple[float, str]:
    kind = provenance_kind(ev)
    if kind in {"WESTCON_DOCUMENT", "RESEARCH_SEED"}:
        return 0.0, "research_seed"
    if kind == "PUBLIC_PRIMARY":
        return 0.88, "public_primary"
    if _is_analyst(ev):
        return 0.76, "analyst"
    if kind == "PUBLIC_SECONDARY":
        return 0.66, "public_secondary"
    return 0.0, "non_accrediting"


def _contradiction(ev: Mapping[str, Any]) -> bool:
    blob = " ".join(str(ev.get(key) or "") for key in ("contradiction", "status", "revalidation", "freshness_status")).casefold()
    return bool(ev.get("contradicted")) or any(token in blob for token in ("contradict", "conflict", "refuted", "rejected"))


def profile(rows: Iterable[Mapping[str, Any]], claim_type: str = "fact") -> dict[str, Any]:
    evidence = [dict(ev) for ev in rows if isinstance(ev, Mapping) and typed_evidence_sufficient(ev)]
    weighted = [(*_strength(ev), ev) for ev in evidence]
    weighted = [row for row in weighted if row[0] > 0]
    counts: Counter[str] = Counter(row[1] for row in weighted)
    independent = {_evidence_identity(row[2]) for row in weighted if _evidence_identity(row[2])}
    current = 0
    stale = 0
    for _, _, ev in weighted:
        age = _age_days(ev)
        if str(ev.get("freshness_status") or "").casefold() == "stale" or (age is not None and age > 730):
            stale += 1
        else:
            current += 1
    contradictions = sum(_contradiction(row[2]) for row in weighted)

    if not weighted:
        score = 0.38 if claim_type == "fact" else 0.34
    else:
        strongest = max(row[0] for row in weighted)
        corroboration = min(0.08, max(0, len(independent) - 1) * 0.03)
        freshness_penalty = min(0.16, stale * 0.04)
        contradiction_penalty = min(0.30, contradictions * 0.15)
        score = strongest + corroboration - freshness_penalty - contradiction_penalty
    if claim_type == "signal":
        score = min(score, 0.59)
    elif claim_type == "interpretation":
        score = min(score, 0.74)
    score = round(max(0.30, min(0.97, score)), 2)
    band = _band(score)

    factors = [
        f"Evidencias acreditativas relevantes: {len(weighted)}; fuentes independientes: {len(independent)}.",
        (
            "Calidad: "
            f"{counts['public_primary']} primaria(s) pública(s), "
            f"{counts['analyst']} analista(s) y {counts['public_secondary']} secundaria(s)."
        ),
        f"Actualidad: {current} vigente(s) y {stale} envejecida(s).",
    ]
    if contradictions:
        factors.append(f"Contradicciones detectadas: {contradictions}; reducen explícitamente la confianza.")
    if not weighted:
        missing = "Vincular una fuente pública actual, específica y atribuible para este dato."
    elif counts["public_primary"]:
        missing = "Revalidar cuando envejezca y resolver cualquier contradicción futura."
    else:
        missing = "Añadir una fuente primaria/oficial clara o corroboración independiente actual."
    factors.append(f"Para subir la confianza: {missing}")

    return {
        "score": score,
        "band": band,
        "factors": factors,
        "details": {
            "relevant_evidence": len(weighted),
            "independent_sources": len(independent),
            "westcon_documents": counts["westcon_document"],
            "public_primary": counts["public_primary"],
            "analyst": counts["analyst"],
            "public_secondary": counts["public_secondary"],
            "current": current,
            "stale": stale,
            "contradictions": contradictions,
            "missing_for_upgrade": missing,
            "method": "strongest-source-plus-quality-freshness-corroboration",
        },
    }


def _apply_target(target: dict[str, Any], fallback_rows: list[Mapping[str, Any]] | None = None) -> None:
    rows = [ev for ev in target.get("evidence") or [] if isinstance(ev, Mapping)]
    if not rows and fallback_rows:
        rows = list(fallback_rows)
    claim = str(target.get("claim_type") or "fact")
    result = profile(rows, claim)
    target["confidence"] = result["score"]
    target["confidence_band"] = result["band"]
    target["fact_confidence"] = result["score"]
    target["interpretation_confidence"] = round(min(result["score"], 0.74 if claim != "fact" else result["score"]), 2)
    target["action_risk"] = "bajo" if result["band"] == "high" else "medio" if result["band"] == "medium" else "alto"
    target["evidence_level"] = "strong" if result["band"] == "high" else "moderate" if result["band"] == "medium" else "weak"
    target["evidence_color"] = "green" if result["band"] == "high" else "yellow" if result["band"] == "medium" else "red"
    target["confidence_factors"] = result["factors"]
    target["confidence_details"] = result["details"]
    target["confidence_reason"] = (
        f"{result['band'].capitalize()}: nivel calculado por calidad, actualidad, corroboración y contradicciones; "
        "no por el número bruto de URLs."
    )


def apply_confidence_model(data: dict[str, Any]) -> dict[str, int]:
    stats = {"fields": 0, "items": 0, "without_accrediting_evidence": 0}
    for section in SECTIONS:
        for row in data.get(section) or []:
            for field in (row.get("fields") or {}).values():
                if not isinstance(field, dict) or field.get("value") in (None, "", [], {}):
                    continue
                field_rows = [ev for ev in field.get("evidence") or [] if isinstance(ev, Mapping)]
                for item in field.get("items") or []:
                    if not isinstance(item, dict) or item.get("value") in (None, "", [], {}):
                        continue
                    _apply_target(item, field_rows)
                    stats["items"] += 1
                    stats["without_accrediting_evidence"] += int(item["confidence_details"]["relevant_evidence"] == 0)
                _apply_target(field)
                stats["fields"] += 1
                stats["without_accrediting_evidence"] += int(field["confidence_details"]["relevant_evidence"] == 0)
    return stats

