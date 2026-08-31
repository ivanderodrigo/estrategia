#!/usr/bin/env python3
from __future__ import annotations
import argparse,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from v318.pipeline import run
from v318.validate_v318 import validate
PROFILE_MAP={'daily':'daily','weekly':'weekly','deep':'weekly','monthly':'monthly','exhaustive':'monthly'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--profile',default='daily',choices=sorted(PROFILE_MAP));p.add_argument('--max-runtime',type=int,default=720);p.add_argument('--fallback-runtime',type=int,default=0);p.add_argument('--skip-foundation',action='store_true');a=p.parse_args();rc=0
 if not a.skip_foundation:
  reserve=max(120,min(360,int(a.max_runtime*.28)));foundation=max(90,a.max_runtime-reserve-max(0,a.fallback_runtime))
  try:rc=subprocess.run([sys.executable,str(ROOT/'scripts/research_supervisor_v317.py'),'--profile',a.profile,'--max-runtime',str(foundation),'--fallback-runtime','0','--skip-v33'],cwd=ROOT,timeout=foundation+60).returncode
  except subprocess.TimeoutExpired:rc=124
 r=run(ROOT,a.profile,rc);errs=validate(ROOT)
 if errs:print('VALIDATION FAIL · '+'; '.join(errs[:20]),file=sys.stderr);return 1
 print(f"v3.18.0 published · gaps {r['research_gaps']} · graph {r['graph']['relationships']} relaciones · linecards {r['graph']['linecards_found']}");return 0
if __name__=='__main__':raise SystemExit(main())
