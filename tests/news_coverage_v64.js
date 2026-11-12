'use strict';
const fs=require('fs'),assert=require('assert');
const bi=require('../assets/app/business-intelligence.js');
function load(section){
 const root=JSON.parse(fs.readFileSync('data/public/sections/'+section+'.json','utf8'));
 const evidence=root.evidence||{};
 const hydrate=value=>{
  if(Array.isArray(value))return value.map(hydrate);
  if(!value||typeof value!=='object')return value;
  const out={};for(const [key,val] of Object.entries(value)){
   if(key==='evidence_ids')out.evidence=(val||[]).map(id=>evidence[id]).filter(Boolean);
   else out[key]=hydrate(val);
  }return out;
 };
 return hydrate(root.rows||[]);
}
const scores={};
for(const section of ['manufacturers','distributors','integrators','clients_public','clients_private','trends','architectures']){
 const rows=load(section);
 const type=section.startsWith('clients_')?'clients':section;
 const publications=bi.uniqueNews(rows,type);
 scores[section]={rows:rows.length,news:publications.length,news_entities:new Set(publications.map(x=>x.vendor)).size,
  sample:publications.slice(0,2).map(n=>({title:n.title,url:n.url}))};
 assert.ok(rows.length>=1,'empty published area '+section);
}
console.log('NEWS_COVERAGE_V64 '+JSON.stringify(scores));
