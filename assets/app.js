const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
const state={data:null,base:null,research:null,selected:null};

const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmtDate=s=>{if(!s)return '—'; const d=new Date(s.length===4?`${s}-01-01`:s); return isNaN(d)?s:new Intl.DateTimeFormat('es-ES',{day:'2-digit',month:'short',year:'numeric'}).format(d)};
const tags=(arr,cls='')=>(arr||[]).slice(0,6).map(x=>`<span class="tag ${cls}">${esc(typeof x==='string'?x:x.name||x.vendor||x.area||x.play)}</span>`).join('')||'<span class="tiny">Sin dato público demostrado</span>';
const prioClass=p=>p.replaceAll(' ','_');
function toast(msg){const t=$('#toast');t.textContent=msg;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2200)}

async function load(){
  const [data,base,research]=await Promise.all([
    fetch('data/vendor_intelligence.json').then(r=>r.json()),
    fetch('data/base.json').then(r=>r.json()),
    fetch('data/research.latest.json').then(r=>r.ok?r.json():{}).catch(()=>({}))
  ]);
  state.data=data;state.base=base;state.research=research;
  initNav();renderAll();
}

function initNav(){
  $$('#tabs button').forEach(b=>b.onclick=()=>switchView(b.dataset.view));
  $$('[data-jump]').forEach(b=>b.onclick=()=>switchView(b.dataset.jump));
  $('#vendorSearch').addEventListener('input',renderVendorTable);
  $('#domainFilter').addEventListener('change',renderVendorTable);
  $('#priorityFilter').addEventListener('change',renderVendorTable);
  $('#btnPdf').onclick=exportPdf;
  $('#btnPptx').onclick=exportPptx;
}
function switchView(id){
  $$('.view').forEach(v=>v.classList.toggle('active',v.id===id));
  $$('#tabs button').forEach(b=>b.classList.toggle('active',b.dataset.view===id));
  window.scrollTo({top:0,behavior:'smooth'});
}

function renderAll(){
  renderKpis();renderBets();renderChanges();renderOverviewVendors();renderFilters();renderVendorTable();renderPlays();renderOverlaps();renderTrends();renderSignals();renderSources();renderResearch();
}
function renderKpis(){
  const d=state.data;
  const k=[
    ['37','Fabricantes','Portfolio FY27 de la presentación'],
    ['$319B','IA EMEA 2026','IDC · +19,2%'],
    ['84%','Plataformización','IDC · prioridad CISO'],
    ['€1,5T+','Tech Europa','Forrester · 2026'],
    ['68%','Negocio recurrente','Westcon FY26 público']
  ];
  $('#marketKpis').innerHTML=k.map(x=>`<div class="kpi"><span>${x[1]}</span><strong>${x[0]}</strong><small>${x[2]}</small></div>`).join('');
}
function renderBets(){
  $('#topBets').innerHTML=state.data.strategyBets.slice(0,4).map(b=>`<article class="bet"><div class="score">${b.score}<small>/100</small></div><h3>${esc(b.name)}</h3><p>${esc(b.why)}</p><b class="action">→ ${esc(b.action)}</b></article>`).join('');
}
function renderChanges(){
  $('#externalChanges').innerHTML=state.data.externalChanges.map(x=>`<div class="time-item"><time>${fmtDate(x.date)}</time><div><b>${esc(x.title)}</b><p>${esc(x.impact)}</p><a class="evidence-link" href="${x.url}" target="_blank" rel="noopener">Fuente pública ↗</a></div></div>`).join('');
}
function channelSummary(v){
  if(!v.channelCompetitors?.length)return '<span class="tiny">Por demostrar</span>';
  const grouped={ES:[],PT:[]};v.channelCompetitors.forEach(x=>grouped[x.country]?.push(x.name));
  return ['ES','PT'].map(c=>grouped[c].length?`<span class="tag channel">${c}: ${esc([...new Set(grouped[c])].join(', '))}</span>`:'').join('')||'<span class="tiny">Por demostrar</span>';
}
function analystSummary(v){
  if(!v.analystSignals?.length)return '<span class="tiny">Sin señal pública específica</span>';
  return v.analystSignals.slice(0,2).map(a=>`<span class="tag analyst">${esc(a.analyst)} · ${esc(a.title.replace('Magic Quadrant for ','').replace('Magic Quadrant para ',''))}</span>`).join('');
}
function internalNames(v){return (v.internalOverlaps||[]).map(x=>x.vendor)}
function synergyNames(v){return [...new Set((v.synergies||[]).flatMap(x=>x.with||[]))]}
function renderOverviewVendors(){
  const rows=[...state.data.vendors].sort((a,b)=>b.priorityScore-a.priorityScore||a.name.localeCompare(b.name)).slice(0,12);
  $('#overviewVendorRows').innerHTML=rows.map(v=>`<tr data-vendor="${esc(v.name)}"><td><span class="vendor-name">${esc(v.name)}</span><span class="tiny">${esc(v.domain)}</span></td><td><span class="priority ${esc(v.priority)}">${esc(v.priority)}</span></td><td>${tags(v.marketCompetitors)}</td><td>${channelSummary(v)}</td><td>${analystSummary(v)}</td><td>${esc(v.action)}</td></tr>`).join('');
  $$('#overviewVendorRows tr').forEach(tr=>tr.onclick=()=>{switchView('fabricantes');selectVendor(tr.dataset.vendor)});
}
function renderFilters(){
  const domains=[...new Set(state.data.vendors.map(v=>v.domain))].sort();
  $('#domainFilter').innerHTML='<option value="all">Todas las áreas</option>'+domains.map(d=>`<option>${esc(d)}</option>`).join('');
}
function filteredVendors(){
  const q=$('#vendorSearch').value.trim().toLowerCase(),d=$('#domainFilter').value,p=$('#priorityFilter').value;
  return state.data.vendors.filter(v=>{
    const blob=[v.name,v.domain,...v.capabilities,...v.marketCompetitors,...internalNames(v),...synergyNames(v),v.action].join(' ').toLowerCase();
    return (!q||blob.includes(q))&&(d==='all'||v.domain===d)&&(p==='all'||v.priority===p);
  }).sort((a,b)=>b.priorityScore-a.priorityScore||a.name.localeCompare(b.name));
}
function renderVendorTable(){
  const rows=filteredVendors();
  $('#vendorRows').innerHTML=rows.map(v=>`<tr data-vendor="${esc(v.name)}" class="${state.selected===v.name?'selected':''}">
  <td><span class="vendor-name">${esc(v.name)}</span><span class="tiny">${v.countries.join(' · ')}</span></td>
  <td>${tags(v.capabilities)}</td>
  <td><span class="priority ${esc(v.priority)}">${esc(v.priority)}</span></td>
  <td>${tags(v.marketCompetitors)}</td>
  <td>${channelSummary(v)}</td>
  <td>${analystSummary(v)}</td>
  <td>${tags(synergyNames(v),'synergy')}</td>
  <td>${tags(internalNames(v),'overlap')}</td>
  <td>${esc(v.action)}</td></tr>`).join('');
  $$('#vendorRows tr').forEach(tr=>tr.onclick=()=>selectVendor(tr.dataset.vendor));
}
function selectVendor(name){
  state.selected=name;renderVendorTable();
  const v=state.data.vendors.find(x=>x.name===name);if(!v)return;
  const chan=(v.channelCompetitors||[]).map(c=>`<div><b>${c.country} · ${esc(c.name)}</b><a class="evidence-link" href="${c.url}" target="_blank" rel="noopener">${esc(c.evidence)} ↗</a></div>`).join('')||'<p>La investigación pública aún no ha demostrado otro mayorista por país. Esto no significa exclusividad.</p>';
  const ana=(v.analystSignals||[]).map(a=>`<div><b>${esc(a.analyst)} · ${fmtDate(a.date)}</b><p>${esc(a.summary)}</p><div>${tags(a.peers)}</div><a class="evidence-link" href="${a.url}" target="_blank" rel="noopener">${esc(a.title)} ↗</a></div>`).join('')||'<p>No hay todavía una evaluación pública suficientemente específica cargada para este fabricante.</p>';
  const syn=(v.synergies||[]).map(s=>`<div><b>${esc(s.play)}</b><p>${esc(s.value)}</p>${tags(s.with,'synergy')}</div>`).join('')||'<p>Sin play multivendor cargado.</p>';
  const ov=(v.internalOverlaps||[]).map(o=>`<span class="tag overlap">${esc(o.vendor)} · ${esc(o.area)}</span>`).join('')||'<span class="tiny">Overlap bajo o no modelado.</span>';
  $('#vendorDetail').innerHTML=`<div class="detail-top"><div class="domain">${esc(v.domain)} · ${v.countries.join(' / ')}</div><h2>${esc(v.name)}</h2><span class="priority ${esc(v.priority)}">${esc(v.priority)}</span><div style="margin-top:8px">${tags(v.capabilities)}</div></div>
  <div class="action-box"><b>ACCIÓN RECOMENDADA</b><p>${esc(v.action)}</p></div>
  <div class="detail-block"><h4>COMPETIDORES DE MERCADO</h4>${tags(v.marketCompetitors)}</div>
  <div class="detail-block"><h4>MAYORISTAS ALTERNATIVOS VERIFICADOS</h4>${chan}</div>
  <div class="detail-block"><h4>LECTURA DE ANALISTAS PÚBLICA</h4>${ana}<p class="tiny">No se reproduce la posición exacta de informes licenciados si no está publicada de forma abierta.</p></div>
  <div class="detail-block"><h4>DIFERENCIAL / QUÉ MIRAR</h4><p>${esc(v.analystDifferential)}</p></div>
  <div class="detail-block"><h4>SINERGIAS</h4>${syn}</div>
  <div class="detail-block"><h4>OVERLAP INTERNO</h4>${ov}</div>`;
  if(window.innerWidth<1200)$('#vendorDetail').scrollIntoView({behavior:'smooth',block:'start'});
}
function renderPlays(){
  const plays=state.base.solutionPlays||[];
  $('#playCards').innerHTML=plays.map((p,i)=>`<article class="play-card"><div class="num">0${i+1}</div><h3>${esc(p.name)}</h3><p>${esc(p.value)}</p><div class="vendor-tags">${p.vendors.map(v=>`<span>${esc(v)}</span>`).join('')}</div></article>`).join('');
}
function renderOverlaps(){
  const counts={};
  state.data.vendors.forEach(v=>(v.internalOverlaps||[]).forEach(o=>{(counts[o.area]??=new Set()).add(v.name);counts[o.area].add(o.vendor)}));
  $('#overlapMap').innerHTML=Object.entries(counts).sort((a,b)=>b[1].size-a[1].size).map(([area,set])=>`<article class="overlap-card"><h3>${esc(area)}</h3><div class="overlap-line">${[...set].map(x=>`<span class="tag overlap">${esc(x)}</span>`).join('')}</div><p>Requiere criterios de cualificación por caso de uso para evitar canibalización y discursos contradictorios.</p></article>`).join('');
}
function renderTrends(){
  $('#trendCards').innerHTML=state.data.strategyBets.map(t=>`<article class="trend-card"><div class="trend-score">${t.score}<span class="tiny">/100 · inferencia</span></div><div class="meter"><i style="--w:${t.score}%"></i></div><h3>${esc(t.name)}</h3><p>${esc(t.why)}</p><b>→ ${esc(t.action)}</b></article>`).join('');
}
function renderSignals(){
  $('#signalCards').innerHTML=state.data.marketSignals.map(s=>`<article class="signal-card"><span>${esc(s.analyst)} · ${fmtDate(s.date)}</span><strong>${esc(s.metric)}</strong><h3>${esc(s.label)}</h3><p>${esc(s.detail)}</p><a class="evidence-link" href="${s.url}" target="_blank" rel="noopener">Fuente ↗</a></article>`).join('');
}
function renderSources(){
  $('#sourceRows').innerHTML=[...state.data.sources].sort((a,b)=>String(b.date).localeCompare(String(a.date))).map(s=>`<tr><td>${fmtDate(s.date)}</td><td>${esc(s.type)}</td><td><b>${esc(s.source)}</b></td><td>${esc(s.title)}</td><td><a class="evidence-link" href="${s.url}" target="_blank" rel="noopener">Abrir ↗</a></td></tr>`).join('');
}
function renderResearch(){
  const r=state.research||{};
  $('#researchSummary').textContent=`Modo: ${r.mode||'baseline público'}\nÚltima generación: ${r.generatedAt||'no ejecutado todavía'}\nQueries: ${r.queryCount||0}\nEvidencias dinámicas: ${r.evidence?.length||0}\nBrave opcional: ${r.braveEnabled?'sí':'no'}\n\nRegla: discovery ≠ evidencia ejecutiva.\nSe valida contra fuente primaria/pública.`;
}

function reportHtml(){
  const d=state.data, top=[...d.vendors].sort((a,b)=>b.priorityScore-a.priorityScore).slice(0,15);
  return `<div class="report-export"><div style="border-top:8px solid #f09e0d;padding-top:18px"><div style="font-size:10px;color:#3195bb;font-weight:800">WESTCON IBERIA · FY27–FY30</div><h1>Radar Estratégico Tecnológico</h1><p class="note">Edición ejecutiva basada exclusivamente en inteligencia pública + portfolio de la presentación FY27 facilitada.</p></div>
  <div class="r-kpis"><div class="r-kpi"><span>Portfolio</span><b>37</b>fabricantes</div><div class="r-kpi"><span>IA EMEA 2026</span><b>$319B</b>IDC</div><div class="r-kpi"><span>Plataformización</span><b>84%</b>IDC</div><div class="r-kpi"><span>Europa 2026</span><b>€1,5T+</b>Forrester</div></div>
  <h2>Prioridades estratégicas</h2>${d.strategyBets.map(x=>`<h3>${x.score}/100 · ${esc(x.name)}</h3><p>${esc(x.why)} <b>Acción:</b> ${esc(x.action)}</p>`).join('')}
  <h2>Fabricantes prioritarios</h2><table><thead><tr><th>Fabricante</th><th>Prioridad</th><th>Competencia</th><th>Canal alternativo</th><th>Acción</th></tr></thead><tbody>${top.map(v=>`<tr><td>${esc(v.name)}</td><td>${esc(v.priority)}</td><td>${esc(v.marketCompetitors.slice(0,4).join(', '))}</td><td>${esc((v.channelCompetitors||[]).map(x=>`${x.country}:${x.name}`).join(' · ')||'Por demostrar')}</td><td>${esc(v.action)}</td></tr>`).join('')}</tbody></table>
  <h2>Sinergias multi-vendor</h2>${(state.base.solutionPlays||[]).map(p=>`<h3>${esc(p.name)}</h3><p><b>${esc(p.vendors.join(' + '))}</b><br>${esc(p.value)}</p>`).join('')}
  <h2>Metodología</h2><p>Se separan hechos, señales de mercado e inferencias. Las fuentes públicas de Gartner, IDC y Forrester se usan únicamente en el alcance visible públicamente. No se reconstruyen contenidos licenciados. Las relaciones de canal se verifican por país cuando es posible; EMEA no se extrapola automáticamente a Iberia.</p></div>`;
}
async function exportPdf(){
  if(!window.html2pdf){toast('Librería PDF no disponible');return}
  const report=$('#report');report.innerHTML=reportHtml();report.style.display='block';
  await html2pdf().set({margin:8,filename:'Westcon_Iberia_Radar_Estrategico_v1.1.pdf',image:{type:'jpeg',quality:.96},html2canvas:{scale:1.5,useCORS:true},jsPDF:{unit:'mm',format:'a4',orientation:'portrait'},pagebreak:{mode:['css','legacy']}}).from(report.firstElementChild).save();
  report.style.display='none';toast('PDF generado');
}
async function exportPptx(){
  if(!window.PptxGenJS){toast('Librería PowerPoint no disponible');return}
  const pptx=new PptxGenJS();pptx.layout='LAYOUT_WIDE';pptx.author='Westcon Iberia Strategy Studio';pptx.subject='Radar Estratégico Tecnológico';pptx.title='Westcon Iberia · Radar Estratégico';pptx.company='Westcon-Comstor';
  pptx.defineSlideMaster({title:'MASTER',background:{color:'FFFFFF'},objects:[{rect:{x:0,y:0,w:13.333,h:.18,fill:{color:'F09E0D'},line:{color:'F09E0D'}}},{text:{text:'WESTCON IBERIA · RADAR ESTRATÉGICO',options:{x:.55,y:.25,w:6,h:.25,fontFace:'Corbel',fontSize:9,bold:true,color:'3195BB'}}},{text:{text:'Inteligencia pública · FY27–FY30',options:{x:9.7,y:.25,w:3.0,h:.25,fontFace:'Corbel',fontSize:8,color:'687B8D',align:'right'}}}],slideNumber:{x:12.75,y:7.12,color:'687B8D',fontSize:8}});
  const addTitle=(s,t,sub='')=>{s.addText(t,{x:.55,y:.65,w:12.2,h:.55,fontFace:'Corbel',fontSize:27,bold:true,color:'082335',margin:0}); if(sub)s.addText(sub,{x:.55,y:1.24,w:11.9,h:.4,fontFace:'Corbel',fontSize:11,color:'687B8D',margin:0});};
  let s=pptx.addSlide('MASTER');addTitle(s,'Una estrategia que se entiende de un vistazo','Portfolio, competencia, canal, analistas, sinergias, solapes y acciones recomendadas.');
  const k=[['37','fabricantes'],['$319B','IA EMEA 2026'],['84%','plataformización'],['€1,5T+','tech Europa 2026']];k.forEach((x,i)=>{s.addShape(pptx.ShapeType.rect,{x:.55+i*3.05,y:2.0,w:2.8,h:1.15,fill:{color:i%2?'F7F9FA':'F2F7F8'},line:{color:'DBE4E9'}});s.addText(x[0],{x:.75+i*3.05,y:2.2,w:2.3,h:.42,fontFace:'Corbel',fontSize:24,bold:true,color:'082335'});s.addText(x[1],{x:.75+i*3.05,y:2.68,w:2.3,h:.24,fontFace:'Corbel',fontSize:9,color:'687B8D'});});
  s.addText('Tesis',{x:.55,y:3.55,w:1.2,h:.3,fontFace:'Corbel',fontSize:10,bold:true,color:'E5007D'});s.addText('La ventaja no está en tener más fabricantes, sino en convertir el portfolio en arquitecturas repetibles, servicios, evidencia y lifecycle que el partner no pueda reproducir fácilmente.',{x:.55,y:3.95,w:11.8,h:1.1,fontFace:'Corbel',fontSize:21,bold:true,color:'113A50',breakLine:false,margin:0});
  s.addText('Solo información pública verificable + portfolio FY27 facilitado. Sin datos internos.',{x:.55,y:6.4,w:11.5,h:.35,fontFace:'Corbel',fontSize:10,color:'687B8D'});

  s=pptx.addSlide('MASTER');addTitle(s,'Prioridades estratégicas','Puntuación inferida a partir de señales públicas y encaje del portfolio.');
  state.data.strategyBets.slice(0,8).forEach((b,i)=>{const col=i%2,row=Math.floor(i/2);const x=.55+col*6.15,y=1.75+row*1.3;s.addShape(pptx.ShapeType.rect,{x,y,w:5.85,h:1.08,fill:{color:'F8FAFB'},line:{color:'DBE4E9'}});s.addText(String(b.score),{x:x+.15,y:y+.12,w:.65,h:.34,fontFace:'Corbel',fontSize:20,bold:true,color:i<3?'169F82':'3195BB'});s.addText(b.name,{x:x+.9,y:y+.12,w:4.7,h:.28,fontFace:'Corbel',fontSize:13,bold:true,color:'082335'});s.addText(b.action,{x:x+.9,y:y+.46,w:4.7,h:.42,fontFace:'Corbel',fontSize:8.5,color:'687B8D',margin:0});});

  s=pptx.addSlide('MASTER');addTitle(s,'Fabricantes prioritarios','Competidores, canal alternativo y acción recomendada.');
  const top=[...state.data.vendors].sort((a,b)=>b.priorityScore-a.priorityScore).slice(0,14);
  const rows=[['Fabricante','Prioridad','Competidores','Mayoristas alternativos','Acción'],...top.map(v=>[v.name,v.priority,v.marketCompetitors.slice(0,3).join(', '),(v.channelCompetitors||[]).map(x=>`${x.country}:${x.name}`).join(' · ')||'Por demostrar',v.action])];
  s.addTable(rows,{x:.45,y:1.62,w:12.45,h:5.2,border:{type:'solid',color:'D9E2E7',pt:.6},fontFace:'Corbel',fontSize:7.2,color:'233746',fill:'FFFFFF',rowH:.34,margin:.04,autoFit:false,colW:[1.55,1.0,2.45,2.1,5.35],bold:false,breakLine:false});

  s=pptx.addSlide('MASTER');addTitle(s,'Sinergias que debemos monetizar','De catálogo de vendors a arquitecturas repetibles.');
  (state.base.solutionPlays||[]).slice(0,6).forEach((p,i)=>{const col=i%3,row=Math.floor(i/3);const x=.55+col*4.12,y=1.75+row*2.42;s.addShape(pptx.ShapeType.rect,{x,y,w:3.78,h:2.05,fill:{color:'082335'},line:{color:'082335'}});s.addText(`0${i+1}`,{x:x+.18,y:y+.16,w:.45,h:.25,fontFace:'Corbel',fontSize:9,bold:true,color:'F09E0D'});s.addText(p.name,{x:x+.18,y:y+.48,w:3.35,h:.42,fontFace:'Corbel',fontSize:16,bold:true,color:'FFFFFF',margin:0});s.addText(p.vendors.join(' + '),{x:x+.18,y:y+.98,w:3.35,h:.4,fontFace:'Corbel',fontSize:7.8,color:'12C7C0',margin:0});s.addText(p.value,{x:x+.18,y:y+1.42,w:3.35,h:.43,fontFace:'Corbel',fontSize:8,color:'CDD6E0',margin:0});});

  s=pptx.addSlide('MASTER');addTitle(s,'Señales de mercado que sostienen la estrategia','Datos públicos: IDC, Forrester y Gartner.');
  state.data.marketSignals.forEach((m,i)=>{const x=.55+i*2.48;s.addShape(pptx.ShapeType.rect,{x,y:1.8,w:2.22,h:2.25,fill:{color:i%2?'113A50':'082335'},line:{color:i%2?'113A50':'082335'}});s.addText(m.analyst,{x:x+.16,y:2.0,w:1.8,h:.22,fontFace:'Corbel',fontSize:8,bold:true,color:'12C7C0'});s.addText(m.metric,{x:x+.16,y:2.35,w:1.85,h:.5,fontFace:'Corbel',fontSize:25,bold:true,color:'F09E0D'});s.addText(m.label,{x:x+.16,y:2.92,w:1.9,h:.35,fontFace:'Corbel',fontSize:10,bold:true,color:'FFFFFF',margin:0});s.addText(m.detail,{x:x+.16,y:3.35,w:1.88,h:.48,fontFace:'Corbel',fontSize:7.5,color:'CDD6E0',margin:0});});
  s.addText('Nota metodológica: no se reproducen posiciones o contenidos de research licenciado salvo que estén publicados de forma abierta. Las puntuaciones estratégicas son inferencias propias.',{x:.55,y:5.0,w:11.8,h:.45,fontFace:'Corbel',fontSize:9,color:'687B8D'});

  await pptx.writeFile({fileName:'Westcon_Iberia_Radar_Estrategico_v1.1.pptx'});toast('PowerPoint generado');
}

load().catch(e=>{console.error(e);document.body.innerHTML=`<div style="padding:40px;font-family:Arial">No se pudo cargar la aplicación: ${esc(e.message)}</div>`});
