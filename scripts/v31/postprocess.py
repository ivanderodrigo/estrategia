from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable

from .atomic_publish import atomic_write_json
from .entity_views import build_entity_views, walk_records
from .recommendations import enrich_views
from .taxonomy import repair_record


def repair_json_tree(data_root: Path):
    changed_files = []
    repairs = 0
    for path in sorted(data_root.rglob("*.json")):
        if "/v31/" in str(path).replace("\\", "/"):
            continue
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        changed = False
        for rec in walk_records(obj):
            current = str(rec.get("classification") or rec.get("category") or rec.get("evidence_type") or "").lower()
            blob = " ".join(str(rec.get(k) or "") for k in ("title","headline","summary","description","url")).lower()
            if "award" in blob or "premio" in blob or "prémio" in blob or "procurement" in current or "adjudic" in current:
                _, did = repair_record(rec)
                if did:
                    changed = True; repairs += 1
        if changed:
            atomic_write_json(path, obj)
            changed_files.append(str(path.relative_to(data_root)).replace("\\", "/"))
    return {"repairs": repairs, "changed_files": changed_files}


def _seed_entities(registry):
    out = []
    for src in registry:
        for ent in src.get("seed_entities") or []:
            if isinstance(ent, dict) and ent.get("name") and ent.get("entity_type"):
                out.append(ent)
    return out


def build_all(data_root: Path, registry, westcon_vendors):
    seeds = _seed_entities(registry)
    known = {(str(x.get("entity_type")), str(x.get("name")).lower()) for x in seeds}
    for name in westcon_vendors:
        if ("vendor", str(name).lower()) not in known:
            seeds.append({"name": name, "entity_type": "vendor", "country": "GLOBAL"})
    views = build_entity_views(data_root, seeds)
    views = enrich_views(views, westcon_vendors)
    views["meta"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "public-evidence graph + v3.1 confidence + explainable inference",
        "confidence_policy": {"high": 0.85, "solid": 0.70, "indicative": 0.55, "weak": 0.40},
    }
    return views
