#!/usr/bin/env python3
from pathlib import Path
import json,re,sys
ROOT=Path(__file__).resolve().parents[1];errors=[]
def err(x):errors.append(x)
if (ROOT/'VERSION').read_text(encoding='utf-8').strip()!='3.20.0':err('VERSION != 3.20.0')
for req in ['engine/pipeline.py','engine/research/web_intelligence.py','config/current/research_policy.json','data/current/intelligence.json','data/current/quality_report.json','data/public/manifest.json','assets/app/intelligence.js']:
 if not (ROOT/req).exists():err('missing '+req)
scan=['index.html','assets/app/intelligence.js','scripts/research_supervisor.py','scripts/publish_research_update.py','engine/pipeline.py']+[str(p.relative_to(ROOT)) for p in (ROOT/'.github/workflows').glob('*.yml')]
for rel in scan:
 txt=(ROOT/rel).read_text(encoding='utf-8')
 if re.search(r'(assets|data|config|scripts)/v\d+',txt,re.I):err('legacy runtime reference: '+rel)
for d in ['assets','data','config','scripts']:
 for p in (ROOT/d).glob('v[0-9]*'):
  if p.exists():err('legacy directory present: '+str(p.relative_to(ROOT)))
D=json.loads((ROOT/'data/current/intelligence.json').read_text(encoding='utf-8'));G=json.loads((ROOT/'data/current/research_gaps.json').read_text(encoding='utf-8'));R=json.loads((ROOT/'data/current/relationship_graph.json').read_text(encoding='utf-8'));Q=json.loads((ROOT/'data/current/quality_report.json').read_text(encoding='utf-8'));M=json.loads((ROOT/'data/public/manifest.json').read_text(encoding='utf-8'))
if D.get('meta',{}).get('version')!='3.20.0':err('dataset version != 3.20.0')
if Q.get('errors'):err('quality audit errors: '+str(Q['errors'][:3]))
if any(r.get('name')=='Comstor' for r in D.get('distributors',[])):err('Comstor classified as competitor distributor')
if any(r.get('name')=='Forescout' for r in D.get('manufacturers',[])):err('Forescout incorrectly in Westcon manufacturers')
mfr={r['name'] for r in D.get('manufacturers',[])}
if any(r['name'] in mfr for r in D.get('distributors',[])):err('manufacturer classified as distributor')
if any(not str(e.get('url') or '').startswith('http') for r in R.get('relationships',[]) for e in r.get('evidence',[])):err('relationship evidence without URL')
if any(g.get('research_state')!='Por investigar' for g in G.get('gaps',[])):err('open gap has invalid state')
if G.get('total_gaps',99999)>=1450:err('release does not reduce v3.19 gaps')
if set(M.get('sections',{}))!={'manufacturers','distributors','integrators','clients_public','clients_private','trends','architectures'}:err('public manifest sections invalid')
js=(ROOT/'assets/app/intelligence.js').read_text(encoding='utf-8');pages=(ROOT/'.github/workflows/pages-deploy.yml').read_text(encoding='utf-8')
if 'data/current/intelligence.json' in js:err('frontend loads internal dataset')
if 'cp data/current' in pages:err('Pages publishes internal data')
names={r['name'] for r in D.get('manufacturers',[])}
if not {'Check Point','Proofpoint'}.issubset(names):err('Portugal portfolio additions missing')
print('v3.20 canonical validation:', 'PASS' if not errors else 'FAIL')
for e in errors:print(' -',e)
sys.exit(1 if errors else 0)
