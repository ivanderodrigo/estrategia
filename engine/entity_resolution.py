
from pathlib import Path
import json
from .model import canonical
ROOT=Path(__file__).resolve().parents[1]
def alias_map():
    cfg=json.loads((ROOT/'config/current/entity_aliases.json').read_text(encoding='utf-8'))
    out={}
    for name,aliases in cfg.items():
        out[canonical(name)]=name
        for a in aliases: out[canonical(a)]=name
    return out
def resolve(name): return alias_map().get(canonical(name),name)
