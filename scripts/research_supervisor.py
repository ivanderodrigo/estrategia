#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from engine.research.distributor_web import run as research
from engine.pipeline import run as build
p=argparse.ArgumentParser();p.add_argument('--profile',choices=['daily','deep','exhaustive'],default='daily');p.add_argument('--max-runtime',type=int,default=720);p.add_argument('--fallback-runtime',type=int,default=0);a=p.parse_args()
start=time.monotonic();status={'version':'3.19.0','profile':a.profile,'started_at':time.time(),'requested_max_runtime_s':a.max_runtime,'stages':[]}
# Reserve time for build/validation. A failed source never fails the entire cycle.
research_budget=max(20,a.max_runtime-min(120,max(30,a.max_runtime//6)))
try:
    r=research(a.profile,max_runtime=research_budget);status['stages'].append({'research':'ok','checked':r['queries_or_urls_checked'],'successful':r.get('successful_fetches',0),'stop_reason':r.get('stop_reason')})
except Exception as e:
    status['stages'].append({'research':'degraded','error':str(e)[:300]})
try:
    m=build();status['stages'].append({'build':'ok','gaps':m['after']['gaps_total'],'distributor_gaps':m['after']['gaps_by_section']['distributors']})
except Exception as e:
    status['stages'].append({'build':'failed','error':str(e)[:300]});raise
finally:
    status['elapsed_s']=round(time.monotonic()-start,2);(ROOT/'data/current/supervisor.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(status,ensure_ascii=False,indent=2))
