from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

SECTIONS = ("manufacturers", "integrators", "distributors", "trends", "architectures")
TODAY = datetime.now(timezone.utc)
ROOT = Path(__file__).resolve().parents[2]


TARGET_FIELDS = {
    "manufacturers": {
        "integrators": 100,
        "distributors": 96,
        "competitors": 78,
        "analyst_signals": 68,
        "recent_signals": 62,
    },
    "integrators": {
        "vendor_relations": 100,
        "services": 88,
        "specializations": 88,
        "capabilities": 82,
        "verticals": 70,
        "public_cases": 68,
        "job_profiles": 56,
    },
    "distributors": {
        "vendor_relations": 100,
        "westcon_overlap": 88,
        "services": 78,
        "specializations": 76,
        "capabilities": 72,
        "verticals": 58,
    },
    "trends": {
        "trend_market_metrics": 100,
        "market_players": 96,
        "westcon_vendors": 90,
        "iberia_context": 88,
        "buyer_priorities": 78,
        "drivers": 74,
        "evolution": 72,
        "adjacent_market_metrics": 58,
    },
    "architectures": {
        "analyst_basis": 92,
        "layers": 90,
        "vendors": 88,
        "limits": 66,
    },
}

REVALIDATE_DAYS = {
    "vendor_relations": 240,
    "integrators": 240,
    "distributors": 240,
    "competitors": 365,
    "market_players": 270,
    "trend_market_metrics": 270,
    "iberia_context": 180,
    "recent_signals": 120,
    "job_profiles": 120,
    "public_cases": 540,
    "default": 365,
}


def _norm(value: Any) -> str:
    text = str(value or "").lower()
    text = text.translate(str.maketrans("áéíóúüñç", "aeiouunc"))
    return re.sub(r"\s+", " ", text).strip()


def _entity_domain(name: str) -> str | None:
    try:
        universe = json.loads((ROOT / "config/source_universe.json").read_text(encoding="utf-8"))
    except Exception:
        return None
    target = _norm(name)
    for bucket in ("integrators", "distributors"):
        for row in universe.get(bucket, []) or []:
            if _norm(row.get("name")) == target and row.get("domain"):
                return str(row.get("domain"))
    return None


def _date(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw or raw.upper().startswith("FY"):
        return None
    raw = raw.replace("Z", "+00:00")
    candidates = [raw, raw[:10]]
    for candidate in candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            pass
    m = re.search(r"\b(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})\b", raw)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
        except Exception:
            return None
    return None


def _evidence_rows(field: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    rows.extend(field.get("evidence") or [])
    for item in field.get("items") or []:
        rows.extend(item.get("evidence") or [])
    return [x for x in rows if isinstance(x, Mapping)]


def _freshness(field_id: str, field: Mapping[str, Any]) -> tuple[int | None, bool]:
    dates = [_date(ev.get("date")) for ev in _evidence_rows(field)]
    dates = [x for x in dates if x]
    if not dates:
        return None, False
    newest = max(dates)
    age = max(0, (TODAY - newest).days)
    limit = int(REVALIDATE_DAYS.get(field_id, REVALIDATE_DAYS["default"]))
    return age, age > limit


def _is_placeholder(field: Mapping[str, Any]) -> bool:
    for ev in _evidence_rows(field):
        if _norm(ev.get("type")) == "research-status" or _norm(ev.get("source")) == "motor westcon intelligence v3.8":
            return True
    return False


def _confidence(field: Mapping[str, Any]) -> float:
    try:
        v = float(field.get("confidence") or 0)
        return v / 100 if v > 1 else v
    except Exception:
        return 0.0


def _gap_queries(section: str, name: str, field_id: str, field: Mapping[str, Any] | None, vendor_names: list[str]) -> list[str]:
    q: list[str] = []
    if section == "manufacturers":
        if field_id == "integrators":
            q += [
                f'"{name}" Spain Portugal partner locator integrator reseller VAR MSP MSSP certified partner',
                f'"{name}" Spain Portugal partner awards systems integrator installer service provider',
            ]
        elif field_id == "distributors":
            q += [f'"{name}" Spain Portugal distributor authorized distribution linecard VAD', f'"{name}" Iberia mayorista distribuidor']
        elif field_id in {"competitors", "analyst_signals"}:
            q += [f'"{name}" Gartner Forrester IDC competitors market landscape 2026', f'"{name}" alternatives competitors market share 2026']
        elif field_id == "recent_signals":
            q += [f'"{name}" 2026 partner product launch case study Spain Portugal']
    elif section == "integrators":
        if field_id == "vendor_relations":
            q += [f'"{name}" technology partners alliances vendors Spain Portugal', f'"{name}" partner Cisco Check Point Palo Alto AWS Microsoft CrowdStrike Extreme F5']
        elif field_id in {"services", "capabilities"}:
            q += [f'"{name}" services managed services MSSP MSP SOC NOC cloud cybersecurity networking']
        elif field_id == "specializations":
            q += [f'"{name}" certifications specializations partner competencies Spain Portugal']
        elif field_id == "verticals":
            q += [f'"{name}" customers sectors verticals case studies Spain Portugal']
        elif field_id == "public_cases":
            q += [f'"{name}" customer case study success story Spain Portugal']
        elif field_id == "job_profiles":
            q += [f'"{name}" jobs careers Cisco Check Point Palo Alto AWS Microsoft security network engineer Spain Portugal']
    elif section == "distributors":
        if field_id in {"vendor_relations", "westcon_overlap"}:
            q += [f'"{name}" vendors portfolio linecard Spain Portugal fabricantes']
        elif field_id in {"services", "capabilities"}:
            q += [f'"{name}" value added services cloud marketplace professional services labs financing training']
        elif field_id == "specializations":
            q += [f'"{name}" cybersecurity networking cloud specialization portfolio Spain Portugal']
        elif field_id == "verticals":
            q += [f'"{name}" vertical sectors customers public sector healthcare finance industry']
    elif section == "trends":
        if field_id == "trend_market_metrics":
            q += [f'"{name}" market size CAGR 2026 2030 Gartner IDC Forrester', f'"{name}" market forecast revenue growth Europe 2026']
        elif field_id == "market_players":
            q += [f'"{name}" vendors leaders market landscape Gartner Forrester IDC 2026']
        elif field_id == "iberia_context":
            q += [f'"{name}" Spain Portugal adoption market 2026', f'"{name}" España Portugal mercado']
        elif field_id == "westcon_vendors":
            q += [f'"{name}" ' + " OR ".join(f'"{v}"' for v in vendor_names[:8])]
        else:
            q += [f'"{name}" {field_id.replace("_", " ")} 2026 Gartner IDC Forrester']
    elif section == "architectures":
        q += [f'"{name}" reference architecture Gartner Forrester IDC NIST 2026']
    domain = _entity_domain(name)
    if domain and section in {"integrators", "distributors"}:
        if section == "integrators":
            q += [
                f'site:{domain} partners alliances vendors certifications',
                f'site:{domain} careers jobs engineer architect certifications',
                f'site:{domain} customer case study managed services MSSP MSP',
            ]
        else:
            q += [
                f'site:{domain} vendors linecard portfolio distributors',
                f'site:{domain} services marketplace training financing labs',
            ]
    # Reciprocal proof route: entity + field in official vendor ecosystem.
    if section == "integrators" and field_id == "vendor_relations":
        q += [f'"{name}" partner locator reseller integrator site:com', f'"{name}" partner award certified partner Spain Portugal']
    if section == "manufacturers" and field_id in {"integrators", "distributors"}:
        q += [f'"{name}" partner directory Spain Portugal official', f'"{name}" authorized distributor reseller Iberia official']
    # Revalidate the concrete value where possible.
    if field and field.get("items"):
        for item in (field.get("items") or [])[:2]:
            val = str(item.get("value") or "").split(" · ", 1)[0].strip()
            if val and val.lower() not in name.lower():
                q.append(f'"{name}" "{val}" 2026')
    # Preserve order while deduplicating.
    out=[]; seen=set()
    for x in q:
        if x and x not in seen:
            seen.add(x); out.append(x)
    return out[:8]


def build_gaps(public: Mapping[str, Any]) -> dict[str, Any]:
    vendors = [x.get("name") for x in public.get("manufacturers", []) if x.get("name")]
    gaps: list[dict[str, Any]] = []
    for section in SECTIONS:
        targets = TARGET_FIELDS.get(section, {})
        for row in public.get(section, []) or []:
            name = str(row.get("name") or "")
            fields = row.get("fields") or {}
            for field_id, base_priority in targets.items():
                field = fields.get(field_id)
                missing = not field or field.get("value") in (None, "", [], {})
                placeholder = bool(field and _is_placeholder(field))
                confidence = _confidence(field or {})
                age_days, stale = _freshness(field_id, field or {}) if field else (None, False)
                low_conf = bool(field and confidence < 0.60)
                if not (missing or placeholder or stale or low_conf):
                    continue
                reasons=[]; priority=base_priority
                if missing:
                    reasons.append("campo vacío"); priority += 14
                if placeholder:
                    reasons.append("placeholder de investigación"); priority += 12
                if stale:
                    reasons.append(f"evidencia envejecida ({age_days} días)"); priority += 10
                if low_conf:
                    reasons.append(f"confianza baja ({round(confidence*100)}%)"); priority += 8
                # Relationships are the most strategically valuable gaps.
                if field_id in {"integrators", "distributors", "vendor_relations"}:
                    priority += 12
                gap = {
                    "section": section,
                    "entity": name,
                    "entity_id": row.get("id"),
                    "field": field_id,
                    "priority": min(125, int(priority)),
                    "reason": "; ".join(reasons),
                    "confidence": round(confidence, 3) if field else None,
                    "age_days": age_days,
                    "query_hints": _gap_queries(section, name, field_id, field, vendors),
                }
                gaps.append({k:v for k,v in gap.items() if v is not None})
    gaps.sort(key=lambda x: (-int(x.get("priority", 0)), x.get("section", ""), _norm(x.get("entity")), x.get("field", "")))
    by_section={s:sum(1 for x in gaps if x.get("section")==s) for s in SECTIONS}
    return {
        "version": "3.8.0",
        "generated_at": TODAY.isoformat(),
        "policy": "Cola interna. Cada celda vacía, placeholder, dato de baja confianza o evidencia envejecida incrementa automáticamente el sondeo; nunca se expone como prioridad al usuario final.",
        "total_gaps": len(gaps),
        "high_priority_gaps": sum(1 for x in gaps if int(x.get("priority",0)) >= 100),
        "by_section": by_section,
        "gaps": gaps,
    }


def write_gaps(root: Path, public: Mapping[str, Any]) -> dict[str, Any]:
    payload = build_gaps(public)
    path = root / "data/v38/research_gaps.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    return payload
