/* Deterministic executive projection. Never promotes historical clues. */
(function(root){
'use strict';
const sections={manufacturers:'Fabricantes',distributors:'Mayoristas',integrators:'Integradores',clients_public:'Contratación pública',clients_private:'Cuentas privadas',trends:'Tendencias',architectures:'Arquitecturas'};
const fields={capabilities:'Capacidad',services:'Servicio',vendor_relations:'Fabricante',specializations:'Especialización',request_or_need:'Necesidad publicada',estimated_amount:'Importe publicado',milestone_date:'Hito publicado',procurement_stage:'Estado publicado',technology_signals:'Señal tecnológica',investment_signals:'Inversión',public_projects:'Proyecto',observed:'Observación',recent_signals:'Señal',layers:'Capa',vendors:'Fabricante',revenue:'Facturación',known_customers:'Cliente documentado',public_cases:'Caso documentado',notice_id:'Expediente'};
const normalize=v=>String(v??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
function safeUrl(raw){try{const u=new URL(raw);return ['https:','http:'].includes(u.protocol)&&!u.username&&!u.password?u.href:'';}catch(_){return '';}}
function support(ev){return ev&&ev.accrediting!==false&&!['stale','rejected','contradicted'].includes(ev.freshness_status)&&!ev.contradicted&&(['A1','A2','B','C'].includes(ev.intelligence_tier)||['PUBLIC_PRIMARY','PUBLIC_SECONDARY','WESTCON_DOCUMENT_CURRENT','WESTCON_FIRST_PARTY_CURRENT'].includes(ev.provenance_origin));}
function dateValue(raw){const s=String(raw||'');if(!/^\d{4}-\d{2}-\d{2}/.test(s))return null;const n=Date.parse(s.slice(0,10)+'T00:00:00Z');return Number.isFinite(n)?n:null;}
function facts(field,key){
 if(!field)return [];
 const values=Array.isArray(field.value)?field.value:[field.value];
 return values.filter(v=>v!==undefined&&v!==null&&v!==''&&v!==false).map(value=>{
  const target=Array.isArray(field.value)?(field.items||[]).find(i=>JSON.stringify(i.value)===JSON.stringify(value)):field;
  const evidence=(target?.evidence||[]).filter(support);
  return {key,label:fields[key]||key,value:String(value),evidence};
 }).filter(f=>f.evidence.length);
}
function build(data,now=Date.now()){
 const result=[];
 for(const [section,label] of Object.entries(sections))for(const row of data[section]||[]){
  const entries=Object.keys(fields).flatMap(k=>facts(row.fields?.[k],k));if(!entries.length)continue;
  const scope=facts(row.fields?.scope,'scope').map(x=>x.value).join(' ')||'Sin ámbito acreditado';
  const milestone=entries.find(x=>x.key==='milestone_date');const deadline=dateValue(milestone?.value);
  const stages=entries.filter(x=>x.key==='procurement_stage').map(x=>normalize(x.value)).join(' ');
  const closed=/adjudic|award|cerrad|closed|cancel|formaliz|result/.test(stages);
  const dated=entries.flatMap(f=>f.evidence.map(e=>dateValue(e.retrieved_at||e.date))).filter(v=>v!==null&&v<=now);
  const checked=dated.length?Math.max(...dated):null;
  result.push({id:section+':'+row.id,name:row.name,section,label,scope,facts:entries,deadline,closed,checked,upcoming:section==='clients_public'&&!closed&&deadline!==null&&deadline>=now-86400000&&deadline<=now+90*86400000,search:normalize([row.name,scope,...entries.map(x=>x.value)].join(' '))});
 }
 return result;
}
function select(rows,options={}){
 const terms=normalize(options.query||'').trim().split(/\s+/).filter(Boolean);
 return rows.filter(r=>(!options.section||r.section===options.section)&&(!options.scope||new RegExp('\\b'+options.scope+'\\b').test(r.scope))&&(!options.watchedOnly||(options.watched||[]).includes(r.id))&&(!options.upcomingOnly||r.upcoming)&&terms.every(t=>r.search.includes(t))).sort((a,b)=>Number(b.upcoming)-Number(a.upcoming)||(a.upcoming&&b.upcoming?a.deadline-b.deadline:0)||(b.checked||0)-(a.checked||0)||a.name.localeCompare(b.name,'es'));
}
const api={sections,fields,safeUrl,support,dateValue,facts,build,select};root.WestconObservatory=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
