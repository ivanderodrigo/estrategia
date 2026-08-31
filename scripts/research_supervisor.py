#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from engine.pipeline import run as build
VERSION='3.20.0'
p=argparse.ArgumentParser();p.add_argument('--profile',choices=['daily','deep','exhaustive'],default='daily');p.add_argument('--max-runtime',type=int,default=720);p.add_argument('--fallback-runtime',type=int,default=0);a=p.parse_args()
start=time.monotonic();status={'version':VERSION,'profile':a.profile,'started_at':time.time(),'requested_max_runtime_s':a.max_runtime,'stages':[]}
reserve=min(180,max(45,a.max_runtime//7)); research_budget=max(20,a.max_runtime-reserve)
cmd=[sys.executable,'-m','engine.research.web_intelligence','--profile',a.profile,'--max-runtime',str(research_budget)]
try:
    proc=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True,timeout=research_budget+15)
    if proc.returncode==0:
        lines=[x for x in proc.stdout.splitlines() if x.strip()];r=json.loads(lines[-1]) if lines else {}
        status['stages'].append({'research':'ok','fetch_attempts':r.get('fetch_attempts',0),'fetch_successes':r.get('fetch_successes',0),'pages_relevant':r.get('pages_relevant',0),'candidate_evidences':r.get('candidate_evidences',0),'accepted_evidences':r.get('accepted_evidences',0),'fields_enriched':r.get('fields_enriched',0),'values_added':r.get('values_added',0),'stop_reason':r.get('stop_reason')})
    else:
        status['stages'].append({'research':'degraded','error':(proc.stderr or proc.stdout)[-500:]})
except subprocess.TimeoutExpired:
    status['stages'].append({'research':'checkpoint-timeout','budget_s':research_budget,'note':'Subproceso terminado por supervisor; se conservan checkpoints parciales.'})
except Exception as e:
    status['stages'].append({'research':'degraded','error':str(e)[:500]})
try:
    m=build(); after=m['after']; before=m['before']
    status['stages'].append({'build':'ok','gaps':after['gaps_total'],'gaps_closed_vs_release_baseline':before['gaps_total']-after['gaps_total'],'distributor_gaps':after['gaps_by_section']['distributors'],'integrator_gaps':after['gaps_by_section']['integrators'],'quality_score':json.loads((ROOT/'data/current/quality_report.json').read_text(encoding='utf-8')).get('score')})
except Exception as e:
    status['stages'].append({'build':'failed','error':str(e)[:500]});raise
finally:
    status['elapsed_s']=round(time.monotonic()-start,2);(ROOT/'data/current/supervisor.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(status,ensure_ascii=False,indent=2))
