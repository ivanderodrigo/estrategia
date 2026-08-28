#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from v310.pipeline import run
from v310.validate_v310 import validate

PROFILE_MAP={'daily':'daily','weekly':'weekly','deep':'weekly','monthly':'monthly','exhaustive':'monthly'}

def parse_args():
    p=argparse.ArgumentParser(description='Westcon Iberia Business Intelligence v3.10 supervisor')
    p.add_argument('--profile',default='daily',choices=sorted(PROFILE_MAP));p.add_argument('--max-runtime',type=int,default=720);p.add_argument('--fallback-runtime',type=int,default=0);p.add_argument('--skip-v33',action='store_true')
    return p.parse_args()

def main():
    args=parse_args();canonical=PROFILE_MAP[args.profile];foundation_rc=0
    if not args.skip_v33:
        reserve=max(75,min(240,int(args.max_runtime*.22)));fallback=max(0,int(args.fallback_runtime or 0));foundation=max(90,args.max_runtime-reserve-fallback)
        print(f'v3.10 foundation · investigación {canonical} hasta {foundation}s',flush=True)
        try: foundation_rc=subprocess.run([sys.executable,str(ROOT/'scripts/research_supervisor_v33.py'),'--profile',canonical,'--max-runtime',str(foundation)],cwd=ROOT,timeout=foundation+60).returncode
        except subprocess.TimeoutExpired: foundation_rc=124
        if foundation_rc and fallback>0:
            print(f'v3.10 fallback · reintento acotado hasta {fallback}s',flush=True)
            try:
                rc=subprocess.run([sys.executable,str(ROOT/'scripts/research_supervisor_v33.py'),'--profile',canonical,'--max-runtime',str(fallback)],cwd=ROOT,timeout=fallback+45).returncode
                if rc==0:foundation_rc=0
            except subprocess.TimeoutExpired: pass
        if foundation_rc:print('v3.10 warning · se conserva la última evidencia pública válida y continúa la reconstrucción',flush=True)
    print('v3.10 · reconstruyendo inteligencia + clientes + aportaciones manuales + documentos del repositorio',flush=True)
    result=run(ROOT,canonical,foundation_rc=foundation_rc);errors=validate(ROOT)
    if errors:
        print('v3.10 validation failed · '+'; '.join(errors[:16]),file=sys.stderr,flush=True);return 1
    repo=result.get('repo_inputs') or {}
    print(f"v3.10.0 published · fabricantes {result['manufacturers']} · mayoristas {result['distributors']} · integradores {result['integrators']} · clientes {result['clients']} · tendencias {result['trends']} · arquitecturas {result['architectures']} · fuentes {result['source_count']} · inputs manual {repo.get('manual_contributions',0)} · docs {repo.get('documents',0)}",flush=True)
    return 0

if __name__=='__main__':raise SystemExit(main())
