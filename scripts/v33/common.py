from __future__ import annotations
import hashlib, json, re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def load_json(path: Path, default: Any):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, value: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(path)


def norm(value: Any)->str:
    import unicodedata
    s=unicodedata.normalize("NFD",str(value or "")).encode("ascii","ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+"," ",s).strip()


def uniq(values: Iterable[Any]):
    out=[];seen=set()
    for x in values:
        if x is None: continue
        s=str(x).strip()
        if not s: continue
        k=norm(s)
        if k in seen: continue
        seen.add(k);out.append(s)
    return out


def f(value: Any)->float:
    try:return float(value or 0)
    except Exception:return 0.0


def clamp(v:float,lo:float=0,hi:float=1)->float:return max(lo,min(hi,v))


def iso_now()->str:return datetime.now(timezone.utc).isoformat()


def stable_id(*parts: Any)->str:
    raw="|".join(norm(x) for x in parts)
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def parse_date(value: Any):
    if not value:return None
    from email.utils import parsedate_to_datetime
    s=str(value)
    try:
        d=parsedate_to_datetime(s)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:pass
    try:
        d=datetime.fromisoformat(s.replace("Z","+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:return None
