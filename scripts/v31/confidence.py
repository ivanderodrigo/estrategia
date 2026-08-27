from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, Iterable, Mapping


def clamp(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _parse_date(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(str(value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(str(value), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def freshness_score(record: Mapping[str, Any], half_life_days: float = 365.0) -> float:
    dt = _parse_date(record.get("published_at") or record.get("date") or record.get("timestamp") or record.get("observed_at"))
    if not dt:
        return 0.55
    age_days = max(0.0, (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds() / 86400)
    # Simple bounded exponential decay.
    return clamp(2 ** (-age_days / max(1.0, half_life_days)))


@dataclass
class ConfidenceBreakdown:
    authority: float
    corroboration: float
    geography: float
    freshness: float
    directness: float
    source_diversity: float
    specificity: float
    contradiction_penalty: float
    inference_penalty: float
    total: float
    band: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def confidence_band(score: float) -> str:
    if score >= 0.85:
        return "alta"
    if score >= 0.70:
        return "solida"
    if score >= 0.55:
        return "indicativa"
    if score >= 0.40:
        return "debil"
    return "insuficiente"


def score_evidence(record: Mapping[str, Any]) -> ConfidenceBreakdown:
    authority = clamp(record.get("authority_score", record.get("source_authority", 0.62)))
    corroboration = clamp(record.get("corroboration_score", 0.45))
    geography = clamp(record.get("geography_score", 0.62))
    directness = clamp(record.get("directness_score", 0.60))
    source_diversity = clamp(record.get("source_diversity_score", 0.45))
    specificity = clamp(record.get("specificity_score", 0.60))
    freshness = freshness_score(record, half_life_days=float(record.get("freshness_half_life_days", 365)))
    contradiction_penalty = clamp(record.get("contradiction_penalty", 0.0))
    inference_penalty = clamp(record.get("inference_penalty", 0.0))

    raw = (
        0.20 * authority
        + 0.18 * corroboration
        + 0.13 * geography
        + 0.13 * freshness
        + 0.13 * directness
        + 0.09 * source_diversity
        + 0.14 * specificity
        - 0.11 * contradiction_penalty
        - 0.08 * inference_penalty
    )
    total = clamp(raw)
    return ConfidenceBreakdown(
        authority=round(authority, 3), corroboration=round(corroboration, 3), geography=round(geography, 3),
        freshness=round(freshness, 3), directness=round(directness, 3), source_diversity=round(source_diversity, 3),
        specificity=round(specificity, 3), contradiction_penalty=round(contradiction_penalty, 3),
        inference_penalty=round(inference_penalty, 3), total=round(total, 3), band=confidence_band(total),
    )


def recommendation_threshold(kind: str) -> float:
    kind = (kind or "").lower().strip()
    if kind in {"invest_heavily", "reduce_focus", "replace_vendor", "strategic_priority", "portfolio_exit"}:
        return 0.85
    if kind in {"invest", "build_capability", "launch_service", "partner_recruitment", "channel_defense"}:
        return 0.78
    if kind in {"pilot", "campaign", "watch", "investigate"}:
        return 0.62
    return 0.70
