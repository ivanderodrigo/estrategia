(() => {
  'use strict';
  const state = {data:null, view:'fabricantes', fontScale:Number(localStorage.getItem('westcon-font-scale')||1), sort:{}, columnOrder:{}, dragCol:null};
  const $ = s => document.querySelector(s);
  const $$ = s => [...document.querySelectorAll(s)];
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const norm = v => String(v ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  const hasValue = v => !(v == null || v === '' || v === false || (Array.isArray(v) && !v.length) || (typeof v === 'object' && !Array.isArray(v) && !Object.keys(v).length));
  const toast = msg => { const el=$('#toast'); if(!el) return; el.textContent=msg; el.classList.add('show'); clearTimeout(el._t); el._t=setTimeout(()=>el.classList.remove('show'),2600); };

  async function load(){
    const res = await fetch('data/v38/intelligence.json', {cache:'no-store'});
    if(!res.ok) throw new Error(`No se pudo cargar data/v38/intelligence.json (${res.status})`);
    state.data = await res.json();
    bind();
    renderAll();
  }

  function bind(){
    $$('#tabs [data-view]').forEach(btn => btn.addEventListener('click', () => switchView(btn.dataset.view)));
    $('#navToggle')?.addEventListener('click', () => { const nav=$('#tabs'); const open=nav.classList.toggle('open'); $('#navToggle').setAttribute('aria-expanded', String(open)); });
    $('#manufacturerSearch')?.addEventListener('input', renderManufacturers);
    $('#integratorSearch')?.addEventListener('input', renderIntegrators);
    $('#integratorScope')?.addEventListener('change', renderIntegrators);
    $('#integratorVendor')?.addEventListener('change', renderIntegrators);
    $('#distributorSearch')?.addEventListener('input', renderDistributors);
    $('#distributorScope')?.addEventListener('change', renderDistributors);
    $('#trendSearch')?.addEventListener('input', renderTrends);
    $('#architectureSearch')?.addEventListener('input', renderArchitectures);
    $('#btnSources')?.addEventListener('click', () => openModal('sourceModal'));
    $('#btnExport')?.addEventListener('click', () => openModal('exportModal'));
    $$('[data-close]').forEach(btn => btn.addEventListener('click', () => closeModal(btn.dataset.close)));
    $$('.modal').forEach(modal => modal.addEventListener('click', e => { if(e.target===modal) closeModal(modal.id); }));
    document.addEventListener('keydown', e => { if(e.key==='Escape') $$('.modal.open').forEach(m=>closeModal(m.id)); });
    $('#sourceSearch')?.addEventListener('input', renderSourceCatalog);
    $('#exportPdf')?.addEventListener('click', exportPdf);
    $('#exportPptx')?.addEventListener('click', exportPptx);
    $('#textSmaller')?.addEventListener('click', () => changeTextScale(-0.1));
    $('#textLarger')?.addEventListener('click', () => changeTextScale(0.1));
    $('#textReset')?.addEventListener('click', resetTextScale);
    document.addEventListener('click', e=>{
      const more=e.target.closest('[data-more-tags]'); if(more){ const box=more.closest('.tag-list'); box?.classList.toggle('expanded'); more.textContent=box?.classList.contains('expanded')?'Mostrar menos':more.dataset.label; }
      const moreText=e.target.closest('[data-more-text]'); if(moreText){ const box=moreText.closest('.scalar-compact'); box?.classList.toggle('expanded'); moreText.textContent=box?.classList.contains('expanded')?'Ver menos':'Ver más'; e.stopPropagation(); }
      const legend=e.target.closest('[data-trend-index]'); if(legend){ const id=legend.dataset.trendIndex; $$('.trend-loop-node').forEach(n=>n.classList.toggle('active',n.dataset.trendIndex===id)); }
      const actorLegend=e.target.closest('[data-actor-index]'); if(actorLegend){ const id=actorLegend.dataset.actorIndex; $$('.actor-point').forEach(n=>n.classList.toggle('active',n.dataset.actorIndex===id)); }
      const th=e.target.closest('th[data-col]'); if(th && !e.target.closest('.help-icon')){ toggleSort(th.closest('table')?.dataset.view, th.dataset.col); }
    });
    document.addEventListener('dragstart', e=>{ const th=e.target.closest('th[data-col]'); if(th){state.dragCol=th.dataset.col; e.dataTransfer.effectAllowed='move';}});
    document.addEventListener('dragover', e=>{if(e.target.closest('th[data-col]')) e.preventDefault();});
    document.addEventListener('drop', e=>{ const th=e.target.closest('th[data-col]'); if(!th||!state.dragCol)return; e.preventDefault(); reorderColumn(th.closest('table')?.dataset.view,state.dragCol,th.dataset.col); state.dragCol=null;});
    applyTextScale();
  }

  function applyTextScale(){
    state.fontScale=Math.max(0.9,Math.min(1.5,Number(state.fontScale)||1));
    document.documentElement.style.setProperty('--font-scale', String(state.fontScale));
    const pct=$('#textReset'); if(pct) pct.textContent=`${Math.round(state.fontScale*100)}%`;
    localStorage.setItem('westcon-font-scale', String(state.fontScale));
  }
  function changeTextScale(delta){ state.fontScale=Math.round((state.fontScale+delta)*10)/10; applyTextScale(); }
  function resetTextScale(){ state.fontScale=1; applyTextScale(); }

  function populateIntegratorVendorFilter(){
    const sel=$('#integratorVendor'); if(!sel||!state.data) return;
    const current=sel.value||'all';
    const names=(state.data.manufacturers||[]).map(x=>x.name).filter(Boolean).sort((a,b)=>a.localeCompare(b,'es'));
    sel.innerHTML='<option value="all">Todos los fabricantes Westcon</option>'+names.map(n=>`<option value="${esc(n)}">${esc(n)}</option>`).join('');
    if([...sel.options].some(o=>o.value===current)) sel.value=current;
  }

  function switchView(id){
    state.view=id;
    $$('.view').forEach(v=>v.classList.toggle('active',v.id===id));
    $$('#tabs [data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===id));
    $('#tabs')?.classList.remove('open');
    $('#navToggle')?.setAttribute('aria-expanded','false');
    window.scrollTo({top:0,behavior:'smooth'});
  }
  function openModal(id){ const el=$('#'+id); if(el){ el.classList.add('open'); el.setAttribute('aria-hidden','false'); } }
  function closeModal(id){ const el=$('#'+id); if(el){ el.classList.remove('open'); el.setAttribute('aria-hidden','true'); } }

  function valueText(value){
    if(Array.isArray(value)) return value.map(v => typeof v==='object' ? JSON.stringify(v) : String(v)).join(' · ');
    if(typeof value==='object') return JSON.stringify(value);
    return String(value ?? '');
  }
  function rowBlob(row){ return norm([row.name, ...Object.values(row.fields||{}).map(f=>valueText(f.value))].join(' ')); }
  function confidencePct(x){const n=Number(x??0);return Math.round((n<=1?n*100:n));}
  function bandLabel(b){return b==='high'?'Alta':b==='medium'?'Media':'Baja';}
  function sourceItem(ev, score, band, reason){
    const title=esc(ev.title||ev.source||'Evidencia'), source=esc(ev.source||'Fuente pública');
    const fresh=ev.freshness_status?`vigencia: ${ev.freshness_status}${Number.isFinite(Number(ev.age_days))?` · ${ev.age_days} días`:''}`:''; const meta=[ev.date,ev.type,ev.country||ev.scope,ev.method,ev.source_grade,fresh].filter(Boolean).map(esc).join(' · ');
    return `<div class="source-item"><div class="source-confidence ${esc(band||'low')}"><b>${confidencePct(score)}%</b><span>${esc(bandLabel(band))}</span></div><div><b>${source}</b><span>${title}</span>${ev.description?`<p>${esc(ev.description)}</p>`:''}${meta?`<small>${meta}</small>`:''}${reason?`<small class="confidence-reason">${esc(reason)}</small>`:''}${ev.revalidation?`<small>${esc(ev.revalidation)}</small>`:''}${ev.note?`<small>${esc(ev.note)}</small>`:''}${ev.url?`<a href="${esc(ev.url)}" target="_blank" rel="noopener">Abrir fuente ↗</a>`:''}</div></div>`;
  }
  function traceable(field, inner, item=null){
    const evidence=(item?.evidence||field?.evidence||[]).slice(0,8);
    const score=item?.confidence ?? field?.confidence ?? 0.66;
    const band=item?.confidence_band || field?.confidence_band || (score>=.8?'high':score>=.6?'medium':'low');
    const reason=item?.confidence_reason || field?.confidence_reason || '';
    const qualifier=item?.qualifier||field?.qualifier;
    return `<div class="traceable" tabindex="0"><div class="trace-value">${inner}</div><span class="trace-mark confidence-dot ${esc(band)}" title="Confianza ${confidencePct(score)}%">i</span><div class="trace-popover"><strong>TRAZABILIDAD DEL DATO</strong><div class="confidence-head ${esc(band)}"><b>${confidencePct(score)}%</b><span>Confianza ${esc(bandLabel(band).toLowerCase())}</span></div>${reason?`<p class="confidence-explain">${esc(reason)}</p>`:''}${qualifier?`<span class="qualifier">${esc(qualifier)}</span>`:''}${evidence.map(ev=>sourceItem(ev,score,band,reason)).join('')}</div></div>`;
  }
  function itemFor(field,value,index){
    const items=field?.items||[]; return items[index]||items.find(x=>String(x.value)===String(value))||null;
  }
  function tagHtml(field,value,index,extra=''){
    const item=itemFor(field,value,index), score=item?.confidence??field?.confidence??.66, band=item?.confidence_band||field?.confidence_band||(score>=.8?'high':score>=.6?'medium':'low');
    const raw=typeof value==='object'?JSON.stringify(value):String(value??'');
    return traceable(field,`<span class="tag confidence-tag ${esc(band)} ${extra}"><span class="tag-label" title="${esc(raw)}">${esc(raw)}</span><small>${confidencePct(score)}%</small></span>`,item);
  }
  function compactScalar(value, max=150){
    const raw=String(value??'');
    if(raw.length<=max) return esc(raw);
    const cut=raw.slice(0,max).replace(/\s+\S*$/,'').trim();
    return `<span class="scalar-compact"><span class="scalar-preview">${esc(cut)}…</span><span class="scalar-full">${esc(raw)}</span><button type="button" class="more-text" data-more-text>Ver más</button></span>`;
  }
  function listLimit(value, context='table'){
    if(context!=='table') return 6;
    const long=value.filter(v=>String(typeof v==='object'?JSON.stringify(v):v).length>34).length;
    if(value.length>=5 || long>=1) return 2;
    return 3;
  }
  function renderValue(field, limit=null, context='table'){
    const value=field?.value;
    if(Array.isArray(value)){
      if(value.length&&typeof value[0]==='object'&&value[0].layer){
        return `<div class="layer-list">${value.map(x=>{const layerField={...field,items:x.vendor_items||[]};const vendors=(x.vendors||[]),lim=limit??listLimit(vendors,context);const tags=vendors.map((v,i)=>`<span class="tag-entry ${i>=lim?'tag-overflow':''}">${tagHtml(layerField,v,i,'emphasis')}</span>`).join('');const more=vendors.length>lim?`<button type="button" class="more-tags" data-more-tags data-label="… +${vendors.length-lim}">… +${vendors.length-lim}</button>`:'';return `<div class="layer"><b>${esc(x.layer)}</b><div class="tag-list">${tags}${more}</div>${x.note?`<small>${compactScalar(x.note,120)}</small>`:''}</div>`;}).join('')}</div>`;
      }
      const lim=limit??listLimit(value,context);
      const tags=value.map((v,i)=>`<span class="tag-entry ${i>=lim?'tag-overflow':''}">${tagHtml(field,v,i)}</span>`).join('');
      const more=value.length>lim?`<button type="button" class="more-tags" data-more-tags data-label="… +${value.length-lim}">… +${value.length-lim}</button>`:'';
      return `<div class="tag-list">${tags}${more}</div>`;
    }
    return traceable(field,compactScalar(value,context==='table'?110:300));
  }
  function headerCell(col, view){
    const sort=state.sort[view], arrow=sort?.col===col.id?(sort.dir===1?' ↑':' ↓'):'';
    return `<th draggable="true" data-col="${esc(col.id)}" class="col-${esc(col.id)}" title="Arrastrar para mover · clic para ordenar"><span class="drag-grip">⋮⋮</span><span class="help-wrap"><span>${esc(col.label)}${arrow}</span>${col.clarify?`<button class="help-icon" type="button" aria-label="Aclaración de ${esc(col.label)}">?</button><span class="help-tip">${esc(col.help||'')}</span>`:''}</span></th>`;
  }
  function activeColumns(schema, rows, view){
    let cols=schema.filter(col=>{
      const populated=rows.filter(row=>hasValue(row.fields?.[col.id]?.value)).length;
      if(!populated) return false;
      if(view==='cards') return true;
      // Evita columnas casi vacías: siguen en la cola automática de investigación
      // y reaparecen cuando alcanzan cobertura suficiente.
      const minimum=rows.length>=50?Math.max(5,Math.ceil(rows.length*.08)):1;
      return populated>=minimum;
    });
    const order=state.columnOrder[view]||JSON.parse(localStorage.getItem(`westcon-cols-${view}`)||'null');
    if(order){state.columnOrder[view]=order; cols.sort((a,b)=>{let ai=order.indexOf(a.id),bi=order.indexOf(b.id);if(ai<0)ai=999;if(bi<0)bi=999;return ai-bi;});}
    return cols;
  }
  function sortedRows(rows,view){const s=state.sort[view];if(!s)return rows;return [...rows].sort((a,b)=>valueText(a.fields?.[s.col]?.value??a.name).localeCompare(valueText(b.fields?.[s.col]?.value??b.name),'es',{numeric:true})*s.dir);}
  function toggleSort(view,col){if(!view)return;const cur=state.sort[view];state.sort[view]={col,dir:cur?.col===col?-cur.dir:1};renderCurrent(view);}
  function reorderColumn(view,from,to){if(!view||from===to)return;const schema=state.data.schemas[view]||[];let order=(state.columnOrder[view]||schema.map(x=>x.id)).filter(x=>schema.some(c=>c.id===x));const a=order.indexOf(from),b=order.indexOf(to);if(a<0||b<0)return;order.splice(b,0,order.splice(a,1)[0]);state.columnOrder[view]=order;localStorage.setItem(`westcon-cols-${view}`,JSON.stringify(order));renderCurrent(view);}
  function renderCurrent(view){({manufacturers:renderManufacturers,integrators:renderIntegrators,distributors:renderDistributors}[view]||(()=>{}))();}
  function tableHtml(rows, schema, emptyText, view){
    if(!rows.length)return `<div class="empty-state">${esc(emptyText)}</div>`;
    const cols=activeColumns(schema,rows,view), ordered=sortedRows(rows,view);
    return `<table data-view="${esc(view)}" class="data-table"><thead><tr><th class="entity-head name-col">Entidad</th>${cols.map(c=>headerCell(c,view)).join('')}</tr></thead><tbody>${ordered.map(row=>{const identity={value:row.name,evidence:row.evidence||[],confidence:.95,confidence_band:'high'};return `<tr><td class="name-cell name-col">${traceable(identity,`<b>${esc(row.name)}</b><small>Identidad trazable</small>`)}</td>${cols.map(col=>{const f=row.fields?.[col.id];return `<td class="col-${esc(col.id)}">${f&&hasValue(f.value)?renderValue(f,null,'table'):'<span class="research-gap">En investigación</span>'}</td>`}).join('')}</tr>`}).join('')}</tbody></table>`;
  }
  function scopeMatch(row, scope){
    if(scope==='all') return true;
    const f=row.fields?.scope?.value;
    return norm(f).includes(norm(scope));
  }
  function setCount(id, shown, total, noun){ const el=$(id); if(el) el.innerHTML=`<b>${shown}</b><span>${esc(noun)}${shown!==total?` · ${total} totales`:''}</span>`; }

  function renderManufacturers(){
    const q=norm($('#manufacturerSearch')?.value);
    const all=state.data.manufacturers||[];
    const rows=all.filter(r=>!q||rowBlob(r).includes(q));
    $('#manufacturerTable').innerHTML=tableHtml(rows,state.data.schemas.manufacturers,'No hay fabricantes con esos filtros.','manufacturers');
    setCount('#manufacturerCount',rows.length,all.length,'fabricantes');
  }
  function renderIntegrators(){
    const q=norm($('#integratorSearch')?.value), scope=$('#integratorScope')?.value||'all', vendor=$('#integratorVendor')?.value||'all';
    const all=state.data.integrators||[];
    const rows=all.filter(r=>{
      const vendorText=norm(valueText(r.fields?.vendor_relations?.value||''));
      const vendorOk=vendor==='all'||vendorText.includes(norm(vendor));
      return (!q||rowBlob(r).includes(q))&&scopeMatch(r,scope)&&vendorOk;
    });
    $('#integratorTable').innerHTML=tableHtml(rows,state.data.schemas.integrators,'No hay partners/integradores con esos filtros.','integrators');
    setCount('#integratorCount',rows.length,all.length,'partners / integradores');
  }
  function renderDistributors(){
    const q=norm($('#distributorSearch')?.value), scope=$('#distributorScope')?.value||'all';
    const all=state.data.distributors||[];
    const rows=all.filter(r=>(!q||rowBlob(r).includes(q))&&scopeMatch(r,scope));
    $('#distributorTable').innerHTML=tableHtml(rows,state.data.schemas.distributors,'No hay mayoristas con esos filtros.','distributors');
    setCount('#distributorCount',rows.length,all.length,'mayoristas competidores');
  }

  function cardField(col,f){if(!f||!hasValue(f.value))return '';const help=col.clarify?`<span class="help-wrap card-help"><span>${esc(col.label)}</span><button class="help-icon" type="button" aria-label="Aclaración de ${esc(col.label)}">?</button><span class="help-tip">${esc(col.help||'')}</span></span>`:esc(col.label);return `<div class="card-field"><label>${help}</label>${renderValue(f,6,'card')}</div>`;}
  function cardGrid(rows, schema, forceAll=false){
    const cols=forceAll?schema:activeColumns(schema,rows,'cards');
    return rows.map(row=>`<article class="intel-card"><div class="eyebrow">INTELIGENCIA TRAZABLE</div><div class="card-title">${traceable({value:row.name,evidence:row.evidence||[],confidence:.9,confidence_band:'high'},`<h3>${esc(row.name)}</h3>`)}</div>${cols.map(c=>cardField(c,row.fields?.[c.id])||`<div class="card-field"><label>${esc(c.label)}</label><span class="research-gap">En investigación</span></div>`).join('')}</article>`).join('');
  }
  function renderTrends(){
    const q=norm($('#trendSearch')?.value), all=state.data.trends||[], rows=all.filter(r=>!q||rowBlob(r).includes(q));
    $('#trendGrid').innerHTML=cardGrid(rows,state.data.schemas.trends,true)||'<div class="empty-state">No hay tendencias con ese filtro.</div>';
    setCount('#trendCount',rows.length,all.length,'tendencias'); renderTrendAnalytics(rows);
  }
  function trendActorData(limit=32){
    const actors=new Map(), portfolio=new Set((state.data.manufacturers||[]).map(x=>norm(x.name)));
    (state.data.trends||[]).forEach(t=>{['market_players','westcon_vendors'].forEach(fid=>{const f=t.fields?.[fid];(f?.items||[]).forEach(it=>{const n=String(it.value||'').split(' · ')[0],k=norm(n);if(!k||n.startsWith('Panorama'))return;const a=actors.get(k)||{name:n,trends:new Set(),evidence:0,portfolio:portfolio.has(k)};a.trends.add(t.name);a.evidence+=Math.max(1,(it.evidence||[]).length);a.portfolio=a.portfolio||fid==='westcon_vendors';actors.set(k,a);});});});
    return [...actors.values()].sort((a,b)=>(b.trends.size*10+b.evidence)-(a.trends.size*10+a.evidence)).slice(0,limit);
  }

  function stageLabel(maturity){
    const m=+maturity||0; return m<25?'Emergente':m<50?'Aceleración':m<75?'Escala':'Consolidación';
  }
  function trendLoopPoint(a){
    const m=Math.max(2,Math.min(98,+a.maturity||0)),t=m/100,angle=(-205+t*300)*Math.PI/180;
    const rx=210,ry=105,cx=245,cy=135,momentum=(+a.momentum||50)-50,nudge=Math.max(-16,Math.min(16,momentum*.18));
    return {x:cx+(rx+nudge)*Math.cos(angle),y:cy+(ry+nudge*.35)*Math.sin(angle)};
  }
  function renderTrendAnalytics(rows){
    const life=$('#trendLifecycleChart'),map=$('#vendorTrendMap');if(!life||!map)return;
    const usable=rows.filter(r=>r.analytics&&Number.isFinite(Number(r.analytics.maturity)));
    const nodes=usable.map((r,i)=>{const a=r.analytics||{},p=trendLoopPoint(a),sz=26+Math.round((+a.buyer_urgency||50)/12);return `<button class="trend-loop-node" data-trend-index="${i+1}" style="left:${p.x}px;top:${p.y}px;width:${sz}px;height:${sz}px" title="${esc(r.name)} · madurez ${a.maturity}% · momentum ${a.momentum}% · urgencia ${a.buyer_urgency}%"><b>${i+1}</b></button>`}).join('');
    const legend=usable.map((r,i)=>{const a=r.analytics||{};return `<button class="trend-legend-item" data-trend-index="${i+1}"><span class="trend-index">${i+1}</span><span class="trend-legend-name">${esc(r.name)}</span><span class="trend-stage">${stageLabel(a.maturity)}</span><span class="mini-meter"><i style="width:${Math.max(5,Math.min(100,+a.momentum||0))}%"></i></span></button>`}).join('');
    life.innerHTML=`<div class="chart-title"><div><span>WESTCON TREND LOOP</span><h3>Madurez, momentum y urgencia de compra</h3><p>Síntesis propia y trazable. Los números mantienen el gráfico limpio; la leyenda conserva todos los nombres completos.</p></div><div class="chart-legend"><i class="portfolio-dot"></i> tamaño = urgencia comprador</div></div><div class="trend-loop-layout"><div class="trend-loop-canvas"><svg viewBox="0 0 490 270" aria-hidden="true"><defs><linearGradient id="trendLoopGradient" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#12c7c0"/><stop offset="46%" stop-color="#3195bb"/><stop offset="76%" stop-color="#f09e0d"/><stop offset="100%" stop-color="#e5007d"/></linearGradient></defs><path class="loop-track-shadow" d="M45 188 C28 95 98 25 210 33 C338 42 456 105 440 189 C426 257 319 253 253 213 C190 175 139 150 99 173 C62 194 80 231 134 235"/><path class="loop-track" d="M45 188 C28 95 98 25 210 33 C338 42 456 105 440 189 C426 257 319 253 253 213 C190 175 139 150 99 173 C62 194 80 231 134 235"/><text x="37" y="211">EMERGENTE</text><text x="125" y="48">ACELERACIÓN</text><text x="321" y="64">ESCALA</text><text x="354" y="232">CONSOLIDACIÓN</text></svg>${nodes}</div><div class="trend-loop-legend">${legend}</div></div>`;
    const actors=trendActorData(26),maxT=Math.max(1,...actors.map(a=>a.trends.size)),maxE=Math.max(1,...actors.map(a=>a.evidence));
    const points=actors.map((a,i)=>{const x=8+84*(a.trends.size/maxT),y=91-80*(a.evidence/maxE),cls=a.portfolio?'westcon':'external';return `<button class="actor-point ${cls}" data-actor-index="${i+1}" style="left:${x}%;top:${y}%" title="${esc(a.name)} · ${a.trends.size} tendencias · ${a.evidence} evidencias"><b>${i+1}</b></button>`}).join('');
    const actorLegend=actors.map((a,i)=>`<button class="actor-legend-item" data-actor-index="${i+1}"><span class="actor-index ${a.portfolio?'westcon':'external'}">${i+1}</span><span class="actor-name">${esc(a.name)}</span><span class="actor-meta">${a.trends.size} tendencias · ${a.evidence} evid.</span></button>`).join('');
    map.innerHTML=`<div class="chart-title"><div><span>WESTCON VENDOR ARENA</span><h3>Fabricantes × tendencias × evidencia pública</h3><p>Relaciona portfolio Westcon y otros actores sin atribuir liderazgo propietario. Números en la matriz y nombres completos en una leyenda estable.</p></div><div class="chart-legend"><i class="portfolio-dot"></i> Westcon · <i class="external-dot"></i> otros</div></div><div class="vendor-arena-layout"><div><div class="actor-y">Más evidencia pública ↑</div><div class="actor-plot actor-plot-clean">${points}</div><div class="actor-x">Menor amplitud temática ← · → Mayor amplitud temática</div></div><div class="actor-legend-list">${actorLegend}</div></div>`;
  }
  function renderArchitectures(){
    const q=norm($('#architectureSearch')?.value), all=state.data.architectures||[], rows=all.filter(r=>!q||rowBlob(r).includes(q));
    $('#architectureGrid').innerHTML=cardGrid(rows,state.data.schemas.architectures)||'<div class="empty-state">No hay arquitecturas con ese filtro.</div>';
    setCount('#architectureCount',rows.length,all.length,'arquitecturas');
  }

  function renderSourceCatalog(){
    const q=norm($('#sourceSearch')?.value); const all=state.data.source_catalog||[];
    const rows=all.filter(s=>!q||norm([s.name,s.class,(s.scope||[]).join(' '),(s.dimensions||[]).join(' ')].join(' ')).includes(q));
    const classes=new Set(all.map(s=>s.class).filter(Boolean)); const dims=new Set(all.flatMap(s=>s.dimensions||[]));
    $('#sourceSummary').innerHTML=`<div><b>${all.length}</b><span>fuentes / familias</span></div><div><b>${classes.size}</b><span>clases de fuente</span></div><div><b>${dims.size}</b><span>dimensiones de inteligencia</span></div><div><b>ES + PT</b><span>foco geográfico</span></div>`;
    $('#sourceCatalog').innerHTML=rows.slice(0,220).map(s=>`<div class="source-row"><b>${esc(s.name)}</b><small>${esc(s.class||'fuente pública')} · ${(s.scope||[]).map(esc).join(' / ')}</small><div class="dims">${(s.dimensions||[]).slice(0,7).map(d=>`<span class="tag">${esc(d)}</span>`).join('')}</div>${s.url&&!String(s.url).startsWith('dynamic://')?`<a href="${esc(s.url)}" target="_blank" rel="noopener">Abrir ↗</a>`:'<small>Enrutado dinámicamente por entidad</small>'}</div>`).join('') || '<div class="empty-state">Sin coincidencias.</div>';
  }

  function selectedModules(){ return new Set($$('.export-modules input:checked').map(x=>x.value)); }
  const exportTheme={navy:'082335',navy2:'113A50',ink:'142B3B',muted:'647986',line:'D9E3E8',bg:'F3F6F8',cyan:'12C7C0',orange:'F09E0D',pink:'E5007D',blue:'3195BB',green:'159B7F',white:'FFFFFF'};
  const domainCopy={
    manufacturers:{label:'Fabricantes',eyebrow:'PORTFOLIO WESTCON',desc:'Portfolio Westcon Iberia con competencia, canal, ecosistema y señales de mercado trazables.',accent:'12C7C0'},
    integrators:{label:'Integradores',eyebrow:'ECOSISTEMA IBERIA',desc:'Partners, integradores, instaladores, VAR, MSP/MSSP, consultoras y service providers vinculados a nuestros fabricantes.',accent:'F09E0D'},
    distributors:{label:'Mayoristas de la competencia',eyebrow:'CANAL COMPETITIVO',desc:'Linecards, solape, servicios y capacidades de los mayoristas competidores con evidencia pública.',accent:'E5007D'},
    trends:{label:'Tendencias',eyebrow:'TENDENCIAS 2026–2030',desc:'Mercado, crecimiento, drivers, demanda y actores relevantes observados en analistas y fuentes sectoriales.',accent:'3195BB'},
    architectures:{label:'Arquitecturas',eyebrow:'ARQUITECTURAS',desc:'Marcos funcionales basados en analistas y estándares, con encaje explícito del portfolio Westcon por capa.',accent:'159B7F'}
  };
  function uniqueEvidence(rows, limit=80){
    const map=new Map();
    rows.forEach(r=>{
      [...(r.evidence||[]),...Object.values(r.fields||{}).flatMap(f=>f.evidence||[])].forEach(ev=>{
        const k=ev.url||`${ev.source}|${ev.title}`;
        if(!map.has(k)) map.set(k,ev);
      });
    });
    return [...map.values()].slice(0,limit);
  }
  function rowEvidenceCount(row){ return uniqueEvidence([row],999).length; }
  function shortText(v,max=165){ const t=valueText(v).replace(/\s+/g,' ').trim(); return t.length>max?`${t.slice(0,max-1)}…`:t; }
  function compactValue(v,maxItems=5,maxChars=175){
    if(Array.isArray(v)){
      if(v.length&&typeof v[0]==='object'&&v[0].layer){
        const parts=v.slice(0,4).map(x=>`${x.layer}: ${(x.vendors||[]).slice(0,5).join(', ')}`); if(v.length>4)parts.push(`+${v.length-4} capas`); return shortText(parts.join(' · '),maxChars);
      }
      const parts=v.slice(0,maxItems).map(x=>typeof x==='object'?JSON.stringify(x):String(x)); if(v.length>maxItems)parts.push(`+${v.length-maxItems}`); return shortText(parts.join(' · '),maxChars);
    }
    if(typeof v==='object') return shortText(JSON.stringify(v),maxChars);
    return shortText(v,maxChars);
  }
  function reportValueHtml(field){
    const v=field?.value;
    if(Array.isArray(v)){
      if(v.length&&typeof v[0]==='object'&&v[0].layer){
        return `<div class="r-layers">${v.slice(0,4).map(x=>`<div><b>${esc(x.layer)}</b><span>${esc((x.vendors||[]).slice(0,6).join(' · '))}</span></div>`).join('')}${v.length>4?`<small>+${v.length-4} capas adicionales en la aplicación</small>`:''}</div>`;
      }
      const shown=v.slice(0,6); return `<div class="r-tags">${shown.map((x,i)=>{const it=itemFor(field,x,i),b=it?.confidence_band||field?.confidence_band||'medium';return `<span class="${esc(b)}">${esc(typeof x==='object'?JSON.stringify(x):x)} · ${confidencePct(it?.confidence??field?.confidence??.66)}%</span>`}).join('')}${v.length>shown.length?`<span class="more">+${v.length-shown.length}</span>`:''}</div>`;
    }
    return `<span>${esc(shortText(v,190))}</span>`;
  }
  function reportBrand(){return `<div class="r-brand"><span class="r-mark"><i></i><i></i><i></i></span><b>WESTCON IBERIA</b><small>BUSINESS INTELLIGENCE</small></div>`;}
  function reportFooter(label){return `<footer class="r-footer"><span>${esc(label)}</span><span>v${esc(state.data.meta.version||'3.8.0')} · ${esc(state.data.meta.scope||'Iberia')} · inteligencia trazable</span></footer>`;}
  function reportCover(title,modules){
    const stats=[
      ['manufacturers','Fabricantes',state.data.manufacturers.length],['integrators','Integradores',state.data.integrators.length],['distributors','Mayoristas',state.data.distributors.length],['trends','Tendencias',state.data.trends.length],['architectures','Arquitecturas',state.data.architectures.length]
    ].filter(x=>modules.has(x[0]));
    return `<section class="report-page report-cover">
      <div class="r-cover-top">${reportBrand()}<span class="r-version">v${esc(state.data.meta.version||'3.8.0')}</span></div>
      <div class="r-cover-main"><div class="r-kicker">INTELIGENCIA DE NEGOCIO · ESPAÑA + PORTUGAL</div><h1>${esc(title)}</h1><p>La misma lógica visual de la aplicación: información útil, estructura limpia y fuentes verificables.</p></div>
      <div class="r-kpis">${stats.map((x,i)=>`<div style="--accent:#${[exportTheme.cyan,exportTheme.orange,exportTheme.pink,exportTheme.blue,exportTheme.green][i%5]}"><b>${esc(x[2])}</b><span>${esc(x[1])}</span></div>`).join('')}<div style="--accent:#${exportTheme.cyan}"><b>${esc(state.data.meta.source_count||0)}</b><span>fuentes / familias</span></div></div>
      <div class="r-cover-note"><b>Generado</b><span>${esc(state.data.meta.generated_at||'')}</span></div>
      ${reportFooter('Westcon Iberia · Business Intelligence')}
    </section>`;
  }
  function chunk(arr,size){const out=[];for(let i=0;i<arr.length;i+=size)out.push(arr.slice(i,i+size));return out;}
  function reportTablePages(key,rows,schema){
    const info=domainCopy[key], cols=activeColumns(schema,rows), colGroups=chunk(cols,5), rowGroups=chunk(rows,18), pages=[];
    const total=Math.max(1,colGroups.length)*Math.max(1,rowGroups.length); let n=0;
    (colGroups.length?colGroups:[[]]).forEach((cg,ci)=>rowGroups.forEach((rg,ri)=>{
      n++; pages.push(`<section class="report-page r-section-page" style="--accent:#${info.accent}">
        <div class="r-page-head"><div>${reportBrand()}<div class="r-eyebrow">${esc(info.eyebrow)}</div><h2>${esc(info.label)}</h2><p>${esc(info.desc)}</p></div><div class="r-page-count"><b>${esc(rows.length)}</b><span>entidades</span></div></div>
        <div class="r-page-meta"><span>Bloque ${ci+1}/${Math.max(1,colGroups.length)}</span><span>Página ${n}/${total}</span><span>Resumen visual; detalle completo en la aplicación</span></div>
        <div class="r-table-wrap"><table class="r-table"><thead><tr><th class="r-entity">Entidad</th>${cg.map(c=>`<th>${esc(c.label)}</th>`).join('')}</tr></thead><tbody>${rg.map(r=>`<tr><td class="r-entity"><b>${esc(r.name)}</b><small>${rowEvidenceCount(r)} fuentes</small></td>${cg.map(c=>{const f=r.fields?.[c.id];return `<td>${f&&hasValue(f.value)?reportValueHtml(f):''}</td>`}).join('')}</tr>`).join('')}</tbody></table></div>
        ${reportFooter(info.label)}
      </section>`);
    })); return pages.join('');
  }
  function reportCardPage(key,row,index,total,schema){
    const info=domainCopy[key], cols=activeColumns(schema,[row]);
    return `<section class="report-page r-section-page r-card-page" style="--accent:#${info.accent}">
      <div class="r-page-head"><div>${reportBrand()}<div class="r-eyebrow">${esc(info.eyebrow)}</div><h2>${esc(row.name)}</h2><p>${esc(info.desc)}</p></div><div class="r-page-count"><b>${index+1}</b><span>de ${total}</span></div></div>
      <div class="r-intel-card"><div class="r-card-title"><h3>${esc(row.name)}</h3><span>${rowEvidenceCount(row)} fuentes</span></div><div class="r-card-fields">${cols.map(c=>{const f=row.fields?.[c.id];return `<div class="r-card-field"><label>${esc(c.label)}</label><div>${reportValueHtml(f)}</div></div>`}).join('')}</div></div>
      ${reportFooter(info.label)}
    </section>`;
  }
  function reportSourcesPages(key,rows){
    const info=domainCopy[key], sources=uniqueEvidence(rows,60); if(!sources.length)return '';
    return chunk(sources,12).map((group,gi)=>`<section class="report-page r-section-page r-source-page" style="--accent:#${info.accent}">
      <div class="r-page-head"><div>${reportBrand()}<div class="r-eyebrow">TRAZABILIDAD</div><h2>Fuentes · ${esc(info.label)}</h2><p>Principales fuentes utilizadas en los datos incluidos en este informe.</p></div><div class="r-page-count"><b>${sources.length}</b><span>fuentes</span></div></div>
      <div class="r-source-grid">${group.map((s,i)=>`<div class="r-source"><span>${gi*12+i+1}</span><div><b>${esc(s.source||'Fuente pública')}</b><p>${esc(s.title||'Evidencia')}</p><small>${esc([s.date,s.type].filter(Boolean).join(' · '))}</small>${s.url?`<a href="${esc(s.url)}">${esc(shortText(s.url,120))}</a>`:''}</div></div>`).join('')}</div>
      ${reportFooter(`Fuentes · ${info.label}`)}
    </section>`).join('');
  }
  function reportTrendAnalyticsPage(){
    const rows=(state.data.trends||[]).filter(r=>r.analytics),actors=trendActorData(28);
    const maxT=Math.max(1,...actors.map(a=>a.trends.size)),maxE=Math.max(1,...actors.map(a=>a.evidence));
    const trendDots=rows.map((r,i)=>{const p=trendLoopPoint(r.analytics||{}),a=r.analytics||{},sz=4.2+((+a.buyer_urgency||50)/100)*2.2;return `<div class="r-number-dot" style="left:${(p.x/490*100).toFixed(1)}%;top:${(p.y/270*100).toFixed(1)}%;width:${sz}mm;height:${sz}mm">${i+1}</div>`}).join('');
    const trendLegend=rows.map((r,i)=>{const a=r.analytics||{};return `<div class="r-number-row"><b>${i+1}</b><span>${esc(r.name)}</span><small>${esc(stageLabel(a.maturity))} · M ${Math.round(+a.momentum||0)} · U ${Math.round(+a.buyer_urgency||0)}</small></div>`}).join('');
    const pulse=`<section class="report-page r-section-page r-analytics-page" style="--accent:#${exportTheme.blue}"><div class="r-page-head"><div>${reportBrand()}<div class="r-eyebrow">WESTCON TREND LOOP</div><h2>Estado, velocidad y urgencia de las tendencias</h2><p>Síntesis Westcon propia y trazable. Los números mantienen el gráfico limpio; la leyenda conserva todos los nombres completos.</p></div></div><div class="r-loop-layout"><div class="r-loop-plot"><svg viewBox="0 0 490 270" aria-hidden="true"><path d="M45 188 C28 95 98 25 210 33 C338 42 456 105 440 189 C426 257 319 253 253 213 C190 175 139 150 99 173 C62 194 80 231 134 235"/><text x="35" y="215">EMERGENTE</text><text x="125" y="45">ACELERACIÓN</text><text x="328" y="61">ESCALA</text><text x="350" y="235">CONSOLIDACIÓN</text></svg>${trendDots}</div><div class="r-number-legend">${trendLegend}</div></div><div class="r-analytics-foot">Posición = madurez · lectura auxiliar = momentum · tamaño = urgencia del comprador. No reproduce metodologías propietarias de Gartner o Forrester.</div>${reportFooter('Tendencias · Trend Loop')}</section>`;
    const actorDots=actors.map((a,i)=>{const x=7+86*(a.trends.size/maxT),y=91-82*(a.evidence/maxE);return `<div class="r-number-dot actor ${a.portfolio?'westcon':'external'}" style="left:${x}%;top:${y}%">${i+1}</div>`}).join('');
    const actorLegend=actors.map((a,i)=>`<div class="r-number-row compact"><b>${i+1}</b><span>${esc(a.name)}</span><small>${a.trends.size} tendencias · ${a.evidence} evid.</small></div>`).join('');
    const actor=`<section class="report-page r-section-page r-analytics-page" style="--accent:#${exportTheme.blue}"><div class="r-page-head"><div>${reportBrand()}<div class="r-eyebrow">WESTCON VENDOR ARENA</div><h2>Actores por amplitud temática y evidencia pública</h2><p>Presencia documentada, no liderazgo ni cuota. Azul = portfolio Westcon; blanco/rosa = otros actores.</p></div></div><div class="r-loop-layout"><div class="r-actor-plot clean">${actorDots}<div class="r-axis-y">MÁS EVIDENCIA ↑</div><div class="r-axis-x">MENOR AMPLITUD ← &nbsp;&nbsp;&nbsp; → MAYOR AMPLITUD</div></div><div class="r-number-legend dense">${actorLegend}</div></div><div class="r-analytics-foot">Cada punto se calcula únicamente desde tendencias y evidencias publicadas en el dataset.</div>${reportFooter('Tendencias · Vendor Arena')}</section>`;
    return pulse+actor;
  }
  function reportHtml(title,modules){
    const sections=[reportCover(title,modules)];
    const order=[['manufacturers',state.data.manufacturers,state.data.schemas.manufacturers],['integrators',state.data.integrators,state.data.schemas.integrators],['distributors',state.data.distributors,state.data.schemas.distributors],['trends',state.data.trends,state.data.schemas.trends],['architectures',state.data.architectures,state.data.schemas.architectures]];
    order.forEach(([key,rows,schema])=>{if(!modules.has(key))return; if(key==='trends'||key==='architectures') rows.forEach((r,i)=>sections.push(reportCardPage(key,r,i,rows.length,schema))); else sections.push(reportTablePages(key,rows,schema)); if(key==='trends')sections.push(reportTrendAnalyticsPage()); sections.push(reportSourcesPages(key,rows));});
    return `<div class="report-export">${sections.join('')}</div>`;
  }
  async function exportPdf(){
    const modules=selectedModules(); if(!modules.size){toast('Selecciona al menos un área');return;}
    const title=$('#reportTitle')?.value.trim()||'Westcon Iberia · Business Intelligence'; const sheet=$('#reportSheet'); sheet.innerHTML=reportHtml(title,modules); sheet.setAttribute('aria-hidden','false'); sheet.classList.add('rendering'); closeModal('exportModal');
    try{
      if(window.html2pdf){ await window.html2pdf().set({margin:0,filename:'Westcon_Iberia_Business_Intelligence_v3.8.0.pdf',image:{type:'jpeg',quality:.98},html2canvas:{scale:2,useCORS:true,backgroundColor:'#ffffff',logging:false},jsPDF:{unit:'mm',format:'a4',orientation:'landscape'},pagebreak:{mode:['css']}}).from(sheet.firstElementChild).save(); toast('PDF generado con diseño Westcon'); }
      else { window.print(); }
    } finally { sheet.classList.remove('rendering'); sheet.setAttribute('aria-hidden','true'); }
  }
  function pptCompact(v,max=115){return compactValue(v,4,max);}
  function pptEvidenceNames(row,max=2){const names=[];for(const ev of uniqueEvidence([row],12)){const n=ev.source||ev.title;if(n&&!names.includes(n))names.push(n);if(names.length>=max)break;}return names;}
  function pptAddBrand(slide,pptx,dark=false){
    const base=dark?exportTheme.white:exportTheme.navy, sub=dark?'C9D7DE':exportTheme.muted;
    [exportTheme.orange,exportTheme.pink,exportTheme.cyan].forEach((c,i)=>slide.addShape(pptx.ShapeType.rect,{x:.52+i*.11,y:.33,w:.075,h:.32,fill:{color:c},line:{color:c}}));
    slide.addText('WESTCON IBERIA',{x:.92,y:.32,w:2.5,h:.2,fontFace:'Aptos',fontSize:9.5,bold:true,color:base,margin:0,charSpacing:1.1});
    slide.addText('BUSINESS INTELLIGENCE',{x:.92,y:.53,w:2.7,h:.16,fontFace:'Aptos',fontSize:5.8,bold:true,color:sub,margin:0,charSpacing:1.2});
  }
  function pptAddFooter(slide,pptx,label,dark=false){
    const line=dark?'315267':'D9E3E8', color=dark?'AFC1CA':'647986';
    slide.addShape(pptx.ShapeType.line,{x:.55,y:7.05,w:12.2,h:0,line:{color:line,pt:.7}});
    slide.addText(label,{x:.55,y:7.1,w:4.8,h:.14,fontFace:'Aptos',fontSize:6.6,color,margin:0});
    slide.addText(`v${state.data.meta.version||'3.8.0'} · ${state.data.meta.scope||'Iberia'} · trazabilidad en la aplicación`,{x:7.0,y:7.1,w:5.75,h:.14,fontFace:'Aptos',fontSize:6.6,color,align:'right',margin:0});
  }
  function pptAddSlideTitle(slide,pptx,title,sub='',accent=exportTheme.cyan){
    pptAddBrand(slide,pptx,false); slide.addShape(pptx.ShapeType.rect,{x:.55,y:.92,w:.08,h:.63,fill:{color:accent},line:{color:accent}});
    slide.addText(title,{x:.78,y:.92,w:11.6,h:.37,fontFace:'Aptos Display',fontSize:23,bold:true,color:exportTheme.navy,margin:0});
    if(sub)slide.addText(sub,{x:.79,y:1.34,w:11.45,h:.24,fontFace:'Aptos',fontSize:8.5,color:exportTheme.muted,margin:0});
  }
  function pptAddDomainDivider(pptx,key,count){
    const info=domainCopy[key], slide=pptx.addSlide(); slide.background={color:exportTheme.bg}; pptAddBrand(slide,pptx,false);
    slide.addShape(pptx.ShapeType.rect,{x:.55,y:1.52,w:.11,h:3.75,fill:{color:info.accent},line:{color:info.accent}});
    slide.addText(info.eyebrow,{x:.9,y:1.6,w:5.8,h:.22,fontFace:'Aptos',fontSize:8.5,bold:true,color:info.accent,margin:0,charSpacing:1.2});
    slide.addText(info.label,{x:.9,y:2.02,w:7.7,h:.72,fontFace:'Aptos Display',fontSize:34,bold:true,color:exportTheme.navy,margin:0});
    slide.addText(info.desc,{x:.92,y:2.95,w:7.35,h:1.0,fontFace:'Aptos',fontSize:14,color:exportTheme.ink,margin:0,breakLine:true});
    slide.addShape(pptx.ShapeType.roundRect,{x:9.2,y:2.02,w:2.7,h:1.65,rectRadius:.05,fill:{color:exportTheme.white},line:{color:exportTheme.line,pt:1}});
    slide.addText(String(count),{x:9.5,y:2.28,w:2.1,h:.55,fontFace:'Aptos Display',fontSize:31,bold:true,color:exportTheme.navy,align:'center',margin:0});
    slide.addText('ENTIDADES / ELEMENTOS',{x:9.45,y:3.0,w:2.2,h:.2,fontFace:'Aptos',fontSize:7.2,bold:true,color:exportTheme.muted,align:'center',margin:0,charSpacing:.8});
    pptAddFooter(slide,pptx,info.label,false);
  }
  function pptBandPalette(band){return band==='high'?{fill:'E5F5EA',line:'79B98A',text:'176332'}:band==='medium'?{fill:'FFF5D6',line:'D6B14A',text:'765500'}:{fill:'FCE8E7',line:'D88B86',text:'8B2E28'};}
  function pptListItems(field,max=3){
    const vals=Array.isArray(field?.value)?field.value:[]; const items=field?.items||[];
    return vals.slice(0,max).map((v,i)=>{const it=items[i]||items.find(x=>String(x.value)===String(v))||{};return{value:String(v),band:it.confidence_band||field?.confidence_band||'medium',confidence:confidencePct(it.confidence??field?.confidence??.66)}});
  }
  function pptAddConfidenceChips(slide,pptx,field,x,y,w,max=3){
    const items=pptListItems(field,max); if(!items.length)return false; let xx=x,yy=y;
    items.forEach(it=>{const pal=pptBandPalette(it.band),label=shortText(it.value,44),cw=Math.min(w,Math.max(.75,Math.min(2.25,.31+label.length*.047))); if(xx+cw>x+w){xx=x;yy+=.27;} slide.addShape(pptx.ShapeType.roundRect,{x:xx,y:yy,w:cw,h:.22,rectRadius:.04,fill:{color:pal.fill},line:{color:pal.line,pt:.55}});slide.addText(`${label} · ${it.confidence}%`,{x:xx+.05,y:yy+.055,w:cw-.1,h:.095,fontFace:'Aptos',fontSize:4.9,bold:true,color:pal.text,margin:0,fit:'shrink'});xx+=cw+.07;});
    const extra=(Array.isArray(field?.value)?field.value.length:0)-items.length;if(extra>0){if(xx+.55>x+w){xx=x;yy+=.27;}slide.addText(`+${extra}`,{x:xx,y:yy+.05,w:.5,h:.11,fontFace:'Aptos',fontSize:5.2,bold:true,color:exportTheme.muted,margin:0});}
    return true;
  }
  function pptAddEntityCard(slide,pptx,row,schema,x,y,w,h,accent){
    slide.addShape(pptx.ShapeType.roundRect,{x,y,w,h,rectRadius:.04,fill:{color:exportTheme.white},line:{color:exportTheme.line,pt:.8}});
    slide.addShape(pptx.ShapeType.rect,{x,y,w,h:.07,fill:{color:accent},line:{color:accent}});
    slide.addText(row.name,{x:x+.16,y:y+.18,w:w-1.15,h:.25,fontFace:'Aptos Display',fontSize:12.5,bold:true,color:exportTheme.navy,margin:0,fit:'shrink'});
    slide.addShape(pptx.ShapeType.roundRect,{x:x+w-.88,y:y+.17,w:.7,h:.27,rectRadius:.05,fill:{color:'EDF3F5'},line:{color:'EDF3F5'}});
    slide.addText(`${rowEvidenceCount(row)} src`,{x:x+w-.84,y:y+.225,w:.62,h:.13,fontFace:'Aptos',fontSize:5.7,bold:true,color:'42606F',align:'center',margin:0});
    const cols=activeColumns(schema,[row]).filter(c=>c.id!=='scope').slice(0,3); let yy=y+.58;
    cols.forEach(c=>{const f=row.fields?.[c.id];slide.addText(c.label.toUpperCase(),{x:x+.16,y:yy,w:1.35,h:.13,fontFace:'Aptos',fontSize:5.5,bold:true,color:exportTheme.muted,margin:0,charSpacing:.4});if(!(Array.isArray(f?.value)&&pptAddConfidenceChips(slide,pptx,f,x+1.52,yy-.015,w-1.7,2)))slide.addText(pptCompact(f?.value,92),{x:x+1.52,y:yy-.01,w:w-1.7,h:.28,fontFace:'Aptos',fontSize:7.2,color:exportTheme.ink,margin:0,fit:'shrink',valign:'top'});yy+=.31;});
    const src=pptEvidenceNames(row,2); if(src.length)slide.addText(`Fuentes: ${src.join(' · ')}`,{x:x+.16,y:y+h-.25,w:w-.32,h:.13,fontFace:'Aptos',fontSize:5.6,color:'758994',italic:true,margin:0,fit:'shrink'});
  }
  function pptAddEntitySlides(pptx,key,rows,schema){
    const info=domainCopy[key], groups=chunk(rows,6); groups.forEach((group,gi)=>{const slide=pptx.addSlide(); slide.background={color:exportTheme.bg}; pptAddSlideTitle(slide,pptx,info.label,`${rows.length} entidades · página ${gi+1}/${groups.length} · resumen visual, detalle completo en la aplicación`,info.accent); const pos=[[.55,1.78],[6.92,1.78],[.55,3.48],[6.92,3.48],[.55,5.18],[6.92,5.18]]; group.forEach((r,i)=>pptAddEntityCard(slide,pptx,r,schema,pos[i][0],pos[i][1],5.86,1.48,info.accent)); pptAddFooter(slide,pptx,info.label,false);});
  }
  function pptAddDetailCard(slide,pptx,row,schema,x,y,w,h,accent){
    slide.addShape(pptx.ShapeType.roundRect,{x,y,w,h,rectRadius:.04,fill:{color:exportTheme.white},line:{color:exportTheme.line,pt:.8}});
    slide.addShape(pptx.ShapeType.rect,{x,y,w:.09,h,fill:{color:accent},line:{color:accent}});
    slide.addText(row.name,{x:x+.25,y:y+.2,w:w-1.45,h:.32,fontFace:'Aptos Display',fontSize:15,bold:true,color:exportTheme.navy,margin:0,fit:'shrink'});
    slide.addText(`${rowEvidenceCount(row)} fuentes`,{x:x+w-1.15,y:y+.23,w:.92,h:.17,fontFace:'Aptos',fontSize:6.4,bold:true,color:exportTheme.muted,align:'right',margin:0});
    const cols=activeColumns(schema,[row]).slice(0,8), left=cols.slice(0,4), right=cols.slice(4,8);
    const draw=(list,xx,ww)=>{let yy=y+.72;list.forEach(c=>{const f=row.fields?.[c.id];slide.addText(c.label.toUpperCase(),{x:xx,y:yy,w:ww,h:.13,fontFace:'Aptos',fontSize:5.8,bold:true,color:exportTheme.muted,margin:0,charSpacing:.45});if(!(Array.isArray(f?.value)&&pptAddConfidenceChips(slide,pptx,f,xx,yy+.19,ww,5)))slide.addText(pptCompact(f?.value,255),{x:xx,y:yy+.17,w:ww,h:.72,fontFace:'Aptos',fontSize:7.7,color:exportTheme.ink,margin:0,fit:'shrink',valign:'top'});yy+=1.02;});};
    draw(left,x+.25,(w-.7)/2);draw(right,x+w/2+.1,(w-.7)/2);
    const src=pptEvidenceNames(row,3); if(src.length)slide.addText(`Fuentes: ${src.join(' · ')}`,{x:x+.25,y:y+h-.28,w:w-.5,h:.13,fontFace:'Aptos',fontSize:5.8,color:'758994',italic:true,margin:0,fit:'shrink'});
  }
  function pptAddDetailSlides(pptx,key,rows,schema){
    const info=domainCopy[key]; rows.forEach((row,gi)=>{const slide=pptx.addSlide(); slide.background={color:exportTheme.bg}; pptAddSlideTitle(slide,pptx,info.label,`${gi+1}/${rows.length} · ficha completa con el lenguaje visual de la web`,info.accent); pptAddDetailCard(slide,pptx,row,schema,.55,1.78,12.22,4.98,info.accent); pptAddFooter(slide,pptx,info.label,false);});
  }
  function pptAddSources(pptx,selectedRows){
    const all=uniqueEvidence(selectedRows,72); if(!all.length)return; const groups=chunk(all,9); groups.forEach((group,gi)=>{const slide=pptx.addSlide(); slide.background={color:exportTheme.bg}; pptAddSlideTitle(slide,pptx,'Fuentes principales',`${all.length} evidencias únicas seleccionadas · página ${gi+1}/${groups.length}`,exportTheme.cyan); let y=1.78; group.forEach((ev,i)=>{slide.addShape(pptx.ShapeType.roundRect,{x:.55,y,w:12.22,h:.52,rectRadius:.03,fill:{color:exportTheme.white},line:{color:exportTheme.line,pt:.6}});slide.addShape(pptx.ShapeType.roundRect,{x:.72,y:y+.13,w:.33,h:.25,rectRadius:.04,fill:{color:'E7F4F5'},line:{color:'E7F4F5'}});slide.addText(String(gi*9+i+1),{x:.75,y:y+.19,w:.27,h:.1,fontFace:'Aptos',fontSize:5.8,bold:true,color:'0A7280',align:'center',margin:0});slide.addText(ev.source||'Fuente pública',{x:1.18,y:y+.1,w:2.2,h:.15,fontFace:'Aptos',fontSize:7.4,bold:true,color:exportTheme.navy,margin:0,fit:'shrink'});slide.addText(shortText(ev.title||'Evidencia',115),{x:3.42,y:y+.08,w:7.75,h:.18,fontFace:'Aptos',fontSize:6.9,color:exportTheme.ink,margin:0,fit:'shrink'});slide.addText([ev.date,ev.type].filter(Boolean).join(' · '),{x:3.42,y:y+.3,w:6.7,h:.12,fontFace:'Aptos',fontSize:5.5,color:exportTheme.muted,margin:0});if(ev.url)slide.addText('Abrir ↗',{x:11.32,y:y+.18,w:1.05,h:.13,fontFace:'Aptos',fontSize:6.2,bold:true,color:'177E9F',align:'right',margin:0,hyperlink:{url:ev.url}});y+=.58;}); pptAddFooter(slide,pptx,'Fuentes principales',false);});
  }
  function pptAddTrendAnalytics(pptx){
    const rows=state.data.trends||[];
    let slide=pptx.addSlide(); slide.background={color:exportTheme.bg};
    pptAddSlideTitle(slide,pptx,'Westcon Trend Loop','Síntesis propia · madurez, momentum y urgencia · nombres completos en leyenda',exportTheme.blue);
    const px=0.55,py=1.72,pw=8.0,ph=4.95,lx=8.82,lw=3.95;
    slide.addShape(pptx.ShapeType.roundRect,{x:px,y:py,w:pw,h:ph,rectRadius:.04,fill:{color:'FFFFFF'},line:{color:exportTheme.line,pt:.8}});
    const loopPts=[[.07,.68],[.04,.36],[.16,.10],[.39,.08],[.67,.15],[.94,.37],[.91,.68],[.75,.88],[.54,.78],[.37,.60],[.20,.61],[.11,.76],[.22,.86]];
    for(let i=0;i<loopPts.length-1;i++){const a=loopPts[i],b=loopPts[i+1];slide.addShape(pptx.ShapeType.line,{x:px+pw*a[0],y:py+ph*a[1],w:pw*(b[0]-a[0]),h:ph*(b[1]-a[1]),line:{color:'45A9C5',pt:5,transparency:12,beginArrowType:'none',endArrowType:'none'}});}
    [['EMERGENTE',.06,.78],['ACELERACIÓN',.25,.07],['ESCALA',.70,.10],['CONSOLIDACIÓN',.70,.91]].forEach(([t,x,y])=>slide.addText(t,{x:px+pw*x,y:py+ph*y,w:1.35,h:.14,fontFace:'Aptos',fontSize:5.4,bold:true,color:exportTheme.muted,margin:0}));
    rows.forEach((r,i)=>{const p=trendLoopPoint(r.analytics||{}),a=r.analytics||{},x=px+pw*(p.x/490),y=py+ph*(p.y/270),sz=.18+.12*((+a.buyer_urgency||50)/100);slide.addShape(pptx.ShapeType.ellipse,{x:x-sz/2,y:y-sz/2,w:sz,h:sz,fill:{color:exportTheme.navy},line:{color:'FFFFFF',pt:1}});slide.addText(String(i+1),{x:x-sz/2,y:y-.035,w:sz,h:.08,fontFace:'Aptos',fontSize:4.8,bold:true,color:'FFFFFF',align:'center',margin:0,fit:'shrink'});});
    let y=1.78; rows.forEach((r,i)=>{const a=r.analytics||{};slide.addShape(pptx.ShapeType.ellipse,{x:lx,y:y+.02,w:.18,h:.18,fill:{color:'E7F4F5'},line:{color:'9BCDD5',pt:.6}});slide.addText(String(i+1),{x:lx,y:y+.07,w:.18,h:.06,fontSize:4.5,bold:true,color:exportTheme.navy,align:'center',margin:0});slide.addText(r.name,{x:lx+.25,y,w:lw-.25,h:.13,fontFace:'Aptos',fontSize:6.2,bold:true,color:exportTheme.ink,margin:0,fit:'shrink'});slide.addText(`${stageLabel(a.maturity)} · M ${Math.round(+a.momentum||0)} · U ${Math.round(+a.buyer_urgency||0)}`,{x:lx+.25,y:y+.14,w:lw-.25,h:.1,fontFace:'Aptos',fontSize:4.8,color:exportTheme.muted,margin:0});y+=.31;});
    pptAddFooter(slide,pptx,'Tendencias · Trend Loop',false);

    const actors=trendActorData(28),maxT=Math.max(1,...actors.map(a=>a.trends.size)),maxE=Math.max(1,...actors.map(a=>a.evidence));
    slide=pptx.addSlide();slide.background={color:exportTheme.bg};pptAddSlideTitle(slide,pptx,'Westcon Vendor Arena','Amplitud temática × evidencia pública · presencia documentada, no liderazgo ni cuota',exportTheme.blue);
    const ax=.65,ay=1.75,aw=7.85,ah=4.95;slide.addShape(pptx.ShapeType.rect,{x:ax,y:ay,w:aw,h:ah,fill:{color:'FFFFFF'},line:{color:exportTheme.line,pt:.8}});[25,50,75].forEach(v=>{slide.addShape(pptx.ShapeType.line,{x:ax+aw*v/100,y:ay,w:0,h:ah,line:{color:'E2EAED',pt:.5,dash:'dash'}});slide.addShape(pptx.ShapeType.line,{x:ax,y:ay+ah*v/100,w:aw,h:0,line:{color:'E8EEF1',pt:.5,dash:'dash'}});});
    actors.forEach((a,i)=>{const x=ax+aw*(.07+.86*(a.trends.size/maxT)),y=ay+ah*(.91-.82*(a.evidence/maxE)),c=a.portfolio?exportTheme.navy:exportTheme.white,l=a.portfolio?exportTheme.navy:exportTheme.pink;slide.addShape(pptx.ShapeType.ellipse,{x:x-.095,y:y-.095,w:.19,h:.19,fill:{color:c},line:{color:l,pt:1}});slide.addText(String(i+1),{x:x-.095,y:y-.03,w:.19,h:.06,fontFace:'Aptos',fontSize:4.1,bold:true,color:a.portfolio?'FFFFFF':'9C175D',align:'center',margin:0});});
    slide.addText('Más evidencia pública ↑',{x:.15,y:2.15,w:.65,h:.2,fontSize:5.5,bold:true,color:exportTheme.muted,rotate:270,margin:0});slide.addText('Menor amplitud ←          → Mayor amplitud',{x:2.5,y:6.72,w:4.2,h:.14,fontSize:5.5,bold:true,color:exportTheme.muted,align:'center',margin:0});
    y=1.78; actors.forEach((a,i)=>{slide.addShape(pptx.ShapeType.ellipse,{x:8.78,y:y+.01,w:.15,h:.15,fill:{color:a.portfolio?exportTheme.navy:exportTheme.white},line:{color:a.portfolio?exportTheme.navy:exportTheme.pink,pt:.8}});slide.addText(String(i+1),{x:8.78,y:y+.055,w:.15,h:.045,fontSize:3.6,bold:true,color:a.portfolio?'FFFFFF':'9C175D',align:'center',margin:0});slide.addText(a.name,{x:8.99,y:y,w:2.5,h:.11,fontFace:'Aptos',fontSize:5.2,bold:true,color:exportTheme.ink,margin:0,fit:'shrink'});slide.addText(`${a.trends.size}T · ${a.evidence}E`,{x:11.55,y:y,w:.78,h:.11,fontFace:'Aptos',fontSize:4.5,color:exportTheme.muted,align:'right',margin:0});y+=.17;});
    slide.addShape(pptx.ShapeType.ellipse,{x:11.0,y:1.31,w:.12,h:.12,fill:{color:exportTheme.navy},line:{color:exportTheme.navy}});slide.addText('Westcon',{x:11.16,y:1.30,w:.63,h:.12,fontSize:5.2,bold:true,color:exportTheme.muted,margin:0});slide.addShape(pptx.ShapeType.ellipse,{x:11.85,y:1.31,w:.12,h:.12,fill:{color:exportTheme.white},line:{color:exportTheme.pink,pt:.9}});slide.addText('Otros',{x:12.01,y:1.30,w:.5,h:.12,fontSize:5.2,bold:true,color:exportTheme.muted,margin:0});pptAddFooter(slide,pptx,'Tendencias · Vendor Arena',false);
  }
  async function exportPptx(){
    if(!window.PptxGenJS){toast('PptxGenJS no está disponible');return;}
    const modules=selectedModules(); if(!modules.size){toast('Selecciona al menos un área');return;}
    const title=$('#reportTitle')?.value.trim()||'Westcon Iberia · Business Intelligence'; const pptx=new window.PptxGenJS(); pptx.layout='LAYOUT_WIDE'; pptx.author='Westcon Iberia'; pptx.company='Westcon Iberia'; pptx.subject='Business Intelligence'; pptx.title=title; pptx.lang='es-ES';
    let slide=pptx.addSlide(); slide.background={color:exportTheme.navy}; pptAddBrand(slide,pptx,true);
    slide.addShape(pptx.ShapeType.rect,{x:12.56,y:0,w:.18,h:7.5,fill:{color:exportTheme.cyan},line:{color:exportTheme.cyan}}); slide.addShape(pptx.ShapeType.rect,{x:12.78,y:0,w:.18,h:7.5,fill:{color:exportTheme.pink},line:{color:exportTheme.pink}}); slide.addShape(pptx.ShapeType.rect,{x:13.0,y:0,w:.18,h:7.5,fill:{color:exportTheme.orange},line:{color:exportTheme.orange}});
    slide.addText('INTELIGENCIA DE NEGOCIO · ESPAÑA + PORTUGAL',{x:.72,y:1.62,w:7.8,h:.22,fontFace:'Aptos',fontSize:9,bold:true,color:exportTheme.cyan,margin:0,charSpacing:1.4});
    slide.addText(title,{x:.72,y:2.05,w:10.7,h:1.2,fontFace:'Aptos Display',fontSize:31,bold:true,color:exportTheme.white,margin:0,fit:'shrink'});
    slide.addText('Fabricantes · Integradores · Mayoristas · Tendencias · Arquitecturas',{x:.74,y:3.55,w:10.7,h:.32,fontFace:'Aptos',fontSize:11.5,color:'D2E0E6',margin:0});
    const stats=[['manufacturers','FAB',state.data.manufacturers.length],['integrators','INT',state.data.integrators.length],['distributors','MAY',state.data.distributors.length],['trends','TEN',state.data.trends.length],['architectures','ARQ',state.data.architectures.length]].filter(x=>modules.has(x[0]));
    stats.slice(0,5).forEach((item,i)=>{const v=item[2],lab=item[1];slide.addShape(pptx.ShapeType.roundRect,{x:.72+i*1.55,y:4.55,w:1.35,h:.78,rectRadius:.04,fill:{color:'113A50',transparency:0},line:{color:'315267',pt:.7}});slide.addText(String(v),{x:.82+i*1.55,y:4.72,w:1.15,h:.25,fontFace:'Aptos Display',fontSize:16,bold:true,color:exportTheme.white,align:'center',margin:0});slide.addText(lab,{x:.82+i*1.55,y:5.06,w:1.15,h:.11,fontFace:'Aptos',fontSize:5.6,bold:true,color:'AFC1CA',align:'center',margin:0,charSpacing:.6});});
    slide.addText(`${state.data.meta.source_count||0} fuentes/familias públicas · generado ${state.data.meta.generated_at||''}`,{x:.72,y:6.35,w:8.5,h:.2,fontFace:'Aptos',fontSize:7.5,color:'9EB8C5',margin:0}); pptAddFooter(slide,pptx,'Westcon Iberia · Business Intelligence',true);
    const order=[['manufacturers',state.data.manufacturers,state.data.schemas.manufacturers],['integrators',state.data.integrators,state.data.schemas.integrators],['distributors',state.data.distributors,state.data.schemas.distributors],['trends',state.data.trends,state.data.schemas.trends],['architectures',state.data.architectures,state.data.schemas.architectures]], selectedRows=[];
    order.forEach(([key,rows,schema])=>{if(!modules.has(key))return;pptAddDomainDivider(pptx,key,rows.length);if(key==='trends'||key==='architectures')pptAddDetailSlides(pptx,key,rows,schema);else pptAddEntitySlides(pptx,key,rows,schema);if(key==='trends')pptAddTrendAnalytics(pptx);selectedRows.push(...rows);});
    pptAddSources(pptx,selectedRows);
    await pptx.writeFile({fileName:'Westcon_Iberia_Business_Intelligence_v3.8.0.pptx'}); closeModal('exportModal'); toast('PowerPoint generado con diseño Westcon');
  }

  function renderAll(){
    populateIntegratorVendorFilter();
    renderManufacturers(); renderIntegrators(); renderDistributors(); renderTrends(); renderArchitectures(); renderSourceCatalog();
    const meta=state.data.meta||{}; const status=$('#footerStatus'); if(status) status.textContent=`v${meta.version||'3.8.0'} · ${meta.source_count||0} fuentes/familias · ${meta.scope||'Iberia'}`;
  }

  load().catch(err => { console.error(err); const main=document.querySelector('main'); if(main) main.innerHTML=`<div class="fatal"><h1>No se pudo cargar la inteligencia</h1><p>${esc(err.message)}</p></div>`; });
})();
