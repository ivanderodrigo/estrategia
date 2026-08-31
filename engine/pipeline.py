
from pathlib import Path
from datetime import datetime,timezone
import json
from .gaps import build_gaps
from .graph import build_graph
from .metrics import calculate
ROOT=Path(__file__).resolve().parents[1]
def load(rel): return json.loads((ROOT/rel).read_text(encoding='utf-8'))
def write(rel,obj,pretty=True):
    p=ROOT/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2 if pretty else None,separators=None if pretty else (',',':')),encoding='utf-8')
def run():
    data=load('data/current/intelligence.json');data['meta']['version']='3.19.0';data['meta']['generated_at']=datetime.now(timezone.utc).isoformat()
    graph=build_graph(data);gaps=build_gaps(data,'3.19.0');metrics=calculate(data,gaps,graph)
    baseline=load('config/current/release_baseline_metrics.json')
    before=baseline['before'];delta={k:metrics.get(k,0)-before.get(k,0) for k in ['entities_total','sources','domains_unique','evidences','official_evidences','gaps_total','relations','manufacturer_distributor_confirmed','manufacturer_integrator_confirmed','client_technology_relations']}
    compare={'definition':'v3.18.0 → v3.19.0 con la misma definición estricta de gap: un valor no cierra el gap sin evidencia pública suficiente.','before':before,'after':metrics,'delta':delta,'gap_reduction_pct':round((before['gaps_total']-metrics['gaps_total'])*100/max(1,before['gaps_total']),2)}
    data['meta']['source_count']=len(data.get('source_catalog',[]));write('data/current/intelligence.json',data,False);write('data/current/relationship_graph.json',graph);write('data/current/research_gaps.json',gaps);write('data/current/metrics_before_after.json',compare)
    write('data/current/coverage_report.json',gaps['coverage']);write('data/current/source_report.json',{'version':'3.19.0','sources':len(data.get('source_catalog',[])),'domains_unique':metrics['domains_unique'],'official_evidences':metrics['official_evidences']});write('data/current/last_run.json',{'version':'3.19.0','generated_at':datetime.now(timezone.utc).isoformat(),'profile':'release-build','status':'ok','metrics':metrics})
    return compare
if __name__=='__main__': print(json.dumps(run(),ensure_ascii=False,indent=2))
