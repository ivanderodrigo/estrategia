#!/usr/bin/env python3
from pathlib import Path
import sys,yaml
ROOT=Path(__file__).resolve().parents[1]
errors=[]
for p in sorted((ROOT/'.github/workflows').glob('*.yml')):
    try:
        obj=yaml.safe_load(p.read_text(encoding='utf-8'))
    except Exception as exc:
        errors.append(f'{p.name}: YAML inválido: {exc}');continue
    if not isinstance(obj,dict) or 'jobs' not in obj: errors.append(f'{p.name}: sin jobs')
    txt=p.read_text(encoding='utf-8')
    if 'actions/checkout@v4' in txt: errors.append(f'{p.name}: checkout@v4 obsoleto')
    if any(x in txt for x in ('data/v3','scripts/v3','config/v3','assets/v3')): errors.append(f'{p.name}: referencia legacy')
print('workflow validation:', 'PASS' if not errors else 'FAIL')
for e in errors: print(' -',e)
sys.exit(1 if errors else 0)
