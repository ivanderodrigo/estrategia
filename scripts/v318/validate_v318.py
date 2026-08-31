#!/usr/bin/env python3
from __future__ import annotations
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def canon(v):return re.sub(r'[^a-z0-9]+',' ',str(v or '').casefold()).strip()
def validate(root=None):
 b=root or ROOT;errs=[]
 def c(ok,msg):
  if not ok:errs.append(msg)
 try:
  d=json.load(open(b/'data/v318/intelligence.json',encoding='utf-8'));g=json.load(open(b/'data/v318/relationship_graph.json',encoding='utf-8'));m=json.load(open(b/'data/v318/metrics_before_after.json',encoding='utf-8'))
 except Exception as e:return [str(e)]
 c((b/'VERSION').read_text().strip()=='3.18.0','VERSION');c(d['meta']['version']=='3.18.0','dataset version')
 c(len(d['manufacturers'])>=36 and len(d['distributors'])>=50 and len(d['integrators'])>=120,'coverage')
 vendors={canon(x['name']) for x in d['manufacturers']};dist={canon(x['name']) for x in d['distributors']};c(not vendors&dist,'fabricantes como mayoristas');c('comstor' not in dist,'Comstor competidor')
 c('forescout' not in vendors,'Forescout en portfolio Westcon')
 c(len(g['relationships'])>=1000,'grafo insuficiente');c(all(r.get('entity_a_id') and r.get('entity_b_id') and r.get('evidence') for r in g['relationships'] if r['status']=='CONFIRMED'),'relaciones confirmadas sin evidencia')
 c(m['after']['research_gaps']<m['before']['research_gaps'],'gaps no reducidos');c(m['graph']['linecards_found']>=9,'linecards insuficientes');c(m['graph']['confirmed_distributor_vendor']>=400,'relaciones mayorista-fabricante insuficientes')
 js=(b/'assets/v318/intelligence.js').read_text(encoding='utf-8');idx=(b/'index.html').read_text(encoding='utf-8')
 for token in ['clients_public:renderClients','clients_private:renderClients','data-col-toggle','col-resizer','westcon-table-widths','resetTablePrefs'] : c(token in js,'tabla común: '+token)
 c("fetch('data/v318/intelligence.json'" in js,'frontend dataset');c('assets/v318/intelligence.js?v=3.18.0' in idx,'index assets')
 for n in ['research-daily.yml','research-weekly.yml','research-monthly.yml']:
  t=(b/'.github/workflows'/n).read_text(encoding='utf-8');c('research_supervisor_v318.py' in t and 'scripts/v318/validate_v318.py' in t,n)
 return errs
if __name__=='__main__':
 e=validate();print('VALIDACIÓN v3.18.0 · PASS' if not e else 'VALIDACIÓN v3.18.0 · FAIL · '+'; '.join(e));raise SystemExit(bool(e))
