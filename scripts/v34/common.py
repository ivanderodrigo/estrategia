from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse


def load_json(path: str | Path, default: Any) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def write_json(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def stable_id(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha256("|".join(norm(x) for x in parts).encode("utf-8")).hexdigest()[:18]
    return f"{prefix}_{digest}"


def number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp(value: Any, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, number(value)))


def unique(values: Iterable[Any]) -> list[Any]:
    result: list[Any] = []
    seen: set[str] = set()
    for value in values:
        if value in (None, "", [], {}):
            continue
        key = norm(value) if not isinstance(value, Mapping) else json.dumps(value, sort_keys=True, ensure_ascii=False)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def parse_date(value: Any) -> datetime | None:
    if not value:
        return None
    raw = str(value).strip()
    try:
        parsed = parsedate_to_datetime(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        pass
    candidate = raw.replace("Z", "+00:00")
    if re.match(r"^\d{4}-\d{2}-\d{2}[+-]\d{2}:\d{2}$", candidate):
        candidate = candidate[:10] + "T00:00:00" + candidate[10:]
    try:
        parsed = datetime.fromisoformat(candidate)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def date_iso(value: Any) -> str:
    parsed = parse_date(value)
    return parsed.date().isoformat() if parsed else ""


def age_days(value: Any, reference: datetime | None = None) -> int | None:
    parsed = parse_date(value)
    if not parsed:
        return None
    reference = reference or datetime.now(timezone.utc)
    return max(0, (reference - parsed).days)


def domain_of(url: Any) -> str:
    try:
        return urlparse(str(url or "")).netloc.lower().removeprefix("www.")
    except ValueError:
        return ""


def source_type(evidence: Mapping[str, Any]) -> str:
    explicit = str(evidence.get("source_type") or "").strip()
    if explicit:
        return explicit
    category = norm(evidence.get("source_category") or evidence.get("sourceTier") or evidence.get("source_grade"))
    source = norm(evidence.get("source"))
    domain = domain_of(evidence.get("url"))
    if any(token in category for token in ("official", "regulator", "public open data")):
        return "primary"
    if any(token in source for token in ("ted eu procurement", "placsp", "cisa", "nvd", "incibe", "cncs", "enisa", "european commission")):
        return "primary"
    if any(token in domain for token in ("ted.europa.eu", "contrataciondelestado.es", "base.gov.pt", "incibe.es", "cisa.gov", "nist.gov", "europa.eu")):
        return "primary"
    if any(token in category for token in ("analyst", "industry press", "channel media")):
        return "secondary-quality"
    if "news.google.com" in domain or "discovery" in category:
        return "aggregator"
    if domain and any(token in norm(evidence.get("method")) for token in ("entity intelligence", "targeted research")):
        return "primary-or-company"
    return "secondary"


def evidence_key(evidence: Mapping[str, Any]) -> str:
    url = str(evidence.get("url") or "").strip()
    if url:
        return norm(url)
    return "|".join(
        norm(evidence.get(key))
        for key in ("title", "source", "date", "published_at", "entity", "vendor")
    )


def dedupe_evidence(rows: Iterable[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    selected: dict[str, dict[str, Any]] = {}
    duplicates = 0
    for raw in rows or []:
        if not isinstance(raw, Mapping):
            continue
        item = dict(raw)
        key = evidence_key(item)
        if not key:
            continue
        item.setdefault("date", item.get("published_at") or item.get("observed_at") or "")
        item["date"] = date_iso(item.get("date")) or str(item.get("date") or "")
        item["source_type"] = source_type(item)
        current = selected.get(key)
        if current:
            duplicates += 1
            if number(item.get("confidence")) > number(current.get("confidence")):
                selected[key] = item
        else:
            selected[key] = item
    return list(selected.values()), duplicates


def evidence_reference(raw: Mapping[str, Any], fact: str = "") -> dict[str, Any]:
    item = dict(raw)
    confidence = number(item.get("confidence"), number(item.get("source_authority"), 0.55))
    if confidence > 1:
        confidence /= 100
    quality = "alta" if confidence >= 0.82 else "media" if confidence >= 0.62 else "baja"
    return {
        "evidence_id": stable_id("ev", item.get("url"), item.get("title"), item.get("source")),
        "fact": fact or str(item.get("summary") or item.get("title") or "Evidencia pública vinculada"),
        "source": item.get("source") or "Fuente pública",
        "url": item.get("url") or "",
        "date": date_iso(item.get("date") or item.get("published_at") or item.get("observed_at")) or "Fecha no publicada",
        "source_type": source_type(item),
        "quality": quality,
        "confidence": round(clamp(confidence), 3),
    }
