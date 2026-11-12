/* Westcon Iberia v6.1 — shared, conservative business-intelligence decisions.
   A keyword is a retrieval clue, never proof of a relationship or contract fit. */
(function(root){
'use strict';
const normalize=v=>String(v??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/\s+/g,' ').trim();
const AREAS=[
 ['Ciberseguridad',/\b(cybersecurity|cyber security|ciberseguridad|ciberseguranca|firewalls?|siem|soar|soc|xdr|edr|mdr|sase|sse|zero trust|iam|identity management|gestion de identidades|gestao de identidades|mfa|pam|nac|seguridad de redes|seguranca de redes|network security|security operations|proteccion de datos|data loss prevention|dlp|pentesting|penetration testing|vulnerability management|vulnerabilidades|seguridad perimetral|threat intelligence|endpoint security|api security)\b/i],
 ['Networking',/\b(networking|network infrastructure|infraestructura de red|infraestruturas de rede|redes de datos|redes corporativas|redes informaticas|redes de comunicaciones|red de comunicaciones|rede de dados|rede corporativa|lan|wlan|wan|sd.wan|wi.fi|wifi|switching|switches|switch|routers?|routing|network access control|ddi|dns|dhcp|ethernet|802\.11|sdn|network automation|fabric ethernet|network fabric)\b/i],
 ['Cloud y Data Center',/\b(cloud|nube publica|nube privada|nube hibrida|servicios en la nube|plataforma en la nube|infraestructura en la nube|nuvem publica|nuvem privada|nuvem hibrida|iaas|paas|kubernetes|cloud native|virtualizacion|virtualization|contenedores de aplicaciones|container orchestration|data center|datacenter|centro de datos|centro de dados|cloud security|hybrid cloud|disaster recovery|backup empresarial|backup cloud|infraestructura hiperconvergente|hyperconverged|observability|observabilidad|observabilidade|apm|load balanc(?:er|ing)|balanceo de carga|adc|infraestructura de servidores)\b/i]
];
const NON_FIT=/\b(printers?|impresoras?|impressoras?|toner|cartuchos?|fotocopiadoras?|photocopiers?|papel|mobiliario|office furniture|water meter|contador(?:es)? de agua|abastecimiento de agua|saneamiento|fontaneria|obra civil|obras de construccion|smartphones?|telemoveis?|telefonos moviles|laptops?|portatiles?|ordenadores personales|personal computers|desktop pc|tablets?|pizarras digitales|proyectores|fotografia|fotografia digital|material escolar|vehiculos|combustible|limpieza|seguridad fisica|vigilancia presencial)\b/i;
const VAGUE=/\b(seguridad|security|redes|rede|telecomunicaciones|telecomunicacoes|monitoring|monitorizacion|informatica|sistemas informaticos|ti|tic|software|sistemas de informacion|plataforma tecnologica|hardware|automatizacion)\b/i;
function classifyNeed(raw){
 const text=normalize(raw);
 if(!text)return {fit:false,areas:[],reason:'Sin descripción tecnológica verificable'};
 const areas=AREAS.filter(([,expression])=>expression.test(text)).map(([name])=>name);
 if(!areas.length)return {fit:false,areas:[],reason:VAGUE.test(text)?'Mención tecnológica genérica, sin solución Westcon identificable':'Sin relación explícita con el portfolio'};
 // Commodity projects need an unmistakable enterprise technology contract, not a general IT reference.
 if(NON_FIT.test(text)&&!/(firewall|cyber|cibersegur|siem|sase|zero trust|sd.wan|switch|network security|seguridad de redes|data center|centro de datos|nac|identity management)/i.test(text)){
   return {fit:false,areas:[],reason:'Objeto principal ajeno al portfolio tecnológico'};
 }
 return {fit:true,areas,reason:'Necesidad tecnológica explícita'};
}
function fieldProof(field){
 if(!field)return false;
 return (field.evidence||[]).some(ev=>ev&&ev.accrediting!==false&&
  !['stale','rejected','contradicted'].includes(String(ev.freshness_status||''))&&
  !/HISTORICAL|ARCHIVE|LEGACY_UNRESOLVED|RESEARCH_SEED/.test(String(ev.provenance_origin||'').toUpperCase())&&
  (/^https?:\/\//i.test(String(ev.url||''))||/WESTCON_DOCUMENT_CURRENT|WESTCON_FIRST_PARTY_CURRENT/.test(String(ev.provenance_origin||''))));
}
function supportedTexts(field){
 if(!field)return [];
 const values=Array.isArray(field.value)?field.value:[field.value];
 return values.filter(x=>x!==undefined&&x!==null&&x!=='').filter(value=>{
  if(!Array.isArray(field.value))return fieldProof(field);
  const item=(field.items||[]).find(i=>JSON.stringify(i.value)===JSON.stringify(value));
  return fieldProof(item);
 }).map(x=>typeof x==='string'?x:JSON.stringify(x));
}
function safeUrl(raw){
 try{const url=new URL(raw);return ['http:','https:'].includes(url.protocol)&&!url.username&&!url.password?url.href:'';}catch(_){return '';}
}
function classifyNotice(row){
 const f=row?.fields||{};
 const needs=supportedTexts(f.request_or_need);
 const tech=supportedTexts(f.technology_signals);
 // A verified, specific need must appear in the original procurement description.
 // Ancillary inferred opportunity fields cannot create a portfolio match.
 const primary=classifyNeed(needs.join(' '));
 const secondary=classifyNeed(tech.join(' '));
 const fit=primary.fit || (secondary.fit && needs.some(v=>/\b(network|red|sistema|infraestructura|servicio|seguridad|cloud|nube|equipamiento|plataforma|tecnologia|technology|software)\b/i.test(normalize(v))));
 const areas=[...new Set([...(primary.fit?primary.areas:[]),...(secondary.fit?secondary.areas:[])])];
 const evidence=[...(f.request_or_need?.evidence||[]),...(f.notice_id?.evidence||[]),...(row.evidence||[])];
 const official=(evidence.map(e=>safeUrl(e?.url)).find(Boolean)||'');
 const pdf=evidence.map(e=>safeUrl(e?.url)).find(url=>/\.pdf(?:[?#]|$)/i.test(url))||'';
 return {fit,areas:fit?areas:[],reason:fit?'Encaje explícito con necesidad documentada':primary.reason,official,pdf};
}
function uniqueNews(rows){
 const news=[],seen=new Set();
 for(const row of rows||[]){
  const field=row?.fields?.recent_signals;
  if(!field)continue;
  const values=Array.isArray(field.value)?field.value:[field.value];
  for(const value of values){
   if(!value||typeof value!=='string')continue;
   const item=Array.isArray(field.value)?(field.items||[]).find(x=>x.value===value):field;
   const evidence=(item?.evidence||[]).filter(ev=>fieldProof({evidence:[ev]})&&safeUrl(ev.url));
   for(const ev of evidence){
    const url=safeUrl(ev.url),title=(ev.title&&ev.title.length>12?ev.title:value).trim();
    const stamp=Date.parse(ev.date||ev.retrieved_at||'')||0;
    const key=row.name.toLowerCase()+'|'+url;
    if(seen.has(key))continue;
    seen.add(key);
    news.push({vendor:row.name,title,url,date:stamp,dateLabel:ev.date||ev.retrieved_at||'',source:ev.source||'Fuente pública',summary:value});
   }
  }
 }
 return news.sort((a,b)=>b.date-a.date||a.vendor.localeCompare(b.vendor,'es')||a.title.localeCompare(b.title,'es'));
}
const api={normalize,classifyNeed,classifyNotice,supportedTexts,safeUrl,uniqueNews};
root.WestconBusiness=api;
if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
