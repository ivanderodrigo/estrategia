from __future__ import annotations

import json
from pathlib import Path
from typing import List

from .taxonomy import classify_record


def _walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values(): yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj: yield from _walk(v)


def validate(repo_root: str | Path) -> List[str]:
    root = Path(repo_root)
    errors = []
    data = root / "data"
    v31 = data / "v31" / "entity_intelligence.json"
    if not v31.exists():
        errors.append("missing data/v31/entity_intelligence.json")
    else:
        try:
            obj = json.loads(v31.read_text(encoding="utf-8"))
            for key in ("vendors", "distributors", "integrators"):
                if key not in obj or not isinstance(obj[key], list): errors.append(f"entity_intelligence missing list: {key}")
        except Exception as exc:
            errors.append(f"entity_intelligence invalid JSON: {exc}")

    # Hard semantic validation: "Awards" without procurement anchors must not be procurement.
    for path in data.rglob("*.json") if data.exists() else []:
        try: obj = json.loads(path.read_text(encoding="utf-8"))
        except Exception: continue
        for rec in _walk(obj):
            title = str(rec.get("title") or rec.get("headline") or "")
            cls = str(rec.get("classification") or rec.get("category") or "").lower()
            if "award" in title.lower() and ("procurement" in cls or "adjudic" in cls):
                result = classify_record(rec)
                if result.classification != "procurement_award":
                    errors.append(f"unsafe award→procurement classification in {path.relative_to(root)}: {title[:100]}")
                    if len(errors) > 30: return errors
    return errors
