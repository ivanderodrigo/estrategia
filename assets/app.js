const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
const state={data:null,base:null,research:null,engine:null,vendors:[],selected:null,quick:'all',deep:false};

const esc=s=>String(s??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]));
const clamp=(n,min=0,max=100)=>Math.max(min,Math.min(max,Math.round(n||0)));
const avg=(a,f=x=>x)=>a?.length?a.reduce((s,x)=>s+Number(f(x)||0),0)/a.length:0;
const uniq=a=>[...new Set((a||[]).filter(Boolean))];
const fmtDate=s=>{if(!s)return '—';const d=new Date(String(s).length===4?`${s}-01-01`:s);return isNaN(d)?s:new Intl.DateTimeFormat('es-ES',{day:'2-digit',month:'short',year:'numeric'}).format(d)};
function toast(msg){const t=$('#toast');t.textContent=msg;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2200)}
function tags(arr,cls='',limit=5){return (arr||[]).slice(0,limit).map(x=>`<span class="tag ${cls}">${esc(typeof x==='string'?x:x.name||x.vendor||x.area||x.play)}</span>`).join('')||'<span class="tiny">Sin dato público demostrado</span>'}
function metricPill(label,value,cls=''){return `<span class="metric-pill ${cls}"><b>${clamp(value)}</b><small>${esc(label)}</small></span>`}
function evidenceLabel(v){return v.analysis.evidenceConfidence>=72?'Fuerte':v.analysis.evidenceConfidence>=50?'Media':'Débil'}

async function load(){
  const [data,base,research,engine]=await Promise.all([
    fetch('data/vendor_intelligence.json').then(r=>r.json()),
    fetch('data/base.json').then(r=>r.json()),
    fetch('data/research.latest.json').then(r=>r.ok?r.json():{}).catch(()=>({})),
    fetch('config/strategy_engine.json').then(r=>r.json())
  ]);
  state.data=data;state.base=base;state.research=research;state.engine=engine;
  state.vendors=data.vendors.map(enrichVendor);
  initNav();renderAll();
}

function allEvidence(){return state.research?.evidence?.length?state.research.evidence:[]}
function relevantEvidence(v){
  const name=v.name.toLowerCase();
  return allEvidence().filter(e=>{
    if(String(e.vendor||'').toLowerCase()===name)return true;
    const tags=(e.tags||[]).map(String).map(x=>x.toLowerCase());
    if(tags.includes(name))return true;
    const blob=`${e.title||''} ${e.summary||''} ${e.snippet||''}`.toLowerCase();
    return blob.includes(name);
  });
}
function channelSignals(v){
  const rows=[];
  (v.channelCompetitors||[]).forEach(c=>rows.push({country:c.country,distributor:c.name,confidence:80,url:c.url,evidence:[c.evidence]}));
  (state.research?.channelSignals||[]).filter(x=>x.vendor===v.name&&String(x.distributor||'').toLowerCase()!=='westcon-comstor').forEach(x=>rows.push(x));
  const map=new Map();
  rows.forEach(x=>{const k=`${x.country}|${x.distributor}`;const cur=map.get(k);if(!cur||Number(x.confidence||0)>Number(cur.confidence||0))map.set(k,x)});
  return [...map.values()].sort((a,b)=>Number(b.confidence||0)-Number(a.confidence||0));
}
function themeMatches(v){
  const txt=[v.domain,...(v.capabilities||[])].join(' ').toLowerCase();
  const direct=new Set();
  (state.base.solutionPlays||[]).filter(p=>p.vendors.includes(v.name)).forEach(p=>(p.themes||[]).forEach(t=>direct.add(t)));
  (state.engine.themeRules||[]).forEach(r=>{if((r.keywords||[]).some(k=>txt.includes(k.toLowerCase())))direct.add(r.theme)});
  return state.base.themes.filter(t=>direct.has(t.id));
}
function domainDefault(v,key){
  const d=state.engine.domainDefaults[v.domain]||state.engine.domainDefaults[v.domain?.split(' / ')[0]]||state.engine.domainDefaults.Other||{};
  return Number(d[key]||65);
}
function evidenceConfidence(v,evidence){
  if(!evidence.length)return 28;
  const tier=state.engine.evidenceTiers||{};
  const now=new Date('2026-08-26T12:00:00Z');
  const scores=evidence.map(e=>{
    let s=Number(e.confidence||tier[e.sourceTier]||45);
    const d=new Date(e.date||e.published||e.collectedAt||'');
    if(!isNaN(d)){
      const days=Math.max(0,(now-d)/86400000);
      const f=days<=180?1:days<=365?0.88:days<=730?0.72:0.55;
      s*=f;
    }
    if(/query context only/i.test(e.scope||''))s-=12;
    return clamp(s);
  });
  const sourceBonus=Math.min(14,uniq(evidence.map(e=>e.source)).length*2);
  return clamp(avg(scores)+sourceBonus);
}
function analystScore(v,evidence){
  const explicit=v.analystSignals||[];
  const pub=evidence.filter(e=>e.sourceTier==='analyst-public'||/gartner|forrester|idc|omdia|canalys|dell.?oro|synergy/i.test(e.source||''));
  const names=uniq([...explicit.map(x=>x.analyst),...pub.map(x=>x.source)]);
  if(!explicit.length&&!pub.length)return 24;
  return clamp(35+explicit.length*13+pub.length*5+names.length*6);
}
function synergyScore(v){
  const vendors=uniq((v.synergies||[]).flatMap(x=>x.with||[]));
  const plays=(state.base.solutionPlays||[]).filter(p=>p.vendors.includes(v.name));
  return clamp(28+vendors.length*7+plays.length*12);
}
function overlapScore(v){
  const ovs=v.internalOverlaps||[];const areas=uniq(ovs.map(x=>x.area));
  return clamp(12+ovs.length*10+areas.length*6);
}
function channelPressure(v,channels){
  const alts=channels.filter(x=>Number(x.confidence||0)>=55);
  const countries=uniq(alts.map(x=>x.country));
  return clamp(alts.length?18+alts.length*14+countries.length*10:16);
}
function recommendationFor(a){
  if(a.evidenceConfidence<40)return 'INVESTIGAR';
  if(a.channelPressure>=58&&a.opportunity>=64)return 'DEFENDER';
  if(a.opportunity>=78&&a.risk<=78)return 'ACELERAR';
  if(a.opportunity>=64)return 'CONSTRUIR';
  return 'OPTIMIZAR';
}
function actionPlan(v,a){
  const strongest=(v.synergies||[]).sort((x,y)=>(y.with?.length||0)-(x.with?.length||0))[0];
  const overlap=(v.internalOverlaps||[])[0];
  const analyst=(v.analystSignals||[])[0];
  const channels=channelSignals(v);
  const p30=a.evidenceConfidence<50
    ?`Cerrar gaps públicos: confirmar canal ES/PT y obtener al menos una referencia primaria/analista adicional.`
    :overlap?`Definir una battlecard de cualificación frente a ${overlap.vendor} en ${overlap.area}.`
    :analyst?`Traducir ${analyst.analyst} a 5 preguntas de discovery y criterios de valor para partners.`
    :`Validar posicionamiento competitivo y casos de uso prioritarios con fuentes públicas recientes.`;
  const p90=strongest
    ?`Construir el play “${strongest.play}” con ${strongest.with.slice(0,3).join(' + ')}: arquitectura, demo, mensajes y criterios de éxito.`
    :`Crear un play comercial/técnico repetible sobre ${v.capabilities.slice(0,2).join(' + ')}.`;
  const p180=channels.length
    ?`Diferenciar frente al canal alternativo con servicios, enablement, labs, soporte y lifecycle medibles.`
    :`Escalar enablement y generación de demanda solo cuando la evidencia confirme mercado y diferenciación suficientes.`;
  return {p30,p90,p180};
}
function enrichVendor(v){
  const themes=themeMatches(v);
  const explicit=[...(v.analystSignals||[]).map(a=>({title:a.title,url:a.url,source:a.analyst,sourceTier:'analyst-public',date:a.date,scope:'Public analyst summary',confidence:90,summary:a.summary})),...(v.channelCompetitors||[]).filter(c=>c.url).map(c=>({title:c.evidence||`${c.name} · ${c.country}`,url:c.url,source:c.name,sourceTier:'official-company',date:'2026',scope:c.country,confidence:84,summary:c.evidence}))];
  const evMap=new Map();[...relevantEvidence(v),...explicit].forEach(e=>evMap.set(e.url||`${e.title}|${e.source}`,e));const ev=[...evMap.values()];const channels=channelSignals(v);
  const market=clamp(themes.length?avg(themes,x=>x.momentum):domainDefault(v,'marketMomentum'));
  const fit=clamp(themes.length?avg(themes,x=>x.portfolioFit)+(v.countries?.length>1?3:0):68+(v.countries?.length>1?5:0));
  const recurring=clamp(themes.length?avg(themes,x=>x.recurringPotential):domainDefault(v,'recurringPotential'));
  const diff=clamp(themes.length?avg(themes,x=>x.differentiation):68);
  const synergy=synergyScore(v),overlap=overlapScore(v),channel=channelPressure(v,channels),econf=evidenceConfidence(v,ev),analyst=analystScore(v,ev),services=domainDefault(v,'servicesLeverage');
  const w=state.engine.opportunityWeights;
  const opportunity=clamp(market*w.marketMomentum+fit*w.portfolioFit+recurring*w.recurringPotential+diff*w.differentiation+synergy*w.synergyPotential+analyst*w.analystSignal+services*w.servicesLeverage+econf*w.evidenceConfidence);
  const rw=state.engine.riskWeights;const risk=clamp(overlap*rw.overlapRisk+channel*rw.channelPressure+(100-econf)*rw.evidenceGap);
  const decisionScore=clamp(opportunity*.84+(100-risk)*.16);
  const analysis={marketMomentum:market,portfolioFit:fit,recurringPotential:recurring,differentiation:diff,synergyPotential:synergy,overlapRisk:overlap,channelPressure:channel,evidenceConfidence:econf,analystSignal:analyst,servicesLeverage:services,opportunity,risk,decisionScore};
  analysis.recommendation=recommendationFor(analysis);
  const plan=actionPlan(v,analysis);
  const drivers=[['Mercado',market],['Sinergia',synergy],['Recurrencia',recurring],['Analistas',analyst],['Encaje',fit]].sort((a,b)=>b[1]-a[1]).slice(0,3);
  const brakes=[['Solape',overlap],['Canal',channel],['Gap de evidencia',100-econf]].sort((a,b)=>b[1]-a[1]).slice(0,2);
  return {...v,analysis,derived:{themes,channels,evidence:ev,plan,drivers,brakes}};
}

function initNav(){
  $$('#tabs button').forEach(b=>b.onclick=()=>switchView(b.dataset.view));
  $$('[data-jump]').forEach(b=>b.onclick=()=>switchView(b.dataset.jump));
  ['vendorSearch','domainFilter','recommendationFilter','countryFilter'].forEach(id=>$('#'+id)?.addEventListener(id==='vendorSearch'?'input':'change',renderVendorTable));
  $$('#smartFilters button').forEach(b=>b.onclick=()=>{state.quick=b.dataset.quick;$$('#smartFilters button').forEach(x=>x.classList.toggle('active',x===b));renderVendorTable()});
  $('#sourceSearch')?.addEventListener('input',renderSources);$('#sourceTierFilter')?.addEventListener('change',renderSources);
  $('#btnDepth').onclick=()=>{state.deep=!state.deep;document.body.classList.toggle('deep-mode',state.deep);$('#btnDepth').textContent=state.deep?'Vista ejecutiva':'Ver datos';if(state.selected)selectVendor(state.selected)};
  $('#btnPdf').onclick=exportPdf;$('#btnPptx').onclick=exportPptx;
}
function switchView(id){$$('.view').forEach(v=>v.classList.toggle('active',v.id===id));$$('#tabs button').forEach(b=>b.classList.toggle('active',b.dataset.view===id));window.scrollTo({top:0,behavior:'smooth'})}

function renderAll(){renderKpis();renderDecisionCards();renderChanges();renderDataHealth();renderFilters();renderOverviewVendors();renderVendorTable();renderPlays();renderOverlaps();renderTrends();renderSignals();renderDataKpis();renderEngine();renderGaps();renderSources();renderResearch()}
function renderKpis(){
  const ev=allEvidence(),official=ev.filter(e=>['official-company','analyst-public','regulator'].includes(e.sourceTier)).length,chan=(state.research?.channelSignals||[]).length,strong=state.vendors.filter(v=>v.analysis.evidenceConfidence>=65).length,gaps=state.vendors.filter(v=>v.analysis.evidenceConfidence<45).length;
  const k=[[state.vendors.length,'Fabricantes','Portfolio FY27'],[ev.length,'Evidencias','públicas trazables'],[official,'Alta confianza','oficial + analista'],[chan,'Relaciones canal','señales ES/PT'],[strong,'Bien cubiertos',`${gaps} con gap alto`]];
  $('#marketKpis').innerHTML=k.map(x=>`<div class="kpi"><span>${x[1]}</span><strong>${x[0]}</strong><small>${x[2]}</small></div>`).join('')
}
function renderDecisionCards(){
  const rows=[...state.vendors].sort((a,b)=>b.analysis.decisionScore-a.analysis.decisionScore).slice(0,4);
  $('#decisionCards').innerHTML=rows.map(v=>`<article class="decision-card" data-vendor="${esc(v.name)}"><div class="decision-head"><span class="priority ${v.analysis.recommendation}">${v.analysis.recommendation}</span><b>${v.analysis.opportunity}</b></div><h3>${esc(v.name)}</h3><p>${esc(v.derived.plan.p90)}</p><div class="mini-metrics">${metricPill('canal',v.analysis.channelPressure,'channel')}${metricPill('solape',v.analysis.overlapRisk,'overlap')}${metricPill('conf.',v.analysis.evidenceConfidence,'confidence')}</div></article>`).join('');
  $$('#decisionCards .decision-card').forEach(x=>x.onclick=()=>{switchView('fabricantes');selectVendor(x.dataset.vendor)})
}
function renderChanges(){$('#externalChanges').innerHTML=[...state.data.externalChanges].sort((a,b)=>String(b.date).localeCompare(String(a.date))).slice(0,6).map(x=>`<div class="time-item"><time>${fmtDate(x.date)}</time><div><b>${esc(x.title)}</b><p>${esc(x.impact)}</p><a class="evidence-link" href="${x.url}" target="_blank" rel="noopener">Fuente pública ↗</a></div></div>`).join('')}
function renderDataHealth(){
  const items=[
    ['Canal ES/PT',state.vendors.filter(v=>v.derived.channels.length).length,state.vendors.length,'Relaciones alternativas públicamente identificadas'],
    ['Consultoras',state.vendors.filter(v=>v.analysis.analystSignal>=50).length,state.vendors.length,'Fabricantes con señal pública específica o de mercado'],
    ['Sinergias',state.vendors.filter(v=>v.analysis.synergyPotential>=60).length,state.vendors.length,'Fabricantes conectados a plays multivendor'],
    ['Evidencia fuerte',state.vendors.filter(v=>v.analysis.evidenceConfidence>=65).length,state.vendors.length,'Cobertura suficiente para una lectura ejecutiva']
  ];
  $('#dataHealth').innerHTML=items.map(x=>{const p=Math.round(x[1]/x[2]*100);return `<div class="health-row"><div><b>${x[0]}</b><span>${x[1]}/${x[2]} · ${x[3]}</span></div><strong>${p}%</strong><div class="healthbar"><i style="--w:${p}%"></i></div></div>`}).join('')
}
function renderFilters(){
  const domains=uniq(state.vendors.map(v=>v.domain)).sort();$('#domainFilter').innerHTML='<option value="all">Todas las áreas</option>'+domains.map(d=>`<option>${esc(d)}</option>`).join('');
  const rec=['ACELERAR','CONSTRUIR','DEFENDER','OPTIMIZAR','INVESTIGAR'];$('#recommendationFilter').innerHTML='<option value="all">Todas las decisiones</option>'+rec.map(x=>`<option>${x}</option>`).join('')
}
function filteredVendors(){
  const q=$('#vendorSearch').value.trim().toLowerCase(),d=$('#domainFilter').value,r=$('#recommendationFilter').value,c=$('#countryFilter').value;
  return state.vendors.filter(v=>{
    const blob=[v.name,v.domain,...v.capabilities,...v.marketCompetitors,...v.derived.channels.map(x=>x.distributor),...(v.internalOverlaps||[]).map(x=>x.vendor),...(v.synergies||[]).flatMap(x=>x.with||[])].join(' ').toLowerCase();
    let ok=(!q||blob.includes(q))&&(d==='all'||v.domain===d)&&(r==='all'||v.analysis.recommendation===r)&&(c==='all'||v.countries.includes(c));
    if(!ok)return false;
    if(state.quick==='opportunity')return v.analysis.opportunity>=78;
    if(state.quick==='channel')return v.analysis.channelPressure>=55;
    if(state.quick==='synergy')return v.analysis.synergyPotential>=70;
    if(state.quick==='overlap')return v.analysis.overlapRisk>=60;
    if(state.quick==='gaps')return v.analysis.evidenceConfidence<50;
    return true;
  }).sort((a,b)=>b.analysis.decisionScore-a.analysis.decisionScore||a.name.localeCompare(b.name));
}
function channelSummary(v){
  const rows=v.derived.channels;if(!rows.length)return '<span class="tiny">Por demostrar</span>';
  const grouped={ES:[],PT:[],IBERIA:[]};rows.forEach(x=>(grouped[x.country]??=[]).push(x.distributor));
  return ['ES','PT','IBERIA'].map(c=>grouped[c]?.length?`<span class="tag channel">${c}: ${esc(uniq(grouped[c]).join(', '))}</span>`:'').join('')
}
function analystSummary(v){
  if(!v.analystSignals?.length)return `<span class="coverage ${v.analysis.analystSignal>=45?'mid':'low'}">${v.analysis.analystSignal} · cobertura ${v.analysis.analystSignal>=45?'media':'baja'}</span>`;
  return v.analystSignals.slice(0,2).map(a=>`<span class="tag analyst">${esc(a.analyst)} · ${esc(a.title.replace('Magic Quadrant for ','').replace('Critical Capabilities for ',''))}</span>`).join('')
}
function synergyNames(v){return uniq((v.synergies||[]).flatMap(x=>x.with||[]))}
function internalNames(v){return uniq((v.internalOverlaps||[]).map(x=>x.vendor))}
function scoreCell(v,key,cls=''){const x=v.analysis[key];return `<div class="score-cell ${cls}"><b>${x}</b><span class="scorebar"><i style="--w:${x}%"></i></span></div>`}
function synergyOverlap(v){return `<span class="balance good">S ${v.analysis.synergyPotential}</span><span class="balance bad">O ${v.analysis.overlapRisk}</span>`}
function renderOverviewVendors(){
  const rows=[...state.vendors].sort((a,b)=>b.analysis.decisionScore-a.analysis.decisionScore).slice(0,12);
  $('#overviewVendorRows').innerHTML=rows.map(v=>`<tr data-vendor="${esc(v.name)}"><td><span class="vendor-name">${esc(v.name)}</span><span class="tiny">${esc(v.domain)}</span></td><td><span class="priority ${v.analysis.recommendation}">${v.analysis.recommendation}</span><span class="tiny">score ${v.analysis.decisionScore}</span></td><td>${tags(v.marketCompetitors,'',3)}</td><td>${channelSummary(v)}</td><td>${analystSummary(v)}</td><td>${synergyOverlap(v)}</td><td>${esc(v.derived.plan.p30)}</td></tr>`).join('');
  $$('#overviewVendorRows tr').forEach(tr=>tr.onclick=()=>{switchView('fabricantes');selectVendor(tr.dataset.vendor)})
}
function renderVendorTable(){
  const rows=filteredVendors();$('#resultCount').textContent=`${rows.length} fabricantes`;
  $('#vendorRows').innerHTML=rows.map(v=>`<tr data-vendor="${esc(v.name)}" class="${state.selected===v.name?'selected':''}"><td><span class="vendor-name">${esc(v.name)}</span><span class="tiny">${v.countries.join(' · ')} · ${esc(v.domain)}</span></td><td><span class="priority ${v.analysis.recommendation}">${v.analysis.recommendation}</span></td><td>${scoreCell(v,'opportunity')}</td><td>${tags(v.marketCompetitors,'',3)}</td><td>${channelSummary(v)}</td><td>${analystSummary(v)}</td><td>${scoreCell(v,'synergyPotential','good')}</td><td>${scoreCell(v,'overlapRisk','bad')}</td><td><span class="confidence-dot ${v.analysis.evidenceConfidence>=65?'high':v.analysis.evidenceConfidence>=45?'mid':'low'}"></span>${v.analysis.evidenceConfidence}<span class="tiny">${evidenceLabel(v)}</span></td><td>${esc(v.derived.plan.p30)}</td></tr>`).join('');
  $$('#vendorRows tr').forEach(tr=>tr.onclick=()=>selectVendor(tr.dataset.vendor))
}
function metricCard(label,value,note,kind=''){return `<div class="metric-card ${kind}"><span>${esc(label)}</span><strong>${clamp(value)}</strong><div class="meter"><i style="--w:${clamp(value)}%"></i></div><small>${esc(note)}</small></div>`}
function selectVendor(name){
  state.selected=name;renderVendorTable();const v=state.vendors.find(x=>x.name===name);if(!v)return;const a=v.analysis;
  const chan=v.derived.channels.map(c=>`<div class="evidence-row"><div><b>${esc(c.country)} · ${esc(c.distributor)}</b><span>Confianza ${clamp(c.confidence||65)}/100</span></div>${c.url?`<a href="${c.url}" target="_blank" rel="noopener">Fuente ↗</a>`:''}</div>`).join('')||'<p>Sin mayorista alternativo demostrado públicamente todavía. No significa exclusividad.</p>';
  const ana=(v.analystSignals||[]).map(x=>`<div class="analyst-row"><b>${esc(x.analyst)} · ${fmtDate(x.date)}</b><p>${esc(x.summary)}</p><div>${tags(x.peers,'',5)}</div><a class="evidence-link" href="${x.url}" target="_blank" rel="noopener">${esc(x.title)} ↗</a></div>`).join('')||'<p>No hay señal pública específica suficientemente fuerte cargada para este fabricante.</p>';
  const syn=(v.synergies||[]).map(s=>`<div class="synergy-row"><b>${esc(s.play)}</b><p>${esc(s.value)}</p>${tags(s.with,'synergy')}</div>`).join('')||'<p>Sin play multivendor explícito cargado.</p>';
  const ov=(v.internalOverlaps||[]).map(o=>`<span class="tag overlap">${esc(o.vendor)} · ${esc(o.area)}</span>`).join('')||'<span class="tiny">Solape bajo o todavía no modelado.</span>';
  const ev=v.derived.evidence.slice(0,state.deep?18:5).map(e=>`<div class="source-mini"><b>${esc(e.source||e.sourceTier)} · ${fmtDate(e.date||e.published)}</b><span>${esc(e.title)}</span><a href="${e.url}" target="_blank" rel="noopener">Abrir ↗</a></div>`).join('')||'<p>La evidencia específica todavía es limitada.</p>';
  const drivers=v.derived.drivers.map(x=>`<span class="driver good"><b>${x[1]}</b>${x[0]}</span>`).join(''),brakes=v.derived.brakes.map(x=>`<span class="driver bad"><b>${x[1]}</b>${x[0]}</span>`).join('');
  $('#vendorDetail').innerHTML=`<div class="detail-top"><div class="domain">${esc(v.domain)} · ${v.countries.join(' / ')}</div><h2>${esc(v.name)}</h2><div class="decision-line"><span class="priority ${a.recommendation}">${a.recommendation}</span><b>${a.decisionScore}<small>/100 decisión</small></b></div><div style="margin-top:8px">${tags(v.capabilities)}</div></div>
  <div class="metric-grid">${metricCard('Oportunidad',a.opportunity,'mercado + encaje + recurrencia','good')}${metricCard('Canal',a.channelPressure,'presión de mayoristas','warn')}${metricCard('Solape',a.overlapRisk,'canibalización potencial','bad')}${metricCard('Confianza',a.evidenceConfidence,'calidad de evidencia','info')}</div>
  <div class="action-box"><b>RECOMENDACIÓN</b><p>${esc(v.derived.plan.p90)}</p></div>
  <div class="drivers"><div><h4>IMPULSA</h4>${drivers}</div><div><h4>FRENA</h4>${brakes}</div></div>
  <div class="detail-block"><h4>COMPETIDORES DE MERCADO</h4>${tags(v.marketCompetitors,'',7)}</div>
  <div class="detail-block"><h4>MAYORISTAS ALTERNATIVOS · ES/PT</h4>${chan}</div>
  <div class="detail-block"><h4>CONSULTORAS / DIFERENCIAL</h4>${ana}<p class="analyst-diff">${esc(v.analystDifferential)}</p></div>
  <div class="detail-block"><h4>SINERGIAS</h4>${syn}</div>
  <div class="detail-block"><h4>OVERLAP</h4>${ov}</div>
  <div class="plan-block"><h4>PLAN PROPUESTO</h4><div><b>30 días</b><p>${esc(v.derived.plan.p30)}</p></div><div><b>90 días</b><p>${esc(v.derived.plan.p90)}</p></div><div><b>6 meses</b><p>${esc(v.derived.plan.p180)}</p></div></div>
  <div class="deep-only detail-block"><h4>DESGLOSE DEL MOTOR</h4><div class="engine-metrics">${Object.entries({Mercado:a.marketMomentum,Encaje:a.portfolioFit,Recurrencia:a.recurringPotential,Diferenciación:a.differentiation,Sinergia:a.synergyPotential,Analistas:a.analystSignal,Servicios:a.servicesLeverage,Canal:a.channelPressure,Solape:a.overlapRisk,Evidencia:a.evidenceConfidence}).map(([k,val])=>metricPill(k,val)).join('')}</div></div>
  <div class="deep-only detail-block"><h4>EVIDENCIAS RELACIONADAS · ${v.derived.evidence.length}</h4>${ev}</div>`;
  if(window.innerWidth<1200)$('#vendorDetail').scrollIntoView({behavior:'smooth',block:'start'})
}

function renderPlays(){
  $('#playCards').innerHTML=(state.base.solutionPlays||[]).map((p,i)=>{const vs=state.vendors.filter(v=>p.vendors.includes(v.name));const op=clamp(avg(vs,x=>x.analysis.opportunity)),sy=clamp(avg(vs,x=>x.analysis.synergyPotential)),ov=clamp(avg(vs,x=>x.analysis.overlapRisk));return `<article class="play-card"><div class="num">0${i+1}</div><div class="play-score">${op}<small>oportunidad</small></div><h3>${esc(p.name)}</h3><p>${esc(p.value)}</p><div class="vendor-tags">${p.vendors.map(v=>`<span>${esc(v)}</span>`).join('')}</div><div class="play-bottom"><span>Sinergia <b>${sy}</b></span><span>Overlap <b>${ov}</b></span><strong>→ Crear oferta repetible + demo + campaña</strong></div></article>`}).join('')
}
function renderOverlaps(){
  const map={};state.vendors.forEach(v=>(v.internalOverlaps||[]).forEach(o=>{const x=map[o.area]??={vendors:new Set(),score:0};x.vendors.add(v.name);x.vendors.add(o.vendor);x.score=Math.max(x.score,v.analysis.overlapRisk)}));
  $('#overlapMap').innerHTML=Object.entries(map).sort((a,b)=>b[1].score-a[1].score).map(([area,x])=>`<article class="overlap-card"><div class="overlap-score">${x.score}</div><h3>${esc(area)}</h3><div class="overlap-line">${[...x.vendors].map(v=>`<span class="tag overlap">${esc(v)}</span>`).join('')}</div><p><b>Acción:</b> segmentar por caso de uso, arquitectura, cliente objetivo y criterio de decisión; evitar mensajes genéricos de “plataforma”.</p></article>`).join('')
}
function renderTrends(){$('#trendCards').innerHTML=state.base.themes.slice().sort((a,b)=>b.momentum-a.momentum).map(t=>{const score=clamp(t.momentum*.32+t.portfolioFit*.25+t.recurringPotential*.18+t.differentiation*.15+t.confidence*.10);return `<article class="trend-card"><div class="trend-score">${score}<span class="tiny">/100 · inferencia</span></div><div class="meter"><i style="--w:${score}%"></i></div><h3>${esc(t.name)}</h3><p>${esc(t.why)}</p><div class="trend-factors"><span>M ${t.momentum}</span><span>Fit ${t.portfolioFit}</span><span>Rec ${t.recurringPotential}</span><span>Dif ${t.differentiation}</span></div></article>`}).join('')}
function renderSignals(){$('#signalCards').innerHTML=state.data.marketSignals.slice().sort((a,b)=>String(b.date).localeCompare(String(a.date))).map(s=>`<article class="signal-card"><span>${esc(s.analyst)} · ${fmtDate(s.date)}</span><strong>${esc(s.metric)}</strong><h3>${esc(s.label)}</h3><p>${esc(s.detail)}</p><a class="evidence-link" href="${s.url}" target="_blank" rel="noopener">Fuente ↗</a></article>`).join('')}

function renderDataKpis(){
  const ev=allEvidence(),tiers={};ev.forEach(e=>tiers[e.sourceTier]=(tiers[e.sourceTier]||0)+1);const gaps=state.vendors.filter(v=>v.analysis.evidenceConfidence<50).length;
  const k=[[ev.length,'Evidencias','baseline + research'],[tiers['analyst-public']||0,'Consultoras','contenido público'],[tiers['official-company']||0,'Fuentes oficiales','fabricantes/mayoristas'],[(state.research?.channelSignals||[]).length,'Canal','relaciones detectadas'],[gaps,'Gaps','fabricantes <50 confianza']];
  $('#dataKpis').innerHTML=k.map(x=>`<div class="kpi"><span>${x[1]}</span><strong>${x[0]}</strong><small>${x[2]}</small></div>`).join('')
}
function renderEngine(){
  const w=state.engine.opportunityWeights;$('#engineExplanation').innerHTML=`<p>La recomendación se recalcula con datos disponibles. No utiliza revenue, pipeline ni información interna.</p><div class="weight-list">${Object.entries(w).map(([k,v])=>`<div><span>${esc(k)}</span><b>${Math.round(v*100)}%</b><i style="--w:${v*100}%"></i></div>`).join('')}</div><p class="tiny">Riesgo: solape ${Math.round(state.engine.riskWeights.overlapRisk*100)}% · presión de canal ${Math.round(state.engine.riskWeights.channelPressure*100)}% · gap de evidencia ${Math.round(state.engine.riskWeights.evidenceGap*100)}%.</p>`
}
function renderGaps(){
  const rows=[...state.vendors].sort((a,b)=>a.analysis.evidenceConfidence-b.analysis.evidenceConfidence).slice(0,10);$('#researchGaps').innerHTML=rows.map(v=>`<div class="gap-row" data-vendor="${esc(v.name)}"><div><b>${esc(v.name)}</b><span>${v.analysis.evidenceConfidence}/100 · ${v.derived.channels.length?'canal parcial':'canal por demostrar'} · ${v.analystSignals?.length?'consultora cargada':'consultora pendiente'}</span></div><strong>Investigar →</strong></div>`).join('');$$('#researchGaps .gap-row').forEach(x=>x.onclick=()=>{switchView('fabricantes');selectVendor(x.dataset.vendor)})
}
function renderSources(){
  const q=($('#sourceSearch')?.value||'').toLowerCase(),tier=$('#sourceTierFilter')?.value||'all';const rows=allEvidence().filter(e=>{const blob=[e.source,e.title,e.summary,e.snippet,e.scope,e.kind,e.vendor,...(e.tags||[])].join(' ').toLowerCase();return(!q||blob.includes(q))&&(tier==='all'||e.sourceTier===tier)}).sort((a,b)=>String(b.date||b.published||'').localeCompare(String(a.date||a.published||'')));
  $('#sourceRows').innerHTML=rows.map(e=>`<tr><td>${fmtDate(e.date||e.published)}</td><td><span class="confidence-badge ${Number(e.confidence||state.engine.evidenceTiers[e.sourceTier]||45)>=80?'high':Number(e.confidence||45)>=60?'mid':'low'}">${clamp(e.confidence||state.engine.evidenceTiers[e.sourceTier]||45)}</span></td><td>${esc(e.scope||'—')}</td><td><b>${esc(e.source||e.sourceTier)}</b><span class="tiny">${esc(e.sourceTier||'')}</span></td><td>${esc(e.evidenceType||e.kind||'general')}</td><td>${esc(e.title)}${e.summary?`<span class="tiny">${esc(e.summary)}</span>`:''}</td><td>${e.url?`<a class="evidence-link" href="${e.url}" target="_blank" rel="noopener">Abrir ↗</a>`:''}</td></tr>`).join('')
}
function renderResearch(){const r=state.research||{};$('#researchSummary').textContent=`Última generación: ${r.generatedAt||'baseline'}\nModo: ${r.mode||'baseline público'}\nConsultas ejecutadas: ${r.queryCount||0}\nEvidencias: ${r.evidence?.length||0}\nCanal detectado: ${r.channelSignals?.length||0}\nAnalistas detectados: ${r.analystSignals?.length||0}\nFuentes alta confianza: ${r.derived?.officialOrAnalystCount||0}\nBrave opcional: ${r.braveEnabled?'sí':'no'}\n\nRegla: discovery ≠ evidencia ejecutiva.\nEMEA ≠ Iberia ≠ ES/PT.`}

function reportHtml(){
  const top=[...state.vendors].sort((a,b)=>b.analysis.decisionScore-a.analysis.decisionScore).slice(0,15);return `<div class="report-export"><div style="border-top:8px solid #f09e0d;padding-top:18px"><div style="font-size:10px;color:#3195bb;font-weight:800">WESTCON IBERIA · FY27–FY30</div><h1>Radar Estratégico Tecnológico</h1><p class="note">Motor v2 · inteligencia pública + portfolio FY27 facilitado. Sin datos internos.</p></div><h2>Decisiones prioritarias</h2><table><thead><tr><th>Fabricante</th><th>Decisión</th><th>Score</th><th>Oportunidad</th><th>Canal</th><th>Solape</th><th>Confianza</th><th>Acción 90 días</th></tr></thead><tbody>${top.map(v=>`<tr><td>${esc(v.name)}</td><td>${v.analysis.recommendation}</td><td>${v.analysis.decisionScore}</td><td>${v.analysis.opportunity}</td><td>${v.analysis.channelPressure}</td><td>${v.analysis.overlapRisk}</td><td>${v.analysis.evidenceConfidence}</td><td>${esc(v.derived.plan.p90)}</td></tr>`).join('')}</tbody></table><h2>Sinergias</h2>${(state.base.solutionPlays||[]).map(p=>`<h3>${esc(p.name)}</h3><p><b>${esc(p.vendors.join(' + '))}</b><br>${esc(p.value)}</p>`).join('')}<h2>Metodología</h2><p>Oportunidad = mercado + encaje + recurrencia + diferenciación + sinergia + señal de analistas + servicios + confianza. Riesgo = overlap + presión de canal + gap de evidencia. La recomendación se recalcula automáticamente.</p></div>`
}
async function exportPdf(){if(!window.html2pdf){toast('Librería PDF no disponible');return}const report=$('#report');report.innerHTML=reportHtml();report.style.display='block';await html2pdf().set({margin:8,filename:'Westcon_Iberia_Radar_Estrategico_v1.2.pdf',image:{type:'jpeg',quality:.96},html2canvas:{scale:1.4,useCORS:true},jsPDF:{unit:'mm',format:'a4',orientation:'landscape'},pagebreak:{mode:['css','legacy']}}).from(report.firstElementChild).save();report.style.display='none';toast('PDF generado')}
async function exportPptx(){
  if(!window.PptxGenJS){toast('Librería PowerPoint no disponible');return}const pptx=new PptxGenJS();pptx.layout='LAYOUT_WIDE';pptx.author='Westcon Iberia Strategy Studio';pptx.title='Westcon Iberia · Radar Estratégico v1.2';pptx.company='Westcon-Comstor';pptx.defineSlideMaster({title:'MASTER',background:{color:'FFFFFF'},objects:[{rect:{x:0,y:0,w:13.333,h:.18,fill:{color:'F09E0D'},line:{color:'F09E0D'}}},{text:{text:'WESTCON IBERIA · RADAR ESTRATÉGICO',options:{x:.55,y:.25,w:6,h:.25,fontFace:'Corbel',fontSize:9,bold:true,color:'3195BB'}}},{text:{text:'Motor v2 · Inteligencia pública',options:{x:9.7,y:.25,w:3.0,h:.25,fontFace:'Corbel',fontSize:8,color:'687B8D',align:'right'}}}],slideNumber:{x:12.75,y:7.12,color:'687B8D',fontSize:8}});const addTitle=(s,t,sub='')=>{s.addText(t,{x:.55,y:.65,w:12.2,h:.55,fontFace:'Corbel',fontSize:27,bold:true,color:'082335',margin:0});if(sub)s.addText(sub,{x:.55,y:1.24,w:11.9,h:.4,fontFace:'Corbel',fontSize:11,color:'687B8D',margin:0})};
  let s=pptx.addSlide('MASTER');addTitle(s,'Decidir rápido. Investigar a fondo.','Competencia, canal, analistas, sinergias, solapes y acciones por fabricante.');const k=[[state.vendors.length,'fabricantes'],[allEvidence().length,'evidencias'],[(state.research?.channelSignals||[]).length,'señales de canal'],[state.vendors.filter(v=>v.analysis.evidenceConfidence>=65).length,'fabricantes bien cubiertos']];k.forEach((x,i)=>{s.addShape(pptx.ShapeType.rect,{x:.55+i*3.05,y:2,w:2.8,h:1.15,fill:{color:i%2?'F7F9FA':'F2F7F8'},line:{color:'DBE4E9'}});s.addText(String(x[0]),{x:.75+i*3.05,y:2.2,w:2.3,h:.42,fontFace:'Corbel',fontSize:24,bold:true,color:'082335'});s.addText(x[1],{x:.75+i*3.05,y:2.68,w:2.3,h:.24,fontFace:'Corbel',fontSize:9,color:'687B8D'})});s.addText('La recomendación se recalcula con mercado, portfolio, recurrencia, analistas, sinergias, canal, overlap y evidencia.',{x:.55,y:3.75,w:11.8,h:1,fontFace:'Corbel',fontSize:21,bold:true,color:'113A50',margin:0});
  s=pptx.addSlide('MASTER');addTitle(s,'Fabricantes que requieren decisión','Score dinámico y acción recomendada.');const top=[...state.vendors].sort((a,b)=>b.analysis.decisionScore-a.analysis.decisionScore).slice(0,14);const rows=[['Fabricante','Decisión','Score','Oport.','Canal','Solape','Conf.','Acción 90 días'],...top.map(v=>[v.name,v.analysis.recommendation,String(v.analysis.decisionScore),String(v.analysis.opportunity),String(v.analysis.channelPressure),String(v.analysis.overlapRisk),String(v.analysis.evidenceConfidence),v.derived.plan.p90])];s.addTable(rows,{x:.35,y:1.6,w:12.6,h:5.4,border:{type:'solid',color:'D9E2E7',pt:.6},fontFace:'Corbel',fontSize:7,color:'233746',fill:'FFFFFF',margin:.035,colW:[1.55,1.05,.55,.55,.55,.55,.55,7.25]});
  s=pptx.addSlide('MASTER');addTitle(s,'Sinergias que debemos monetizar','El portfolio como arquitecturas, no como catálogo.');(state.base.solutionPlays||[]).slice(0,6).forEach((p,i)=>{const col=i%3,row=Math.floor(i/3),x=.55+col*4.12,y=1.75+row*2.42;s.addShape(pptx.ShapeType.rect,{x,y,w:3.78,h:2.05,fill:{color:'082335'},line:{color:'082335'}});s.addText(p.name,{x:x+.18,y:y+.25,w:3.35,h:.42,fontFace:'Corbel',fontSize:16,bold:true,color:'FFFFFF',margin:0});s.addText(p.vendors.join(' + '),{x:x+.18,y:y+.82,w:3.35,h:.4,fontFace:'Corbel',fontSize:7.5,color:'12C7C0',margin:0});s.addText(p.value,{x:x+.18,y:y+1.25,w:3.35,h:.55,fontFace:'Corbel',fontSize:8,color:'CDD6E0',margin:0})});
  s=pptx.addSlide('MASTER');addTitle(s,'Cómo funciona el motor','Hechos, señales, inferencia y riesgo separados.');const labels=[['Mercado',24],['Encaje portfolio',16],['Sinergia',14],['Recurrencia',12],['Diferenciación',12],['Analistas',10],['Servicios',7],['Evidencia',5]];labels.forEach((x,i)=>{s.addText(x[0],{x:.7,y:1.8+i*.52,w:2.1,h:.25,fontFace:'Corbel',fontSize:10,color:'082335'});s.addShape(pptx.ShapeType.rect,{x:2.75,y:1.82+i*.52,w:x[1]*.23,h:.18,fill:{color:i<3?'12C7C0':'3195BB'},line:{color:'FFFFFF',transparency:100}});s.addText(`${x[1]}%`,{x:8.6,y:1.78+i*.52,w:.6,h:.25,fontFace:'Corbel',fontSize:9,bold:true,color:'687B8D'})});s.addText('El riesgo pondera solape, presión de canal y falta de evidencia. Si la confianza es baja, el motor recomienda INVESTIGAR antes de elevar inversión.',{x:9.2,y:1.8,w:3.3,h:2,fontFace:'Corbel',fontSize:14,bold:true,color:'113A50',margin:0});
  await pptx.writeFile({fileName:'Westcon_Iberia_Radar_Estrategico_v1.2.pptx'});toast('PowerPoint generado')
}

load().catch(e=>{console.error(e);document.body.innerHTML=`<div style="padding:40px;font-family:Arial">No se pudo cargar la aplicación: ${esc(e.message)}</div>`});
