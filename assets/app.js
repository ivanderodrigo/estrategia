const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
const state={data:null,base:null,research:null,engine:null,ecosystem:null,status:null,changes:null,vendors:[],selected:null,quick:'all',deep:false};

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
  const [data,base,research,engine,ecosystem,status,changes]=await Promise.all([
    fetch('data/vendor_intelligence.json').then(r=>r.json()),
    fetch('data/base.json').then(r=>r.json()),
    fetch('data/research.latest.json').then(r=>r.ok?r.json():{}).catch(()=>({})),
    fetch('config/strategy_engine.json').then(r=>r.json()),
    fetch('data/ecosystem.json').then(r=>r.json()),
    fetch('data/research_status.json').then(r=>r.ok?r.json():{}).catch(()=>({})),
    fetch('data/changes.latest.json').then(r=>r.ok?r.json():{}).catch(()=>({}))
  ]);
  state.data=data;state.base=base;state.research=research;state.engine=engine;state.ecosystem=ecosystem;state.status=status;state.changes=changes;
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
function initiativeSet(a){
  const out=[];const add=(name,why)=>{if(!out.some(x=>x.name===name))out.push({name,why})};
  if(a.channelPressure>=55){add('3D Labs','diferenciar por prueba y time-to-value');add('Tech Xpert','ganar preferencia técnica del partner');add('Servicios Westcon','salir de la comparación puramente transaccional');add('Lifecycle / ServiceView','anclar renovación, adopción y expansión')}
  if(a.customerProof<50||a.whiteSpace>=62){add('Tech Assessments','convertir gaps en oportunidad medible');add('Intelligent Demand','crear demanda en whitespace y verticales')}
  if(a.partnerConcentration>=60){add('BLUEPRINT','activar y especializar un segundo ecosistema de partners');add('Tech Xpert','ampliar capacidad técnica del canal')}
  if(a.overlapRisk>=55||a.synergyPotential>=72){add('BLUEPRINT','gobernar solapes y empaquetar plays multivendor');add('3D Labs','demostrar la arquitectura conjunta')}
  if(a.recurringPotential>=82){add('FLEX','convertir CAPEX en propuesta OPEX multivendor');add('Cloud Marketplaces','acelerar recurrencia y private offers');add('Lifecycle / ServiceView','maximizar expansión y renovación')}
  if(a.countryImbalance>=55){add('GSCS','apoyar proyectos multinacionales y cobertura cross-border');add('BLUEPRINT','replicar el modelo en el país menos cubierto')}
  if(a.competitorCustomerPressure>=45){add('Tech Assessments','abrir displacement con evidencia, no con producto');add('3D Labs','reducir riesgo de migración con prueba guiada')}
  return out.slice(0,7);
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
function actionPlan(v,a,ctx){
  const {ints,customers,sharedInts,sharedCust}=ctx,topI=ints[0],topC=customers[0],strongest=(v.synergies||[]).sort((x,y)=>(y.with?.length||0)-(x.with?.length||0))[0];
  const attackRows=(state.research?.competitiveAttackMatrix||[]).filter(x=>norm(x.vendor)===norm(v.name)).sort((x,y)=>(y.proofStrength+y.whiteSpace)-(x.proofStrength+x.whiteSpace));
  const primaryAttack=attackRows[0],primaryCompetitor=primaryAttack?.competitor||(v.marketCompetitors||[])[0]||'competidores directos',initiatives=initiativeSet(a),gaps=competitiveGapHypotheses(a),topGap=gaps[0];
  const inames=initiatives.slice(0,3).map(x=>x.name).join(' + '),crossVendors=Object.keys(sharedInts).slice(0,3),crossCustomers=Object.entries(sharedCust).slice(0,2);
  let p30,p90,p180;
  if(a.evidenceConfidence<50)p30='Cerrar primero los gaps de evidencia pública que condicionan la decisión: canal ES/PT, integradores, clientes, analistas y cambios recientes.';
  else if(a.competitorCustomerPressure>=45)p30=`Seleccionar las cuentas públicas donde aparecen ${primaryCompetitor} u otros rivales y abrir hipótesis de displacement/cross-sell con Tech Assessment + battlecard + criterios de éxito.`;
  else if(primaryAttack&&primaryAttack.proofStrength>=45)p30=`Ataque frente a ${primaryCompetitor}: validar ${primaryAttack.sharedIntegrators||0} integradores y ${primaryAttack.sharedCustomers||0} clientes compartidos, convertir ${primaryAttack.recommendedInitiatives?.slice(0,3).join(' + ')||inames||'3D Labs + Servicios + FLEX'} en criterios de decisión y documentar un displacement medible.`;
  else if(a.channelPressure>=55)p30=`Battlecard de canal: demostrar por qué comprar ${v.name} vía Westcon aporta más que una transacción. Convertir ${inames||'3D Labs + Servicios + Lifecycle'} en criterios de selección.`;
  else if(a.partnerConcentration>=70&&topI)p30=`Usar ${topI.name} como referencia y activar un segundo integrador; BLUEPRINT + Tech Xpert + Intelligent Demand para reducir concentración.`;
  else if(topGap)p30=`Atacar el gap “${topGap.label}” con ${inames||'BLUEPRINT + 3D Labs + Servicios Westcon'}.`;
  else p30=`Actualizar mapa de ${primaryCompetitor}, canal, integradores y cuentas; elegir dos casos de uso donde ${v.name} tenga ventaja demostrable.`;

  if(topC&&strongest)p90=`Replicar ${topC.name} (${topC.sector}) como patrón de venta con “${strongest.play}”, integrando ${strongest.with.slice(0,2).join(' + ')} y ${inames||'servicios Westcon'}.`;
  else if(topI&&crossVendors.length)p90=`Con ${topI.name}, industrializar un play ${v.name} + ${crossVendors.join(' + ')}: arquitectura, 3D Lab, assessment, battlecard y campaña Intelligent Demand.`;
  else if(strongest)p90=`Industrializar “${strongest.play}”: arquitectura, demo, criterios de éxito, objection handling frente a ${primaryCompetitor} y attach de servicios/FLEX/lifecycle.`;
  else p90=`Crear un play repetible de ${v.capabilities.slice(0,2).join(' + ')} y validarlo contra ${primaryCompetitor} con demo, servicios y modelo recurrente.`;

  if(a.countryImbalance>=55)p180='Replicar el play en el país Iberia menos cubierto: integrador especializado, primera referencia, evento técnico, GSCS y generación de demanda.';
  else if(crossCustomers.length)p180=`Priorizar cuentas públicas multivendor (${uniq(crossCustomers.flatMap(x=>x[1])).slice(0,2).join(', ')}) para expansión; usar lifecycle y servicios como mecanismo de entrada.`;
  else if(a.channelPressure>=55)p180='Medir desplazamiento frente al canal alternativo: win-rate público/market-led, referencias, partners activados, servicios attach, recurrencia y renovaciones.';
  else p180='Escalar por verticales con playbooks repetibles, partners diversificados, referencias públicas y revisión mensual de nuevas señales competitivas.';
  return {p30,p90,p180,initiatives,gaps,competitiveAttack:primaryAttack||null};
}
function enrichVendor(v){
  const themes=themeMatches(v),channels=channelSignals(v),ints=integratorSignals(v),customers=customerSignals(v),eco=ecosystemMetrics(v,ints,customers,channels);
  const sharedInts=sharedIntegratorAdjacency(v,ints),sharedCust=sharedCustomerAdjacency(v,customers);
  const explicit=[...(v.analystSignals||[]).map(a=>({title:a.title,url:a.url,source:a.analyst,sourceTier:'analyst-public',date:a.date,scope:'Public analyst summary',confidence:91,summary:a.summary,vendor:v.name,evidenceType:'analyst'})),...(v.channelCompetitors||[]).filter(c=>c.url).map(c=>({title:c.evidence||`${c.name} · ${c.country}`,url:c.url,source:c.name,sourceTier:'official-company',date:'2026',scope:c.country,confidence:86,summary:c.evidence,vendor:v.name,evidenceType:'channel'})),...ecosystemEvidence(v,ints,customers)];
  const evMap=new Map();[...relevantEvidence(v),...explicit].forEach(e=>evMap.set(e.url||`${e.title}|${e.source}`,e));const ev=[...evMap.values()];
  const market=clamp(themes.length?avg(themes,x=>x.momentum):domainDefault(v,'marketMomentum'));
  const fit=clamp(themes.length?avg(themes,x=>x.portfolioFit)+(v.countries?.length>1?3:0):68+(v.countries?.length>1?5:0));
  const recurring=clamp(themes.length?avg(themes,x=>x.recurringPotential):domainDefault(v,'recurringPotential'));
  const diff=clamp(themes.length?avg(themes,x=>x.differentiation):68),baseSyn=baseSynergyScore(v);
  const ecosystemAdj=Math.min(18,Object.keys(sharedInts).length*3+Object.keys(sharedCust).length*4),synergy=clamp(baseSyn+ecosystemAdj);
  const overlap=overlapScore(v),channel=channelPressure(v,channels),competitive=competitiveIntensity(v),econf=evidenceConfidence(v,ev),analyst=analystScore(v,ev),services=domainDefault(v,'servicesLeverage');
  const compInts=competitorIntegratorPressure(v,ints),compCust=competitorCustomerPressure(v,customers);
  const partnerCap=clamp(eco.integratorStrength*.78+Math.min(22,Object.keys(sharedInts).length*4)),countryCov=eco.countryCoverage;
  const w=state.engine.opportunityWeights;
  const rawOpportunity=clamp(market*w.marketMomentum+fit*w.portfolioFit+recurring*w.recurringPotential+diff*w.differentiation+synergy*w.synergyPotential+analyst*w.analystSignal+services*w.servicesLeverage+eco.strength*w.ecosystemStrength+eco.customerProof*w.customerProof+partnerCap*w.partnerCapability+countryCov*w.countryCoverage+econf*w.evidenceConfidence);
  const completeness=clamp((channels.length?14:0)+(ints.length?18:0)+(customers.length?18:0)+(analyst>=45?14:0)+(ev.length>=4?14:ev.length*3)+(themes.length?12:0)+(v.marketCompetitors?.length?10:0));
  const um=state.engine.uncertaintyModel||{},reliability=clamp(econf*(um.evidenceWeight||.58)+completeness*(um.completenessWeight||.42)),prior=Number(um.neutralPrior||55),shrink=Math.max(Number(um.minimumReliability||.35),reliability/100);
  const opportunity=clamp(prior+(rawOpportunity-prior)*shrink);
  const pConc=partnerConcentration(ints),cConc=clientConcentration(customers),freshRisk=clamp(100-avg(ev.slice(0,20),e=>freshnessScore(e.date||e.published||e.collectedAt))),cImb=countryImbalance(v,eco),weakEco=100-eco.strength,rw=state.engine.riskWeights;
  const risk=clamp(overlap*rw.overlapRisk+channel*rw.channelPressure+competitive*(rw.competitiveIntensity||0)+pConc*rw.partnerConcentration+cConc*rw.clientConcentration+(100-econf)*rw.evidenceGap+freshRisk*rw.freshnessRisk+cImb*rw.countryImbalance+weakEco*rw.weakLocalEcosystem);
  const whiteSpace=clamp(opportunity-eco.strength+45),aw=state.engine.attackOpportunityWeights||{};
  const attackRaw=clamp(opportunity*(aw.marketOpportunity||.18)+channel*(aw.channelPressure||.13)+competitive*(aw.competitiveIntensity||.10)+whiteSpace*(aw.whiteSpace||.11)+synergy*(aw.synergyPotential||.11)+services*(aw.servicesLeverage||.08)+partnerCap*(aw.integratorLeverage||.08)+eco.customerProof*(aw.customerProof||.06)+Math.max(overlap,55)*(aw.overlapExploitability||.05)+analyst*(aw.analystSignal||.05)+econf*(aw.evidenceConfidence||.05)+compInts.score*.05+compCust.score*.05);
  const attackScore=clamp((attackRaw*.72)+(reliability*.18)+(100-risk)*.10);
  const decisionScore=clamp(opportunity*.55+attackScore*.18+(100-risk)*.12+eco.strength*.07+econf*.05+recurring*.03);
  const analysis={marketMomentum:market,portfolioFit:fit,recurringPotential:recurring,differentiation:diff,synergyPotential:synergy,overlapRisk:overlap,channelPressure:channel,competitiveIntensity:competitive,competitorIntegratorPressure:compInts.score,competitorCustomerPressure:compCust.score,evidenceConfidence:econf,analystSignal:analyst,servicesLeverage:services,ecosystemStrength:eco.strength,integratorStrength:eco.integratorStrength,customerProof:eco.customerProof,partnerCapability:partnerCap,countryCoverage:countryCov,partnerConcentration:pConc,clientConcentration:cConc,freshnessRisk:freshRisk,countryImbalance:cImb,weakLocalEcosystem:weakEco,dataCompleteness:completeness,reliability,rawOpportunity,whiteSpace,opportunity,risk,attackScore,decisionScore};
  analysis.recommendation=recommendationFor(analysis);
  const plan=actionPlan(v,analysis,{ints,customers,sharedInts,sharedCust});
  const drivers=[['Mercado',market],['Ecosistema',eco.strength],['Sinergia',synergy],['Clientes',eco.customerProof],['Analistas',analyst],['Recurrencia',recurring]].sort((a,b)=>b[1]-a[1]).slice(0,4);
  const brakes=[['Solape',overlap],['Canal',channel],['Concentración partner',pConc],['Gap evidencia',100-econf],['Desbalance país',cImb]].sort((a,b)=>b[1]-a[1]).slice(0,3);
  return {...v,analysis,derived:{themes,channels,integrators:ints,customers,evidence:ev,plan,drivers,brakes,sharedIntegrators:sharedInts,sharedCustomers:sharedCust,competitorIntegratorRows:compInts.rows,competitorCustomerRows:compCust.rows}};
}

function initNav(){
  $$('#tabs button').forEach(b=>b.onclick=()=>switchView(b.dataset.view));$$('[data-jump]').forEach(b=>b.onclick=()=>switchView(b.dataset.jump));
  ['vendorSearch','domainFilter','recommendationFilter','countryFilter'].forEach(id=>$('#'+id)?.addEventListener(id==='vendorSearch'?'input':'change',renderVendorTable));
  $$('#smartFilters button').forEach(b=>b.onclick=()=>{state.quick=b.dataset.quick;$$('#smartFilters button').forEach(x=>x.classList.toggle('active',x===b));renderVendorTable()});
  $('#sourceSearch')?.addEventListener('input',renderSources);['sourceTierFilter','sourceTypeFilter','sourceGeoFilter'].forEach(id=>$('#'+id)?.addEventListener('change',renderSources));
  $('#btnDepth').onclick=()=>{state.deep=!state.deep;document.body.classList.toggle('deep-mode',state.deep);$('#btnDepth').textContent=state.deep?'Vista ejecutiva':'Ver datos';if(state.selected)selectVendor(state.selected)};
  $('#btnPdf').onclick=exportPdf;$('#btnPptx').onclick=exportPptx;
}
function switchView(id){$$('.view').forEach(v=>v.classList.toggle('active',v.id===id));$$('#tabs button').forEach(b=>b.classList.toggle('active',b.dataset.view===id));window.scrollTo({top:0,behavior:'smooth'})}
function renderAll(){renderKpis();renderDecisionCards();renderChanges();renderDataHealth();renderFilters();renderOverviewVendors();renderVendorTable();renderPlays();renderOverlaps();renderTrends();renderSignals();renderDataKpis();renderEngine();renderGaps();renderSources();renderResearch()}
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
function renderChanges(){const auto=(state.changes?.changes||[]).map(x=>({date:x.detectedAt,title:`${x.vendor||''} · ${x.title}${x.entity?` · ${x.entity}`:''}`,impact:x.type==='coverage'?`Cobertura ${x.from} → ${x.to}`:`Nueva señal pública ${x.country||''} · confianza ${x.confidence||'—'}`,url:x.url}));const rows=[...auto,...state.data.externalChanges].sort((a,b)=>String(b.date||'').localeCompare(String(a.date||''))).slice(0,8);$('#externalChanges').innerHTML=rows.map(x=>`<div class="time-item"><time>${fmtDate(x.date)}</time><div><b>${esc(x.title)}</b><p>${esc(x.impact||'Cambio detectado por el motor de investigación.')}</p>${x.url?`<a class="evidence-link" href="${x.url}" target="_blank" rel="noopener">Fuente pública ↗</a>`:''}</div></div>`).join('')}
function renderDataHealth(){
  const items=[['Canal ES/PT',state.vendors.filter(v=>v.derived.channels.length).length,state.vendors.length,'Mayoristas alternativos identificados'],['Integradores',state.vendors.filter(v=>v.derived.integrators.length).length,state.vendors.length,'Partners/integradores con prueba pública'],['Clientes públicos',state.vendors.filter(v=>v.derived.customers.length).length,state.vendors.length,'Referencias finales ES/PT'],['Consultoras',state.vendors.filter(v=>v.analysis.analystSignal>=50).length,state.vendors.length,'Señal pública específica o de mercado'],['Evidencia fuerte',state.vendors.filter(v=>v.analysis.evidenceConfidence>=65).length,state.vendors.length,'Cobertura suficiente para lectura ejecutiva']];
  $('#dataHealth').innerHTML=items.map(x=>{const p=Math.round(x[1]/x[2]*100);return `<div class="health-row"><div><b>${x[0]}</b><span>${x[1]}/${x[2]} · ${x[3]}</span></div><strong>${p}%</strong><div class="healthbar"><i style="--w:${p}%"></i></div></div>`}).join('')
}
function renderFilters(){const domains=uniq(state.vendors.map(v=>v.domain)).sort();$('#domainFilter').innerHTML='<option value="all">Todas las áreas</option>'+domains.map(d=>`<option>${esc(d)}</option>`).join('');const rec=['ACELERAR','CONSTRUIR','DEFENDER','OPTIMIZAR','INVESTIGAR'];$('#recommendationFilter').innerHTML='<option value="all">Todas las decisiones</option>'+rec.map(x=>`<option>${x}</option>`).join('')}
function filteredVendors(){
  const q=$('#vendorSearch').value.trim().toLowerCase(),d=$('#domainFilter').value,r=$('#recommendationFilter').value,c=$('#countryFilter').value;
  return state.vendors.filter(v=>{
    const blob=[v.name,v.domain,...v.capabilities,...v.marketCompetitors,...v.derived.channels.map(x=>x.distributor),...v.derived.integrators.map(x=>x.name),...v.derived.customers.flatMap(x=>[x.name,x.sector,x.solution]),...(v.internalOverlaps||[]).map(x=>x.vendor),...(v.synergies||[]).flatMap(x=>x.with||[])].join(' ').toLowerCase();
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
  const ev=v.derived.evidence.slice(0,state.deep?24:6).map(e=>`<div class="source-mini"><b>${esc(e.source||e.sourceTier)} · ${fmtDate(e.date||e.published)}</b><span>${esc(e.title)}</span><a href="${e.url}" target="_blank" rel="noopener">Abrir ↗</a></div>`).join('')||'<p>La evidencia específica todavía es limitada.</p>';
  const drivers=v.derived.drivers.map(x=>`<span class="driver good"><b>${x[1]}</b>${x[0]}</span>`).join(''),brakes=v.derived.brakes.map(x=>`<span class="driver bad"><b>${x[1]}</b>${x[0]}</span>`).join('');
  $('#vendorDetail').innerHTML=`<div class="detail-top"><div class="domain">${esc(v.domain)} · ${v.countries.join(' / ')}</div><h2>${esc(v.name)}</h2><div class="decision-line"><span class="priority ${a.recommendation}">${a.recommendation}</span><b>${a.decisionScore}<small>/100 decisión</small></b></div><div style="margin-top:8px">${tags(v.capabilities)}</div></div>
  <div class="metric-grid ecosystem-metrics">${metricCard('Oportunidad',a.opportunity,'atractivo estratégico','good')}${metricCard('Ecosistema',a.ecosystemStrength,'integradores + clientes','good')}${metricCard('Referencias',a.customerProof,'prueba cliente ES/PT','info')}${metricCard('Canal',a.channelPressure,'presión mayorista','warn')}${metricCard('Solape',a.overlapRisk,'canibalización potencial','bad')}${metricCard('Confianza',a.evidenceConfidence,'calidad de evidencia','info')}</div>
  <div class="action-box"><b>RECOMENDACIÓN</b><p>${esc(v.derived.plan.p90)}</p></div>
  <div class="drivers"><div><h4>IMPULSA</h4>${drivers}</div><div><h4>FRENA</h4>${brakes}</div></div>
  <div class="detail-block"><h4>COMPETIDORES DE MERCADO</h4>${tags(v.marketCompetitors,'',7)}</div>
  <div class="detail-block"><h4>MAYORISTAS ALTERNATIVOS · ES/PT</h4>${chan}</div>
  <div class="detail-block"><h4>INTEGRADORES / PARTNERS IBERIA</h4>${ints}</div>
  <div class="detail-block"><h4>CLIENTES FINALES PÚBLICOS · ES/PT</h4>${customers}</div>
  <div class="detail-block"><h4>OPORTUNIDADES DE ECOSISTEMA</h4><div class="ecosystem-adj"><div><b>Integradores compartidos con otros vendors</b>${adjacencyHtml(v.derived.sharedIntegrators,'partner')}</div><div><b>Clientes con señales de otros vendors</b>${adjacencyHtml(v.derived.sharedCustomers,'cuenta')}</div></div></div>
  <div class="detail-block"><h4>CONSULTORAS / DIFERENCIAL</h4>${ana}<p class="analyst-diff">${esc(v.analystDifferential)}</p></div>
  <div class="detail-block"><h4>SINERGIAS</h4>${syn}</div><div class="detail-block"><h4>OVERLAP</h4>${ov}</div>
  <div class="detail-block"><h4>CÓMO ATACAR LA COMPETENCIA</h4><p><b>Potencial de ataque ${a.attackScore}/100.</b> ${esc(v.derived.plan.gaps?.[0]?.label||'Buscar gaps demostrables de canal, ecosistema, prueba, servicios y recurrencia.')}</p><div>${(v.derived.plan.initiatives||[]).map(x=>`<span class="tag synergy">${esc(x.name)}</span>`).join('')}</div></div>
  <div class="plan-block"><h4>PLAN PROPUESTO</h4><div><b>30 días</b><p>${esc(v.derived.plan.p30)}</p></div><div><b>90 días</b><p>${esc(v.derived.plan.p90)}</p></div><div><b>6 meses</b><p>${esc(v.derived.plan.p180)}</p></div></div>
  <div class="deep-only detail-block"><h4>DESGLOSE DEL MOTOR V3</h4><div class="engine-metrics">${Object.entries({Mercado:a.marketMomentum,Encaje:a.portfolioFit,Recurrencia:a.recurringPotential,Diferenciación:a.differentiation,Sinergia:a.synergyPotential,Analistas:a.analystSignal,Servicios:a.servicesLeverage,Ecosistema:a.ecosystemStrength,Integradores:a.integratorStrength,Clientes:a.customerProof,Cobertura:a.countryCoverage,Canal:a.channelPressure,Solape:a.overlapRisk,Competencia:a.competitiveIntensity,Concentración:a.partnerConcentration,Evidencia:a.evidenceConfidence,Fiabilidad:a.reliability,Completitud:a.dataCompleteness,WhiteSpace:a.whiteSpace,Ataque:a.attackScore,"Integradores rival":a.competitorIntegratorPressure,"Clientes rival":a.competitorCustomerPressure}).map(([k,val])=>metricPill(k,val)).join('')}</div></div>
  <div class="deep-only detail-block"><h4>EVIDENCIAS RELACIONADAS · ${v.derived.evidence.length}</h4>${ev}</div>`;
  if(window.innerWidth<1200)$('#vendorDetail').scrollIntoView({behavior:'smooth',block:'start'})
}
function renderPlays(){$('#playCards').innerHTML=(state.base.solutionPlays||[]).map((p,i)=>{const vs=state.vendors.filter(v=>p.vendors.includes(v.name));const op=clamp(avg(vs,x=>x.analysis.opportunity)),sy=clamp(avg(vs,x=>x.analysis.synergyPotential)),ov=clamp(avg(vs,x=>x.analysis.overlapRisk)),eco=clamp(avg(vs,x=>x.analysis.ecosystemStrength));return `<article class="play-card"><div class="num">0${i+1}</div><div class="play-score">${op}<small>oportunidad</small></div><h3>${esc(p.name)}</h3><p>${esc(p.value)}</p><div class="vendor-tags">${p.vendors.map(v=>`<span>${esc(v)}</span>`).join('')}</div><div class="play-bottom"><span>Sinergia <b>${sy}</b></span><span>Ecosistema <b>${eco}</b></span><span>Overlap <b>${ov}</b></span><strong>→ Oferta repetible + integradores + referencias + demo + campaña</strong></div></article>`}).join('')}
function renderOverlaps(){const map={};state.vendors.forEach(v=>(v.internalOverlaps||[]).forEach(o=>{const x=map[o.area]??={vendors:new Set(),score:0};x.vendors.add(v.name);x.vendors.add(o.vendor);x.score=Math.max(x.score,v.analysis.overlapRisk)}));$('#overlapMap').innerHTML=Object.entries(map).sort((a,b)=>b[1].score-a[1].score).map(([area,x])=>`<article class="overlap-card"><div class="overlap-score">${x.score}</div><h3>${esc(area)}</h3><div class="overlap-line">${[...x.vendors].map(v=>`<span class="tag overlap">${esc(v)}</span>`).join('')}</div><p><b>Acción:</b> segmentar por caso de uso, integrador, vertical y criterio de decisión; activar sinergias donde el mismo partner pueda vender varios vendors.</p></article>`).join('')}
function renderTrends(){$('#trendCards').innerHTML=state.base.themes.slice().sort((a,b)=>b.momentum-a.momentum).map(t=>{const score=clamp(t.momentum*.32+t.portfolioFit*.25+t.recurringPotential*.18+t.differentiation*.15+t.confidence*.10);return `<article class="trend-card"><div class="trend-score">${score}<span class="tiny">/100 · inferencia</span></div><div class="meter"><i style="--w:${score}%"></i></div><h3>${esc(t.name)}</h3><p>${esc(t.why)}</p><div class="trend-factors"><span>M ${t.momentum}</span><span>Fit ${t.portfolioFit}</span><span>Rec ${t.recurringPotential}</span><span>Dif ${t.differentiation}</span></div></article>`}).join('')}
function renderSignals(){$('#signalCards').innerHTML=state.data.marketSignals.slice().sort((a,b)=>String(b.date).localeCompare(String(a.date))).map(s=>`<article class="signal-card"><span>${esc(s.analyst)} · ${fmtDate(s.date)}</span><strong>${esc(s.metric)}</strong><h3>${esc(s.label)}</h3><p>${esc(s.detail)}</p><a class="evidence-link" href="${s.url}" target="_blank" rel="noopener">Fuente ↗</a></article>`).join('')}
function renderDataKpis(){const ev=allEvidence(),tiers={};ev.forEach(e=>tiers[e.sourceTier]=(tiers[e.sourceTier]||0)+1);const gaps=state.vendors.filter(v=>v.analysis.dataCompleteness<50).length,ints=state.vendors.reduce((s,v)=>s+v.derived.integrators.length,0),cust=state.vendors.reduce((s,v)=>s+v.derived.customers.length,0),total=ev.length+ints+cust;const k=[[total,'Evidencias','mercado + canal + ecosistema'],[tiers['analyst-public']||0,'Consultoras','contenido público'],[ints,'Integradores','relaciones ES/PT'],[cust,'Clientes','referencias públicas'],[gaps,'Gaps','completitud <50']];$('#dataKpis').innerHTML=k.map(x=>`<div class="kpi"><span>${x[1]}</span><strong>${x[0]}</strong><small>${x[2]}</small></div>`).join('')}
function renderEngine(){
  const labels={marketMomentum:'Mercado',portfolioFit:'Encaje portfolio',recurringPotential:'Recurrencia',differentiation:'Diferenciación',synergyPotential:'Sinergias',analystSignal:'Analistas',servicesLeverage:'Servicios',ecosystemStrength:'Ecosistema local',customerProof:'Referencias cliente',partnerCapability:'Capacidad integradores',countryCoverage:'Cobertura ES/PT',evidenceConfidence:'Confianza'};
  const w=state.engine.opportunityWeights;$('#engineExplanation').innerHTML=`<p>Motor v4 multicriterio, competitivo y condicional. Integra canal, competencia, consultoras, integradores, clientes públicos y relaciones multivendor. No utiliza revenue, pipeline ni información interna.</p><div class="weight-list">${Object.entries(w).map(([k,v])=>`<div><span>${esc(labels[k]||k)}</span><b>${Math.round(v*100)}%</b><i style="--w:${v*100}%"></i></div>`).join('')}</div><p class="tiny">El riesgo añade solape, presión de canal, concentración de partners/clientes, frescura, balance ES/PT y gaps. ACELERAR exige además evidencia y ecosistema mínimos.</p>`
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
Analistas: ${r.analystSignals?.length||0}
Fuentes alta confianza: ${r.derived?.officialOrAnalystCount||0}
Cambios detectados: ${ch.changes?.length||r.changes?.length||0}
Conflictos a validar: ${ch.conflicts?.length||r.conflicts?.length||0}
Brave opcional: ${r.braveEnabled?'sí':'no'}

Autoactualización: diaria + investigación profunda semanal.
Fuentes: webs/sitemaps oficiales, Google News RSS, GDELT, Arquivo.pt, TED, PLACSP, dados.gov.pt/BASE y analistas públicos.
Reglas: discovery ≠ evidencia ejecutiva · EMEA ≠ Iberia ≠ ES/PT · ausencia pública ≠ inexistencia.
Partner directory ≠ capacidad probada: adjudicaciones, premios y casos pesan más.`}
function reportHtml(){const top=[...state.vendors].sort((a,b)=>b.analysis.decisionScore-a.analysis.decisionScore).slice(0,15);return `<div class="report-export"><div style="border-top:8px solid #f09e0d;padding-top:18px"><div style="font-size:10px;color:#3195bb;font-weight:800">WESTCON IBERIA · FY27–FY30</div><h1>Radar Estratégico Tecnológico</h1><p class="note">Motor v4 · inteligencia pública + portfolio FY27 facilitado. Incluye ecosistema de integradores y referencias públicas de cliente.</p></div><h2>Decisiones prioritarias</h2><table><thead><tr><th>Fabricante</th><th>Decisión</th><th>Score</th><th>Oportunidad</th><th>Ecosistema</th><th>Clientes</th><th>Canal</th><th>Solape</th><th>Conf.</th><th>Acción 90 días</th></tr></thead><tbody>${top.map(v=>`<tr><td>${esc(v.name)}</td><td>${v.analysis.recommendation}</td><td>${v.analysis.decisionScore}</td><td>${v.analysis.opportunity}</td><td>${v.analysis.ecosystemStrength}</td><td>${v.derived.customers.length}</td><td>${v.analysis.channelPressure}</td><td>${v.analysis.overlapRisk}</td><td>${v.analysis.evidenceConfidence}</td><td>${esc(v.derived.plan.p90)}</td></tr>`).join('')}</tbody></table><h2>Sinergias</h2>${(state.base.solutionPlays||[]).map(p=>`<h3>${esc(p.name)}</h3><p><b>${esc(p.vendors.join(' + '))}</b><br>${esc(p.value)}</p>`).join('')}<h2>Metodología</h2><p>Motor multicriterio: mercado, encaje, recurrencia, diferenciación, analistas, servicios, ecosistema, referencias, integradores, cobertura geográfica y evidencia. Riesgo: overlap, canal, concentración, frescura, balance ES/PT y gaps.</p></div>`}
async function exportPdf(){if(!window.html2pdf){toast('Librería PDF no disponible');return}const report=$('#report');report.innerHTML=reportHtml();report.style.display='block';await html2pdf().set({margin:8,filename:'Westcon_Iberia_Radar_Estrategico_v1.4.pdf',image:{type:'jpeg',quality:.96},html2canvas:{scale:1.4,useCORS:true},jsPDF:{unit:'mm',format:'a4',orientation:'landscape'},pagebreak:{mode:['css','legacy']}}).from(report.firstElementChild).save();report.style.display='none';toast('PDF generado')}
async function exportPptx(){
  if(!window.PptxGenJS){toast('Librería PowerPoint no disponible');return}const pptx=new PptxGenJS();pptx.layout='LAYOUT_WIDE';pptx.author='Westcon Iberia Strategy Studio';pptx.title='Westcon Iberia · Radar Estratégico v1.4';pptx.company='Westcon-Comstor';pptx.defineSlideMaster({title:'MASTER',background:{color:'FFFFFF'},objects:[{rect:{x:0,y:0,w:13.333,h:.18,fill:{color:'F09E0D'},line:{color:'F09E0D'}}},{text:{text:'WESTCON IBERIA · RADAR ESTRATÉGICO',options:{x:.55,y:.25,w:6,h:.25,fontFace:'Corbel',fontSize:9,bold:true,color:'3195BB'}}},{text:{text:'Motor v4 · Inteligencia pública',options:{x:9.7,y:.25,w:3.0,h:.25,fontFace:'Corbel',fontSize:8,color:'687B8D',align:'right'}}}],slideNumber:{x:12.75,y:7.12,color:'687B8D',fontSize:8}});const addTitle=(s,t,sub='')=>{s.addText(t,{x:.55,y:.65,w:12.2,h:.55,fontFace:'Corbel',fontSize:27,bold:true,color:'082335',margin:0});if(sub)s.addText(sub,{x:.55,y:1.24,w:11.9,h:.4,fontFace:'Corbel',fontSize:11,color:'687B8D',margin:0})};
  let s=pptx.addSlide('MASTER');addTitle(s,'Decidir rápido. Investigar a fondo.','Competencia, canal, analistas, integradores, clientes, sinergias y acciones por fabricante.');const k=[[state.vendors.length,'fabricantes'],[allEvidence().length,'evidencias'],[state.vendors.reduce((n,v)=>n+v.derived.integrators.length,0),'integradores'],[state.vendors.reduce((n,v)=>n+v.derived.customers.length,0),'clientes públicos']];k.forEach((x,i)=>{s.addShape(pptx.ShapeType.rect,{x:.55+i*3.05,y:2,w:2.8,h:1.15,fill:{color:i%2?'F7F9FA':'F2F7F8'},line:{color:'DBE4E9'}});s.addText(String(x[0]),{x:.75+i*3.05,y:2.2,w:2.3,h:.42,fontFace:'Corbel',fontSize:24,bold:true,color:'082335'});s.addText(x[1],{x:.75+i*3.05,y:2.68,w:2.3,h:.24,fontFace:'Corbel',fontSize:9,color:'687B8D'})});s.addText('La recomendación incorpora explícitamente la fortaleza del ecosistema Iberia y la prueba pública de cliente.',{x:.55,y:3.75,w:11.8,h:1,fontFace:'Corbel',fontSize:21,bold:true,color:'113A50',margin:0});
  s=pptx.addSlide('MASTER');addTitle(s,'Fabricantes que requieren decisión','Score dinámico, ecosistema y acción recomendada.');const top=[...state.vendors].sort((a,b)=>b.analysis.decisionScore-a.analysis.decisionScore).slice(0,14);const rows=[['Fabricante','Decisión','Score','Oport.','Eco.','Clientes','Canal','Solape','Conf.','Acción 90 días'],...top.map(v=>[v.name,v.analysis.recommendation,String(v.analysis.decisionScore),String(v.analysis.opportunity),String(v.analysis.ecosystemStrength),String(v.derived.customers.length),String(v.analysis.channelPressure),String(v.analysis.overlapRisk),String(v.analysis.evidenceConfidence),v.derived.plan.p90])];s.addTable(rows,{x:.25,y:1.6,w:12.8,h:5.4,border:{type:'solid',color:'D9E2E7',pt:.6},fontFace:'Corbel',fontSize:6.6,color:'233746',fill:'FFFFFF',margin:.03,colW:[1.35,.9,.48,.48,.48,.48,.48,.48,.48,6.79]});
  s=pptx.addSlide('MASTER');addTitle(s,'Ecosistema Iberia','Integradores y clientes públicos como aceleradores de estrategia.');const ecoTop=[...state.vendors].filter(v=>v.derived.integrators.length||v.derived.customers.length).sort((a,b)=>b.analysis.ecosystemStrength-a.analysis.ecosystemStrength).slice(0,10);const erows=[['Fabricante','Ecosistema','Integradores destacados','Clientes públicos','Acción'],...ecoTop.map(v=>[v.name,String(v.analysis.ecosystemStrength),v.derived.integrators.slice(0,3).map(x=>`${x.country}:${x.name}`).join(' · '),v.derived.customers.slice(0,3).map(x=>x.name).join(' · '),v.derived.plan.p90])];s.addTable(erows,{x:.3,y:1.6,w:12.7,h:5.35,border:{type:'solid',color:'D9E2E7',pt:.6},fontFace:'Corbel',fontSize:7,color:'233746',fill:'FFFFFF',margin:.035,colW:[1.5,.7,3.0,3.0,4.5]});
  s=pptx.addSlide('MASTER');addTitle(s,'Sinergias que debemos monetizar','El portfolio como arquitecturas y ecosistemas, no como catálogo.');(state.base.solutionPlays||[]).slice(0,6).forEach((p,i)=>{const col=i%3,row=Math.floor(i/3),x=.55+col*4.12,y=1.75+row*2.42;s.addShape(pptx.ShapeType.rect,{x,y,w:3.78,h:2.05,fill:{color:'082335'},line:{color:'082335'}});s.addText(p.name,{x:x+.18,y:y+.25,w:3.35,h:.42,fontFace:'Corbel',fontSize:16,bold:true,color:'FFFFFF',margin:0});s.addText(p.vendors.join(' + '),{x:x+.18,y:y+.82,w:3.35,h:.4,fontFace:'Corbel',fontSize:7.5,color:'12C7C0',margin:0});s.addText(p.value,{x:x+.18,y:y+1.25,w:3.35,h:.55,fontFace:'Corbel',fontSize:8,color:'CDD6E0',margin:0})});
  await pptx.writeFile({fileName:'Westcon_Iberia_Radar_Estrategico_v1.4.pptx'});toast('PowerPoint generado')
}
load().catch(e=>{console.error(e);document.body.innerHTML=`<div style="padding:40px;font-family:Arial">No se pudo cargar la aplicación: ${esc(e.message)}</div>`});
