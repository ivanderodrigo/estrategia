#!/usr/bin/env python3
from __future__ import annotations
import argparse, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from v316.pipeline import run
from v316.validate_v316 import validate
PROFILE_MAP={'daily':'daily','weekly':'weekly','deep':'weekly','monthly':'monthly','exhaustive':'monthly'}
def parse_args():
    p=argparse.ArgumentParser(description='Westcon Iberia Business Intelligence v3.16 supervisor');p.add_argument('--profile',default='daily',choices=sorted(PROFILE_MAP));p.add_argument('--max-runtime',type=int,default=720);p.add_argument('--fallback-runtime',type=int,default=0);p.add_argument('--skip-v33',action='store_true');return p.parse_args()
def main():
    args=parse_args();canonical=PROFILE_MAP[args.profile];foundation_rc=0
    if not args.skip_v33:
        reserve=max(90,min(300,int(args.max_runtime*.24)));fallback=max(0,int(args.fallback_runtime or 0));foundation=max(90,args.max_runtime-reserve-fallback)
        print(f'v3.16 foundation · investigación {canonical} hasta {foundation}s · fuentes ampliadas',flush=True)
        try:foundation_rc=subprocess.run([sys.executable,str(ROOT/'scripts/research_supervisor_v33.py'),'--profile',canonical,'--max-runtime',str(foundation)],cwd=ROOT,timeout=foundation+60).returncode
        except subprocess.TimeoutExpired:foundation_rc=124
        if foundation_rc and fallback>0:
            try:
                rc=subprocess.run([sys.executable,str(ROOT/'scripts/research_supervisor_v33.py'),'--profile',canonical,'--max-runtime',str(fallback)],cwd=ROOT,timeout=fallback+45).returncode
                if rc==0:foundation_rc=0
            except subprocess.TimeoutExpired:pass
        if foundation_rc:print('v3.16 warning · se conserva la última evidencia pública válida y continúa la reconstrucción',flush=True)
    print('v3.16 · reconstruyendo mayoristas validados + ecosistema fabricante↔integrador + IBEX/PSI + contratación exacta',flush=True)
    result=run(ROOT,args.profile,foundation_rc=foundation_rc);errors=validate(ROOT)
    if errors:print('v3.16 validation failed · '+'; '.join(errors[:20]),file=sys.stderr,flush=True);return 1
    graph=result.get('integrator_graph') or {};dist=result.get('distributor_validation') or {};proc=result.get('public_procurement') or {}
    print(f"v3.16.0 published · fabricantes {result['manufacturers']} · mayoristas validados {result['distributors']} · integradores {result['integrators']} · relaciones fabricante↔integrador {graph.get('unique_vendor_integrator_edges',0)} · clientes {result['clients']} · pliegos exactos {proc.get('exact_notices',0)} · fuentes {result['sources']} · descartados no validados {len(dist.get('removed_unvalidated') or [])} · gaps activos {result['research_gaps']}",flush=True);return 0
if __name__=='__main__':raise SystemExit(main())
