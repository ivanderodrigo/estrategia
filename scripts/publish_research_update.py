#!/usr/bin/env python3
import argparse,os,subprocess,sys
p=argparse.ArgumentParser();p.add_argument('--message',default='chore: update current decision intelligence');p.add_argument('--attempts',type=int,default=3);a=p.parse_args()
allowed=[
 'data/current/intelligence.json','data/current/last_run.json','data/current/relationship_graph.json','data/current/research_gaps.json','data/current/metrics_before_after.json','data/current/coverage_report.json','data/current/source_report.json','data/current/research_learning.json','data/current/research_ledger.json','data/current/quality_report.json','data/current/supervisor.json',
 'data/public/manifest.json','data/public/last_run.json','data/public/sections/manufacturers.json','data/public/sections/distributors.json','data/public/sections/integrators.json','data/public/sections/clients_public.json','data/public/sections/clients_private.json','data/public/sections/trends.json','data/public/sections/architectures.json']
if os.environ.get('GITHUB_ACTIONS','').lower()=='true':
 subprocess.run(['git','config','--local','user.name','github-actions[bot]'],check=True);subprocess.run(['git','config','--local','user.email','41898282+github-actions[bot]@users.noreply.github.com'],check=True)
# Do not publish a stale research snapshot over code/data that changed while this job was running.
if os.environ.get('GITHUB_ACTIONS','').lower()=='true':
 subprocess.run(['git','fetch','origin','main'],check=True)
 local=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();remote=subprocess.check_output(['git','rev-parse','origin/main'],text=True).strip()
 if local!=remote:
  print('Remote main changed during research; skipping stale snapshot publication safely.');sys.exit(0)
subprocess.run(['git','add','--',*allowed],check=True)
if subprocess.run(['git','diff','--cached','--quiet']).returncode==0: print('No canonical intelligence changes to publish');sys.exit(0)
subprocess.run(['git','commit','-m',a.message],check=True)
for _ in range(max(1,a.attempts)):
 r=subprocess.run(['git','push','origin','HEAD:main'])
 if r.returncode==0:sys.exit(0)
 subprocess.run(['git','fetch','origin','main'],check=False);time_to_retry=False
print('Unable to publish canonical intelligence after retries');sys.exit(1)
