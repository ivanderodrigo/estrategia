const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
const state={data:null,base:null,research:null,engine:null,decision:null,capability:null,ecosystem:null,status:null,changes:null,vendors:[],selected:null,selectedRole:'country_manager',quick:'all',deep:false,fontScale:1,reportModules:new Set()};

const esc=s=>String(s??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]));
const clamp=(n,min=0,max=100)=>Math.max(min,Math.min(max,Math.round(Number(n)||0)));
const avg=(a,f=x=>x)=>a?.length?a.reduce((s,x)=>s+Number(f(x)||0),0)/a.length:0;
const uniq=a=>[...new Set((a||[]).filter(Boolean))];
const norm=s=>String(s||'').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/g,' ').trim();
const fmtDate=s=>{if(!s)return '—';const d=new Date(String(s).length===4?`${s}-01-01`:s);return isNaN(d)?s:new Intl.DateTimeFormat('es-ES',{day:'2-digit',month:'short',year:'numeric'}).format(d)};
function toast(msg){const t=$('#toast');t.textContent=msg;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2200)}
function tags(arr,cls='',limit=5){return (arr||[]).slice(0,limit).map(x=>`<span class="tag ${cls}">${esc(typeof x==='string'?x:x.name||x.vendor||x.area||x.play)}</span>`).join('')||'<span class="tiny">Sin dato público demostrado</span>'}
function metricPill(label,value,cls=''){return `<span class="metric-pill ${cls}"><b>${clamp(value)}</b><small>${esc(label)}</small></span>`}
function evidenceLabel(v){return v.analysis.evidenceConfidence>=72?'Fuerte':v.analysis.evidenceConfidence>=50?'Media':'Débil'}
function countryLabel(c){return c==='ES'?'España':c==='PT'?'Portugal':c==='IBERIA'?'Iberia':c||'—'}

async function load(){
  const [data,base,research,engine,decision,capability,ecosystem,status,changes]=await Promise.all([
    fetch('data/vendor_intelligence.json').then(r=>r.json()),
    fetch('data/base.json').then(r=>r.json()),
    fetch('data/research.latest.json').then(r=>r.ok?r.json():{}).catch(()=>({})),
    fetch('config/strategy_engine.json').then(r=>r.json()),
    fetch('config/decision_intelligence.json').then(r=>r.json()),
    fetch('config/capability_intelligence.json').then(r=>r.json()),
    fetch('data/ecosystem.json').then(r=>r.json()),
    fetch('data/research_status.json').then(r=>r.ok?r.json():{}).catch(()=>({})),
    fetch('data/changes.latest.json').then(r=>r.ok?r.json():{}).catch(()=>({}))
  ]);
  state.data=data;state.base=base;state.research=research;state.engine=engine;state.decision=decision;state.capability=capability;state.ecosystem=ecosystem;state.status=status;state.changes=changes;state.reportModules=new Set((decision.exportModules||[]).filter(x=>x.default).map(x=>x.id));
  state.vendors=data.vendors.map(enrichVendor);
  initNav();renderAll();
}

function allEvidence(){return state.research?.evidence?.length?state.research.evidence:[]}
function relevantEvidence(v){
  const name=norm(v.name);
  return allEvidence().filter(e=>{
    if(norm(e.vendor)===name)return true;
    const etags=(e.tags||[]).map(norm);if(etags.includes(name))return true;
    return norm(`${e.title||''} ${e.summary||''} ${e.snippet||''}`).includes(name);
  });
}
function channelSignals(v){
  const rows=[];
  (v.channelCompetitors||[]).forEach(c=>rows.push({country:c.country,distributor:c.name,confidence:84,url:c.url,evidence:[c.evidence],status:'curated-public'}));
  (state.research?.channelSignals||[]).filter(x=>norm(x.vendor)===norm(v.name)&&!['westcon comstor','comstor'].includes(norm(x.distributor))).forEach(x=>rows.push(x));
  const map=new Map();rows.forEach(x=>{const k=`${x.country}|${norm(x.distributor)}`;const cur=map.get(k);if(!cur||Number(x.confidence||0)>Number(cur.confidence||0))map.set(k,x)});
  return [...map.values()].sort((a,b)=>Number(b.confidence||0)-Number(a.confidence||0));
}
function integratorSignals(v){
  const rows=[...(state.ecosystem?.integrators||[]),...(state.research?.integratorSignals||[])].filter(x=>norm(x.vendor)===norm(v.name));
  const map=new Map();rows.forEach(x=>{const k=`${x.country}|${norm(x.name)}`;const cur=map.get(k);if(!cur||Number(x.confidence||0)>Number(cur.confidence||0))map.set(k,x)});
  return [...map.values()].sort((a,b)=>Number(b.confidence||0)-Number(a.confidence||0));
}
function customerSignals(v){
  const rows=[...(state.ecosystem?.customers||[]),...(state.research?.customerSignals||[])].filter(x=>norm(x.vendor)===norm(v.name));
  const map=new Map();rows.forEach(x=>{const k=`${x.country}|${norm(x.name)}`;const cur=map.get(k);if(!cur||Number(x.confidence||0)>Number(cur.confidence||0))map.set(k,x)});
  return [...map.values()].sort((a,b)=>Number(b.confidence||0)-Number(a.confidence||0));
}
function themeMatches(v){
  const txt=[v.domain,...(v.capabilities||[])].join(' ').toLowerCase(),direct=new Set();
  (state.base.solutionPlays||[]).filter(p=>p.vendors.includes(v.name)).forEach(p=>(p.themes||[]).forEach(t=>direct.add(t)));
  (state.engine.themeRules||[]).forEach(r=>{if((r.keywords||[]).some(k=>txt.includes(k.toLowerCase())))direct.add(r.theme)});
  return state.base.themes.filter(t=>direct.has(t.id));
}
function domainDefault(v,key){const d=state.engine.domainDefaults[v.domain]||state.engine.domainDefaults[v.domain?.split(' / ')[0]]||state.engine.domainDefaults.Other||{};return Number(d[key]||65)}
function freshnessScore(date){
  if(!date)return 55;const d=new Date(date);if(isNaN(d))return 55;const now=new Date(),days=Math.max(0,(now-d)/86400000);
  return days<=180?100:days<=365?90:days<=730?76:days<=1460?62:48;
}
function geoScore(scope,country,v){
  const s=norm(scope||country);const targets=v?.countries||['ES','PT'];
  if((s.includes('spain')||s.includes('espana')||country==='ES')&&targets.includes('ES'))return 100;
  if((s.includes('portugal')||country==='PT')&&targets.includes('PT'))return 100;
  if(s.includes('iberia')||country==='IBERIA')return 94;
  if(s.includes('europe')||s.includes('emea'))return 67;
  if(s.includes('query context'))return 38;
  return 55;
}
function qualityOfEvidence(e,v){
  const q=state.engine.evidenceQualityDimensions||{},tier=state.engine.evidenceTiers||{};
  const authority=Number(e.confidence||tier[e.sourceTier]||48),fresh=freshnessScore(e.date||e.published||e.collectedAt),geo=geoScore(e.scope,e.country,v);
  const direct=['regulator','official-company','analyst-public'].includes(e.sourceTier)||e.curated||e.status==='curated-public'?96:e.sourceTier==='industry-press'?68:42;
  const specific=norm(e.vendor)===norm(v.name)||norm(`${e.title} ${e.summary} ${e.snippet}`).includes(norm(v.name))?94:62;
  return clamp(authority*(q.authority||.28)+fresh*(q.freshness||.18)+geo*(q.geographicPrecision||.16)+direct*(q.directness||.14)+75*(q.corroboration||.10)+70*(q.sourceDiversity||.08)+specific*(q.specificity||.06));
}
function ecosystemEvidence(v,ints,customers){
  return [...ints.map(x=>({title:`${x.name} · ${x.signal||x.role}`,url:x.url,source:x.source||x.name,sourceTier:'official-company',date:x.date,scope:x.country,country:x.country,confidence:x.confidence,summary:x.signal,vendor:v.name,curated:true,evidenceType:'integrator'})),...customers.map(x=>({title:`${x.name} · ${x.solution}`,url:x.url,source:x.source||x.name,sourceTier:'official-company',date:x.date,scope:x.country,country:x.country,confidence:x.confidence,summary:`${x.sector}: ${x.solution}`,vendor:v.name,curated:true,evidenceType:'customer'}))];
}
function evidenceConfidence(v,evidence){
  if(!evidence.length)return 25;
  const scores=evidence.map(e=>qualityOfEvidence(e,v)).sort((a,b)=>b-a).slice(0,18),sources=uniq(evidence.map(e=>norm(e.source))).length,types=uniq(evidence.map(e=>e.evidenceType||e.kind)).length;
  const diversity=Math.min(12,sources*1.5+types);return clamp(avg(scores)+diversity);
}
function analystScore(v,evidence){
  const explicit=v.analystSignals||[],pub=evidence.filter(e=>e.sourceTier==='analyst-public'||/gartner|forrester|idc|omdia|canalys|dell.?oro|synergy/i.test(e.source||''));
  const names=uniq([...explicit.map(x=>x.analyst),...pub.map(x=>x.source)]);if(!explicit.length&&!pub.length)return 24;return clamp(34+explicit.length*12+Math.min(pub.length,5)*5+names.length*6);
}
function procurementContext(v){
  const themeIds=new Set(themeMatches(v).map(x=>x.id)),targets=new Set(v.countries||['ES']);
  const rows=(state.research?.procurementMarket||[]).filter(r=>targets.has(r.country)&&(r.themeIds||[]).some(t=>themeIds.has(t)));
  const explicit=allEvidence().filter(e=>e.evidenceType==='procurement'&&norm(e.vendor)===norm(v.name));
  const buyerMap=new Map();rows.forEach(r=>(r.topBuyers||[]).forEach(b=>buyerMap.set(b.name,(buyerMap.get(b.name)||0)+Number(b.signals||1))));
  const winnerMap=new Map();rows.forEach(r=>(r.topWinners||[]).forEach(b=>winnerMap.set(b.name,(winnerMap.get(b.name)||0)+Number(b.signals||1))));
  const topBuyers=[...buyerMap.entries()].sort((a,b)=>b[1]-a[1]).slice(0,8).map(([name,signals])=>({name,signals}));
  const topWinners=[...winnerMap.entries()].sort((a,b)=>b[1]-a[1]).slice(0,8).map(([name,signals])=>({name,signals}));
  const countries=uniq(rows.map(r=>r.country));const value=rows.reduce((n,r)=>n+Number(r.knownValueEUR||0),0);
  const demand=rows.length?clamp(avg(rows,r=>r.demandIndex)*.72+Math.min(12,explicit.length*2)+Math.min(8,countries.length*4)+Math.min(8,Math.log10(Math.max(1,value))*1.2)):Number(state.engine.publicDemandModel?.neutralPrior||42);
  const totalSignals=topBuyers.reduce((n,b)=>n+b.signals,0),concentration=totalSignals?clamp((topBuyers[0]?.signals||0)/totalSignals*100):45;
  return {rows,explicit,topBuyers,topWinners,demand,concentration,knownValueEUR:value,countries,technologies:uniq(rows.map(r=>r.technology))};
}
function competitiveProofScore(v,evidence,compInts,compCust){
  const pairs=evidence.filter(e=>e.kind==='competitive-pair'||e.evidenceType==='competitive');
  const official=pairs.filter(e=>['official-company','analyst-public','public-open-data','regulator'].includes(e.sourceTier)).length;
  const domains=uniq(pairs.map(e=>e.source)).length;
  if(!pairs.length&&!compInts.rows.length&&!compCust.rows.length)return 24;
  return clamp(28+Math.min(28,pairs.length*4)+Math.min(14,official*4)+Math.min(10,domains*2)+compInts.score*.10+compCust.score*.10);
}
function initiativeFitScore(a){
  return clamp(35+a.servicesLeverage*.18+a.synergyPotential*.17+a.recurringPotential*.13+(100-a.overlapRisk)*.08+a.countryCoverage*.08+a.ecosystemStrength*.12+a.publicDemand*.10);
}
function sharedIntegratorAdjacency(v,ints){
  const mine=new Set(ints.map(x=>norm(x.name))),out={};
  state.data.vendors.forEach(other=>{if(other.name===v.name)return;const matches=integratorSignals(other).filter(x=>mine.has(norm(x.name)));if(matches.length)out[other.name]=matches.map(x=>x.name)});
  return out;
}
function sharedCustomerAdjacency(v,customers){
  const mine=new Set(customers.map(x=>norm(x.name))),out={};
  state.data.vendors.forEach(other=>{if(other.name===v.name)return;const matches=customerSignals(other).filter(x=>mine.has(norm(x.name)));if(matches.length)out[other.name]=matches.map(x=>x.name)});
  return out;
}
function competitorIntegratorPressure(v,ints){
  const mine=new Set(ints.map(x=>norm(x.name))),competitors=new Set((v.marketCompetitors||[]).map(norm));
  const rows=(state.research?.integratorSignals||[]).filter(x=>competitors.has(norm(x.vendor))&&mine.has(norm(x.name)));
  return {score:clamp(rows.length?35+Math.min(50,uniq(rows.map(x=>norm(x.name))).length*12)+Math.min(15,uniq(rows.map(x=>norm(x.vendor))).length*5):12),rows};
}
function competitorCustomerPressure(v,customers){
  const mine=new Set(customers.map(x=>norm(x.name))),competitors=new Set((v.marketCompetitors||[]).map(norm));
  const rows=(state.research?.customerSignals||[]).filter(x=>competitors.has(norm(x.vendor))&&mine.has(norm(x.name)));
  return {score:clamp(rows.length?30+Math.min(55,uniq(rows.map(x=>norm(x.name))).length*14)+Math.min(15,uniq(rows.map(x=>norm(x.vendor))).length*5):10),rows};
}

function vendorTraits(v,a,ctx){
  const caps=norm((v.capabilities||[]).join(' ')),domain=norm(v.domain),ev=ctx.ev||[],sharedI=Object.keys(ctx.sharedInts||{}).length,sharedC=Object.keys(ctx.sharedCust||{}).length;
  const has=(...xs)=>xs.some(x=>caps.includes(norm(x)));
  const hw=clamp((domain.includes('network')?62:domain.includes('multi domain')?48:domain.includes('cloud')?15:domain.includes('cyber')?24:35)+(has('networking','switch','routing','wi fi','wlan','optical','transport','5g','sbc','gateway','edge','hpc','server','data center','data centre')?28:0)+(has('software','saas','iam','xdr','sase','cloud security','rpa')?-12:0));
  const cloud=clamp((domain.includes('cloud')?72:22)+(has('cloud','saas','aws','azure','cnapp','marketplace','ucaas','ccaas')?28:0));
  const complexity=clamp(38+(v.capabilities?.length||0)*7+(a.synergyPotential||0)*.16+(a.overlapRisk||0)*.12+(has('ot','optical','hpc','api','ddos','sase','xdr','cnapp','5g')?14:0));
  const proofNeed=clamp((a.competitiveIntensity||0)*.28+(a.channelPressure||0)*.20+(a.overlapRisk||0)*.18+(100-(a.customerProof||0))*.18+(a.differentiation||0)*.16);
  const reg=clamp((domain.includes('cyber')?62:28)+(has('identity','data','ot','api','encryption','zero trust','ddos','dns','firewall')?25:0)+(a.publicDemand||0)*.12);
  const marketplaceProof=ev.some(e=>/marketplace|private offer|cloud marketplace/i.test(`${e.title||''} ${e.summary||''} ${e.snippet||''}`));const marketplace=clamp(cloud*.32+(a.recurringPotential||0)*.20+((v.name==='AWS'||v.name==='Microsoft Azure')?38:0)+(marketplaceProof?28:0)+(has('saas')?8:0));
  const finance=clamp(hw*.30+(a.recurringPotential||0)*.25+(a.opportunity||0)*.17+(a.channelPressure||0)*.10+(has('subscription','saas','cloud','hardware','networking')?12:0));
  const deployment=clamp(hw*.36+complexity*.34+(a.publicDemand||0)*.12+(a.customerProof||0)*.10+(has('campus','data centre','optical','5g','edge','sbc')?10:0));
  const support=clamp(complexity*.30+(a.customerProof||0)*.22+(a.recurringPotential||0)*.20+(100-(a.partnerCapability||0))*.16+(has('critical','security','networking','edge','ot')?9:0));
  const managed=clamp((domain.includes('cyber')?25:domain.includes('network')?12:0)+(a.recurringPotential||0)*.35+support*.28+(a.marketMomentum||0)*.12);
  const global=clamp((a.countryImbalance||0)*.24+hw*.18+deployment*.20+(a.customerProof||0)*.12+(a.opportunity||0)*.12+(has('optical','5g','cloud','edge','networking')?10:0));
  const stock=clamp(hw*.52+deployment*.18+(a.publicDemand||0)*.10+(a.customerProof||0)*.10+(a.channelPressure||0)*.10);
  const lifecycle=clamp((a.recurringPotential||0)*.42+(a.customerProof||0)*.28+(a.ecosystemStrength||0)*.12+support*.10);
  const demandNeed=clamp((a.whiteSpace||0)*.35+(a.opportunity||0)*.25+(100-(a.customerProof||0))*.20+(a.marketMomentum||0)*.12);
  const enableNeed=clamp((100-(a.partnerCapability||0))*.45+(a.whiteSpace||0)*.22+complexity*.14+(a.marketMomentum||0)*.10);
  const vendorSignals=ev.filter(e=>['product','m&a','market','partner-program','financial'].includes(String(e.evidenceType||e.kind||'').toLowerCase()));
  const vendorMomentum=clamp(42+Math.min(28,vendorSignals.filter(e=>freshnessScore(e.date||e.published)>=76).length*5)+(a.analystSignal||0)*.18+(a.marketMomentum||0)*.16);
  const mna=clamp(Math.min(100,ev.filter(e=>String(e.evidenceType||e.kind||'').toLowerCase()==='m&a').length*28));
  return {hardwareIntensity:hw,cloudIntensity:cloud,technicalComplexity:complexity,technicalProofNeed:proofNeed,regulatoryFit:reg,marketplaceFit:marketplace,financeFit:finance,deploymentComplexity:deployment,supportNeed:support,managedServiceFit:managed,globalDeliveryNeed:global,stockNeed:stock,lifecycleFit:lifecycle,demandGenerationNeed:demandNeed,partnerEnablementNeed:enableNeed,vendorMomentum,mnaDisruption:mna,sharedEcosystem:clamp(sharedI*13+sharedC*19),verticalDiversity:ctx.eco?.verticalDiversity||50,sustainabilityFit:clamp(hw*.55+lifecycle*.30),dealScalePotential:clamp(hw*.28+deployment*.24+(a.customerProof||0)*.16+(a.publicDemand||0)*.12+(a.opportunity||0)*.15),strategicOptionality:clamp((a.synergyPotential||0)*.48+(a.portfolioFit||0)*.22+(sharedI*7+sharedC*10)),riskInverse:clamp(100-(a.risk||50))};
}
function actionMetric(key,a,t){
  if(key.startsWith('gap.'))return 100-Number(a[key.slice(4)]??t[key.slice(4)]??50);
  return Number(a[key]??t[key]??50);
}
function actionScore(action,v,a,t){
  let sum=0,w=0,parts=[];Object.entries(action.factors||{}).forEach(([k,wt])=>{const val=clamp(actionMetric(k,a,t));sum+=val*Math.abs(wt);w+=Math.abs(wt);parts.push({metric:k,value:val,impact:val*Math.abs(wt)});});
  let score=w?sum/w:Number(action.base||50);score=score*.82+Number(action.base||50)*.18;
  if(action.domainBoosts?.[v.domain])score+=Number(action.domainBoosts[v.domain]);
  const caps=norm((v.capabilities||[]).join(' '));(action.keywordBoosts||[]).forEach(x=>{if(caps.includes(norm(x.keyword)))score+=Number(x.points||0)});
  if((action.excludeDomains||[]).includes(v.domain))score-=35;
  const passes=rules=>Object.entries(rules||{}).every(([k,r])=>{const val=actionMetric(k,a,t),rule=typeof r==='number'?{min:r}:r;return (rule.min===undefined||val>=rule.min)&&(rule.max===undefined||val<=rule.max)});
  if(action.requires&&!passes(action.requires))score-=Number(action.gatePenalty||32);
  if(action.anyOf?.length&&!action.anyOf.some(passes))score-=Number(action.gatePenalty||32);
  if(a.evidenceConfidence<42)score=55+(score-55)*.62;
  parts.sort((x,y)=>y.impact-x.impact);return {score:clamp(score),basis:parts.slice(0,4)};
}
function capabilityProgramme(id){return (state.capability?.programmes||[]).find(x=>x.id===id)}
function capabilityStatus(v,capId){
  if(!capId)return {eligible:true,status:'NO_GATE',reason:'Acción estratégica general sin programa Westcon específico.'};
  const configured=state.capability?.vendorApplicability?.[v.name]?.[capId];
  const dynamic=(state.research?.capabilitySignals||[]).filter(x=>norm(x.vendor)===norm(v.name)&&x.capabilityId===capId).sort((a,b)=>Number(b.confidence||0)-Number(a.confidence||0))[0];
  const status=dynamic?.status||configured?.status||'UNVERIFIED',prog=capabilityProgramme(capId);
  const hardSpecific=state.capability?.researchPolicy?.vendorSpecificRequiredFor?.includes(capId);
  const verified=['VERIFIED_PUBLIC','VERIFIED_PUBLIC_DISCOVERED','VERIFIED_SOURCE','USER_CONFIRMED','SOURCE_PRESENTATION'].includes(status);
  const contextual=['PROGRAMME_ELIGIBLE','MODEL_ELIGIBLE'].includes(status);
  return {eligible:verified||(!hardSpecific&&contextual),verified,contextual,status,scope:dynamic?.scope||configured?.scope||prog?.scope,reason:dynamic?.title||configured?.reason||'No hay evidencia suficiente de aplicabilidad específica.',programme:prog,dynamic};
}
function vendorCapabilities(v){
  const mapped=state.capability?.vendorApplicability?.[v.name]||{}, ids=new Set(Object.keys(mapped));
  (state.research?.capabilitySignals||[]).filter(x=>norm(x.vendor)===norm(v.name)).forEach(x=>ids.add(x.capabilityId));
  return [...ids].map(id=>({id,...capabilityStatus(v,id)})).filter(x=>x.eligible).sort((a,b)=>(b.verified-a.verified)||String(a.programme?.family||'').localeCompare(String(b.programme?.family||'')));
}
function capabilityBadge(v,action){const c=capabilityStatus(v,action.capabilityId);if(!action.capabilityId)return '';const label=c.programme?.name||action.capabilityId;const cls=c.verified?'cap-verified':'cap-context';return `<span class="cap-badge ${cls}">${esc(label)} · ${esc(c.status.replaceAll('_',' '))}</span>`}
function kpiFor(action){
  const p=capabilityProgramme(action.capabilityId),k=(p?.kpis||[]).slice(0,3);return k.length?k.join(' · '):'avance de la acción · pipeline influenciado · conversión';
}
function actionPlainLanguage(v,action){
  const c=capabilityStatus(v,action.capabilityId),name=action.name,competitor=v.marketCompetitors?.[0],ctx=v.derived||{};
  if(action.id==='no-action')return action.value;
  if(action.capabilityId==='tech-insights')return `Abrir oportunidades de ${v.name} mediante un Tech Insights confirmado para este fabricante: seleccionar cuentas con un gap concreto, ejecutar el assessment y convertir el resultado en workshop, oportunidad y siguiente paso técnico.`;
  if(action.capabilityId==='3d-lab')return `Usar los laboratorios 3D Lab disponibles para ${v.name} para formar al integrador o demostrar un caso de uso antes de una PoC; elegir un escenario ligado a una oportunidad real y cerrar la sesión con criterios de decisión.`;
  if(action.capabilityId==='local-presales')return `Poner la preventa local de ${v.name} delante de las oportunidades donde la decisión sea técnica: discovery, arquitectura y defensa frente a ${competitor||'la alternativa principal'}, evitando competir solo en precio.`;
  if(action.capabilityId==='intelligent-demand')return `Usar Intelligent Demand para localizar cuentas con mayor propensión y whitespace para ${v.name}; convertir la selección de cuentas en una campaña conjunta y en una lista priorizada para PSM/VSM.`;
  if(action.capabilityId==='academy'||action.capabilityId==='tech-xpert')return `Aumentar la capacidad del canal de ${v.name}: identificar integradores con gap técnico, habilitarlos con ${c.programme?.name||name} y ligar el enablement a una oportunidad o especialización concreta.`;
  if(action.capabilityId==='support'||action.capabilityId==='professional-services')return `Adjuntar ${c.programme?.name||name} únicamente en oportunidades de ${v.name} donde reduzca riesgo de implantación u operación; definir alcance, SLA y margen antes de incorporarlo a la propuesta.`;
  if(action.capabilityId==='supply-chain')return `Convertir disponibilidad, staging y logística en ventaja para ${v.name} en proyectos de despliegue: anticipar BOM/stock, preparar configuración y medir lead time frente a alternativas.`;
  if(action.capabilityId==='flex')return `Usar FLEX en ${v.name} solo cuando la barrera sea presupuestaria o de modelo de consumo: comparar compra tradicional frente a 1–5 años y, si mejora el cierre, empaquetar hardware/software/servicios en un pago predecible.`;
  if(action.capabilityId==='marketplace')return `Canalizar ${v.name} por marketplace cuando esté confirmado y aporte una ventaja real: consumir compromiso cloud, simplificar procurement o crear private offer; no usarlo como fin en sí mismo.`;
  if(action.capabilityId==='marketing-local')return `Diseñar con ${v.name} una acción local sobre el gap de mercado más defendible: una audiencia, un problema, un CTA y un siguiente paso técnico/comercial medible, no una campaña genérica.`;
  if(action.capabilityId==='psm')return `Priorizar los integradores que pueden hacer crecer ${v.name}: distinguir partners para activar, especializar o cross-sell y dar a cada uno una acción concreta con plazo y objetivo.`;
  if(action.capabilityId==='vsm')return `Traducir la tesis de ${v.name} a un plan de fabricante: 2–3 apuestas, gaps de canal, competidores a desplazar, partners prioritarios y métricas de avance; eliminar actividades que no soporten esa tesis.`;
  if(v.name==='Extreme Networks'&&/displace|desplaz|compet/i.test(name))return `Atacar de forma selectiva la base Juniper/HPE: localizar renovaciones y partners con contexto Juniper, cualificar dónde Extreme ofrece una migración defendible y activar preventa, demo y servicios solo en esas cuentas.`;
  return `${name} para ${v.name}: ${action.value}`;
}
function recEvidence(v,action){
  const types=new Set(action.evidenceTypes||[]);const ev=(v.derived?.evidence||[]).filter(e=>types.has(String(e.evidenceType||e.kind||'general').toLowerCase()));
  return ev.sort((a,b)=>Number(b.confidence||0)-Number(a.confidence||0)).slice(0,3);
}
function roleRecommendations(v,a,t){
  const out={};(state.decision.roles||[]).forEach(role=>{
    let rows=(state.decision.actions||[]).filter(x=>(x.roles||[]).includes(role.id)).filter(x=>capabilityStatus(v,x.capabilityId).eligible).map(x=>{const sc=actionScore(x,v,a,t);return {...x,score:sc.score,basis:sc.basis};}).filter(x=>x.score>=44).sort((x,y)=>y.score-x.score);
    const picked=[],cats=new Set();for(const x of rows){if(picked.length>=3)break;if(cats.has(x.category)&&picked.length<2)continue;cats.add(x.category);picked.push({...x,evidence:recEvidence(v,x)});}
    if(!picked.length){const best=rows[0];out[role.id]=[{id:'no-action',name:'Sin acción prioritaria',category:'Monitorización',roles:[role.id],score:best?.score||35,value:`No activar una palanca específica de ${role.name} con la evidencia actual; monitorizar cambios antes de consumir recursos.`,basis:best?.basis||[],evidence:[]}];}
    else out[role.id]=picked;
  });return out;
}
function archetypeFor(v,a,t){
  const list=state.decision.archetypes||[],get=id=>list.find(x=>x.id===id)||{id,name:id,description:''};
  if(a.evidenceConfidence<45||a.dataCompleteness<38)return get('INVESTIGATE');
  if(a.overlapRisk>=72&&a.synergyPotential>=55)return get('GOVERN_OVERLAP');
  if(a.publicDemand>=72&&a.evidenceConfidence>=58)return get('PUBLIC_SECTOR');
  if(a.competitiveProof>=62&&a.attackScore>=70)return get('DISPLACE');
  if(a.channelPressure>=62&&a.opportunity>=68)return get('DEFEND_CHANNEL');
  if(a.whiteSpace>=62&&a.ecosystemStrength<58)return get('BUILD_ECOSYSTEM');
  if(a.synergyPotential>=76&&t.sharedEcosystem>=35)return get('CROSS_SELL');
  if(t.hardwareIntensity>=72&&a.opportunity>=64)return get('HARDWARE_SCALE');
  if(a.recurringPotential>=88&&a.customerProof>=48)return get('RECURRING_EXPANSION');
  return get('SCALE_PLATFORM');
}
function executiveActions(roleRecs){
  const priority=['country_manager','director_vsm_sa','director_psm','vsm','psm','sa','marketing','services','operations','finance','logistics'],all=[];
  priority.forEach(r=>(roleRecs[r]||[]).filter(x=>x.id!=='no-action').forEach(x=>all.push({...x,role:r})));all.sort((a,b)=>b.score-a.score);const picked=[],seen=new Set(),cats=new Set();for(const x of all){if(picked.length>=5)break;if(seen.has(x.id))continue;if(cats.has(x.category)&&picked.length<3)continue;seen.add(x.id);cats.add(x.category);picked.push(x)}return picked;
}
function executivePlan(v,a,archetype,recs,legacy){
  const all=executiveActions(recs),roleName=id=>(state.decision.roles||[]).find(r=>r.id===id)?.name||id;
  const fmt=x=>x?`${x.name} (${roleName(x.role)})`:'';
  const p30=all[0]?`Prioridad inmediata: ${fmt(all[0])}. ${all[0].value}`:legacy.p30;
  const p90=all.length?`${archetype.name}: ${all.slice(0,3).map(fmt).join(' · ')}.`:legacy.p90;
  const strategic=(recs.country_manager||[])[0]||(recs.director_vsm_sa||[])[0]||all[0];
  const p180=strategic?`Escalar solo si la evidencia confirma la tesis: ${fmt(strategic)}. Medir evolución de mercado, canal, ecosistema, referencias, recurrencia y win/displacement.`:legacy.p180;
  return {...legacy,p30,p90,p180,executiveActions:all,archetype,thesis:`${archetype.name}. ${archetype.description} ${all.slice(0,3).map(x=>x.name).join(' + ')}.`};
}
function capabilitySourceFor(action){const n=norm(action.name),src=state.decision.capabilitySources||[];let key='BLUEPRINT';if(n.includes('3d lab'))key='3D Lab';else if(n.includes('tech xpert')||n.includes('tech connex'))key='Tech Xpert';else if(n.includes('intelligent demand'))key='Intelligent Demand';else if(n.includes('flex'))key='FLEX';else if(n.includes('staging')||n.includes('logistica')||n.includes('stock')||n.includes('ior')||n.includes('gscs'))key='Supply Chain';else if(n.includes('support')||n.includes('care')||n.includes('assist')||n.includes('managed services'))key='Soporte';else if(n.includes('skillboost')||n.includes('academy')||n.includes('certificacion'))key='Educación';else if(n.includes('servicios profesionales')||n.includes('instalacion')||n.includes('health')||n.includes('engineer'))key='Servicios profesionales';return src.find(x=>x.name===key)||src[0]}
function decisionMetricLabel(k){const m={opportunity:'Oportunidad',marketMomentum:'Momentum mercado',portfolioFit:'Encaje portfolio',recurringPotential:'Recurrencia',differentiation:'Diferenciación',synergyPotential:'Sinergias',analystSignal:'Señal consultoras',servicesLeverage:'Leverage servicios',ecosystemStrength:'Ecosistema Iberia',customerProof:'Prueba cliente',partnerCapability:'Capacidad partners',countryCoverage:'Cobertura ES/PT',publicDemand:'Demanda pública',competitiveProof:'Prueba competitiva',competitiveIntensity:'Intensidad competitiva',channelPressure:'Presión de canal',overlapRisk:'Solape interno',evidenceConfidence:'Confianza evidencia',reliability:'Fiabilidad',whiteSpace:'White space',competitorCustomerPressure:'Presión en clientes',competitorIntegratorPressure:'Presión en integradores',technicalComplexity:'Complejidad técnica',technicalProofNeed:'Necesidad de prueba',regulatoryFit:'Encaje regulatorio',marketplaceFit:'Encaje marketplace',financeFit:'Encaje financiero',deploymentComplexity:'Complejidad despliegue',supportNeed:'Necesidad soporte',managedServiceFit:'Encaje managed services',globalDeliveryNeed:'Necesidad global',stockNeed:'Necesidad stock',lifecycleFit:'Encaje lifecycle',demandGenerationNeed:'Necesidad demanda',partnerEnablementNeed:'Necesidad enablement',vendorMomentum:'Momentum fabricante',mnaDisruption:'Disrupción M&A',sharedEcosystem:'Ecosistema compartido',verticalDiversity:'Diversidad vertical',dealScalePotential:'Escala potencial',strategicOptionality:'Opcionalidad estratégica',hardwareIntensity:'Intensidad hardware',cloudIntensity:'Intensidad cloud',riskInverse:'Riesgo inverso'};const gap=k.startsWith('gap.');const key=gap?k.slice(4):k;return `${gap?'Gap · ':''}${m[key]||key}`}
function roleRecommendationHtml(v,roleId){
  const role=(state.decision.roles||[]).find(r=>r.id===roleId),rows=v.derived.roleRecommendations?.[roleId]||[];
  return `<div class="role-head"><b>${esc(role?.name||roleId)}</b><span>${esc(role?.scope||'')}</span></div>${rows.map(x=>{const cs=capabilitySourceFor(x),plain=actionPlainLanguage(v,x),cap=capabilityStatus(v,x.capabilityId);return `<div class="role-rec"><div><strong>${x.score}</strong><b>${esc(x.name)}</b></div>${x.id!=='no-action'?capabilityBadge(v,x):''}<p><b>Qué hacer.</b> ${esc(plain)}</p><p class="rec-why"><b>Por qué.</b> ${esc(x.value)}</p><div class="rec-basis">${x.basis.map(b=>`<span>${esc(decisionMetricLabel(b.metric))} <b>${b.value}</b></span>`).join('')}</div><p class="rec-kpi"><b>Medir.</b> ${esc(kpiFor(x))}</p>${x.id!=='no-action'&&x.capabilityId?`<small class="method-note">Compatibilidad: ${esc(cap.status.replaceAll('_',' '))} · ${esc(cap.scope||'ámbito por validar')}. ${esc(cap.reason||'')}</small>`:''}${x.id!=='no-action'&&cs?`<a class="evidence-link" href="${cs.url}" target="_blank" rel="noopener">Capacidad Westcon · ${esc(cap.programme?.name||cs.name)} ↗</a>`:''}${x.evidence?.length?`<details><summary>Datos que soportan la acción</summary>${x.evidence.map(e=>`<a class="evidence-link" href="${e.url}" target="_blank" rel="noopener">${esc(e.source||e.sourceTier)} · ${esc(e.title)} ↗</a>`).join('')}</details>`:`<small class="method-note">La acción se apoya en las métricas agregadas; no hay evidencia de mercado adicional suficientemente fuerte.</small>`}</div>`}).join('')||'<p>Sin recomendación suficientemente fuerte para este perfil.</p>'}`;
}

function initiativeSet(v,a){
  const out=[];const add=(capId,name,why)=>{const c=capabilityStatus(v,capId);if(c.eligible&&!out.some(x=>x.name===name))out.push({capId,name,why,status:c.status})};
  if(a.channelPressure>=55){add('local-presales','Preventa local','diferenciar por discovery y defensa técnica');add('3d-lab','3D Lab','diferenciar por prueba y time-to-value');add('tech-xpert','Tech Xpert','ganar preferencia técnica del partner');add('professional-services','Servicios profesionales','salir de la comparación puramente transaccional');add('lifecycle','Lifecycle','anclar renovación, adopción y expansión')}
  if(a.customerProof<50||a.whiteSpace>=62){add('tech-insights','Tech Insights','convertir gaps en oportunidad medible');add('intelligent-demand','Intelligent Demand','crear demanda en whitespace y verticales')}
  if(a.partnerConcentration>=60){add('psm','Partner Success','activar y especializar un segundo ecosistema de partners');add('tech-xpert','Tech Xpert','ampliar capacidad técnica del canal');add('academy','Academy / SkillBoost','crear capacidad certificada')}
  if(a.overlapRisk>=55||a.synergyPotential>=72){add('local-presales','Preventa / arquitectura','gobernar solapes por discovery');add('3d-lab','3D Lab','demostrar la arquitectura conjunta')}
  if(a.recurringPotential>=82){add('flex','FLEX','eliminar barreras presupuestarias cuando exista fit');add('marketplace','Cloud Marketplace','acelerar transacción recurrente cuando esté habilitado');add('lifecycle','Lifecycle','maximizar expansión y renovación')}
  if(a.countryImbalance>=55){add('gscs','GSCS','apoyar proyectos multinacionales y cobertura cross-border');add('psm','Partner Success','replicar el modelo en el país menos cubierto')}
  if(a.competitorCustomerPressure>=45){add('tech-insights','Tech Insights','abrir displacement con evidencia');add('3d-lab','3D Lab','reducir riesgo de migración con prueba guiada');add('local-presales','Preventa local','definir criterios técnicos de sustitución')}
  if(v.name==='Extreme Networks'){add('local-presales','Preventa local Extreme','cualificar migraciones desde Juniper/HPE');add('3d-lab','3D Lab Extreme','demostrar la alternativa antes de migrar');add('intelligent-demand','Intelligent Demand','buscar renovaciones y whitespace de campus')}
  return out.slice(0,8);
}
function competitiveGapHypotheses(a){
  const gaps=[];const push=(id,label,score)=>gaps.push({id,label,score:clamp(score)});
  if(a.channelPressure>=55)push('channel_commoditization','Evitar guerra de precio: convertir servicios, labs y lifecycle en criterio de selección',a.channelPressure);
  if(a.partnerConcentration>=60)push('integrator_concentration','Dependencia de pocos integradores: diversificar y especializar ecosistema',a.partnerConcentration);
  if(a.customerProof<48)push('local_reference_gap','Poca prueba pública local: fabricar una referencia replicable por vertical',100-a.customerProof);
  if(a.countryImbalance>=55)push('country_coverage_gap','Desbalance ES/PT: atacar el país con menor prueba y ecosistema',a.countryImbalance);
  if(a.overlapRisk>=60)push('multivendor_gap','Solape interno explotable: ganar con discovery y arquitectura conjunta',a.overlapRisk);
  if(a.competitorIntegratorPressure>=45)push('enablement_gap','Integradores compartidos con rivales: aumentar preferencia técnica y especialización',a.competitorIntegratorPressure);
  if(a.competitorCustomerPressure>=45)push('proof_gap','Clientes con señales de competidores: priorizar displacement/cross-sell basado en assessment',a.competitorCustomerPressure);
  if(a.whiteSpace>=65)push('local_reference_gap','White space elevado: concentrar Intelligent Demand + assessment + demo',a.whiteSpace);
  return gaps.sort((x,y)=>y.score-x.score).slice(0,5);
}
function baseSynergyScore(v){const vendors=uniq((v.synergies||[]).flatMap(x=>x.with||[])),plays=(state.base.solutionPlays||[]).filter(p=>p.vendors.includes(v.name));return clamp(28+vendors.length*7+plays.length*12)}
function overlapScore(v){const ovs=v.internalOverlaps||[],areas=uniq(ovs.map(x=>x.area));return clamp(12+ovs.length*10+areas.length*6)}
function channelPressure(v,channels){const alts=channels.filter(x=>Number(x.confidence||0)>=55),countries=uniq(alts.map(x=>x.country)),names=uniq(alts.map(x=>norm(x.distributor)));if(!alts.length)return 16;const q=avg(alts,x=>Number(x.confidence||65));return clamp(12+Math.min(42,names.length*10)+Math.min(18,countries.length*9)+q*.28)}
function competitiveIntensity(v){const direct=uniq(v.marketCompetitors||[]).length,peers=uniq((v.analystSignals||[]).flatMap(x=>x.peers||[])).length,overlaps=uniq((v.internalOverlaps||[]).map(x=>x.vendor)).length;return clamp(20+Math.min(38,direct*7)+Math.min(24,peers*3)+Math.min(18,overlaps*5))}
function integratorStrength(v,ints){
  if(!ints.length)return 18;const weights=state.engine.integratorSignalWeights||{};const qs=ints.map(x=>Math.min(Number(x.confidence||70),weights[x.proofType]||85)).sort((a,b)=>b-a).slice(0,6);
  const countries=uniq(ints.map(x=>x.country)),proofs=uniq(ints.map(x=>x.proofType));return clamp(avg(qs)*.72+Math.min(14,ints.length*3)+countries.length*5+proofs.length*3);
}
function customerProof(v,customers){
  if(!customers.length)return 16;const sectors=uniq(customers.map(x=>x.sector)),countries=uniq(customers.map(x=>x.country)),qs=customers.map(x=>Number(x.confidence||80)).sort((a,b)=>b-a).slice(0,8);
  return clamp(avg(qs)*.64+Math.min(18,customers.length*3.2)+Math.min(12,sectors.length*3)+countries.length*4);
}
function targetCountryCoverage(v,channels,ints,customers){
  const targets=v.countries?.length?v.countries:['ES'];let covered=0;
  targets.forEach(c=>{if(channels.some(x=>x.country===c||x.country==='IBERIA')||ints.some(x=>x.country===c||x.country==='IBERIA')||customers.some(x=>x.country===c||x.country==='IBERIA'))covered++});
  return clamp(targets.length?covered/targets.length*100:60);
}
function ecosystemMetrics(v,ints,customers,channels){
  const iStrength=integratorStrength(v,ints),cProof=customerProof(v,customers),country=targetCountryCoverage(v,channels,ints,customers),vertical=clamp(25+uniq(customers.map(x=>x.sector)).length*14),recent=clamp(avg([...ints,...customers],x=>freshnessScore(x.date))||45),proofD=clamp(30+uniq([...ints,...customers].map(x=>x.proofType)).length*16),w=state.engine.ecosystemWeights||{};
  const strength=clamp(iStrength*(w.integratorStrength||.34)+cProof*(w.customerProof||.28)+country*(w.countryBalance||.14)+vertical*(w.verticalDiversity||.12)+recent*(w.referenceRecency||.07)+proofD*(w.proofDiversity||.05));
  return {strength,integratorStrength:iStrength,customerProof:cProof,countryCoverage:country,verticalDiversity:vertical,referenceRecency:recent,proofDiversity:proofD};
}
function partnerConcentration(ints){if(!ints.length)return 72;if(ints.length===1)return 88;if(ints.length===2)return 62;if(ints.length===3)return 46;return 28}
function clientConcentration(customers){if(!customers.length)return 58;if(customers.length===1)return 82;const sectors=uniq(customers.map(x=>x.sector)).length;if(sectors<=1)return 68;if(sectors===2)return 48;return 30}
function countryImbalance(v,ecos){return ecos.countryCoverage>=100?18:ecos.countryCoverage>=50?58:84}
function recommendationFor(a){
  const g=state.engine.decisionGates||{};
  if(a.evidenceConfidence<(g.minimumEvidenceForAction||45)||a.dataCompleteness<35)return 'INVESTIGAR';
  if(a.opportunity>=(g.minimumOpportunityForAccelerate||80)&&a.evidenceConfidence>=(g.minimumEvidenceForAccelerate||58)&&a.reliability>=(g.minimumReliabilityForAccelerate||58)&&a.ecosystemStrength>=(g.minimumEcosystemForAccelerate||48)&&a.risk<=(g.maximumRiskForAccelerate||66))return 'ACELERAR';
  if(a.opportunity>=68&&(a.channelPressure>=(g.channelDefenseThreshold||60)||a.attackScore>=72))return 'DEFENDER';
  if(a.overlapRisk>=(g.overlapOptimizationThreshold||72)&&a.opportunity<76&&a.attackScore<68)return 'OPTIMIZAR';
  if(a.opportunity>=(g.minimumOpportunityForBuild||65))return 'CONSTRUIR';
  return 'OPTIMIZAR';
}

function hashNum(seed){let h=2166136261;for(const c of String(seed)){h^=c.charCodeAt(0);h=Math.imul(h,16777619)}return (h>>>0)/4294967295}
function decisionStability(v,a,baseRec){
  const sm=state.engine.sensitivityModel||{},runs=Number(sm.runs||32),amp=Number(sm.maxPerturbation||9),uncert=Math.max(.28,1-a.reliability/135);let same=0;const counts={};
  for(let i=0;i<runs;i++){
    const n=(k)=>(hashNum(`${v.name}|${i}|${k}`)*2-1)*amp*uncert;
    const x={...a,opportunity:clamp(a.opportunity+n('o')),risk:clamp(a.risk+n('r')),attackScore:clamp(a.attackScore+n('a')),evidenceConfidence:clamp(a.evidenceConfidence+n('e')*.65),reliability:clamp(a.reliability+n('rel')*.65),ecosystemStrength:clamp(a.ecosystemStrength+n('eco')*.7),channelPressure:clamp(a.channelPressure+n('ch')*.65),overlapRisk:clamp(a.overlapRisk+n('ov')*.65),dataCompleteness:clamp(a.dataCompleteness+n('dc')*.5)};
    const r=recommendationFor(x);counts[r]=(counts[r]||0)+1;if(r===baseRec)same++;
  }
  const score=clamp(same/runs*100),alternatives=Object.entries(counts).sort((a,b)=>b[1]-a[1]).map(([name,count])=>({name,count,share:clamp(count/runs*100)}));return {score,alternatives};
}
function robustRecommendation(base,a,stability){
  const g=state.engine.decisionGates||{};
  if(base==='ACELERAR'&&stability<Number(g.minimumStabilityForAccelerate||65))return a.channelPressure>=60?'DEFENDER':'CONSTRUIR';
  if(base==='DEFENDER'&&stability<Number(g.minimumStabilityForDefend||54))return 'CONSTRUIR';
  if(base==='CONSTRUIR'&&stability<Number(g.minimumStabilityForBuild||44)&&a.reliability<55)return 'INVESTIGAR';
  return base;
}
function capabilityInitiativeLabels(v,desired){
  const map={'Tech Insights':'tech-insights','Tech Assessments':'tech-insights','3D Labs':'3d-lab','3D Lab':'3d-lab','Tech Xpert':'tech-xpert','Intelligent Demand':'intelligent-demand','Servicios Westcon':'professional-services','FLEX':'flex','Lifecycle / ServiceView':'lifecycle','Cloud Marketplaces':'marketplace','GSCS':'gscs','BLUEPRINT':'psm','Preventa local':'local-presales','Academy':'academy','Support':'support'};
  return desired.filter(x=>{const id=map[x];return !id||capabilityStatus(v,id).eligible});
}
function strategicMotions(v,a,ctx){
  const sharedI=Object.keys(ctx.sharedInts||{}).length,sharedC=Object.keys(ctx.sharedCust||{}).length,proc=ctx.proc||{},motions=[];
  const add=(id,label,score,why,initiatives)=>motions.push({id,label,score:clamp(score),why,initiatives:capabilityInitiativeLabels(v,initiatives)});
  add('DISPLACE','Desplazar competencia',a.attackScore*.32+a.competitiveProof*.23+a.competitorCustomerPressure*.20+a.competitorIntegratorPressure*.13+a.evidenceConfidence*.12,'Hay prueba competitiva suficiente para buscar cuentas/rivales concretos y convertir assessments y demos en criterios de migración.',['Tech Assessments','3D Labs','BLUEPRINT']);
  add('CHANNEL','Ganar al mayorista alternativo',a.channelPressure*.30+a.servicesLeverage*.18+a.initiativeFit*.18+a.synergyPotential*.15+a.ecosystemStrength*.10+a.reliability*.09,'La presión de canal justifica competir por valor añadido, no por transacción: técnica, labs, servicios, financiación y lifecycle.',['3D Labs','Tech Xpert','Servicios Westcon','FLEX','Lifecycle / ServiceView']);
  add('ECOSYSTEM','Construir / diversificar ecosistema',a.whiteSpace*.24+(100-a.ecosystemStrength)*.23+a.opportunity*.18+a.publicDemand*.13+a.partnerConcentration*.12+a.reliability*.10,'Existe oportunidad que aún no está plenamente convertida en integradores, especialización y referencias locales.',['BLUEPRINT','Tech Xpert','Intelligent Demand']);
  add('CROSSSELL','Cross-sell multivendor',a.synergyPotential*.30+Math.min(100,(sharedI*15+sharedC*22))*.24+a.customerProof*.15+a.partnerCapability*.12+a.recurringPotential*.10+a.reliability*.09,'Integradores/clientes compartidos y sinergias permiten entrar con una arquitectura conjunta en lugar de una marca aislada.',['BLUEPRINT','3D Labs','FLEX','Cloud Marketplaces']);
  add('PUBLIC','Atacar demanda pública',a.publicDemand*.34+a.partnerCapability*.17+a.competitiveProof*.14+a.servicesLeverage*.12+(100-a.procurementConcentration)*.10+a.reliability*.13,'La contratación pública muestra demanda relativa suficiente para preparar partners, pliegos tipo, referencias y arquitectura sectorial.',['Tech Assessments','Servicios Westcon','GSCS','FLEX']);
  add('PLATFORM','Gobernar overlap y platformización',a.overlapRisk*.26+a.synergyPotential*.23+a.analystSignal*.17+a.servicesLeverage*.12+a.recurringPotential*.10+a.reliability*.12,'El solape puede convertirse en ventaja si Westcon gobierna el discovery y decide cuándo liderar con cada plataforma o combinarlas.',['BLUEPRINT','Tech Xpert','3D Labs']);
  add('COUNTRY','Expandir país menos cubierto',a.countryImbalance*.30+a.opportunity*.22+a.servicesLeverage*.15+a.synergyPotential*.12+a.evidenceConfidence*.09+a.publicDemand*.12,'El desequilibrio ES/PT crea una acción clara: replicar el play en el país con menor evidencia/ecosistema antes de escalar inversión.',['GSCS','BLUEPRINT','Tech Xpert','Intelligent Demand']);
  return motions.filter(x=>x.score>=52).sort((x,y)=>y.score-x.score).slice(0,5);
}

function actionPlan(v,a,ctx){
  const {ints,customers,sharedInts,sharedCust,proc}=ctx,topI=ints[0],topC=customers[0],strongest=(v.synergies||[]).sort((x,y)=>(y.with?.length||0)-(x.with?.length||0))[0];
  const primaryCompetitor=(v.marketCompetitors||[])[0]||'competidores directos',initiatives=initiativeSet(v,a),gaps=competitiveGapHypotheses(a),topGap=gaps[0];
  const inames=initiatives.slice(0,3).map(x=>x.name).join(' + '),crossVendors=Object.keys(sharedInts).slice(0,3),crossCustomers=Object.entries(sharedCust).slice(0,2);
  let p30,p90,p180;
  if(a.evidenceConfidence<50)p30='Cerrar primero los gaps de evidencia pública que condicionan la decisión: canal ES/PT, integradores, clientes, analistas y cambios recientes.';
  else if(v.name==='Extreme Networks')p30=`Construir una lista de renovaciones y cuentas con señal Juniper/HPE; usar ${inames||'preventa local Extreme'} solo donde exista una migración técnicamente defendible y un partner con acceso.`;
  else if(a.competitorCustomerPressure>=45)p30=`Seleccionar cuentas donde aparecen ${primaryCompetitor} u otros rivales y abrir una hipótesis de displacement con ${inames||'discovery + criterios de éxito'}, usando únicamente capacidades confirmadas para ${v.name}.`;
  else if(a.channelPressure>=55)p30=`Battlecard de canal: demostrar por qué trabajar ${v.name} con Westcon aporta más que una transacción. Convertir ${inames||'la preventa, el ecosistema y la ejecución disponibles'} en criterios de selección verificables.`;
  else if(a.partnerConcentration>=70&&topI)p30=`Usar ${topI.name} como referencia y activar un segundo integrador; elegir entre ${inames||'enablement, PSM y demanda'} las capacidades realmente confirmadas para ${v.name}.`;
  else if(a.publicDemand>=62&&proc?.topBuyers?.length)p30=`Convertir la demanda pública detectada en ${proc.technologies.slice(0,2).join(' + ')} en un mapa de cuentas: vigilar ${proc.topBuyers.slice(0,2).map(x=>x.name).join(' y ')} y preparar criterios técnicos, partner y capacidad Westcon aplicable.`;
  else if(topGap)p30=`Atacar el gap “${topGap.label}” con ${inames||'las capacidades Westcon verificadas para este fabricante'}.`;
  else p30=`Actualizar mapa de ${primaryCompetitor}, canal, integradores y cuentas; elegir dos casos de uso donde ${v.name} tenga ventaja demostrable.`;

  if(a.publicDemand>=68&&proc?.topWinners?.length&&strongest)p90=`Activar a ${proc.topWinners.slice(0,2).map(x=>x.name).join(' / ')} como señales de capacidad adjudicataria y empaquetar “${strongest.play}” para contratación pública, con assessment, demo, servicios y criterios de pliego.`;
  else if(topC&&strongest)p90=`Replicar ${topC.name} (${topC.sector}) como patrón de venta con “${strongest.play}”, integrando ${strongest.with.slice(0,2).join(' + ')} y ${inames||'servicios Westcon'}.`;
  else if(topI&&crossVendors.length)p90=`Con ${topI.name}, industrializar un play ${v.name} + ${crossVendors.join(' + ')} y elegir ${inames||'arquitectura, enablement y demanda'} según la compatibilidad real de cada capacidad.`;
  else if(strongest)p90=`Industrializar “${strongest.play}”: criterios de éxito y objection handling frente a ${primaryCompetitor}; adjuntar solo ${inames||'las capacidades confirmadas'} que mejoren win-rate, margen o velocidad.`;
  else p90=`Crear un play repetible de ${v.capabilities.slice(0,2).join(' + ')} y validarlo contra ${primaryCompetitor}; usar ${inames||'las capacidades Westcon disponibles'} únicamente si resuelven un gap concreto.`;

  if(a.countryImbalance>=55)p180='Replicar el play en el país Iberia menos cubierto: integrador especializado, primera referencia, evento técnico, GSCS y generación de demanda.';
  else if(crossCustomers.length)p180=`Priorizar cuentas públicas multivendor (${uniq(crossCustomers.flatMap(x=>x[1])).slice(0,2).join(', ')}) para expansión; usar lifecycle y servicios como mecanismo de entrada.`;
  else if(a.channelPressure>=55)p180='Medir desplazamiento frente al canal alternativo: win-rate público/market-led, referencias, partners activados, servicios attach, recurrencia y renovaciones.';
  else p180='Escalar por verticales con playbooks repetibles, partners diversificados, referencias públicas y revisión mensual de nuevas señales competitivas.';
  return {p30,p90,p180,initiatives,gaps};
}
function enrichVendor(v){
  const themes=themeMatches(v),channels=channelSignals(v),ints=integratorSignals(v),customers=customerSignals(v),eco=ecosystemMetrics(v,ints,customers,channels);
  const sharedInts=sharedIntegratorAdjacency(v,ints),sharedCust=sharedCustomerAdjacency(v,customers),proc=procurementContext(v);
  const explicit=[...(v.analystSignals||[]).map(a=>({title:a.title,url:a.url,source:a.analyst,sourceTier:'analyst-public',date:a.date,scope:'Public analyst summary',confidence:91,summary:a.summary,vendor:v.name,evidenceType:'analyst'})),...(v.channelCompetitors||[]).filter(c=>c.url).map(c=>({title:c.evidence||`${c.name} · ${c.country}`,url:c.url,source:c.name,sourceTier:'official-company',date:'2026',scope:c.country,confidence:86,summary:c.evidence,vendor:v.name,evidenceType:'channel'})),...ecosystemEvidence(v,ints,customers)];
  const evMap=new Map();[...relevantEvidence(v),...explicit].forEach(e=>evMap.set(e.url||`${e.title}|${e.source}`,e));const ev=[...evMap.values()];
  const market=clamp(themes.length?avg(themes,x=>x.momentum):domainDefault(v,'marketMomentum'));
  const fit=clamp(themes.length?avg(themes,x=>x.portfolioFit)+(v.countries?.length>1?3:0):68+(v.countries?.length>1?5:0));
  const recurring=clamp(themes.length?avg(themes,x=>x.recurringPotential):domainDefault(v,'recurringPotential'));
  const diff=clamp(themes.length?avg(themes,x=>x.differentiation):68),baseSyn=baseSynergyScore(v);
  const ecosystemAdj=Math.min(18,Object.keys(sharedInts).length*3+Object.keys(sharedCust).length*4),synergy=clamp(baseSyn+ecosystemAdj);
  const overlap=overlapScore(v),channel=channelPressure(v,channels),competitive=competitiveIntensity(v),econf=evidenceConfidence(v,ev),analyst=analystScore(v,ev),services=domainDefault(v,'servicesLeverage');
  const compInts=competitorIntegratorPressure(v,ints),compCust=competitorCustomerPressure(v,customers),competitiveProof=competitiveProofScore(v,ev,compInts,compCust);
  const partnerCap=clamp(eco.integratorStrength*.78+Math.min(22,Object.keys(sharedInts).length*4)),countryCov=eco.countryCoverage;
  const w=state.engine.opportunityWeights;
  const rawOpportunity=clamp(market*w.marketMomentum+fit*w.portfolioFit+recurring*w.recurringPotential+diff*w.differentiation+synergy*w.synergyPotential+analyst*w.analystSignal+services*w.servicesLeverage+eco.strength*w.ecosystemStrength+eco.customerProof*w.customerProof+partnerCap*w.partnerCapability+countryCov*w.countryCoverage+proc.demand*(w.publicDemand||0)+competitiveProof*(w.competitiveProof||0)+econf*w.evidenceConfidence);
  const completeness=clamp((channels.length?12:0)+(ints.length?15:0)+(customers.length?15:0)+(analyst>=45?12:0)+(ev.length>=4?12:ev.length*3)+(themes.length?10:0)+(v.marketCompetitors?.length?8:0)+(proc.rows.length?9:0)+(competitiveProof>=45?7:0));
  const um=state.engine.uncertaintyModel||{},reliability=clamp(econf*(um.evidenceWeight||.58)+completeness*(um.completenessWeight||.42)),prior=Number(um.neutralPrior||55),shrink=Math.max(Number(um.minimumReliability||.35),reliability/100);
  const opportunity=clamp(prior+(rawOpportunity-prior)*shrink);
  const pConc=partnerConcentration(ints),cConc=clientConcentration(customers),freshRisk=clamp(100-avg(ev.slice(0,20),e=>freshnessScore(e.date||e.published||e.collectedAt))),cImb=countryImbalance(v,eco),weakEco=100-eco.strength,rw=state.engine.riskWeights;
  const risk=clamp(overlap*rw.overlapRisk+channel*rw.channelPressure+competitive*(rw.competitiveIntensity||0)+pConc*rw.partnerConcentration+cConc*rw.clientConcentration+(100-econf)*rw.evidenceGap+freshRisk*rw.freshnessRisk+cImb*rw.countryImbalance+weakEco*rw.weakLocalEcosystem+proc.concentration*(rw.procurementConcentration||0)+(100-competitiveProof)*(rw.competitiveProofGap||0));
  const whiteSpace=clamp(opportunity-eco.strength+45),aw=state.engine.attackOpportunityWeights||{};
  const preAttack={servicesLeverage:services,synergyPotential:synergy,recurringPotential:recurring,overlapRisk:overlap,countryCoverage:countryCov,ecosystemStrength:eco.strength,publicDemand:proc.demand};const initiativeFit=initiativeFitScore(preAttack);
  const attackRaw=clamp(opportunity*(aw.marketOpportunity||0)+channel*(aw.channelPressure||0)+competitive*(aw.competitiveIntensity||0)+whiteSpace*(aw.whiteSpace||0)+synergy*(aw.synergyPotential||0)+services*(aw.servicesLeverage||0)+partnerCap*(aw.integratorLeverage||0)+eco.customerProof*(aw.customerProof||0)+Math.max(overlap,55)*(aw.overlapExploitability||0)+analyst*(aw.analystSignal||0)+econf*(aw.evidenceConfidence||0)+proc.demand*(aw.publicDemand||0)+competitiveProof*(aw.competitiveProof||0)+initiativeFit*(aw.initiativeFit||0)+compInts.score*.035+compCust.score*.035);
  const attackScore=clamp((attackRaw*.72)+(reliability*.18)+(100-risk)*.10);
  const decisionScore=clamp(opportunity*.55+attackScore*.18+(100-risk)*.12+eco.strength*.07+econf*.05+recurring*.03);
  const analysis={marketMomentum:market,portfolioFit:fit,recurringPotential:recurring,differentiation:diff,synergyPotential:synergy,overlapRisk:overlap,channelPressure:channel,competitiveIntensity:competitive,competitorIntegratorPressure:compInts.score,competitorCustomerPressure:compCust.score,competitiveProof,publicDemand:proc.demand,procurementConcentration:proc.concentration,initiativeFit,evidenceConfidence:econf,analystSignal:analyst,servicesLeverage:services,ecosystemStrength:eco.strength,integratorStrength:eco.integratorStrength,customerProof:eco.customerProof,partnerCapability:partnerCap,countryCoverage:countryCov,partnerConcentration:pConc,clientConcentration:cConc,freshnessRisk:freshRisk,countryImbalance:cImb,weakLocalEcosystem:weakEco,dataCompleteness:completeness,reliability,rawOpportunity,whiteSpace,opportunity,risk,attackScore,decisionScore};
  const baseRecommendation=recommendationFor(analysis),stability=decisionStability(v,analysis,baseRecommendation);analysis.decisionStability=stability.score;analysis.recommendationAlternatives=stability.alternatives;analysis.baseRecommendation=baseRecommendation;analysis.recommendation=robustRecommendation(baseRecommendation,analysis,stability.score);
  const motions=strategicMotions(v,analysis,{ints,customers,sharedInts,sharedCust,proc});
  const legacyPlan=actionPlan(v,analysis,{ints,customers,sharedInts,sharedCust,proc,motions});legacyPlan.motions=motions;
  const traits=vendorTraits(v,analysis,{ev,sharedInts,sharedCust,eco,proc});Object.assign(analysis,traits);
  const roleRecs=roleRecommendations({...v,derived:{evidence:ev}},analysis,traits),archetype=archetypeFor(v,analysis,traits),plan=executivePlan(v,analysis,archetype,roleRecs,legacyPlan);
  const drivers=[['Mercado',market],['Vendor momentum',traits.vendorMomentum],['Demanda pública',proc.demand],['Ecosistema',eco.strength],['Sinergia',synergy],['Clientes',eco.customerProof],['Prueba competitiva',competitiveProof],['Analistas',analyst],['Recurrencia',recurring]].sort((a,b)=>b[1]-a[1]).slice(0,5);
  const brakes=[['Solape',overlap],['Canal',channel],['Concentración partner',pConc],['Gap evidencia',100-econf],['Desbalance país',cImb],['Disrupción M&A',traits.mnaDisruption]].sort((a,b)=>b[1]-a[1]).slice(0,4);
  return {...v,analysis,derived:{themes,channels,integrators:ints,customers,evidence:ev,plan,drivers,brakes,roleRecommendations:roleRecs,archetype,traits,sharedIntegrators:sharedInts,sharedCustomers:sharedCust,competitorIntegratorRows:compInts.rows,competitorCustomerRows:compCust.rows,procurement:proc}};
}

function initNav(){
  $$('#tabs button').forEach(b=>b.onclick=()=>switchView(b.dataset.view));$$('[data-jump]').forEach(b=>b.onclick=()=>switchView(b.dataset.jump));
  ['vendorSearch','domainFilter','recommendationFilter','countryFilter'].forEach(id=>$('#'+id)?.addEventListener(id==='vendorSearch'?'input':'change',renderVendorTable));
  $$('#smartFilters button').forEach(b=>b.onclick=()=>{state.quick=b.dataset.quick;$$('#smartFilters button').forEach(x=>x.classList.toggle('active',x===b));renderVendorTable()});
  $('#sourceSearch')?.addEventListener('input',renderSources);['sourceTierFilter','sourceTypeFilter','sourceGeoFilter'].forEach(id=>$('#'+id)?.addEventListener('change',renderSources));
  $('#btnDepth').onclick=()=>{state.deep=!state.deep;document.body.classList.toggle('deep-mode',state.deep);$('#btnDepth').textContent=state.deep?'Vista ejecutiva':'Ver datos';if(state.selected)selectVendor(state.selected)};
  $('#btnFontDown')?.addEventListener('click',()=>changeFont(-.08));$('#btnFontUp')?.addEventListener('click',()=>changeFont(.08));$('#btnExport')?.addEventListener('click',openExport);$('#exportClose')?.addEventListener('click',closeExport);$('#exportPdf')?.addEventListener('click',()=>{closeExport();exportPdf()});$('#exportPptx')?.addEventListener('click',()=>{closeExport();exportPptx()});renderExportModules();
}
function changeFont(delta){state.fontScale=Math.max(.82,Math.min(1.30,Math.round((state.fontScale+delta)*100)/100));document.documentElement.style.setProperty('--font-scale',state.fontScale);localStorage.setItem('westcon-font-scale',state.fontScale);toast(`Tamaño ${Math.round(state.fontScale*100)}%`)}
function renderExportModules(){const box=$('#exportModules');if(!box)return;box.innerHTML=(state.decision.exportModules||[]).map(m=>`<label><input type="checkbox" data-module="${m.id}" ${state.reportModules.has(m.id)?'checked':''}> ${esc(m.name)}</label>`).join('');$$('#exportModules input').forEach(x=>x.onchange=()=>{x.checked?state.reportModules.add(x.dataset.module):state.reportModules.delete(x.dataset.module)})}
function openExport(){$('#exportModal')?.classList.add('open')}function closeExport(){$('#exportModal')?.classList.remove('open')}
function switchView(id){$$('.view').forEach(v=>v.classList.toggle('active',v.id===id));$$('#tabs button').forEach(b=>b.classList.toggle('active',b.dataset.view===id));window.scrollTo({top:0,behavior:'smooth'})}
function renderAll(){state.fontScale=Number(localStorage.getItem('westcon-font-scale')||1);document.documentElement.style.setProperty('--font-scale',state.fontScale);renderKpis();renderDecisionCards();renderChanges();renderDataHealth();renderFilters();renderOverviewVendors();renderVendorTable();renderPlays();renderOverlaps();renderTrends();renderSignals();renderDataKpis();renderEngine();renderGaps();renderSources();renderResearch()}
function renderKpis(){
  const ev=allEvidence(),official=ev.filter(e=>['official-company','analyst-public','regulator'].includes(e.sourceTier)).length,ints=state.vendors.reduce((s,v)=>s+v.derived.integrators.length,0),cust=state.vendors.reduce((s,v)=>s+v.derived.customers.length,0),strong=state.vendors.filter(v=>v.analysis.evidenceConfidence>=65).length;
  const k=[[state.vendors.length,'Fabricantes','Portfolio FY27'],[ev.length,'Evidencias','públicas trazables'],[ints,'Integradores','señales Iberia'],[cust,'Clientes públicos','referencias ES/PT'],[strong,'Bien cubiertos','confianza ≥65']];
  $('#marketKpis').innerHTML=k.map(x=>`<div class="kpi"><span>${x[1]}</span><strong>${x[0]}</strong><small>${x[2]}</small></div>`).join('')
}
function renderDecisionCards(){
  const rows=[...state.vendors].sort((a,b)=>b.analysis.decisionScore-a.analysis.decisionScore).slice(0,4);
  $('#decisionCards').innerHTML=rows.map(v=>`<article class="decision-card" data-vendor="${esc(v.name)}"><div class="decision-head"><span class="priority ${v.analysis.recommendation}">${v.analysis.recommendation}</span><b>${v.analysis.opportunity}</b></div><h3>${esc(v.name)}</h3><p>${esc(v.derived.plan.p90)}</p><div class="mini-metrics">${metricPill('ecos.',v.analysis.ecosystemStrength,'confidence')}${metricPill('canal',v.analysis.channelPressure,'channel')}${metricPill('solape',v.analysis.overlapRisk,'overlap')}${metricPill('conf.',v.analysis.evidenceConfidence,'confidence')}</div></article>`).join('');
  $$('#decisionCards .decision-card').forEach(x=>x.onclick=()=>{switchView('fabricantes');selectVendor(x.dataset.vendor)})
}
function renderChanges(){const impact=x=>x.type==='coverage'?`Cobertura ${x.from} → ${x.to}`:x.type==='channel-ended'?`Fin de relación de canal detectado · ${x.country||''} · confianza ${x.confidence||'—'}`:x.type==='channel-missing'?`La relación ya no está confirmada · requiere validación`:x.type==='public-procurement-demand'?`Índice relativo de demanda pública ${x.from} → ${x.to}`:x.type==='public-procurement-buyer'?`Nuevo comprador público relevante · ${x.country||''}`:x.type==='public-procurement-winner'?`Nuevo adjudicatario/integrador relevante · ${x.country||''}`:`Nueva señal pública ${x.country||''} · confianza ${x.confidence||'—'}`;const auto=(state.changes?.changes||[]).map(x=>({date:x.detectedAt,title:`${x.vendor||x.technology||''} · ${x.title}${x.entity?` · ${x.entity}`:''}`,impact:impact(x),url:x.url}));const rows=[...auto,...state.data.externalChanges].sort((a,b)=>String(b.date||'').localeCompare(String(a.date||''))).slice(0,8);$('#externalChanges').innerHTML=rows.map(x=>`<div class="time-item"><time>${fmtDate(x.date)}</time><div><b>${esc(x.title)}</b><p>${esc(x.impact||'Cambio detectado por el motor de investigación.')}</p>${x.url?`<a class="evidence-link" href="${x.url}" target="_blank" rel="noopener">Fuente pública ↗</a>`:''}</div></div>`).join('')}
function renderDataHealth(){
  const items=[['Canal ES/PT',state.vendors.filter(v=>v.derived.channels.length).length,state.vendors.length,'Mayoristas alternativos identificados'],['Integradores',state.vendors.filter(v=>v.derived.integrators.length).length,state.vendors.length,'Partners/integradores con prueba pública'],['Clientes públicos',state.vendors.filter(v=>v.derived.customers.length).length,state.vendors.length,'Referencias finales ES/PT'],['Demanda pública',state.vendors.filter(v=>v.analysis.publicDemand>=35).length,state.vendors.length,'Señales estructuradas de contratación ES/PT'],['Consultoras',state.vendors.filter(v=>v.analysis.analystSignal>=50).length,state.vendors.length,'Señal pública específica o de mercado'],['Evidencia fuerte',state.vendors.filter(v=>v.analysis.evidenceConfidence>=65).length,state.vendors.length,'Cobertura suficiente para lectura ejecutiva']];
  $('#dataHealth').innerHTML=items.map(x=>{const p=Math.round(x[1]/x[2]*100);return `<div class="health-row"><div><b>${x[0]}</b><span>${x[1]}/${x[2]} · ${x[3]}</span></div><strong>${p}%</strong><div class="healthbar"><i style="--w:${p}%"></i></div></div>`}).join('')
}
function renderFilters(){const domains=uniq(state.vendors.map(v=>v.domain)).sort();$('#domainFilter').innerHTML='<option value="all">Todas las áreas</option>'+domains.map(d=>`<option>${esc(d)}</option>`).join('');const rec=['ACELERAR','CONSTRUIR','DEFENDER','OPTIMIZAR','INVESTIGAR'];$('#recommendationFilter').innerHTML='<option value="all">Todas las decisiones</option>'+rec.map(x=>`<option>${x}</option>`).join('')}
function filteredVendors(){
  const q=$('#vendorSearch').value.trim().toLowerCase(),d=$('#domainFilter').value,r=$('#recommendationFilter').value,c=$('#countryFilter').value;
  return state.vendors.filter(v=>{
    const blob=[v.name,v.domain,...v.capabilities,...v.marketCompetitors,...v.derived.channels.map(x=>x.distributor),...v.derived.integrators.map(x=>x.name),...v.derived.customers.flatMap(x=>[x.name,x.sector,x.solution]),...(v.internalOverlaps||[]).map(x=>x.vendor),...(v.synergies||[]).flatMap(x=>x.with||[]),...vendorCapabilities(v).map(x=>x.programme?.name||x.id)].join(' ').toLowerCase();
    let ok=(!q||blob.includes(q))&&(d==='all'||v.domain===d)&&(r==='all'||v.analysis.recommendation===r)&&(c==='all'||v.countries.includes(c));if(!ok)return false;
    if(state.quick==='opportunity')return v.analysis.opportunity>=78;if(state.quick==='channel')return v.analysis.channelPressure>=55;if(state.quick==='synergy')return v.analysis.synergyPotential>=70;if(state.quick==='overlap')return v.analysis.overlapRisk>=60;if(state.quick==='ecosystem')return v.analysis.ecosystemStrength>=68;if(state.quick==='whitespace')return v.analysis.whiteSpace>=62;if(state.quick==='references')return v.derived.customers.length>=2;if(state.quick==='gaps')return v.analysis.evidenceConfidence<50||v.analysis.dataCompleteness<50;return true;
  }).sort((a,b)=>b.analysis.decisionScore-a.analysis.decisionScore||a.name.localeCompare(b.name));
}
function channelSummary(v){const rows=v.derived.channels;if(!rows.length)return '<span class="tiny">Por demostrar</span>';const grouped={ES:[],PT:[],IBERIA:[]};rows.forEach(x=>(grouped[x.country]??=[]).push(x.distributor));return ['ES','PT','IBERIA'].map(c=>grouped[c]?.length?`<span class="tag channel">${c}: ${esc(uniq(grouped[c]).join(', '))}</span>`:'').join('')}
function ecosystemSummary(v){const ints=v.derived.integrators.slice(0,2),cust=v.derived.customers;return `${ints.length?ints.map(x=>`<span class="tag ecosystem">${esc(x.country)}: ${esc(x.name)}</span>`).join(''):'<span class="tiny">Integrador por demostrar</span>'}<span class="tiny ecosystem-count">${cust.length} referencia${cust.length===1?'':'s'} pública${cust.length===1?'':'s'} · ecosistema ${v.analysis.ecosystemStrength}</span>`}
function analystSummary(v){if(!v.analystSignals?.length)return `<span class="coverage ${v.analysis.analystSignal>=45?'mid':'low'}">${v.analysis.analystSignal} · cobertura ${v.analysis.analystSignal>=45?'media':'baja'}</span>`;return v.analystSignals.slice(0,2).map(a=>`<span class="tag analyst">${esc(a.analyst)} · ${esc(a.title.replace('Magic Quadrant for ','').replace('Critical Capabilities for ',''))}</span>`).join('')}
function scoreCell(v,key,cls=''){const x=v.analysis[key];return `<div class="score-cell ${cls}"><b>${x}</b><span class="scorebar"><i style="--w:${x}%"></i></span></div>`}
function synergyOverlap(v){return `<span class="balance good">S ${v.analysis.synergyPotential}</span><span class="balance bad">O ${v.analysis.overlapRisk}</span>`}
function renderOverviewVendors(){
  const rows=[...state.vendors].sort((a,b)=>b.analysis.decisionScore-a.analysis.decisionScore).slice(0,12);
  $('#overviewVendorRows').innerHTML=rows.map(v=>`<tr data-vendor="${esc(v.name)}"><td><span class="vendor-name">${esc(v.name)}</span><span class="tiny">${esc(v.domain)}</span></td><td><span class="priority ${v.analysis.recommendation}">${v.analysis.recommendation}</span><span class="tiny">score ${v.analysis.decisionScore}</span></td><td>${tags(v.marketCompetitors,'',3)}</td><td>${channelSummary(v)}</td><td>${ecosystemSummary(v)}</td><td>${analystSummary(v)}</td><td>${synergyOverlap(v)}</td><td>${esc(v.derived.plan.p30)}</td></tr>`).join('');
  $$('#overviewVendorRows tr').forEach(tr=>tr.onclick=()=>{switchView('fabricantes');selectVendor(tr.dataset.vendor)})
}
function renderVendorTable(){
  const rows=filteredVendors();$('#resultCount').textContent=`${rows.length} fabricantes`;
  $('#vendorRows').innerHTML=rows.map(v=>`<tr data-vendor="${esc(v.name)}" class="${state.selected===v.name?'selected':''}"><td><span class="vendor-name">${esc(v.name)}</span><span class="tiny">${v.countries.join(' · ')} · ${esc(v.domain)}</span></td><td><span class="priority ${v.analysis.recommendation}">${v.analysis.recommendation}</span></td><td>${scoreCell(v,'opportunity')}</td><td>${tags(v.marketCompetitors,'',3)}</td><td>${channelSummary(v)}</td><td>${ecosystemSummary(v)}</td><td>${analystSummary(v)}</td><td>${scoreCell(v,'synergyPotential','good')}</td><td>${scoreCell(v,'overlapRisk','bad')}</td><td><span class="confidence-dot ${v.analysis.evidenceConfidence>=65?'high':v.analysis.evidenceConfidence>=45?'mid':'low'}"></span>${v.analysis.evidenceConfidence}<span class="tiny">${evidenceLabel(v)}</span></td><td>${esc(v.derived.plan.p30)}</td></tr>`).join('');
  $$('#vendorRows tr').forEach(tr=>tr.onclick=()=>selectVendor(tr.dataset.vendor))
}
function metricCard(label,value,note,kind=''){return `<div class="metric-card ${kind}"><span>${esc(label)}</span><strong>${clamp(value)}</strong><div class="meter"><i style="--w:${clamp(value)}%"></i></div><small>${esc(note)}</small></div>`}
function adjacencyHtml(obj,label){const rows=Object.entries(obj);if(!rows.length)return '<span class="tiny">Sin señal cruzada demostrada.</span>';return rows.slice(0,6).map(([vendor,names])=>`<div class="adj-row"><b>${esc(vendor)}</b><span>${esc(label)}: ${esc(uniq(names).join(', '))}</span></div>`).join('')}
function selectVendor(name){
  state.selected=name;renderVendorTable();const v=state.vendors.find(x=>x.name===name);if(!v)return;const a=v.analysis;
  const chan=v.derived.channels.map(c=>`<div class="evidence-row"><div><b>${esc(c.country)} · ${esc(c.distributor)}</b><span>Confianza ${clamp(c.confidence||65)}/100</span></div>${c.url?`<a href="${c.url}" target="_blank" rel="noopener">Fuente ↗</a>`:''}</div>`).join('')||'<p>Sin mayorista alternativo demostrado públicamente todavía. No significa exclusividad.</p>';
  const ints=v.derived.integrators.map(x=>`<div class="ecosystem-row"><div><b>${esc(countryLabel(x.country))} · ${esc(x.name)}</b><span>${esc(x.role||'Partner')} · confianza ${clamp(x.confidence||70)}</span><small>${esc(x.signal||'Prueba pública de relación')}</small></div>${x.url?`<a href="${x.url}" target="_blank" rel="noopener">Fuente ↗</a>`:''}</div>`).join('')||'<p>No hay integrador Iberia suficientemente demostrado todavía.</p>';
  const customers=v.derived.customers.map(x=>`<div class="customer-row"><div><b>${esc(countryLabel(x.country))} · ${esc(x.name)}</b><span>${esc(x.sector||'Sector no clasificado')}</span><small>${esc(x.solution||'Referencia pública')}</small>${x.integrator?`<em>Integrador: ${esc(x.integrator)}</em>`:''}</div>${x.url?`<a href="${x.url}" target="_blank" rel="noopener">Caso ↗</a>`:''}</div>`).join('')||'<p>No hay cliente final Iberia suficientemente demostrado todavía.</p>';
  const ana=(v.analystSignals||[]).map(x=>`<div class="analyst-row"><b>${esc(x.analyst)} · ${fmtDate(x.date)}</b><p>${esc(x.summary)}</p><div>${tags(x.peers,'',5)}</div><a class="evidence-link" href="${x.url}" target="_blank" rel="noopener">${esc(x.title)} ↗</a></div>`).join('')||'<p>No hay señal pública específica suficientemente fuerte cargada para este fabricante.</p>';
  const syn=(v.synergies||[]).map(s=>`<div class="synergy-row"><b>${esc(s.play)}</b><p>${esc(s.value)}</p>${tags(s.with,'synergy')}</div>`).join('')||'<p>Sin play multivendor explícito cargado.</p>';
  const ov=(v.internalOverlaps||[]).map(o=>`<span class="tag overlap">${esc(o.vendor)} · ${esc(o.area)}</span>`).join('')||'<span class="tiny">Solape bajo o todavía no modelado.</span>';
  const ev=v.derived.evidence.slice(0,state.deep?30:7).map(e=>`<div class="source-mini"><b>${esc(e.source||e.sourceTier)} · ${fmtDate(e.date||e.published)}</b><span>${esc(e.title)}</span><a href="${e.url}" target="_blank" rel="noopener">Abrir ↗</a></div>`).join('')||'<p>La evidencia específica todavía es limitada.</p>';
  const drivers=v.derived.drivers.map(x=>`<span class="driver good"><b>${x[1]}</b>${x[0]}</span>`).join(''),brakes=v.derived.brakes.map(x=>`<span class="driver bad"><b>${x[1]}</b>${x[0]}</span>`).join('');
  const roleOpts=(state.decision.roles||[]).map(r=>`<option value="${r.id}" ${r.id===state.selectedRole?'selected':''}>${esc(r.name)}</option>`).join('');
  const execActs=(v.derived.plan.executiveActions||[]).slice(0,5).map(x=>`<div class="action-mini"><strong>${x.score}</strong><div><b>${esc(x.name)}</b><span>${esc((state.decision.roles||[]).find(r=>r.id===x.role)?.name||x.role)}</span></div></div>`).join('');
  $('#vendorDetail').innerHTML=`<div class="detail-top"><div class="domain">${esc(v.domain)} · ${v.countries.join(' / ')}</div><h2>${esc(v.name)}</h2><div class="decision-line"><span class="priority ${a.recommendation}">${a.recommendation}</span><b>${a.decisionScore}<small>/100 decisión</small></b></div><div style="margin-top:8px">${tags(v.capabilities)}</div></div>
  <div class="archetype-box"><span>TESIS ESTRATÉGICA</span><b>${esc(v.derived.archetype?.name||'Estrategia selectiva')}</b><p>${esc(v.derived.plan.thesis||v.derived.archetype?.description||'')}</p></div>
  <div class="metric-grid ecosystem-metrics">${metricCard('Oportunidad',a.opportunity,'atractivo estratégico','good')}${metricCard('Vendor',a.vendorMomentum,'momentum / innovación','good')}${metricCard('Ecosistema',a.ecosystemStrength,'integradores + clientes','good')}${metricCard('Canal',a.channelPressure,'presión mayorista','warn')}${metricCard('Solape',a.overlapRisk,'canibalización potencial','bad')}${metricCard('Fiabilidad',a.reliability,'evidencia + completitud','info')}</div>
  <div class="action-box"><b>QUÉ HACER</b><p>${esc(v.derived.plan.p90)}</p></div>
  <div class="detail-block"><h4>ACCIONES PRIORITARIAS CROSS-FUNCTION</h4><div class="action-stack">${execActs}</div></div>
  <div class="detail-block"><div class="role-picker"><h4>RECOMENDACIONES POR PERFIL</h4><select id="roleSelect">${roleOpts}</select></div><div id="roleRecommendations">${roleRecommendationHtml(v,state.selectedRole)}</div><div class="method-note">Cada acción se selecciona por ajuste al contexto del fabricante. FLEX, 3D Lab, servicios, stock, marketing o enablement solo aparecen si sus señales superan el umbral del motor.</div></div>
  <div class="drivers"><div><h4>IMPULSA</h4>${drivers}</div><div><h4>FRENA</h4>${brakes}</div></div>
  <div class="detail-block"><h4>CAPACIDADES WESTCON CONFIRMADAS / ELEGIBLES</h4><div class="capability-grid">${vendorCapabilities(v).map(c=>`<div class="capability-item"><b>${esc(c.programme?.name||c.id)}</b><span>${esc(c.status.replaceAll('_',' '))} · ${esc(c.scope||'')}</span><small>${esc(c.reason||c.programme?.purpose||'')}</small></div>`).join('')||'<span class="tiny">Sin capacidades específicas verificadas todavía.</span>'}</div></div>
  <div class="detail-block"><h4>COMPETIDORES DE MERCADO</h4>${tags(v.marketCompetitors,'',7)}</div>
  <div class="detail-block"><h4>MAYORISTAS ALTERNATIVOS · ES/PT</h4>${chan}</div>
  <div class="detail-block"><h4>INTEGRADORES / PARTNERS IBERIA</h4>${ints}</div>
  <div class="detail-block"><h4>CLIENTES FINALES PÚBLICOS · ES/PT</h4>${customers}</div>
  <div class="deep-only detail-block"><h4>DEMANDA PÚBLICA DETECTADA · ES/PT</h4><p><b>Índice relativo ${a.publicDemand}/100.</b> ${esc(v.derived.procurement.technologies.join(' · ')||'Sin señal suficiente por tecnología.')}</p>${v.derived.procurement.topBuyers.slice(0,6).map(x=>`<span class="tag">${esc(x.name)} · ${x.signals}</span>`).join('')||'<span class="tiny">Sin compradores públicos agregados todavía.</span>'}<p class="tiny">Señal de contratación pública; no equivale a oportunidad comercial confirmada ni a cuota de mercado.</p></div>
  <div class="detail-block"><h4>OPORTUNIDADES DE ECOSISTEMA</h4><div class="ecosystem-adj"><div><b>Integradores compartidos con otros vendors</b>${adjacencyHtml(v.derived.sharedIntegrators,'partner')}</div><div><b>Clientes con señales de otros vendors</b>${adjacencyHtml(v.derived.sharedCustomers,'cuenta')}</div></div></div>
  <div class="detail-block"><h4>CONSULTORAS / DIFERENCIAL</h4>${ana}<p class="analyst-diff">${esc(v.analystDifferential)}</p></div>
  <div class="detail-block"><h4>SINERGIAS</h4>${syn}</div><div class="detail-block"><h4>OVERLAP</h4>${ov}</div>
  <div class="detail-block"><h4>CÓMO ATACAR LA COMPETENCIA</h4><p><b>${esc(v.derived.plan.motions?.[0]?.label||'Ataque competitivo')} · ${v.derived.plan.motions?.[0]?.score||a.attackScore}/100.</b> ${esc(v.derived.plan.motions?.[0]?.why||v.derived.plan.gaps?.[0]?.label||'Buscar gaps demostrables de canal, ecosistema, prueba, servicios y recurrencia.')}</p></div>
  <div class="plan-block"><h4>PLAN PROPUESTO</h4><div><b>30 días</b><p>${esc(v.derived.plan.p30)}</p></div><div><b>90 días</b><p>${esc(v.derived.plan.p90)}</p></div><div><b>6 meses</b><p>${esc(v.derived.plan.p180)}</p></div></div>
  <div class="deep-only detail-block"><h4>DESGLOSE DEL MOTOR V6</h4><div class="engine-metrics">${Object.entries({Mercado:a.marketMomentum,'Vendor momentum':a.vendorMomentum,Encaje:a.portfolioFit,Recurrencia:a.recurringPotential,Diferenciación:a.differentiation,Sinergia:a.synergyPotential,Analistas:a.analystSignal,Servicios:a.servicesLeverage,Ecosistema:a.ecosystemStrength,Integradores:a.integratorStrength,Clientes:a.customerProof,Cobertura:a.countryCoverage,Canal:a.channelPressure,Solape:a.overlapRisk,Competencia:a.competitiveIntensity,'Complejidad técnica':a.technicalComplexity,'Necesidad prueba':a.technicalProofNeed,'Hardware':a.hardwareIntensity,'Cloud':a.cloudIntensity,'Marketplace':a.marketplaceFit,'Financiación fit':a.financeFit,'Stock fit':a.stockNeed,'Managed services':a.managedServiceFit,'Lifecycle':a.lifecycleFit,'Generación demanda':a.demandGenerationNeed,'Enablement need':a.partnerEnablementNeed,Evidencia:a.evidenceConfidence,Fiabilidad:a.reliability,Completitud:a.dataCompleteness,WhiteSpace:a.whiteSpace,'Demanda pública':a.publicDemand,'Prueba competitiva':a.competitiveProof,'Estabilidad decisión':a.decisionStability,Ataque:a.attackScore}).map(([k,val])=>metricPill(k,val)).join('')}</div></div>
  <div class="deep-only detail-block"><h4>EVIDENCIAS RELACIONADAS · ${v.derived.evidence.length}</h4>${ev}</div>`;
  $('#roleSelect').onchange=e=>{state.selectedRole=e.target.value;$('#roleRecommendations').innerHTML=roleRecommendationHtml(v,state.selectedRole)};
  if(window.innerWidth<1200)$('#vendorDetail').scrollIntoView({behavior:'smooth',block:'start'})
}
function renderPlays(){$('#playCards').innerHTML=(state.base.solutionPlays||[]).map((p,i)=>{const vs=state.vendors.filter(v=>p.vendors.includes(v.name));const op=clamp(avg(vs,x=>x.analysis.opportunity)),sy=clamp(avg(vs,x=>x.analysis.synergyPotential)),ov=clamp(avg(vs,x=>x.analysis.overlapRisk)),eco=clamp(avg(vs,x=>x.analysis.ecosystemStrength));return `<article class="play-card"><div class="num">0${i+1}</div><div class="play-score">${op}<small>oportunidad</small></div><h3>${esc(p.name)}</h3><p>${esc(p.value)}</p><div class="vendor-tags">${p.vendors.map(v=>`<span>${esc(v)}</span>`).join('')}</div><div class="play-bottom"><span>Sinergia <b>${sy}</b></span><span>Ecosistema <b>${eco}</b></span><span>Overlap <b>${ov}</b></span><strong>→ Oferta repetible + integradores + referencias + demo + campaña</strong></div></article>`}).join('')}
function renderOverlaps(){const map={};state.vendors.forEach(v=>(v.internalOverlaps||[]).forEach(o=>{const x=map[o.area]??={vendors:new Set(),score:0};x.vendors.add(v.name);x.vendors.add(o.vendor);x.score=Math.max(x.score,v.analysis.overlapRisk)}));$('#overlapMap').innerHTML=Object.entries(map).sort((a,b)=>b[1].score-a[1].score).map(([area,x])=>`<article class="overlap-card"><div class="overlap-score">${x.score}</div><h3>${esc(area)}</h3><div class="overlap-line">${[...x.vendors].map(v=>`<span class="tag overlap">${esc(v)}</span>`).join('')}</div><p><b>Acción:</b> segmentar por caso de uso, integrador, vertical y criterio de decisión; activar sinergias donde el mismo partner pueda vender varios vendors.</p></article>`).join('')}
function renderTrends(){$('#trendCards').innerHTML=state.base.themes.slice().sort((a,b)=>b.momentum-a.momentum).map(t=>{const score=clamp(t.momentum*.32+t.portfolioFit*.25+t.recurringPotential*.18+t.differentiation*.15+t.confidence*.10);return `<article class="trend-card"><div class="trend-score">${score}<span class="tiny">/100 · inferencia</span></div><div class="meter"><i style="--w:${score}%"></i></div><h3>${esc(t.name)}</h3><p>${esc(t.why)}</p><div class="trend-factors"><span>M ${t.momentum}</span><span>Fit ${t.portfolioFit}</span><span>Rec ${t.recurringPotential}</span><span>Dif ${t.differentiation}</span></div></article>`}).join('')}
function renderSignals(){$('#signalCards').innerHTML=state.data.marketSignals.slice().sort((a,b)=>String(b.date).localeCompare(String(a.date))).map(s=>`<article class="signal-card"><span>${esc(s.analyst)} · ${fmtDate(s.date)}</span><strong>${esc(s.metric)}</strong><h3>${esc(s.label)}</h3><p>${esc(s.detail)}</p><a class="evidence-link" href="${s.url}" target="_blank" rel="noopener">Fuente ↗</a></article>`).join('')}
function renderDataKpis(){const ev=allEvidence(),tiers={};ev.forEach(e=>tiers[e.sourceTier]=(tiers[e.sourceTier]||0)+1);const gaps=state.vendors.filter(v=>v.analysis.dataCompleteness<50).length,ints=state.vendors.reduce((s,v)=>s+v.derived.integrators.length,0),cust=state.vendors.reduce((s,v)=>s+v.derived.customers.length,0),total=ev.length+ints+cust;const caps=(state.research?.capabilitySignals||[]).length+(state.capability?.programmes||[]).length;const k=[[total,'Evidencias','mercado + canal + ecosistema'],[caps,'Capacidades','programas + verificaciones'],[tiers['analyst-public']||0,'Consultoras','contenido público'],[ints,'Integradores','relaciones ES/PT'],[cust,'Clientes','referencias públicas'],[gaps,'Gaps','completitud <50']];$('#dataKpis').innerHTML=k.map(x=>`<div class="kpi"><span>${x[1]}</span><strong>${x[0]}</strong><small>${x[2]}</small></div>`).join('')}
function renderEngine(){
  const labels={marketMomentum:'Mercado',portfolioFit:'Encaje portfolio',recurringPotential:'Recurrencia',differentiation:'Diferenciación',synergyPotential:'Sinergias',analystSignal:'Analistas',servicesLeverage:'Servicios',ecosystemStrength:'Ecosistema local',customerProof:'Referencias cliente',partnerCapability:'Capacidad integradores',countryCoverage:'Cobertura ES/PT',publicDemand:'Demanda pública',competitiveProof:'Prueba competitiva',evidenceConfidence:'Confianza'};
  const w=state.engine.opportunityWeights;$('#engineExplanation').innerHTML=`<p><b>Motor v8 Market + Capability Intelligence.</b> Separa atractivo, riesgo, fiabilidad y estabilidad; añade momentum del fabricante, encaje operativo, ecosistema, canal y demanda; después puntúa <b>${state.decision.actions.length} acciones</b> para <b>${state.decision.roles.length} perfiles</b>. Antes de recomendar una palanca, valida su existencia y aplicabilidad al fabricante mediante la matriz de capacidades Westcon. Mercado externo y capacidades operativas se mantienen como capas distintas.</p><div class="weight-list">${Object.entries(w).map(([k,v])=>`<div><span>${esc(labels[k]||k)}</span><b>${Math.round(v*100)}%</b><i style="--w:${v*100}%"></i></div>`).join('')}</div><p class="tiny">Una capacidad Westcon pasa dos gates: compatibilidad real con el fabricante y score contextual. Las capacidades vendor-specific no verificadas quedan bloqueadas. Por eso FLEX, 3D Lab, stock, servicios, Intelligent Demand, Tech Xpert o lifecycle aparecen en vendors distintos y por motivos distintos.</p>`
}
function renderGaps(){const rows=[...state.vendors].sort((a,b)=>a.analysis.dataCompleteness-b.analysis.dataCompleteness||a.analysis.evidenceConfidence-b.analysis.evidenceConfidence).slice(0,12);$('#researchGaps').innerHTML=rows.map(v=>`<div class="gap-row" data-vendor="${esc(v.name)}"><div><b>${esc(v.name)}</b><span>completitud ${v.analysis.dataCompleteness}/100 · ${v.derived.integrators.length?'integradores '+v.derived.integrators.length:'integrador pendiente'} · ${v.derived.customers.length?'clientes '+v.derived.customers.length:'cliente pendiente'} · evidencia ${v.analysis.evidenceConfidence}</span></div><strong>Investigar →</strong></div>`).join('');$$('#researchGaps .gap-row').forEach(x=>x.onclick=()=>{switchView('fabricantes');selectVendor(x.dataset.vendor)})}
function renderSources(){const q=($('#sourceSearch')?.value||'').toLowerCase(),tier=$('#sourceTierFilter')?.value||'all',type=$('#sourceTypeFilter')?.value||'all',geo=$('#sourceGeoFilter')?.value||'all';const ecoEv=state.vendors.flatMap(v=>ecosystemEvidence(v,v.derived.integrators,v.derived.customers));const all=[...allEvidence(),...ecoEv];const map=new Map();all.forEach(e=>map.set(`${e.url||e.title}|${e.vendor||''}|${e.evidenceType||e.kind||''}`,e));const rows=[...map.values()].filter(e=>{const blob=[e.source,e.title,e.summary,e.snippet,e.scope,e.country,e.kind,e.vendor,e.evidenceType,...(e.tags||[])].join(' ').toLowerCase(),et=String(e.evidenceType||e.kind||'general').toLowerCase(),eg=String(e.country||e.scope||'').toUpperCase();const typeOk=type==='all'||et.includes(type.toLowerCase());const geoOk=geo==='all'||(geo==='EMEA'?/EMEA|EUROPE|EUROPA/.test(eg):eg.includes(geo));return(!q||blob.includes(q))&&(tier==='all'||e.sourceTier===tier)&&typeOk&&geoOk}).sort((a,b)=>String(b.date||b.published||'').localeCompare(String(a.date||a.published||'')));$('#sourceRows').innerHTML=rows.map(e=>`<tr><td>${fmtDate(e.date||e.published)}</td><td><span class="confidence-badge ${Number(e.confidence||state.engine.evidenceTiers[e.sourceTier]||45)>=80?'high':Number(e.confidence||45)>=60?'mid':'low'}">${clamp(e.confidence||state.engine.evidenceTiers[e.sourceTier]||45)}</span></td><td>${esc(e.scope||'—')}</td><td><b>${esc(e.source||e.sourceTier)}</b><span class="tiny">${esc(e.sourceTier||'')}</span></td><td>${esc(e.evidenceType||e.kind||'general')}</td><td>${esc(e.title)}${e.summary?`<span class="tiny">${esc(e.summary)}</span>`:''}</td><td>${e.url?`<a class="evidence-link" href="${e.url}" target="_blank" rel="noopener">Abrir ↗</a>`:''}</td></tr>`).join('')}
function renderResearch(){const r=state.research||{},st=state.status||{},ch=state.changes||{};$('#researchSummary').textContent=`Última generación: ${r.generatedAt||st.generatedAt||'baseline'}
Perfil: ${r.profile||st.profile||'baseline'}
Motor: ${r.mode||'baseline público'}
Consultas planificadas: ${r.queryCount||st.queryCount||0}
Evidencias acumuladas: ${r.evidence?.length||0}
Canal: ${r.channelSignals?.length||0}
Integradores: ${state.vendors.reduce((s,v)=>s+v.derived.integrators.length,0)}
Clientes públicos: ${state.vendors.reduce((s,v)=>s+v.derived.customers.length,0)}
Contratación pública: ${r.derived?.procurementSignalCount||0}
Buckets demanda pública: ${r.derived?.procurementMarketBuckets||r.procurementMarket?.length||0}
Analistas: ${r.analystSignals?.length||0}
Fuentes alta confianza: ${r.derived?.officialOrAnalystCount||0}
Cambios detectados: ${ch.changes?.length||r.changes?.length||0}
Conflictos a validar: ${ch.conflicts?.length||r.conflicts?.length||0}
Brave opcional: ${r.braveEnabled?'sí':'no'}

Autoactualización: diaria + profunda semanal + barrido exhaustivo mensual.
Fuentes: webs/sitemaps oficiales, Common Crawl (descubrimiento + revalidación), Google News RSS, GDELT, Arquivo.pt, TED, PLACSP, dados.gov.pt/BASE y analistas públicos.
Reglas: discovery ≠ evidencia ejecutiva · EMEA ≠ Iberia ≠ ES/PT · ausencia pública ≠ inexistencia.
Partner directory ≠ capacidad probada: adjudicaciones, premios y casos pesan más. Las acciones por perfil se recalculan con cada actualización.`}
function moduleOn(id){return state.reportModules.has(id)}
function roleSummaryRows(v){const roles=['country_manager','director_vsm_sa','director_psm','vsm','psm','sa','marketing','services','operations','finance','logistics'];return roles.map(id=>{const r=(state.decision.roles||[]).find(x=>x.id===id),a=v.derived.roleRecommendations?.[id]?.[0];return a?{role:r?.name||id,action:a.name,score:a.score,value:actionPlainLanguage(v,a)}:null}).filter(Boolean)}
function reportHtml(){
  const top=[...state.vendors].sort((a,b)=>b.analysis.decisionScore-a.analysis.decisionScore).slice(0,15),parts=[];
  parts.push(`<div class="report-export"><div style="border-top:8px solid #f09e0d;padding-top:18px"><div style="font-size:10px;color:#3195bb;font-weight:800">WESTCON IBERIA · FY27–FY30</div><h1>Radar Estratégico Tecnológico</h1><p class="note">Motor v8 · Decision Intelligence pública + portfolio FY27 facilitado. Recomendaciones por fabricante, función y evidencia.</p></div>`);
  if(moduleOn('executive'))parts.push(`<section class="report-module"><h2>Resumen ejecutivo</h2><p>El motor separa atractivo, riesgo y fiabilidad; clasifica cada vendor por arquetipo estratégico y selecciona acciones Westcon según el problema que realmente hay que resolver.</p>${top.slice(0,6).map(v=>`<h3>${esc(v.name)} · ${esc(v.derived.archetype?.name||v.analysis.recommendation)}</h3><p><b>${v.analysis.recommendation} · score ${v.analysis.decisionScore}</b> — ${esc(v.derived.plan.thesis)}</p>`).join('')}</section>`);
  if(moduleOn('portfolio'))parts.push(`<section class="report-module"><h2>Prioridades por fabricante</h2><table><thead><tr><th>Fabricante</th><th>Tesis</th><th>Decisión</th><th>Score</th><th>Oportunidad</th><th>Vendor</th><th>Ecosistema</th><th>Canal</th><th>Solape</th><th>Fiabilidad</th><th>Acción 90 días</th></tr></thead><tbody>${top.map(v=>`<tr><td>${esc(v.name)}</td><td>${esc(v.derived.archetype?.name||'')}</td><td>${v.analysis.recommendation}</td><td>${v.analysis.decisionScore}</td><td>${v.analysis.opportunity}</td><td>${v.analysis.vendorMomentum}</td><td>${v.analysis.ecosystemStrength}</td><td>${v.analysis.channelPressure}</td><td>${v.analysis.overlapRisk}</td><td>${v.analysis.reliability}</td><td>${esc(v.derived.plan.p90)}</td></tr>`).join('')}</tbody></table></section>`);
  if(moduleOn('roles'))parts.push(`<section class="report-module"><h2>Recomendaciones por perfil</h2>${top.slice(0,8).map(v=>`<h3>${esc(v.name)}</h3><div class="report-role-grid">${roleSummaryRows(v).slice(0,8).map(x=>`<div><b>${esc(x.role)} · ${x.score}</b><p>${esc(x.action)} — ${esc(x.value)}</p></div>`).join('')}</div>`).join('')}</section>`);
  if(moduleOn('channel'))parts.push(`<section class="report-module"><h2>Canal y competencia</h2><table><thead><tr><th>Fabricante</th><th>Competidores</th><th>Mayoristas alternativos ES/PT</th><th>Presión</th><th>Prueba competitiva</th></tr></thead><tbody>${top.map(v=>`<tr><td>${esc(v.name)}</td><td>${esc((v.marketCompetitors||[]).slice(0,5).join(', '))}</td><td>${esc(v.derived.channels.slice(0,5).map(x=>`${x.country}:${x.distributor}`).join(' · ')||'Por demostrar')}</td><td>${v.analysis.channelPressure}</td><td>${v.analysis.competitiveProof}</td></tr>`).join('')}</tbody></table></section>`);
  if(moduleOn('capabilities'))parts.push(`<section class="report-module"><h2>Capacidades Westcon verificadas</h2><table><thead><tr><th>Fabricante</th><th>Capacidades confirmadas / elegibles</th><th>Gaps</th></tr></thead><tbody>${top.map(v=>{const cc=vendorCapabilities(v);const verified=cc.filter(x=>x.verified).map(x=>x.programme?.name||x.id);const gaps=(state.capability?.programmes||[]).filter(p=>state.capability?.researchPolicy?.vendorSpecificRequiredFor?.includes(p.id)&&!capabilityStatus(v,p.id).eligible).map(p=>p.name);return `<tr><td>${esc(v.name)}</td><td>${esc(verified.join(' · ')||'—')}</td><td>${esc(gaps.slice(0,5).join(' · ')||'—')}</td></tr>`}).join('')}</tbody></table></section>`);
  if(moduleOn('analysts'))parts.push(`<section class="report-module"><h2>Consultoras y mercado</h2>${top.filter(v=>v.analystSignals?.length).slice(0,10).map(v=>`<h3>${esc(v.name)}</h3>${v.analystSignals.slice(0,2).map(a=>`<p><b>${esc(a.analyst)}</b> — ${esc(a.summary)}</p>`).join('')}`).join('')}</section>`);
  if(moduleOn('ecosystem'))parts.push(`<section class="report-module"><h2>Ecosistema Iberia</h2><table><thead><tr><th>Fabricante</th><th>Integradores</th><th>Clientes públicos</th><th>Ecosistema</th><th>White space</th></tr></thead><tbody>${top.map(v=>`<tr><td>${esc(v.name)}</td><td>${esc(v.derived.integrators.slice(0,4).map(x=>`${x.country}:${x.name}`).join(' · ')||'—')}</td><td>${esc(v.derived.customers.slice(0,4).map(x=>x.name).join(' · ')||'—')}</td><td>${v.analysis.ecosystemStrength}</td><td>${v.analysis.whiteSpace}</td></tr>`).join('')}</tbody></table></section>`);
  if(moduleOn('synergies'))parts.push(`<section class="report-module"><h2>Sinergias y overlap</h2>${(state.base.solutionPlays||[]).map(p=>`<h3>${esc(p.name)}</h3><p><b>${esc(p.vendors.join(' + '))}</b><br>${esc(p.value)}</p>`).join('')}</section>`);
  if(moduleOn('trends'))parts.push(`<section class="report-module"><h2>Tendencias 2026–2030</h2>${state.base.themes.slice().sort((a,b)=>b.momentum-a.momentum).slice(0,10).map(t=>`<h3>${esc(t.name)} · momentum ${t.momentum}</h3><p>${esc(t.why)}</p>`).join('')}</section>`);
  if(moduleOn('evidence'))parts.push(`<section class="report-module"><h2>Evidencias destacadas</h2>${allEvidence().slice().sort((a,b)=>Number(b.confidence||0)-Number(a.confidence||0)).slice(0,35).map(e=>`<p><b>${esc(e.source||e.sourceTier)} · ${clamp(e.confidence||50)}/100</b> — ${esc(e.title)} <span>${esc(e.scope||'')}</span></p>`).join('')}</section>`);
  if(moduleOn('methodology'))parts.push(`<section class="report-module"><h2>Metodología</h2><p>Decision Intelligence v8: mercado, competencia, ecosistema y capacidades Westcon verificadas. 47 acciones se puntúan contra el contexto de cada fabricante y, además, pasan una matriz obligatoria de compatibilidad fabricante × capacidad × ámbito × evidencia. Datos públicos externos + presentación FY27 facilitada; contenidos licenciados de analistas no se reconstruyen.</p></section>`);
  parts.push('</div>');return parts.join('')
}
async function exportPdf(){if(!window.html2pdf){toast('Librería PDF no disponible');return}const report=$('#report');report.innerHTML=reportHtml();report.style.display='block';await html2pdf().set({margin:8,filename:'Westcon_Iberia_Decision_Intelligence_v1.8.pdf',image:{type:'jpeg',quality:.96},html2canvas:{scale:1.4,useCORS:true},jsPDF:{unit:'mm',format:'a4',orientation:'landscape'},pagebreak:{mode:['css','legacy']}}).from(report.firstElementChild).save();report.style.display='none';toast('PDF generado')}
async function exportPptx(){
  if(!window.PptxGenJS){toast('Librería PowerPoint no disponible');return}const pptx=new PptxGenJS();pptx.layout='LAYOUT_WIDE';pptx.author='Westcon Iberia Strategy Studio';pptx.title='Westcon Iberia · Decision Intelligence v1.8';pptx.company='Westcon-Comstor';pptx.defineSlideMaster({title:'MASTER',background:{color:'FFFFFF'},objects:[{rect:{x:0,y:0,w:13.333,h:.18,fill:{color:'F09E0D'},line:{color:'F09E0D'}}},{text:{text:'WESTCON IBERIA · DECISION INTELLIGENCE',options:{x:.55,y:.25,w:6,h:.25,fontFace:'Corbel',fontSize:9,bold:true,color:'3195BB'}}},{text:{text:'Motor v8 · Inteligencia pública',options:{x:9.7,y:.25,w:3.0,h:.25,fontFace:'Corbel',fontSize:8,color:'687B8D',align:'right'}}}],slideNumber:{x:12.75,y:7.12,color:'687B8D',fontSize:8}});const addTitle=(s,t,sub='')=>{s.addText(t,{x:.55,y:.65,w:12.2,h:.55,fontFace:'Corbel',fontSize:27,bold:true,color:'082335',margin:0});if(sub)s.addText(sub,{x:.55,y:1.24,w:11.9,h:.4,fontFace:'Corbel',fontSize:11,color:'687B8D',margin:0})};const top=[...state.vendors].sort((a,b)=>b.analysis.decisionScore-a.analysis.decisionScore).slice(0,14);let s;
  if(moduleOn('executive')){s=pptx.addSlide('MASTER');addTitle(s,'Decidir rápido. Pensar como una consultora.','La interfaz es simple; el motor cruza mercado, vendor, canal, ecosistema, clientes, analistas, competencia, operaciones y fiabilidad.');const k=[[state.vendors.length,'fabricantes'],[allEvidence().length,'evidencias'],[state.decision.actions.length,'acciones modeladas'],[state.decision.roles.length,'perfiles Westcon']];k.forEach((x,i)=>{s.addShape(pptx.ShapeType.rect,{x:.55+i*3.05,y:2,w:2.8,h:1.15,fill:{color:i%2?'F7F9FA':'F2F7F8'},line:{color:'DBE4E9'}});s.addText(String(x[0]),{x:.75+i*3.05,y:2.2,w:2.3,h:.42,fontFace:'Corbel',fontSize:24,bold:true,color:'082335'});s.addText(x[1],{x:.75+i*3.05,y:2.68,w:2.3,h:.24,fontFace:'Corbel',fontSize:9,color:'687B8D'})});s.addText(top.slice(0,4).map(v=>`${v.name}: ${v.derived.archetype.name} · ${v.derived.plan.executiveActions?.[0]?.name||v.derived.plan.p90}`).join('\n'),{x:.65,y:3.65,w:11.7,h:2.3,fontFace:'Corbel',fontSize:15,bold:true,color:'113A50',breakLine:true,margin:0})}
  if(moduleOn('portfolio')){s=pptx.addSlide('MASTER');addTitle(s,'Prioridades por fabricante','Tesis dinámica, fiabilidad y acción recomendada.');const rows=[['Fabricante','Tesis','Decisión','Score','Oport.','Vendor','Eco.','Canal','Solape','Fiab.','Acción'],...top.map(v=>[v.name,v.derived.archetype.name,v.analysis.recommendation,String(v.analysis.decisionScore),String(v.analysis.opportunity),String(v.analysis.vendorMomentum),String(v.analysis.ecosystemStrength),String(v.analysis.channelPressure),String(v.analysis.overlapRisk),String(v.analysis.reliability),v.derived.plan.executiveActions?.[0]?.name||v.derived.plan.p90])];s.addTable(rows,{x:.2,y:1.55,w:12.9,h:5.55,border:{type:'solid',color:'D9E2E7',pt:.6},fontFace:'Corbel',fontSize:6.4,color:'233746',fill:'FFFFFF',margin:.025,colW:[1.22,1.1,.72,.42,.42,.42,.42,.42,.42,.42,6.9]})}
  if(moduleOn('roles')){for(const v of top.slice(0,6)){s=pptx.addSlide('MASTER');addTitle(s,`${v.name} · acciones por perfil`,`${v.derived.archetype.name} · ${v.analysis.recommendation} · fiabilidad ${v.analysis.reliability}/100`);const rr=roleSummaryRows(v).slice(0,10);const rows=[['Perfil','Score','Acción','Por qué'],...rr.map(x=>[x.role,String(x.score),x.action,x.value])];s.addTable(rows,{x:.35,y:1.55,w:12.5,h:5.4,border:{type:'solid',color:'D9E2E7',pt:.6},fontFace:'Corbel',fontSize:7.4,color:'233746',fill:'FFFFFF',margin:.035,colW:[2.0,.55,3.0,6.95]})}}
  if(moduleOn('channel')){s=pptx.addSlide('MASTER');addTitle(s,'Canal y competencia','Dónde existe presión y dónde podemos diferenciarnos.');const rows=[['Fabricante','Competidores','Mayoristas alternativos','Canal','Prueba comp.','Ataque'],...top.slice(0,12).map(v=>[v.name,(v.marketCompetitors||[]).slice(0,4).join(', '),v.derived.channels.slice(0,4).map(x=>`${x.country}:${x.distributor}`).join(' · ')||'Por demostrar',String(v.analysis.channelPressure),String(v.analysis.competitiveProof),String(v.analysis.attackScore)])];s.addTable(rows,{x:.3,y:1.55,w:12.7,h:5.45,border:{type:'solid',color:'D9E2E7',pt:.6},fontFace:'Corbel',fontSize:7,color:'233746',fill:'FFFFFF',margin:.03,colW:[1.4,3.0,4.5,.65,.65,.65]})}
  if(moduleOn('ecosystem')){s=pptx.addSlide('MASTER');addTitle(s,'Ecosistema Iberia','Integradores y clientes como señal de capacidad real.');const rows=[['Fabricante','Ecosistema','Integradores','Clientes públicos','White space'],...top.slice(0,12).map(v=>[v.name,String(v.analysis.ecosystemStrength),v.derived.integrators.slice(0,3).map(x=>`${x.country}:${x.name}`).join(' · '),v.derived.customers.slice(0,3).map(x=>x.name).join(' · '),String(v.analysis.whiteSpace)])];s.addTable(rows,{x:.3,y:1.55,w:12.7,h:5.45,border:{type:'solid',color:'D9E2E7',pt:.6},fontFace:'Corbel',fontSize:7,color:'233746',fill:'FFFFFF',margin:.03,colW:[1.5,.7,4.0,5.5,.7]})}
  if(moduleOn('capabilities')){s=pptx.addSlide('MASTER');addTitle(s,'Capacidades Westcon por fabricante','Solo aparecen como confirmadas las capacidades con evidencia suficiente; los programas generales siguen sujetos a fit.');const rows=[['Fabricante','Confirmadas','Contextuales / programa','Gaps vendor-specific'],...top.slice(0,14).map(v=>{const cc=vendorCapabilities(v),ver=cc.filter(x=>x.verified).map(x=>x.programme?.name||x.id).slice(0,6).join(' · '),ctx=cc.filter(x=>!x.verified).map(x=>x.programme?.name||x.id).slice(0,4).join(' · '),g=(state.capability?.programmes||[]).filter(p=>state.capability?.researchPolicy?.vendorSpecificRequiredFor?.includes(p.id)&&!capabilityStatus(v,p.id).eligible).map(p=>p.name).slice(0,4).join(' · ');return [v.name,ver||'—',ctx||'—',g||'—']})];s.addTable(rows,{x:.25,y:1.55,w:12.8,h:5.5,border:{type:'solid',color:'D9E2E7',pt:.6},fontFace:'Corbel',fontSize:6.6,color:'233746',fill:'FFFFFF',margin:.03,colW:[1.5,4.2,3.3,3.8]})}
  if(moduleOn('analysts')){s=pptx.addSlide('MASTER');addTitle(s,'Consultoras y señales de mercado','Se usan resúmenes públicos; no se reconstruyen contenidos licenciados.');let y=1.55;for(const v of top.filter(v=>v.analystSignals?.length).slice(0,7)){s.addText(v.name,{x:.55,y,w:2,h:.3,fontFace:'Corbel',fontSize:12,bold:true,color:'082335',margin:0});s.addText(v.analystSignals[0].summary,{x:2.45,y,w:10.2,h:.55,fontFace:'Corbel',fontSize:9,color:'445D6C',margin:0});y+=.72}}
  if(moduleOn('synergies')){s=pptx.addSlide('MASTER');addTitle(s,'Sinergias que debemos monetizar','El portfolio como arquitecturas y ecosistemas, no como catálogo.');(state.base.solutionPlays||[]).slice(0,6).forEach((p,i)=>{const col=i%3,row=Math.floor(i/3),x=.55+col*4.12,y=1.75+row*2.42;s.addShape(pptx.ShapeType.rect,{x,y,w:3.78,h:2.05,fill:{color:'082335'},line:{color:'082335'}});s.addText(p.name,{x:x+.18,y:y+.25,w:3.35,h:.42,fontFace:'Corbel',fontSize:16,bold:true,color:'FFFFFF',margin:0});s.addText(p.vendors.join(' + '),{x:x+.18,y:y+.82,w:3.35,h:.4,fontFace:'Corbel',fontSize:7.5,color:'12C7C0',margin:0});s.addText(p.value,{x:x+.18,y:y+1.25,w:3.35,h:.55,fontFace:'Corbel',fontSize:8,color:'CDD6E0',margin:0})})}
  if(moduleOn('trends')){s=pptx.addSlide('MASTER');addTitle(s,'Tendencias 2026–2030','Señales que deben mover la cartera.');const rows=[['Tendencia','Momentum','Fit','Recurrencia','Diferenciación','Por qué'],...state.base.themes.slice().sort((a,b)=>b.momentum-a.momentum).slice(0,10).map(t=>[t.name,String(t.momentum),String(t.portfolioFit),String(t.recurringPotential),String(t.differentiation),t.why])];s.addTable(rows,{x:.3,y:1.55,w:12.7,h:5.45,border:{type:'solid',color:'D9E2E7',pt:.6},fontFace:'Corbel',fontSize:7,color:'233746',fill:'FFFFFF',margin:.03,colW:[2.0,.65,.65,.75,.8,7.85]})}
  if(moduleOn('methodology')){s=pptx.addSlide('MASTER');addTitle(s,'Metodología','Simplicidad visible; lógica interna brutal y trazable.');s.addText('14 dimensiones estratégicas\n+ riesgo y estabilidad\n+ matriz fabricante × capacidad\n+ 47 acciones Westcon\n+ 11 perfiles\n+ evidencia pública trazable\n+ actualización diaria / semanal / mensual',{x:.65,y:1.8,w:4.0,h:3.3,fontFace:'Corbel',fontSize:20,bold:true,color:'082335',margin:0,breakLine:true});s.addText('Cada acción se puntúa por fabricante y primero supera un gate de compatibilidad real. El motor evita recomendaciones genéricas: financiación solo cuando existe encaje económico; 3D Lab cuando una prueba técnica aporta ventaja; stock y staging en hardware/despliegues; Intelligent Demand en whitespace; lifecycle en recurrencia/base instalada; enablement cuando el gap real es capacidad del partner.',{x:5.0,y:1.8,w:7.3,h:3.3,fontFace:'Corbel',fontSize:14,color:'445D6C',margin:0})}
  await pptx.writeFile({fileName:'Westcon_Iberia_Decision_Intelligence_v1.8.pptx'});toast('PowerPoint generado')
}
load().catch(e=>{console.error(e);document.body.innerHTML=`<div style="padding:40px;font-family:Arial">No se pudo cargar la aplicación: ${esc(e.message)}</div>`});
