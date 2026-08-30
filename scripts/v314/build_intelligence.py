#!/usr/bin/env python3
from __future__ import annotations
import copy,json
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from v313.build_intelligence import build as build_v313, canonical, _field_value, _field_evidence
from v38.build_intelligence import field,atomic_item,dedupe_evidence,evidence,write
from v314.gap_engine import build_gaps
VERSION='3.14.0'
def load(rel,default=None):
 try:return json.loads((ROOT/rel).read_text(encoding='utf8'))
 except Exception:return {} if default is None else default
def ev(source,title,url,date='2026-08-30',description='',scope='GLOBAL',grade='B'):
 return evidence({'source':source,'title':title,'url':url,'date':date,'description':description,'scope':scope,'source_grade':grade,'classification':'public'})
def merge_list(row,fid,values,evs,confidence=.9,qualifier=None):
 old=(row.setdefault('fields',{}).get(fid) or {});existing=old.get('value') or [];existing=existing if isinstance(existing,list) else [existing];items=list(old.get('items') or [])
 for value in values:
  head=canonical(str(value).split('·',1)[0])
  if not any(canonical(str(v).split('·',1)[0])==head for v in existing):existing.append(value)
  if not any(canonical(str(i.get('value','')).split('·',1)[0])==head for i in items):
   a=atomic_item(value,evs,confidence)
   if a:items.append(a)
 built=field(existing,dedupe_evidence([*(old.get('evidence') or []),*evs],12),max(float(old.get('confidence') or 0),confidence),qualifier or old.get('qualifier'),items=items)
 if built:row['fields'][fid]=built
def schema(data,section):return data.setdefault('schemas',{}).setdefault(section,[])
def set_schema(data,section,order,updates):
 by={x.get('id'):dict(x) for x in schema(data,section)}
 for fid,spec in updates.items():by[fid]={**by.get(fid,{'id':fid}),**spec}
 tail=[fid for fid in by if fid not in order];data['schemas'][section]=[by[f] for f in [*order,*tail] if f in by]
def enrich_sources(data):
 rows={x.get('id'):dict(x) for x in data.get('source_catalog',[]) if x.get('id')}
 for raw in load('config/v314/source_additions.json',{}).get('sources',[]):
  sid=raw.get('source_id');rows[sid]={'id':sid,'name':raw.get('name'),'url':raw.get('url'),'class':raw.get('source_class'),'scope':raw.get('scope') or [],'dimensions':raw.get('dimensions') or [],'access_policy':raw.get('access_policy') or 'public'}
 data['source_catalog']=sorted(rows.values(),key=lambda x:(str(x.get('class') or ''),str(x.get('name') or '')));data['meta']['source_count']=len(data['source_catalog'])
def enrich_distributors(data):
 cfg=load('config/v314/business_enrichment.json',{});rows={r['name']:r for r in data.get('distributors',[])}
 rankev=ev('Channel Partner','Ranking del Canal 2026 · mayoristas por facturación 2025','https://www.channelpartner.es/mayoristas/los-primeros-mayoristas-de-espana-por-facturacion/','2026-04-08','Datos facilitados por las compañías o estimaciones de Channel Partner; se conserva el alcance España y el ejercicio 2025.','ES','B+')
 nationev=ev('Channel Partner','Mayoristas de capital nacional por ingresos 2025','https://www.channelpartner.es/mayoristas/los-primeros-mayoristas-de-capital-nacional-por-ingresos/','2026-04-17','Ranking español de distribuidores de capital nacional.','ES','B+')
 national={'Depau','Inforpor','DMI Computer','Ticnova','Infortisa'}
 for name,value in cfg.get('revenue_2025_es',{}).items():
  row=rows.get(name)
  if row:row.setdefault('fields',{})['revenue']=field(value,[nationev if name in national else rankev],.94,'Facturación/ventas públicas de la entidad en España; no se mezcla con cifra global del grupo.')
 caps_sources={
  'TD SYNNEX':ev('TD SYNNEX','PartnerFirst España','https://www.tdsynnex.com/eu/es/es/partnerfirst.html','2026-08-30','Portal oficial de capacidades y servicios de canal.','ES','A'),
  'Arrow ECS':ev('Arrow ECS','Arrow ECS España','https://www.arrow.com/globalecs/es/','2026-08-30','Portal oficial español de Arrow Enterprise Computing Solutions.','ES','A'),
  'ALSO':ev('ALSO','ALSO Cloud Marketplace España','https://www.also.com/ec/cms5/es_2610/2610/services/digital-services/also-cloud-marketplace/index.jsp','2026-08-30','Marketplace oficial con provisioning, billing y modelos de suscripción.','ES','A')}
 for name,values in cfg.get('official_capabilities',{}).items():
  row=rows.get(name);source=caps_sources.get(name)
  if row and source:merge_list(row,'differential_capabilities',values,[source],.93,'Capacidades diferenciales observadas públicamente; no implica superioridad frente a Westcon.')
 # Reuse already evidenced services/capabilities/specializations so the decision column is richer without inventing facts.
 for row in data.get('distributors',[]):
  values=[];evs=[]
  for fid in ('services','capabilities','specializations'):
   val=_field_value(row,fid) or [];val=val if isinstance(val,list) else [val]
   for v in val:
    if v not in values:values.append(v)
   evs.extend(_field_evidence(row,fid))
  if values and evs:merge_list(row,'differential_capabilities',values[:12],dedupe_evidence(evs,8),.82,'Síntesis derivada exclusivamente de capacidades/servicios con evidencia del propio mayorista.')
 # Direct competitive linecard signals with explicit geography.
 ex=rows.get('Exclusive Networks');exev=ev('IT Channel Portugal','Exclusive Networks e Fortinet reforçam Parceria em Portugal','https://www.itchannel.pt/news/distribuicao/exclusive-networks-e-fortinet-reforcam-parceria-em-portugal','2026-08-17','Exclusive Networks distribuye en Portugal todo el portfolio Fortinet.','PT','B+')
 if ex:merge_list(ex,'competitor_vendor_overlap',['Fortinet · Portugal'],[exev],.94,'Fabricante fuera del portfolio Westcon que compite con fabricantes/arquitecturas del portfolio.')
 td=rows.get('TD SYNNEX');tdev=ev('IT Channel Portugal','TD Synnex torna-se distribuidor global da Fortinet','https://www.itchannel.pt/news/distribuicao','2026-07-20','Señal global de distribución Fortinet; no se presenta como prueba de linecard ibérico específico.','GLOBAL','B')
 if td:merge_list(td,'competitor_vendor_overlap',['Fortinet · GLOBAL · Iberia por validar'],[tdev],.78,'Señal global competitiva; alcance Iberia pendiente de evidencia específica.')
 return {'revenue_rows':sum(bool(_field_value(r,'revenue')) for r in data.get('distributors',[])),'differential_capability_rows':sum(bool(_field_value(r,'differential_capabilities')) for r in data.get('distributors',[])),'competitor_linecard_rows':sum(bool(_field_value(r,'competitor_vendor_overlap')) for r in data.get('distributors',[]))}
def enrich_manufacturer_competitors(data):
 cfg=load('config/v314/business_enrichment.json',{}).get('manufacturer_competitors',{});rows={r['name']:r for r in data.get('manufacturers',[])}
 urls={
 '1Password':'https://www.gartner.com/reviews/product/1password/alternatives','Anomali':'https://www.gartner.com/reviews/product/the-anomali-platform/alternatives','AttackIQ':'https://www.gartner.com/reviews/product/attackiq-platform/alternatives','AudioCodes':'https://www.gartner.com/reviews/market/enterprise-sbc','Avaya':'https://www.gartner.com/reviews/product/avaya-aura-ucaas/alternatives','EfficientIP':'https://www.gartner.com/reviews/product/efficientip-solidserver-ddi/alternatives','FireMon':'https://www.gartner.com/reviews/product/firemon-policy-manager/alternatives','Fortanix':'https://www.gartner.com/reviews/product/fortanix-data-security-manager/alternatives','LevelBlue':'https://www.gartner.com/reviews/market/managed-security-services','Menlo Security':'https://www.gartner.com/reviews/market/security-service-edge/compare/cisco-systems-vs-menlo-security','XM Cyber':'https://www.gartner.com/reviews/product/xm-cyber-exposure-management-platform/alternatives'}
 touched=0
 for name,values in cfg.items():
  row=rows.get(name)
  if not row:continue
  source=ev('Gartner Peer Insights',f'{name} · market alternatives / peer comparison',urls[name],'2026-08-30','Competidores/alternativas utilizados como panorama de mercado; Peer Insights refleja comparaciones de usuarios y no un endorsement de Gartner.','GLOBAL','B')
  merge_list(row,'competitors',values,[source],.86,'Peers/alternativas de mercado; no implica equivalencia funcional total.');touched+=1
 return touched
def derive_distributor_overlap(data):
 active={canonical(r['name']):r['name'] for r in data.get('manufacturers',[])}
 for row in data.get('distributors',[]):
  vals=_field_value(row,'vendor_relations') or [];vals=vals if isinstance(vals,list) else [vals];evs=_field_evidence(row,'vendor_relations')
  overlap=[]
  for raw in vals:
   head=str(raw).split('·',1)[0].strip();key=canonical(head)
   if key in active:overlap.append(active[key])
  if overlap and evs:merge_list(row,'westcon_overlap',overlap,dedupe_evidence(evs,8),.88,'Intersección entre linecard público del mayorista y portfolio Westcon activo.')
def configure_schema(data):
 set_schema(data,'distributors',['validation_status','distributor_type','market_position','scope','revenue','vendor_relations','westcon_overlap','competitor_vendor_overlap','differential_capabilities','specializations','services','capabilities','job_vendors','job_profiles'],{
  'revenue':{'label':'Facturación / escala pública','help':'Ventas/facturación con año, geografía y fuente explícitos. No se mezclan cifras globales con España/Portugal.','clarify':True,'decision_required':True,'empty_mode':'neutral'},
  'vendor_relations':{'label':'Fabricantes / linecard público','help':'Fabricantes encontrados en linecards, anuncios de distribución o páginas oficiales. El alcance geográfico se conserva.','clarify':True,'decision_required':True,'empty_mode':'critical'},
  'westcon_overlap':{'label':'Fabricantes coincidentes con Westcon','help':'Intersección evidenciada entre el linecard del mayorista y el portfolio Westcon Iberia.','clarify':True,'decision_required':True,'empty_mode':'critical'},
  'competitor_vendor_overlap':{'label':'Fabricantes competidores de Westcon','help':'Fabricantes fuera del portfolio que compiten con fabricantes o arquitecturas Westcon y que aparecen en el linecard del mayorista. Una señal global se etiqueta como tal.','clarify':True,'decision_required':True,'empty_mode':'critical'},
  'differential_capabilities':{'label':'Capacidades diferenciales','help':'Servicios de valor, formación, financiación, marketplace, soporte, logística, servicios profesionales u otras capacidades públicas relevantes.','clarify':True,'decision_required':True,'empty_mode':'critical'},
  'market_position':{'empty_mode':'neutral'},'specializations':{'empty_mode':'neutral'},'services':{'empty_mode':'neutral'},'capabilities':{'empty_mode':'neutral'},'job_vendors':{'empty_mode':'neutral'},'job_profiles':{'empty_mode':'neutral'}})
 # Mark decision fields versus optional enrichments across the remaining sections.
 critical={'manufacturers':{'competitors','distributors','integrators'},'integrators':{'vendor_relations','specializations','services','capabilities'},'clients_public':{'opportunity_area','procurement_stage','technology_signals'},'clients_private':{'technology_signals','hiring_signals','westcon_fit','opportunity_notes'}}
 for sec,ids in critical.items():
  for col in schema(data,sec):
   if col.get('id') in ids:col['decision_required']=True;col['empty_mode']='critical'
   elif col.get('id') not in {'scope','domain','entity_type','notice_id','source_portal','segment','account_priority','index_universe'}:col.setdefault('empty_mode','neutral')
def build():
 data=copy.deepcopy(build_v313());data.setdefault('meta',{})['version']=VERSION;data['meta']['generated_at']=datetime.now(timezone.utc).isoformat();data['meta']['principle']='v3.14: encabezados descriptivos orientados al usuario, mayoristas orientados a decisión y separación explícita entre gaps críticos y enriquecimiento opcional.'
 enrich_sources(data);configure_schema(data);data['meta']['distributor_business_enrichment']=enrich_distributors(data);derive_distributor_overlap(data);data['meta']['manufacturer_competitor_enrichment']=enrich_manufacturer_competitors(data)
 data['meta']['traceability']='Las filas, inclusiones, exclusiones y derivaciones deben justificarse. Una ausencia opcional no se muestra como investigación crítica; una relación competitiva conserva fuente y alcance geográfico.'
 return data
def write_snapshot(data):
 out=ROOT/'data/v314';out.mkdir(parents=True,exist_ok=True);write('data/v314/intelligence.json',data);gaps=build_gaps(data);gaps['note']='v3.14 reduce falsos gaps: solo campos decisionales vacíos/obsoletos alimentan la cola crítica; señales opcionales siguen contabilizadas por separado.';write('data/v314/research_gaps.json',gaps)
 trace=sum(1 for sec in ('manufacturers','distributors','integrators','clients_public','clients_private','trends','architectures') for row in data.get(sec,[]) for spec in (row.get('fields') or {}).values() if spec and spec.get('evidence'))
 result={'version':VERSION,'generated_at':data['meta']['generated_at'],'finished_at':data['meta']['generated_at'],'profile':'snapshot','status':'published','manufacturers':len(data.get('manufacturers',[])),'distributors':len(data.get('distributors',[])),'integrators':len(data.get('integrators',[])),'clients':len(data.get('clients_public',[]))+len(data.get('clients_private',[])),'clients_public':len(data.get('clients_public',[])),'clients_private':len(data.get('clients_private',[])),'clients_private_es':sum(_field_value(r,'index_universe')=='IBEX 35' for r in data.get('clients_private',[])),'clients_private_pt':sum(_field_value(r,'index_universe')=='PSI' for r in data.get('clients_private',[])),'trends':len(data.get('trends',[])),'architectures':len(data.get('architectures',[])),'source_count':len(data.get('source_catalog',[])),'traceable_fields':trace,'research_gaps':gaps['total_gaps'],'high_priority_research_gaps':gaps['high_priority_gaps'],'gap_by_section':gaps['by_section'],'gap_missing_by_field':gaps['missing_by_field'],'optional_missing_by_field':gaps['optional_missing_by_field'],'distributor_validation':data['meta'].get('distributor_validation',{}),'distributor_business_enrichment':data['meta'].get('distributor_business_enrichment',{}),'public_procurement':data['meta'].get('public_procurement',{}),'integrator_graph':data['meta'].get('integrator_graph',{}),'research_policy':{'decision_gaps':'critical-only','optional_enrichment':'tracked-not-noisy','distributors':'positive-validation-first + business-columns','public_procurement':'exact-link-only','private_accounts':'IBEX35+PSI-complete'}}
 write('data/v314/last_run.json',result);return result
if __name__=='__main__':print(json.dumps(write_snapshot(build()),ensure_ascii=False))
