/* Westcon Iberia v6.5 — shared, conservative business-intelligence decisions.
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

function verifiedCompetitionFor(row,manufacturers=[]){
 const vendorField=row?.fields?.vendor_relations||{};
 const vendors=supportedTexts(vendorField);
 const mapped=[];
 for(const vendor of vendors){
  const matched=[];
  const vendorItem=(vendorField.items||[]).find(x=>sameBusinessName(x?.value,vendor));
  if(!vendorItem?.evidence?.length)continue;
  let sourceEvidence=[...vendorItem.evidence];
  for(const manufacturer of manufacturers||[]){
   const field=manufacturer?.fields?.competitors||{};
   const competitor=supportedTexts(field).find(v=>sameBusinessName(v,vendor));
   if(!competitor)continue;
   const item=(field.items||[]).find(x=>sameBusinessName(x?.value,competitor));
   if(!item?.evidence?.length)continue;
   matched.push(manufacturer.name);
   sourceEvidence=[...sourceEvidence,...item.evidence];
  }
  if(matched.length)mapped.push({
   value:vendor,evidence:sourceEvidence,claim_type:'interpretation',
   confidence:0.67,confidence_band:'medium',assertion_status:'DERIVADO',
   qualifier:'Relación acreditada del actor con el fabricante y comparación acreditada con cada fabricante Westcon.',
   competes_with_westcon:[...new Set(matched)],competition_mapping_status:'EVIDENCIADO'
  });
 }
 return {value:mapped.map(x=>x.value),items:mapped,
   evidence:mapped.flatMap(x=>x.evidence),confidence:0.67,
   claim_type:'interpretation',assertion_status:'DERIVADO',
   qualifier:'Cruce de dos relaciones con evidencia; no se deriva por compartir una categoría tecnológica.'};
}

const NEWS_FIELDS={
 manufacturers:['recent_signals','analyst_signals'],
 distributors:['recent_signals','vendor_relations','acquisitions'],
 integrators:['recent_signals','public_cases','public_contracts','alliances'],
 clients:['recent_signals','investment_signals','public_projects','contracts','technology_signals','strategic_programs','request_or_need'],
 trends:['recent_signals','sources','drivers','evolution','market_players','technology_signals','buyer_priorities'],
 architectures:['recent_signals','sources','use_cases','vendors','layers','technology_signals','market_drivers']
};
function isPublicationUrl(href){
 try{
  const parsed=new URL(href),path=decodeURI(parsed.pathname).toLowerCase();
  if(!['https:','http:'].includes(parsed.protocol)||/\.(pdf|zip|xlsx?|pptx?|docx?|xml|json|csv|jpg|png|gif|webp)$/i.test(path))return false;
  // An individual article may be filed by topic, by pressroom or by date.
  const folders=/(?:^|\/)(?:news|noticias?|actualidad|novidades|press|prensa|sala.de.prensa|press.releases?|releases?|comunicados?|announcements?|blog|insights|articles?|artigos?|actualites|research|reports?|estudios|publicaciones?|case.studies|casos.de.exito|success.stories|media|newsroom|comunicacao|comunicacion)(?:\/|$)/i;
  const dated=/(?:^|\/)20(?:2[0-9]|3[0-5])\/(?:0?[1-9]|1[0-2])\/[a-z0-9][a-z0-9-]{7,}/i;
  if(dated.test(path))return true;
  const match=folders.exec(path);if(!match)return false;
  const suffix=path.slice(match.index+match[0].length).replace(/^\/+|\/+$/g,'');
  // Never treat a generic news landing page or a section index as a news item.
  return suffix.length>=9 && /[a-z]/.test(suffix) && !/^(index|archive|archivo|archivo-de-noticias|recent-news|all|latest|tag|category|page)(\/|$)/.test(suffix);
 }catch(_){return false;}
}
function distinctEvidence(field,value){
 if(!field)return [];
 if(!Array.isArray(field.value))return field.evidence||[];
 const item=(field.items||[]).find(x=>JSON.stringify(x?.value)===JSON.stringify(value));
 // No guessing that one field-level link supports a different element of a list.
 return item?.evidence||[];
}
function uniqueNews(rows,section='manufacturers'){
 const news=[],seen=new Set(),fields=NEWS_FIELDS[section]||NEWS_FIELDS.manufacturers;
 for(const row of rows||[]){
  const owner=String(row?.name||'').trim();
  if(!owner)continue;
  for(const fieldName of fields){
   const field=row?.fields?.[fieldName];if(!field)continue;
   const values=Array.isArray(field.value)?field.value:[field.value];
   for(const value of values){
    if(value===null||value===undefined||value==='')continue;
    const supportive=distinctEvidence(field,value).filter(ev=>fieldProof({evidence:[ev]})&&isPublicationUrl(safeUrl(ev.url)));
    for(const ev of supportive){
     const url=safeUrl(ev.url);
     const fallback=typeof value==='string'?value:'';
     const title=String(ev.title||fallback).trim();
     if(title.length<16||title.length>240||/^(noticias?|news|press releases?|actualidad|blog|inicio|home|casos de exito|latest updates|todas las noticias)$/i.test(title))continue;
     const key=normalize(owner)+'|'+url.toLowerCase();
     if(seen.has(key))continue;
     seen.add(key);
     // 'date' may be an evidence/retrieval date, not a publication date.
     const pubDate=ev.published_at||ev.published_date||ev.date_published||'';
     const stamp=Number.isFinite(Date.parse(pubDate))?Date.parse(pubDate):0;
     const summary=typeof value==='string' ? value : title;
     news.push({vendor:owner,title,url,date:stamp,dateLabel:pubDate,
       source:ev.source||'Fuente pública',summary,field:fieldName,
       publicationDateVerified:stamp>0});
    }
   }
  }
 }
 return news.sort((a,b)=>b.date-a.date||a.vendor.localeCompare(b.vendor,'es')||a.title.localeCompare(b.title,'es'));
}


function technicalNews(article){
 // The article headline, not the surrounding evidence summary, must identify
 // the technology. Otherwise an unrelated municipal or corporate story can
 // inherit the technology category of its parent entity.
 const headline=normalize(article?.title||'');
 if(!headline)return false;
 return classifyNeed(headline).fit ||
  /\b(inteligencia artificial|ia generativa|agentic ai|machine learning|deep learning|llms?|gpu|inferencia de ia|ciber\.?gal|5g industrial|5g empresarial|software libre|open source|infraestructura digital|transformacion digital|digital workplace|observabilidad|sre|automatizacion de redes|automacao de redes|data governance|gobierno del dato|centro de datos|zero trust|cloud computing|ciberseguridad|seguridad informatica)\b/i.test(headline);
}
// Each link uses the headline of an already source-accredited publication.
// Architecture-name broad words like "security" or "experience" never count.
const ARCHITECTURE_HEADLINE_ANCHORS={
 'sase / sse':['sase','sse','secure access service edge','security service edge'],
 'zero trust':['zero trust'],
 'identity security':['identity security','identity governance','identity threat detection','itdr','non human identity','machine identity','identity and access management'],
 'ai security':['ai security','ai systems security','security for ai','security of ai','genai security','llm security','shadow ai','ai governance','agent security'],
 'modern soc / secops':['security operations','security operation center','security operations center','secops','soc','xdr','mdr','ctem','siem'],
 'network platform / aiops':['aiops','ai native networking','networking platforms','network platform','network automation','cloud managed network'],
 'secure campus / lan':['secure campus','campus networking','campus security','secure lan','campus lan','cloud managed network','wired and wireless'],
 'ot / cps security':['cps','cyber physical systems','operational technology','industrial control systems','ics security','industrial cybersecurity','xiot security'],
 'ai ready data center & edge':['ai ready data center','ai data center','gpu infrastructure','gpu data center','data center fabric','edge computing','edge ai'],
 'observability / digital experience':['observability','digital experience monitoring','digital experience management','application performance monitoring','network performance monitoring'],
 'naas / managed networking':['naas','network as a service','managed network services','managed networking'],
 'agentic automation':['agentic ai','agentic automation','ai agents','autonomous ai agents','ai powered automation'],
};
function architectureTitleAnchors(owner){
 const key=normalize(owner).replace(/[^\p{L}\p{N}]+/gu,' ').trim();
 // Keys declared as readable taxonomy names; canonicalise them just like titles.
 const configured=Object.entries(ARCHITECTURE_HEADLINE_ANCHORS)
  .find(([name])=>normalize(name).replace(/[^\p{L}\p{N}]+/gu,' ').trim()===key);
 if(configured)return configured[1];
 const blocked=new Set(['architecture','arquitectura','security','seguridad','network','networking','cloud','infraestructura','infrastructure','platform','platforms','technology','digital','services','data','center','modern','ready','managed','experience']);
 return key.split(/\s+/).filter(t=>t.length>=5&&!blocked.has(t));
}
function relatedArchitectureNews(architectures, trendPublications){
 const matches=[],seen=new Set();
 for(const row of architectures||[]){
  const owner=String(row?.name||'').trim();
  if(!owner)continue;
  const aliases=architectureTitleAnchors(owner).map(v=>' '+normalize(v).replace(/[^\p{L}\p{N}]+/gu,' ').trim()+' ');
  if(!aliases.length)continue;
  for(const article of trendPublications||[]){
   const title=' '+normalize(article.title||'').replace(/[^\p{L}\p{N}]+/gu,' ').trim()+' ';
   if(!aliases.some(alias=>title.includes(alias)))continue;
   const url=safeUrl(article.url||'');
   if(!url)continue;
   const key=normalize(owner)+'|'+url.toLowerCase();
   if(seen.has(key))continue;
   seen.add(key);
   matches.push({...article,url,vendor:owner,related:true,
    summary:'Referencia tecnológica relacionada con '+owner+'. '+article.title,
    originalTopic:article.vendor,field:'referencia-tematica'});
  }
 }
 return matches.sort((a,b)=>b.date-a.date||a.vendor.localeCompare(b.vendor,'es'));
}

const api={normalize,classifyNeed,classifyNotice,supportedTexts,safeUrl,uniqueNews,isPublicationUrl,distributorContext,sameBusinessName,verifiedCompetitionFor,technicalNews,relatedArchitectureNews};
root.WestconBusiness=api;
if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
