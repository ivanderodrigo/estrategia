/* Westcon Iberia v6.3 — shared, conservative business-intelligence decisions.
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
 // Secondary signals can refine a tender, but cannot turn a generic IT purchase
 // into a portfolio opportunity. Require a specific technical anchor in the
 // evidenced procurement object, not words like "sistema" or "servicio".
 const anchor=/\b(ciberseguridad|ciberseguranca|cybersecurity|seguridad informatica|seguridad de redes|network security|infraestructura de red|red de datos|red corporativa|rede de dados|lan|wlan|wan|wifi|wi.fi|switches?|routers?|firewalls?|siem|soar|sase|sse|zero trust|sd.wan|cloud|nube|nuvem|data.?center|centro de datos|centro de dados|kubernetes|virtualizacion|virtualization|backup empresarial|observabilidad|observability)\b/i;
 const fit=primary.fit || (secondary.fit && needs.some(v=>anchor.test(normalize(v))));
 const areas=[...new Set([...(primary.fit?primary.areas:[]),...(secondary.fit?secondary.areas:[])])];
 const evidence=[...(f.request_or_need?.evidence||[]),...(f.notice_id?.evidence||[]),...(row.evidence||[])];
 const official=(evidence.map(e=>safeUrl(e?.url)).find(Boolean)||'');
 const pdf=evidence.map(e=>safeUrl(e?.url)).find(url=>/\.pdf(?:[?#]|$)/i.test(url))||'';
 return {fit,areas:fit?areas:[],reason:fit?'Encaje explícito con necesidad documentada':primary.reason,official,pdf};
}

function entityKey(raw){
 return normalize(raw).replace(/\b(s\.?a\.?|s\.?l\.?|ltd|limited|inc|corp|corporation)\b/g,'')
  .replace(/[^\p{L}\p{N}\s]/gu,' ').replace(/\s+/g,' ').trim();
}
function sameBusinessName(a,b){
 const left=entityKey(a),right=entityKey(b);
 if(!left||!right)return false;
 if(left===right)return true;
 // Country suffixes on official partner locators are accepted, never arbitrary substrings.
 const countries=/^(espana|spain|portugal|iberia)$/;
 if(left.startsWith(right+' ')&&countries.test(left.slice(right.length).trim()))return true;
 if(right.startsWith(left+' ')&&countries.test(right.slice(left.length).trim()))return true;
 return false;
}
function distributorContext(row,manufacturers=[]){
 const f=row?.fields||{},reasons=[];
 const overlap=supportedTexts(f.westcon_overlap);
 const competitorOverlap=supportedTexts(f.competitor_vendor_overlap);
 if(overlap.length)reasons.push('Fabricante Westcon acreditado: '+overlap.slice(0,3).join(', '));
 if(competitorOverlap.length)reasons.push('Fabricante competidor acreditado: '+competitorOverlap.slice(0,3).join(', '));
 const vendorRelations=supportedTexts(f.vendor_relations);
 const vendorMatches=[];
 for(const manufacturer of manufacturers||[]){
  const name=manufacturer?.name||'';
  if(!name)continue;
  if(vendorRelations.some(v=>sameBusinessName(v,name))){
   vendorMatches.push(name);
  }
  const documentedDistributors=supportedTexts(manufacturer.fields?.distributors);
  if(documentedDistributors.some(v=>sameBusinessName(v,row?.name))){
   vendorMatches.push(name);
  }
  // A competitor is a documented manufacturer-level relationship, not
  // a generic product-category similarity.
  const documentedCompetitors=supportedTexts(manufacturer.fields?.competitors);
  if(vendorRelations.some(v=>documentedCompetitors.some(c=>sameBusinessName(v,c)))){
   reasons.push('Competidor tecnológico relacionado con '+name);
  }
 }
 if(vendorMatches.length){
  reasons.push('Coincidencia contrastada en el ecosistema Westcon: '+[...new Set(vendorMatches)].slice(0,3).join(', '));
 }
 return {
  relevant:reasons.length>0,
  reasons:[...new Set(reasons)],
  vendorCount:vendorRelations.length,
  contextStatus:reasons.length>0?'Acreditado':'Sin relación competitiva acreditada'
 };
}

const NEWS_FIELDS={
 manufacturers:['recent_signals'],
 distributors:['recent_signals'],
 integrators:['recent_signals','public_cases','public_contracts'],
 clients:['recent_signals','investment_signals','public_projects','contracts']
};
function isPublicationUrl(href){
 try{
  const path=new URL(href).pathname.toLowerCase();
  const match=path.match(/\/(news|noticias|noticia|actualidad|novidades|press|press-releases|releases|comunicados|announcements|announcement|blog|insights|articles|case-studies|customer-stories|casos-de-exito|success-stories|media|prensa)(?:\/|$)/);
  if(!match)return false;
  const suffix=path.slice(match.index+match[0].length);
  // A section homepage is never a publication (except a dated standalone announcement URL).
  return suffix.replace(/\//g,'').length>=5 || /^(announcement|comunicados|releases)$/.test(match[1]);
 }catch(_){return false;}
}
function uniqueNews(rows,section='manufacturers'){
 const news=[],seen=new Set(),fields=NEWS_FIELDS[section]||NEWS_FIELDS.manufacturers;
 for(const row of rows||[]){
  const owner=String(row?.name||'').trim();
  if(!owner)continue;
  for(const fieldName of fields){
   const field=row?.fields?.[fieldName];
   if(!field)continue;
   const values=Array.isArray(field.value)?field.value:[field.value];
   for(const value of values){
    if(!value||typeof value!=='string')continue;
    const item=Array.isArray(field.value)?(field.items||[]).find(x=>x.value===value):field;
    const evidence=(item?.evidence||[]).filter(ev=>fieldProof({evidence:[ev]})&&isPublicationUrl(safeUrl(ev.url)));
    for(const ev of evidence){
     const url=safeUrl(ev.url),title=String(ev.title||value).trim();
     if(title.length<12||/^(noticias|news|press releases?|actualidad|blog|inicio|home|casos de exito)$/i.test(title))continue;
     const key=normalize(owner)+'|'+url.toLowerCase();
     if(seen.has(key))continue;
     seen.add(key);
     const publicationDate=ev.published_at||ev.published_date||ev.date||'';
     const stamp=Date.parse(publicationDate)||0;
     news.push({vendor:owner,title,url,date:stamp,dateLabel:publicationDate,source:ev.source||'Fuente pública',summary:value,field:fieldName});
    }
   }
  }
 }
 return news.sort((a,b)=>b.date-a.date||a.vendor.localeCompare(b.vendor,'es')||a.title.localeCompare(b.title,'es'));
}
const api={normalize,classifyNeed,classifyNotice,supportedTexts,safeUrl,uniqueNews,isPublicationUrl,distributorContext,sameBusinessName};
root.WestconBusiness=api;
if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
