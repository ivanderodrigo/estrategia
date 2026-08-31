
from __future__ import annotations
import re,unicodedata,hashlib

def canonical(value):
    s=unicodedata.normalize('NFKD',str(value or '')).encode('ascii','ignore').decode().casefold()
    return re.sub(r'[^a-z0-9]+',' ',s).strip()

def stable_id(kind,name): return kind[:4]+'_'+hashlib.sha1(canonical(name).encode()).hexdigest()[:16]

def values(v): return v if isinstance(v,list) else ([] if v in (None,'') else [v])
