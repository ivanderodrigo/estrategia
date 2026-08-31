#!/usr/bin/env python3
from pathlib import Path
import re,sys
ROOT=Path(__file__).resolve().parents[2]
errs=[]
for f in (ROOT/'.github/workflows').glob('*.yml'):
 t=f.read_text(encoding='utf-8')
 for path in re.findall(r'(?:(?:python|node)\s+)([^\s|]+)',t):
  if '${{' in path or path.startswith('-'):continue
  p=ROOT/path
  if not p.exists():errs.append(f'{f.name}: referencia inexistente {path}')
 for m in re.findall(r'(scripts/v\d+/validate_v\d+\.py)',t):
  if not (ROOT/m).exists():errs.append(f'{f.name}: validador inexistente {m}')
if errs:
 print('\n'.join(errs));raise SystemExit(1)
print('WORKFLOW REFERENCE AUDIT · PASS')
