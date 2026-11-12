'use strict';
// Published-data audit of the distributor business lens. Does not edit or purge data.
const fs=require('fs');
const bi=require('../assets/app/business-intelligence.js');
function load(name){
  const path='data/public/sections/'+name+'.json';
  const payload=JSON.parse(fs.readFileSync(path,'utf8'));
  const registry=payload.evidence||{};
  const hydrate=obj=>{
    if(Array.isArray(obj))return obj.map(hydrate);
    if(!obj||typeof obj!=='object')return obj;
    const out={};
    for(const [k,v] of Object.entries(obj)){
      if(k==='evidence_ids')out.evidence=(v||[]).map(id=>registry[id]).filter(Boolean);
      else out[k]=hydrate(v);
    }
    return out;
  };
  return hydrate(payload.rows||[]);
}
const distributors=load('distributors');
const manufacturers=load('manufacturers');
const relevant=[],archived=[];
for(const row of distributors){
  const context=bi.distributorContext(row,manufacturers);
  (context.relevant?relevant:archived).push({name:row.name,reason:context.reasons[0]||'Sin vínculo competitivo acreditado'});
}
const report={
  distributors_total:distributors.length,
  with_westcon_context:relevant.length,
  archived_unproven:archived.length,
  retained_for_research:true,
  representative_relevant:relevant.slice(0,12),
  representative_archived:archived.slice(0,8)
};
console.log('AUDITORIA_MAYORISTAS_V63 '+JSON.stringify(report));
if(distributors.length&&relevant.length===0){
  throw new Error('La vista principal quedaría vacía; revisar mapeo de evidencias antes de desplegar');
}
