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
const clientNews=[
 ...bi.uniqueNews(load('clients_public'),'clients'),
 ...bi.uniqueNews(load('clients_private'),'clients'),
];
const clientTech=clientNews.filter(bi.technicalNews);
const linked=bi.relatedArchitectureNews(load('architectures'),bi.uniqueNews(load('trends'),'trends'));
scores.client_technology={
 news:clientTech.length,
 entities:new Set(clientTech.map(x=>x.vendor)).size,
 sample:clientTech.slice(0,4).map(n=>({title:n.title,url:n.url}))
};
scores.architecture_topic_crosslinks={
 crosslinked:linked.length,topics:new Set(linked.map(x=>x.vendor)).size,
 sample:linked.slice(0,3).map(n=>({topic:n.vendor,title:n.title}))
};
assert.ok(clientTech.length>0,'Client news must include at least one sourced technology story in the public snapshot');
assert.ok(scores.trends.news>0,'Trend news cannot be empty when sourced technical articles exist');
assert.ok(scores.architectures.news+linked.length>0,'Architectures must have some sourced topical publications');

// AI/OT architecture news must use precise headline anchors, not generic
// "security", "modern", "experience", or topics merely adjacent to technology.
const sampleArchitectureNews=bi.relatedArchitectureNews(
 [{name:'AI Security'},{name:'OT / CPS Security'},{name:'Observability / Digital Experience'}],
 [
  {vendor:'AI Trends',title:'AI Systems Security Market Grows in 2026',url:'https://example.org/news/ai-security-market',date:4},
  {vendor:'Industry Trends',title:'Operational Technology Security in Industrial Control Systems',url:'https://example.org/news/industrial-control-systems',date:3},
  {vendor:'AI Trends',title:'AI agents transform employee productivity',url:'https://example.org/news/agents-and-productivity',date:2},
  {vendor:'Marketing',title:'Modern Customer Experience: Spring Promotions',url:'https://example.org/news/modern-customer-experience',date:1},
 ],
);
assert.deepStrictEqual(new Set(sampleArchitectureNews.map(x=>x.vendor)),
  new Set(['AI Security','OT / CPS Security']));
assert.strictEqual(sampleArchitectureNews.length,2,'related technical news cannot fabricate unrelated architecture links');
assert.ok(scores.architecture_topic_crosslinks.crosslinked>=3,
  'existing accredited architecture topic references must be preserved');

console.log('NEWS_COVERAGE_V64 '+JSON.stringify(scores));
