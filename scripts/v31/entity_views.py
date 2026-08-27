from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from .confidence import score_evidence
from .taxonomy import classify_record

DISTRIBUTOR_WORDS = {"distributor", "distribution", "mayorista", "distribuidor", "wholesaler", "vado", "value-added distributor"}
INTEGRATOR_WORDS = {"integrator", "integrador", "systems integrator", "mssp", "msp", "partner", "reseller"}
VENDOR_WORDS = {"vendor", "fabricante", "manufacturer", "technology vendor"}


def stable_id(*parts: str) -> str:
    raw = "|".join(str(x or "").strip().lower() for x in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:14]


def _str(v):
    return str(v or "").strip()


def infer_entity_type(record: Mapping[str, Any]) -> str | None:
    type_text = " ".join(_str(record.get(k)).lower() for k in ("entity_type", "type", "role", "kind", "category"))
    if any(x in type_text for x in DISTRIBUTOR_WORDS): return "distributor"
    if any(x in type_text for x in INTEGRATOR_WORDS): return "integrator"
    if any(x in type_text for x in VENDOR_WORDS): return "vendor"
    return None


def extract_entity_name(record: Mapping[str, Any]) -> str:
    for key in ("entity_name", "name", "vendor", "manufacturer", "distributor", "integrator", "partner", "company", "organization", "organisation"):
        value = record.get(key)
        if isinstance(value, str) and 2 < len(value.strip()) < 160:
            return value.strip()
    return ""


def walk_records(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from walk_records(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from walk_records(item)


def load_json_records(data_root: Path):
    for path in sorted(data_root.rglob("*.json")):
        normalized = str(path).replace("\\", "/")
        if "/v31/" in normalized and path.name not in {"discovery_signals.json"}:
            continue
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for rec in walk_records(obj):
            yield path, rec


def _country(rec: Mapping[str, Any]) -> str:
    txt = " ".join(_str(rec.get(k)) for k in ("country", "geography", "market", "region")).lower()
    if any(x in txt for x in ("portugal", "pt", "portugu")): return "PT"
    if any(x in txt for x in ("spain", "españa", "espana", "es")): return "ES"
    if "iberia" in txt: return "IBERIA"
    return "GLOBAL"


def _listify(value):
    if value is None: return []
    if isinstance(value, list): return [str(x) for x in value if x]
    if isinstance(value, (tuple, set)): return [str(x) for x in value if x]
    if isinstance(value, str):
        if any(sep in value for sep in (",", ";", "|")):
            return [x.strip() for x in re.split(r"[,;|]", value) if x.strip()]
        return [value.strip()] if value.strip() else []
    return [str(value)]


def build_entity_views(data_root: str | Path, seed_entities: Iterable[Dict[str, Any]] = ()): 
    data_root = Path(data_root)
    entities: Dict[tuple, Dict[str, Any]] = {}

    def ensure(name, etype, country="GLOBAL"):
        key = (etype, name.lower(), country)
        if key not in entities:
            entities[key] = {
                "id": stable_id(etype, name, country), "name": name, "entity_type": etype, "country": country,
                "vendors": set(), "certifications": set(), "services": set(), "verticals": set(), "customers": set(),
                "distributors": set(), "integrators": set(), "evidence": [], "signals": defaultdict(int),
                "confidence_samples": [], "last_verified": None,
            }
        return entities[key]

    for seed in seed_entities:
        name = _str(seed.get("name")); etype = _str(seed.get("entity_type")); country = _str(seed.get("country") or "GLOBAL")
        if name and etype in {"vendor", "distributor", "integrator"}:
            ent = ensure(name, etype, country)
            for k in ("vendors", "certifications", "services", "verticals"):
                ent[k].update(_listify(seed.get(k)))

    for path, rec in load_json_records(data_root):
        etype = infer_entity_type(rec)
        name = extract_entity_name(rec)
        if not etype or not name:
            continue
        country = _country(rec)
        ent = ensure(name, etype, country)
        vendors = _listify(rec.get("vendors") or rec.get("manufacturers") or rec.get("vendor"))
        certs = _listify(rec.get("certifications") or rec.get("specializations") or rec.get("specialisations"))
        services = _listify(rec.get("services") or rec.get("capabilities"))
        verticals = _listify(rec.get("verticals") or rec.get("industries"))
        customers = _listify(rec.get("customers") or rec.get("clients"))
        ent["vendors"].update(vendors); ent["certifications"].update(certs); ent["services"].update(services); ent["verticals"].update(verticals); ent["customers"].update(customers)
        classification = classify_record(rec)
        conf = score_evidence(rec)
        ent["signals"][classification.classification] += 1
        ent["confidence_samples"].append(conf.total)
        date = _str(rec.get("published_at") or rec.get("date") or rec.get("observed_at"))
        if date and (not ent["last_verified"] or date > ent["last_verified"]): ent["last_verified"] = date
        if rec.get("url") or rec.get("source"):
            ent["evidence"].append({
                "title": _str(rec.get("title") or rec.get("headline") or name),
                "url": _str(rec.get("url")), "source": _str(rec.get("source") or rec.get("source_name")),
                "classification": classification.classification, "confidence": round(conf.total, 3),
                "date": date, "file": str(path.relative_to(data_root)).replace("\\", "/"),
            })

    result = {"vendors": [], "distributors": [], "integrators": []}
    mapping = {"vendor": "vendors", "distributor": "distributors", "integrator": "integrators"}
    for (_, _, _), ent in entities.items():
        samples = ent.pop("confidence_samples")
        ent["confidence"] = round(sum(samples) / len(samples), 3) if samples else 0.45
        ent["evidence_count"] = len(ent["evidence"])
        ent["signals"] = dict(ent["signals"])
        for key in ("vendors", "certifications", "services", "verticals", "customers", "distributors", "integrators"):
            ent[key] = sorted(ent[key])[:60]
        ent["evidence"] = sorted(ent["evidence"], key=lambda x: (x.get("confidence", 0), x.get("date", "")), reverse=True)[:40]
        result[mapping[ent["entity_type"]]].append(ent)
    for key in result:
        result[key].sort(key=lambda x: (x["confidence"], x["evidence_count"], x["name"]), reverse=True)
    return result
