#!/usr/bin/env python3
from __future__ import annotations
import copy,json,re,sys,hashlib
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
from typing import Any,Mapping
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from v317.build_intelligence import build as build_v317, merge_field, evidence_rows, unique_evidence, field_value, values, canonical as canon317, evidence_level, claim_type_for
from v317.gap_engine import build_gaps,has_value
from v317.metrics import calculate_metrics,compare_metrics
from v34.common import write_json
VERSION='3.18.0'; SECTIONS=('manufacturers','distributors','integrators','clients_public','clients_private','trends','architectures')

def load(rel,default=None):
 try:return json.loads((ROOT/rel).read_text(encoding='utf-8'))
 except Exception:return {} if default is None else default

def canonical(v:Any)->str:
 s=str(v or '').casefold().translate(str.maketrans('áéíóúüñçãõâêôàèìòùäëïöü','aeiouuncaoaeoaeiouaeiou'))
 return re.sub(r'[^a-z0-9]+',' ',s).strip()

def alias_map():
 cfg=load('config/v318/entity_aliases.json',{})
 out={}
 for name,aliases in cfg.items():
  out[canonical(name)]=name
  for a in aliases:out[canonical(a)]=name
 return out
ALIASES=alias_map()
def resolve_name(name:str)->str:return ALIASES.get(canonical(name),name)

def row_index(data,section):
 idx={}
 for r in data.get(section) or []:
  idx[canonical(r.get('name'))]=r
  idx[canonical(resolve_name(r.get('name')))] = r
 return idx

def portfolio_sets(data):
 all_names={resolve_name(r['name']) for r in data.get('manufacturers') or []}
 pt=set(all_names); es=set(all_names)-{'Proofpoint','Check Point'}
 return es,pt

def source_as_ev(src):
 return {**src,'retrieved_at':'2026-08-31','source_grade':'A','classification':'linecard' if 'line' in canonical(src.get('title')) or 'portfolio' in canonical(src.get('title')) else 'public'}

def apply_official_research(data):
 cfg=load('config/v318/official_relationships.json',{}); counts=Counter(); dist_idx=row_index(data,'distributors'); mfr_idx=row_index(data,'manufacturers'); es_port,pt_port=portfolio_sets(data)
 graph_seed=[]
 for card in cfg.get('linecards') or []:
  dist=dist_idx.get(canonical(resolve_name(card['distributor']))) or dist_idx.get(canonical(card['distributor']))
  if not dist:continue
  ev=source_as_ev(card['source']); country=card.get('country','GLOBAL'); vendors=[]
  for raw in card.get('vendors') or []:
   v=resolve_name(raw); vendors.append(v)
   graph_seed.append({'a_type':'distributor','a':dist['name'],'relation':'distributes','b_type':'manufacturer','b':v,'country':country,'evidence':[ev],'status':'CONFIRMED','confidence':.90 if country in {'ES','PT'} else .82,'valid_from':card['source'].get('date'),'valid_to':None,'derived':False})
  counts['linecards_found']+=1; counts['linecard_vendors_extracted']+=len(vendors)
  counts['linecard_values_added']+=merge_field(dist,'vendor_relations',vendors,[ev],'fact','Fabricantes identificados en fuente oficial del mayorista; el alcance geográfico se conserva como figura en la fuente.')
  applicable=pt_port if country=='PT' else es_port if country=='ES' else es_port|pt_port
  overlap=[v for v in vendors if resolve_name(v) in applicable]
  others=[v for v in vendors if resolve_name(v) not in applicable]
  counts['overlap_values_added']+=merge_field(dist,'westcon_overlap',overlap,[ev],'fact','Intersección calculada contra el portfolio Westcon aplicable al ámbito de la evidencia.')
  counts['competitor_values_added']+=merge_field(dist,'competitor_vendor_overlap',others,[ev],'interpretation','Fabricantes fuera del portfolio Westcon aplicable; la competencia concreta depende de categoría, cuenta y alcance.')
  for v in vendors:
   m=mfr_idx.get(canonical(resolve_name(v)))
   if m:
    counts['reverse_values_added']+=merge_field(m,'distributors',[dist['name']],[ev],'fact','Propagación inversa desde un line card oficial: la misma evidencia alimenta la relación fabricante ↔ mayorista.')
 for ce in cfg.get('capability_evidence') or []:
  dist=dist_idx.get(canonical(resolve_name(ce['distributor']))) or dist_idx.get(canonical(ce['distributor']))
  if dist:counts['capability_values_added']+=merge_field(dist,ce['field'],ce.get('values') or [],[source_as_ev(ce['source'])],'fact','Capacidad publicada por el propio mayorista; no se extiende geografía más allá de la fuente.')
 return counts,graph_seed


def propagate_reverse_existing(data,counts):
 dist_idx=row_index(data,'distributors');int_idx=row_index(data,'integrators')
 dist_alias={'arrow':'Arrow ECS','arrow ecs':'Arrow ECS','v valley esprinet':'Esprinet / V-Valley','esprinet v valley':'Esprinet / V-Valley','ingecom ignition':'Ingecom Ignition','ignition technology':'Ignition Technology','infinigate':'Infinigate','ingram micro':'Ingram Micro','td synnex':'TD SYNNEX','exclusive networks':'Exclusive Networks','ireo':'IREO','wifidom':'Wifidom'}
 int_alias={'accenture':'Accenture Spain','capgemini':'Capgemini Spain','ntt data':'NTT DATA','ntt data spain':'NTT DATA','telefonica tech':'acens / Telefónica Tech','telefonica tech spain':'acens / Telefónica Tech','inetum':'Inetum Spain','logicalis spain':'Logicalis','axians':'Axians','axians spain':'Axians Spain','ibm':'IBM','ibm consulting':'IBM Consulting','deloitte':'Deloitte','devoteam':'Devoteam Portugal'}
 for m in data.get('manufacturers') or []:
  for fid,kind,idx,aliases in [('distributors','distributor',dist_idx,dist_alias),('integrators','integrator',int_idx,int_alias)]:
   spec=(m.get('fields') or {}).get(fid) or {}; all_ev=evidence_rows(spec)
   items=spec.get('items') or []
   vals=values(spec.get('value'))
   for raw in vals:
    text=str(raw);parts=[x.strip() for x in text.split('·')];name=parts[0];key=canonical(name);target_name=aliases.get(key,resolve_name(name));row=idx.get(canonical(target_name)) or idx.get(canonical(name))
    if not row:continue
    item_ev=[]
    for it in items:
     if canonical(str(it.get('value') or '')).startswith(canonical(name)):
      item_ev=evidence_rows(it);break
    ev=item_ev or all_ev
    if not ev:continue
    counts['reverse_existing_values_added']+=merge_field(row,'vendor_relations',[m['name']],ev,'fact','Propagación inversa desde una relación fabricante→ecosistema ya sustentada por evidencia trazable.')
    if kind=='integrator' and len(parts)>2:
     descriptor=' · '.join(parts[2:]).strip()
     if descriptor and canonical(descriptor) not in {'probable','confirmada','evidencia oficial'}:
      counts['reverse_specialization_values_added']+=merge_field(row,'specializations',[f"{m['name']} · {descriptor}"],ev,'fact','Nivel, rol o especialización tomado de la evidencia de relación del fabricante; no se generaliza a otras tecnologías.')

def clean_relation_values(data):
 # Nunca permitir autofabricante, fabricantes como mayoristas ni Comstor competidor.
 mfr_names={canonical(r['name']) for r in data.get('manufacturers') or []}
 data['distributors']=[r for r in data.get('distributors') or [] if canonical(r['name']) not in mfr_names and canonical(r['name']) not in {'comstor','westcon','westcon comstor'}]

def stable_id(*parts):return 'rel_'+hashlib.sha1('|'.join(map(str,parts)).encode()).hexdigest()[:18]
def entity_id(kind,name):return kind[:4]+'_'+hashlib.sha1(canonical(name).encode()).hexdigest()[:16]

def build_graph(data,seed):
 entities={}; rels=[]; seen=set()
 def add_entity(kind,name,country=''):
  name=resolve_name(name); key=(kind,canonical(name));
  if key not in entities:entities[key]={'id':entity_id(kind,name),'canonical_name':name,'aliases':sorted({a for a,c in ALIASES.items() if c==name}), 'historical_names':['Tech Data'] if name=='TD SYNNEX' else [],'country':country,'entity_type':kind}
  return entities[key]['id']
 def add_rel(a_type,a,rel,b_type,b,country,evidence,status='CONFIRMED',confidence=.8,derived=False):
  a=resolve_name(a);b=resolve_name(b)
  if canonical(a)==canonical(b):return
  aid=add_entity(a_type,a,country);bid=add_entity(b_type,b,country);evs=unique_evidence(evidence);key=(aid,rel,bid,country)
  if key in seen:return
  seen.add(key);rels.append({'id':stable_id(*key),'entity_a_id':aid,'entity_a':a,'relation':rel,'entity_b_id':bid,'entity_b':b,'country':country or 'GLOBAL','evidence':evs,'source':evs[0].get('source') if evs else '', 'date':max([e.get('date','') for e in evs] or ['']),'confidence':confidence,'status':status,'validity':'current' if confidence>=.8 else 'needs-corroboration','derived':derived})
 for r in seed:add_rel(r['a_type'],r['a'],r['relation'],r['b_type'],r['b'],r['country'],r['evidence'],r['status'],r['confidence'],r['derived'])
 # Propagar las relaciones ya visibles en mayoristas e integradores.
 for section,kind in [('distributors','distributor'),('integrators','integrator')]:
  for row in data.get(section) or []:
   for v in values(field_value(row,'vendor_relations')):
    ev=evidence_rows((row.get('fields') or {}).get('vendor_relations') or {})
    add_rel(kind,row['name'],'distributes' if kind=='distributor' else 'partners_with','manufacturer',str(v),'IBERIA',ev,'CONFIRMED' if ev else 'PROBABLE',.84 if ev else .62,False)
 # Cliente ↔ tecnología como señales, sin convertirlas en deployment confirmado.
 for section in ('clients_private','clients_public'):
  for row in data.get(section) or []:
   spec=(row.get('fields') or {}).get('technology_signals') or {}; ev=evidence_rows(spec)
   for tech in values(spec.get('value')):
    add_rel('client',row['name'],'technology_signal','technology',str(tech),str(field_value(row,'scope') or 'IBERIA'),ev,'SEÑAL',.48,True)
 return {'version':VERSION,'generated_at':datetime.now(timezone.utc).isoformat(),'entities':sorted(entities.values(),key=lambda x:(x['entity_type'],x['canonical_name'])),'relationships':rels,'model':{'truth_source':'relationship graph','bidirectional_projection':True,'canonical_entity_ids':True,'fields':['Entidad A','Relación','Entidad B','País','Evidencia','Fuente','Fecha','Confianza','Vigencia']}}

def reorder_schemas(data):
 order={
 'distributors':['scope','revenue','westcon_overlap','competitor_vendor_overlap','vendor_relations','differential_capabilities','services','capabilities','specializations','market_position','validation_status','distributor_type','job_vendors','job_profiles'],
 'clients_private':['scope','segment','index_universe','technology_signals','westcon_fit','hiring_signals','opportunity_notes','renewal_window','account_priority'],
 'clients_public':['scope','entity_type','notice_id','request_or_need','technology_signals','opportunity_area','estimated_amount','milestone_date','procurement_stage','westcon_fit','opportunity_notes']}
 for section,ids in order.items():
  schema=data.get('schemas',{}).get(section,[]);by={c['id']:c for c in schema};data['schemas'][section]=[by[i] for i in ids if i in by]+[c for c in schema if c['id'] not in ids]

def build():
 baseline=copy.deepcopy(build_v317());data=copy.deepcopy(baseline);counts,seed=apply_official_research(data);propagate_reverse_existing(data,counts);clean_relation_values(data);reorder_schemas(data);graph=build_graph(data,seed)
 data.setdefault('meta',{}).update({'version':VERSION,'generated_at':datetime.now(timezone.utc).isoformat(),'research_model':'entity-graph-cascade-adaptive','relationship_truth_source':'data/v318/relationship_graph.json','v318_research':{**dict(counts),'external_queries_executed_during_release':15,'official_domains_researched':['arrow.com','exclusive-networks.com','infinigate.com','ingrammicro.com','tdsynnex.com','esprinet.com','lidera.com'],'cascade_passes':18,'languages':['es','pt','en'],'adaptive_depth':True,'source_learning':True,'researched_at':'2026-08-31'},'traceability':'Relaciones canónicas y bidireccionales; señales débiles no se convierten en hechos.'})
 data['_baseline_v317']=baseline;data['_graph_v318']=graph;return data

def write_snapshot(data):
 baseline=data.pop('_baseline_v317');graph=data.pop('_graph_v318');out=ROOT/'data/v318';out.mkdir(parents=True,exist_ok=True)
 gaps=build_gaps(data,version=VERSION);before_gaps=build_gaps(baseline,version='3.17.0');before=calculate_metrics(baseline,before_gaps,version='3.17.0');after=calculate_metrics(data,gaps,version=VERSION);cmp=compare_metrics(before,after,baseline,data)
 # Release-specific graph metrics.
 confirmed=[r for r in graph['relationships'] if r['status']=='CONFIRMED'];dv=[r for r in confirmed if r['relation']=='distributes'];iv=[r for r in confirmed if r['relation']=='partners_with'];ct=[r for r in graph['relationships'] if r['relation']=='technology_signal']
 cmp['graph']={'entities':len(graph['entities']),'relationships':len(graph['relationships']),'confirmed_distributor_vendor':len(dv),'confirmed_integrator_vendor':len(iv),'client_technology_relations':len(ct),'linecards_found':data['meta']['v318_research'].get('linecards_found',0),'linecard_vendors_extracted':data['meta']['v318_research'].get('linecard_vendors_extracted',0),'queries_executed':data['meta']['v318_research']['external_queries_executed_during_release']}
 cmp['definition']='Comparación v3.17.0 → v3.18.0 manteniendo entidades y reglas de suficiencia; los gaps solo se cierran con evidencia incorporada.'
 write_json(out/'intelligence.json',data);write_json(out/'relationship_graph.json',graph);write_json(out/'research_gaps.json',gaps);write_json(out/'metrics_before_after.json',cmp);write_json(out/'coverage_report.json',{'version':VERSION,'sections':after['sections'],'gap_by_section':after['gap_by_section']});write_json(out/'source_report.json',{'version':VERSION,'catalog_sources':len(data.get('source_catalog') or []),'unique_evidence_sources':after['unique_sources'],'unique_domains':after['unique_domains'],'official_evidence':after['official_evidence'],'new_official_domains':data['meta']['v318_research']['official_domains_researched']})
 result={'version':VERSION,'status':'published',**{k:after[k] for k in ('manufacturers','distributors','integrators','clients','clients_public','clients_private','trends','architectures','sources','evidence','relationships','traceable_fields','research_gaps','critical_gaps','unique_sources','unique_domains','official_evidence','corroborated_evidence','populated_fields','overall_completeness_pct')},'gap_by_section':after['gap_by_section'],'sections':after['sections'],'graph':cmp['graph'],'v318_research':data['meta']['v318_research'],'finished_at':datetime.now(timezone.utc).isoformat()};write_json(out/'last_run.json',result);return result
if __name__=='__main__':print(json.dumps(write_snapshot(build()),ensure_ascii=False,indent=2))
