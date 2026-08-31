"""Resilient queue/checkpoint primitives for the v3.17 gap researcher.

Network adapters can consume this queue without coupling publication to one
provider. A source failure is recorded and the remaining work continues.
"""
from __future__ import annotations
import json
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
from typing import Any,Callable
def run_queue(gaps:dict[str,Any],adapter:Callable[[dict[str,Any]],dict[str,Any]],out_dir:Path,max_tasks:int|None=None)->dict[str,Any]:
 out_dir.mkdir(parents=True,exist_ok=True);checkpoint=out_dir/'research_checkpoint.json';learning_path=out_dir/'research_learning.json';previous={}
 if checkpoint.exists():
  try:previous=json.loads(checkpoint.read_text(encoding='utf-8'))
  except json.JSONDecodeError:previous={}
 completed=set(previous.get('completed_task_ids') or []);events=[];domain_failures=defaultdict(int);filled=0;errors=0;duplicates=0;processed=0
 for gap in gaps.get('gaps') or []:
  for step in gap.get('passes') or []:
   task_id=f"{gap['id']}:{step['pass']}"
   if task_id in completed:continue
   if max_tasks is not None and processed>=max_tasks:break
   processed+=1;started=datetime.now(timezone.utc)
   try:
    result=adapter({'task_id':task_id,'gap':gap,'step':step,'timeout_seconds':20,'retry':gap.get('retry')}) or {};status=str(result.get('status') or 'no-result');filled+=int(bool(result.get('field_updated')));duplicates+=int(result.get('duplicates') or 0);completed.add(task_id)
   except Exception as exc:
    status='error';result={'error':f'{type(exc).__name__}: {exc}'};errors+=1
   events.append({'task_id':task_id,'query':step.get('query'),'strategy':step.get('strategy'),'source':result.get('source'),'status':status,'results':int(result.get('results') or 0),'fields_filled':int(bool(result.get('field_updated'))),'quality':result.get('quality'),'elapsed_ms':round((datetime.now(timezone.utc)-started).total_seconds()*1000,1),'error':result.get('error'),'duplicates':int(result.get('duplicates') or 0)})
   if len(events)%25==0:checkpoint.write_text(json.dumps({'updated_at':datetime.now(timezone.utc).isoformat(),'completed_task_ids':sorted(completed)},ensure_ascii=False,indent=2),encoding='utf-8')
  if max_tasks is not None and processed>=max_tasks:break
 checkpoint.write_text(json.dumps({'updated_at':datetime.now(timezone.utc).isoformat(),'completed_task_ids':sorted(completed)},ensure_ascii=False,indent=2),encoding='utf-8')
 strategies=defaultdict(lambda:{'attempts':0,'useful':0,'errors':0})
 for event in events:
  row=strategies[event['strategy']];row['attempts']+=1;row['useful']+=int(event['fields_filled']>0);row['errors']+=int(event['status']=='error')
 learning={'version':'3.17.0','updated_at':datetime.now(timezone.utc).isoformat(),'events':events,'strategy_performance':dict(strategies),'summary':{'processed':processed,'fields_filled':filled,'errors':errors,'duplicates':duplicates},'policy':'Priorizar estrategias con utilidad observada; reducir temporalmente fuentes con errores repetidos sin eliminarlas.'};learning_path.write_text(json.dumps(learning,ensure_ascii=False,indent=2),encoding='utf-8');return learning
