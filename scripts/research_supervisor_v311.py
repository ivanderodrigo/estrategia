#!/usr/bin/env python3
from __future__ import annotations
import argparse, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from v311.pipeline import run
from v311.validate_v311 import validate
PROFILE_MAP={'daily':'daily','weekly':'weekly','deep':'weekly','monthly':'monthly','exhaustive':'monthly'}
def parse_args():
    p=argparse.ArgumentParser(description='Westcon Iberia Business Intelligence v3.11 supervisor');p.add_argument('--profile',default='daily',choices=sorted(PROFILE_MAP));p.add_argument('--max-runtime',type=int,default=720);p.add_argument('--fallback-runtime',type=int,default=0);p.add_argument('--skip-v33',action='store_true');return p.parse_args()
def main():
    args=parse_args();canonical=PROFILE_MAP[args.profile];foundation_rc=0
    if not args.skip_v33:
        reserve=max(75,min(240,int(args.max_runtime*.22)));fallback=max(0,int(args.fallback_runtime or 0));foundation=max(90,args.max_runtime-reserve-fallback)
        print(f'v3.11 foundation · investigación {canonical} hasta {foundation}s',flush=True)
        try:foundation_rc=subprocess.run([sys.executable,str(ROOT/'scripts/research_supervisor_v33.py'),'--profile',canonical,'--max-runtime',str(foundation)],cwd=ROOT,timeout=foundation+60).returncode
        except subprocess.TimeoutExpired:foundation_rc=124
        if foundation_rc and fallback>0:
            try:
                rc=subprocess.run([sys.executable,str(ROOT/'scripts/research_supervisor_v33.py'),'--profile',canonical,'--max-runtime',str(fallback)],cwd=ROOT,timeout=fallback+45).returncode
                if rc==0:foundation_rc=0
            except subprocess.TimeoutExpired:pass
        if foundation_rc:print('v3.11 warning · se conserva la última evidencia pública válida y continúa la reconstrucción',flush=True)
    print('v3.11 · reconstruyendo inteligencia pública trazable y clasificación estricta de mayoristas',flush=True)
    result=run(ROOT,canonical,foundation_rc=foundation_rc);errors=validate(ROOT)
    if errors:print('v3.11 validation failed · '+'; '.join(errors[:16]),file=sys.stderr,flush=True);return 1
    cleanup=result.get('distribution_cleanup') or {}
    print(f"v3.11.0 published · fabricantes {result['manufacturers']} · mayoristas {result['distributors']} · integradores {result['integrators']} · clientes {result['clients']} · tendencias {result['trends']} · arquitecturas {result['architectures']} · fuentes {result['source_count']} · fabricantes retirados de Mayoristas {cleanup.get('removed_manufacturer_rows',0)}",flush=True);return 0
if __name__=='__main__':raise SystemExit(main())
