(() => {
  'use strict';
  const state = {data:null, lastRun:null, view:'fabricantes', fontScale:Number(localStorage.getItem('westcon-font-scale')||1), sort:{}, columnOrder:{}, dragCol:null, traceSource:null, helpSource:null};
  const $ = s => document.querySelector(s);
  const $$ = s => [...document.querySelectorAll(s)];
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const norm = v => String(v ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  const hasValue = v => {
    if(v == null || v === '' || v === false || (Array.isArray(v) && !v.length) || (typeof v === 'object' && !Array.isArray(v) && !Object.keys(v).length)) return false;
    return !['—','n/d','nd','pendiente','pendiente de evidencia','por investigar'].includes(norm(v).trim());
  };
  const toast = msg => { const el=$('#toast'); if(!el) return; el.textContent=msg; el.classList.add('show'); clearTimeout(el._t); el._t=setTimeout(()=>el.classList.remove('show'),2600); };

  async function load(){
    const [res, runRes] = await Promise.all([
      fetch('data/v315/intelligence.json', {cache:'no-store'}),
      fetch('data/v315/last_run.json', {cache:'no-store'}).catch(()=>null)
    ]);
    if(!res.ok) throw new Error(`No se pudo cargar data/v315/intelligence.json (${res.status})`);
    state.data = await res.json();
    if(runRes?.ok){ try{ state.lastRun = await runRes.json(); }catch(_){ state.lastRun=null; } }
    bind();
    renderAll();
  }

  function bind(){
    $$('#tabs [data-view]').forEach(btn => btn.addEventListener('click', () => switchView(btn.dataset.view)));
    $('#utilityMenuToggle')?.addEventListener('click', e => { e.stopPropagation(); toggleUtilityMenu(); });
    $('#manufacturerSearch')?.addEventListener('input', renderManufacturers);
    $('#integratorSearch')?.addEventListener('input', renderIntegrators);
    $('#integratorScope')?.addEventListener('change', renderIntegrators);
    $('#integratorVendor')?.addEventListener('change', renderIntegrators);
    $('#distributorSearch')?.addEventListener('input', renderDistributors);
    $('#distributorScope')?.addEventListener('change', renderDistributors);
    $('#publicClientSearch')?.addEventListener('input', renderClients);
    $('#publicClientScope')?.addEventListener('change', renderClients);
    $('#privateClientSearch')?.addEventListener('input', renderClients);
    $('#privateClientScope')?.addEventListener('change', renderClients);
    $('#trendSearch')?.addEventListener('input', renderTrends);
    $('#architectureSearch')?.addEventListener('input', renderArchitectures);
    $('#dataStatusBtn')?.addEventListener('click', () => { closeUtilityMenu(); openModal('updateModal'); });
    $('#confidenceHelpBtn')?.addEventListener('click', () => { closeUtilityMenu(); openModal('confidenceModal'); });
    $('#btnSources')?.addEventListener('click', () => { closeUtilityMenu(); openModal('sourceModal'); });
    $('#btnExport')?.addEventListener('click', () => { closeUtilityMenu(); openModal('exportModal'); });
    $$('[data-close]').forEach(btn => btn.addEventListener('click', () => closeModal(btn.dataset.close)));
    $$('.modal').forEach(modal => modal.addEventListener('click', e => { if(e.target===modal) closeModal(modal.id); }));
    document.addEventListener('keydown', e => { if(e.key==='Escape'){ $$('.modal.open').forEach(m=>closeModal(m.id)); closeUtilityMenu(); hideTracePortal(); hideHelpPortal(); } });
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
      const confidenceHelp=e.target.closest('[data-confidence-help]'); if(confidenceHelp){ openModal('confidenceModal'); e.preventDefault(); e.stopPropagation(); }
      const helpIcon=e.target.closest('.help-icon'); if(helpIcon){const wrap=helpIcon.closest('.help-wrap');if(wrap){showHelpPortal(wrap);e.preventDefault();e.stopPropagation();return;}}
      const traceMark=e.target.closest('.trace-mark'); if(traceMark){const trace=traceMark.closest('.traceable');if(trace){showTracePortal(trace);e.preventDefault();e.stopPropagation();return;}}
      const trace=e.target.closest('.traceable');
      if(trace && !e.target.closest('a,button,input,select,textarea')){showTracePortal(trace);e.preventDefault();e.stopPropagation();return;}
      if(!e.target.closest('#tracePortal')) hideTracePortal();
      if(!e.target.closest('#helpPortal')) hideHelpPortal();
      if(!e.target.closest('.utility-wrap')) closeUtilityMenu();
      const th=e.target.closest('th[data-col]'); if(th && !e.target.closest('.help-icon')){ toggleSort(th.closest('table')?.dataset.view, th.dataset.col); }
    });
    $('#tracePortal')?.addEventListener('wheel', e=>e.stopPropagation(), {passive:true});
    $('#helpPortal')?.addEventListener('wheel', e=>e.stopPropagation(), {passive:true});
    window.addEventListener('scroll', ()=>{ repositionTracePortal(); repositionHelpPortal(); }, true);
    window.addEventListener('resize', ()=>{ repositionTracePortal(); repositionHelpPortal(); });
    document.addEventListener('keydown', e=>{
      if((e.key==='Enter'||e.key===' ') && e.target.matches('.traceable')){showTracePortal(e.target);e.preventDefault();}
      if((e.key==='Enter'||e.key===' ') && e.target.matches('.help-icon')){const wrap=e.target.closest('.help-wrap');if(wrap)showHelpPortal(wrap);e.preventDefault();}
      if(e.key==='Escape'){hideTracePortal();hideHelpPortal();}
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
    closeUtilityMenu();
    hideTracePortal();
    window.scrollTo({top:0,behavior:'smooth'});
  }
  function openModal(id){ hideTracePortal(); const el=$('#'+id); if(el){ el.classList.add('open'); el.setAttribute('aria-hidden','false'); } }
  function closeModal(id){ const el=$('#'+id); if(el){ el.classList.remove('open'); el.setAttribute('aria-hidden','true'); } }

  function toggleUtilityMenu(){
    const menu=$('#utilityMenu'),btn=$('#utilityMenuToggle'); if(!menu||!btn)return;
    const open=!menu.classList.contains('open');
    menu.classList.toggle('open',open); menu.setAttribute('aria-hidden',String(!open)); btn.setAttribute('aria-expanded',String(open));
  }
  function closeUtilityMenu(){ const menu=$('#utilityMenu'),btn=$('#utilityMenuToggle'); if(menu){menu.classList.remove('open');menu.setAttribute('aria-hidden','true');} if(btn)btn.setAttribute('aria-expanded','false'); }

  let traceHideTimer=null, helpHideTimer=null;
  function cancelTraceHide(){ if(traceHideTimer){clearTimeout(traceHideTimer);traceHideTimer=null;} }
  function scheduleTraceHide(){ cancelTraceHide(); traceHideTimer=setTimeout(hideTracePortal,420); }
  function hideTracePortal(){ cancelTraceHide(); const portal=$('#tracePortal'); if(portal){portal.classList.remove('open');portal.setAttribute('aria-hidden','true');portal.innerHTML='';} state.traceSource=null; }
  function positionPortal(portal, source){
    if(!portal||!source||!portal.classList.contains('open'))return;
    const rect=source.getBoundingClientRect(),pr=portal.getBoundingClientRect(),pad=12,gap=9;
    let left=rect.left; if(left+pr.width>window.innerWidth-pad)left=window.innerWidth-pr.width-pad; left=Math.max(pad,left);
    let top=rect.bottom+gap; if(top+pr.height>window.innerHeight-pad)top=Math.max(pad,rect.top-pr.height-gap);
    portal.style.left=`${Math.round(left)}px`;portal.style.top=`${Math.round(top)}px`;
  }
  function showTracePortal(trace){
    const source=trace?.querySelector(':scope > .trace-popover'),portal=$('#tracePortal');if(!source||!portal)return;
    cancelTraceHide();state.traceSource=trace;portal.innerHTML=`<button class="floating-close" type="button" aria-label="Cerrar">×</button>${source.innerHTML}`;portal.classList.add('open');portal.setAttribute('aria-hidden','false');
    portal.querySelector('.floating-close')?.addEventListener('click',hideTracePortal);positionPortal(portal,trace);
  }
  function repositionTracePortal(){if(state.traceSource)positionPortal($('#tracePortal'),state.traceSource);}
  function cancelHelpHide(){if(helpHideTimer){clearTimeout(helpHideTimer);helpHideTimer=null;}}
  function scheduleHelpHide(){cancelHelpHide();helpHideTimer=setTimeout(hideHelpPortal,360);}
  function hideHelpPortal(){cancelHelpHide();const portal=$('#helpPortal');if(portal){portal.classList.remove('open');portal.setAttribute('aria-hidden','true');portal.textContent='';}state.helpSource=null;}
  function showHelpPortal(wrap){const source=wrap?.querySelector('.help-tip'),portal=$('#helpPortal');if(!source||!portal)return;cancelHelpHide();state.helpSource=wrap;portal.textContent=source.textContent||'';portal.classList.add('open');portal.setAttribute('aria-hidden','false');positionPortal(portal,wrap);}
  function repositionHelpPortal(){if(state.helpSource)positionPortal($('#helpPortal'),state.helpSource);}

  function valueText(value){
    if(Array.isArray(value)) return value.map(v => typeof v==='object' ? JSON.stringify(v) : String(v)).join(' · ');
    if(typeof value==='object') return JSON.stringify(value);
    return String(value ?? '');
  }
  function rowBlob(row){ return norm([row.name, ...Object.values(row.fields||{}).map(f=>valueText(f.value))].join(' ')); }
  function confidencePct(x){const n=Number(x??0);return Math.round((n<=1?n*100:n));}
  function bandLabel(b){return b==='high'?'Alta':b==='medium'?'Media':'Baja';}
  function sourceItem(ev, score, band){
    const title=esc(ev.title||ev.source||'Evidencia'), source=esc(ev.source||'Fuente pública');
    const fresh=ev.freshness_status?`vigencia: ${ev.freshness_status}${Number.isFinite(Number(ev.age_days))?` · ${ev.age_days} días`:''}`:''; const meta=[ev.date,ev.type,ev.country||ev.scope,ev.method,ev.source_grade,fresh].filter(Boolean).map(esc).join(' · ');
    return `<div class="source-item"><div class="source-confidence ${esc(band||'low')}"><b>${confidencePct(score)}%</b><span>dato</span></div><div><b>${source}</b><span>${title}</span>${ev.description?`<p>${esc(ev.description)}</p>`:''}${meta?`<small>${meta}</small>`:''}${ev.revalidation?`<small>${esc(ev.revalidation)}</small>`:''}${ev.note?`<small>${esc(ev.note)}</small>`:''}${ev.url?`<a href="${esc(ev.url)}" target="_blank" rel="noopener">Abrir fuente ↗</a>`:''}</div></div>`;
  }
  function deriveConfidenceFactors(field,item,band,evidence){
    const stored=item?.confidence_factors||field?.confidence_factors; if(Array.isArray(stored)&&stored.length)return stored;
    const factors=[], independent=new Set(evidence.map(ev=>norm(ev.source||ev.url||ev.title)).filter(Boolean)).size;
    const blobs=evidence.map(ev=>norm([ev.type,ev.method,ev.source,ev.source_type,ev.source_grade,ev.url].join(' ')));
    const official=blobs.filter(b=>/(official|primary|partner-locator|partner-directory|user-provided|vendor-own|integrator-own)/.test(b)).length;
    const indirect=blobs.filter(b=>/(job|career|vacan|aggregator|semantic|discovery|secondary)/.test(b)).length;
    const stale=evidence.filter(ev=>ev.freshness_status==='stale').length, aging=evidence.filter(ev=>ev.freshness_status==='aging').length;
    factors.push(independent>=2?`Corroboración: ${independent} fuentes/evidencias independientes.`:'Corroboración limitada: solo una fuente/evidencia independiente.');
    factors.push(official?`Calidad: ${official} evidencia(s) oficial(es) o primaria(s).`:'Calidad: todavía no hay evidencia oficial/primaria directa enlazada.');
    if(indirect)factors.push(`Tipo de señal: ${indirect} evidencia(s) son indirectas; aportan contexto o indicio, no confirmación aislada.`);
    if(stale)factors.push(`Vigencia: ${stale} evidencia(s) están fuera de ventana y requieren revalidación.`); else if(aging)factors.push(`Vigencia: ${aging} evidencia(s) están envejeciendo.`);
    if(band==='medium')factors.push('Para subir a alta: más corroboración, una fuente oficial/directa o evidencia más reciente.');
    if(band==='low')factors.push('Para subir: corroborar el indicio con fuente oficial/directa o varias evidencias independientes actuales.');
    return factors;
  }
  function traceable(field, inner, item=null){
    const evidence=(item?.evidence||field?.evidence||[]).slice(0,8);
    const score=item?.confidence ?? field?.confidence ?? 0.66;
    const band=item?.confidence_band || field?.confidence_band || (score>=.8?'high':score>=.6?'medium':'low');
    const reason=item?.confidence_reason || field?.confidence_reason || '';
    const qualifier=item?.qualifier||field?.qualifier;
    const claim=item?.claim_type||field?.claim_type||'fact';
    const factScore=item?.fact_confidence??field?.fact_confidence??score;
    const interpretationScore=item?.interpretation_confidence??field?.interpretation_confidence??Math.min(score,.7);
    const actionRisk=item?.action_risk||field?.action_risk||'medio';
    const claimLabel=claim==='signal'?'Señal':claim==='interpretation'?'Interpretación':'Hecho';
    const factors=deriveConfidenceFactors(field,item,band,evidence);
    const why=(band==='medium'||band==='low'||factors.length)?`<div class="confidence-why"><b>Por qué tiene este nivel</b><ul>${factors.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div>`:'';
    return `<div class="traceable" tabindex="0"><div class="trace-value">${inner}</div><span class="trace-mark confidence-dot ${esc(band)}" title="Confianza del hecho ${confidencePct(factScore)}%">i</span><div class="trace-popover"><strong>TRAZABILIDAD DEL DATO</strong><div class="claim-kind">${esc(claimLabel)}</div><div class="confidence-three"><span><b>${confidencePct(factScore)}%</b>Hecho</span><span><b>${confidencePct(interpretationScore)}%</b>Interpretación</span><span><b>${esc(actionRisk)}</b>Riesgo de acción</span></div>${reason?`<p class="confidence-explain">${esc(reason)}</p>`:''}${why}${qualifier?`<span class="qualifier">${esc(qualifier)}</span>`:''}<div class="trace-source-heading">Fuentes que sostienen este dato</div>${evidence.map(ev=>sourceItem(ev,factScore,band)).join('')}<button type="button" class="confidence-help-link" data-confidence-help>¿Cómo se calcula e interpreta la confianza?</button></div></div>`;
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
    const long=value.filter(v=>String(typeof v==='object'?JSON.stringify(v):v).length>34).length;
    if(context==='trend') return (value.length>=4 || long>=1) ? 2 : 3;
    if(context==='card') return (value.length>=6 || long>=2) ? 3 : 4;
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
    let cols=schema.filter(col=>col.hidden!==true);
    const order=state.columnOrder[view]||JSON.parse(localStorage.getItem(`westcon-cols-${view}`)||'null');
    if(order){state.columnOrder[view]=order; cols.sort((a,b)=>{let ai=order.indexOf(a.id),bi=order.indexOf(b.id);if(ai<0)ai=999;if(bi<0)bi=999;return ai-bi;});}
    return cols;
  }
  function missingMarkup(col){
    return '<span class="research-gap critical-gap" title="El motor mantiene este campo como tarea activa">Por investigar</span>';
  }
  function sortedRows(rows,view){const s=state.sort[view];if(!s)return rows;return [...rows].sort((a,b)=>valueText(a.fields?.[s.col]?.value??a.name).localeCompare(valueText(b.fields?.[s.col]?.value??b.name),'es',{numeric:true})*s.dir);}
  function toggleSort(view,col){if(!view)return;const cur=state.sort[view];state.sort[view]={col,dir:cur?.col===col?-cur.dir:1};renderCurrent(view);}
  function reorderColumn(view,from,to){if(!view||from===to)return;const schema=state.data.schemas[view]||[];let order=(state.columnOrder[view]||schema.map(x=>x.id)).filter(x=>schema.some(c=>c.id===x));const a=order.indexOf(from),b=order.indexOf(to);if(a<0||b<0)return;order.splice(b,0,order.splice(a,1)[0]);state.columnOrder[view]=order;localStorage.setItem(`westcon-cols-${view}`,JSON.stringify(order));renderCurrent(view);}
  function renderCurrent(view){({manufacturers:renderManufacturers,integrators:renderIntegrators,distributors:renderDistributors}[view]||(()=>{}))();}
  function tableHtml(rows, schema, emptyText, view){
    if(!rows.length)return `<div class="empty-state">${esc(emptyText)}</div>`;
    const cols=activeColumns(schema,rows,view), ordered=sortedRows(rows,view);
    return `<table data-view="${esc(view)}" class="data-table"><thead><tr><th class="entity-head name-col">Entidad</th>${cols.map(c=>headerCell(c,view)).join('')}</tr></thead><tbody>${ordered.map(row=>{const identity={value:row.name,evidence:row.evidence||[],confidence:.95,confidence_band:'high'};const direct=view==='manufacturers'&&row.direct_sales?`<span class="direct-sales-badge" title="Fabricante con señal de venta directa; no se clasifica como mayorista">Venta directa</span>`:'';return `<tr data-section="${esc(view)}" data-entity="${esc(row.name)}"><td class="name-cell name-col">${traceable(identity,`<div class="entity-name-line"><b>${esc(row.name)}</b>${direct}</div><small>Identidad trazable</small>`)}</td>${cols.map(col=>{const f=row.fields?.[col.id];return `<td data-field="${esc(col.id)}" class="col-${esc(col.id)}">${f&&hasValue(f.value)?renderValue(f,null,'table'):missingMarkup(col)}</td>`}).join('')}</tr>`}).join('')}</tbody></table>`;
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
  function renderClients(){
    const publicQ=norm($('#publicClientSearch')?.value), publicScope=$('#publicClientScope')?.value||'all';
    const privateQ=norm($('#privateClientSearch')?.value), privateScope=$('#privateClientScope')?.value||'all';
    const publicAll=state.data.clients_public||[];
    const privateAll=state.data.clients_private||[];
    const publicRows=publicAll.filter(r=>(!publicQ||rowBlob(r).includes(publicQ))&&scopeMatch(r,publicScope));
    const privateRows=privateAll.filter(r=>(!privateQ||rowBlob(r).includes(privateQ))&&scopeMatch(r,privateScope));
    $('#publicClientTable').innerHTML=tableHtml(publicRows,state.data.schemas.clients_public,'No hay oportunidades públicas con esos filtros.','clients_public');
    $('#privateClientTable').innerHTML=tableHtml(privateRows,state.data.schemas.clients_private,'No hay grandes cuentas privadas con esos filtros.','clients_private');
    setCount('#publicClientCount',publicRows.length,publicAll.length,'oportunidades públicas');
    setCount('#privateClientCount',privateRows.length,privateAll.length,'grandes cuentas privadas');
    setCount('#clientCount',publicRows.length+privateRows.length,publicAll.length+privateAll.length,'clientes / oportunidades');
  }

  function cardField(col,f,context='card'){if(!f||!hasValue(f.value))return '';const help=col.clarify?`<span class="help-wrap card-help"><span>${esc(col.label)}</span><button class="help-icon" type="button" aria-label="Aclaración de ${esc(col.label)}">?</button><span class="help-tip">${esc(col.help||'')}</span></span>`:esc(col.label);return `<div class="card-field"><label>${help}</label>${renderValue(f,null,context)}</div>`;}
  function cardGrid(rows, schema, forceAll=false, context='card'){
    const cols=forceAll?schema:activeColumns(schema,rows,'cards');
    const cardClass=context==='trend'?'intel-card trend-card':'intel-card';
    return rows.map(row=>`<article class="${cardClass}"><div class="eyebrow">INTELIGENCIA TRAZABLE</div><div class="card-title">${traceable({value:row.name,evidence:row.evidence||[],confidence:.9,confidence_band:'high'},`<h3>${esc(row.name)}</h3>`)}</div>${cols.map(c=>cardField(c,row.fields?.[c.id],context)||`<div class="card-field"><label>${esc(c.label)}</label>${missingMarkup(c)}</div>`).join('')}</article>`).join('');
  }
  function renderTrends(){
    const q=norm($('#trendSearch')?.value), all=state.data.trends||[], rows=all.filter(r=>!q||rowBlob(r).includes(q));
    $('#trendGrid').innerHTML=cardGrid(rows,state.data.schemas.trends,true,'trend')||'<div class="empty-state">No hay tendencias con ese filtro.</div>';
    setCount('#trendCount',rows.length,all.length,'tendencias'); renderTrendAnalytics(rows);
  }
  function trendActorData(limit=32){
    const actors=new Map(), portfolio=new Set((state.data.manufacturers||[]).map(x=>norm(x.name)));
    (state.data.trends||[]).forEach(t=>{['market_players','westcon_vendors'].forEach(fid=>{const f=t.fields?.[fid];(f?.items||[]).forEach(it=>{const n=String(it.value||'').split(' · ')[0],k=norm(n);if(!k||n.startsWith('Panorama'))return;const a=actors.get(k)||{name:n,trends:new Set(),evidence:0,portfolio:portfolio.has(k)};a.trends.add(t.name);a.evidence+=Math.max(1,(it.evidence||[]).length);a.portfolio=a.portfolio||fid==='westcon_vendors';actors.set(k,a);});});});
    return [...actors.values()].sort((a,b)=>(b.trends.size*10+b.evidence)-(a.trends.size*10+a.evidence)).slice(0,limit);
  }

  function stageKey(maturity){
    const m=+maturity||0; return m<25?'emerging':m<50?'accelerating':m<75?'scaling':'consolidating';
  }
  function stageLabel(maturity){
    return ({emerging:'Emergente',accelerating:'Aceleración',scaling:'Escala',consolidating:'Consolidación'})[stageKey(maturity)];
  }
  function trendLoopPoint(a){
    const m=Math.max(2,Math.min(98,+a.maturity||0)),t=m/100,angle=(-205+t*300)*Math.PI/180;
    const rx=210,ry=105,cx=245,cy=135,momentum=(+a.momentum||50)-50,nudge=Math.max(-16,Math.min(16,momentum*.18));
    return {x:cx+(rx+nudge)*Math.cos(angle),y:cy+(ry+nudge*.35)*Math.sin(angle)};
  }
  function renderTrendAnalytics(rows){
    const life=$('#trendLifecycleChart'),map=$('#vendorTrendMap');if(!life||!map)return;
    const usable=rows.filter(r=>r.analytics&&Number.isFinite(Number(r.analytics.maturity)));
    const nodes=usable.map((r,i)=>{const a=r.analytics||{},p=trendLoopPoint(a),sz=26+Math.round((+a.buyer_urgency||50)/12),stage=stageKey(a.maturity);return `<button class="trend-loop-node stage-${stage}" data-trend-index="${i+1}" style="left:${p.x}px;top:${p.y}px;width:${sz}px;height:${sz}px" title="${esc(r.name)} · fase ${esc(stageLabel(a.maturity))} · madurez ${a.maturity}% · momentum ${a.momentum}% · urgencia ${a.buyer_urgency}%"><b>${i+1}</b></button>`}).join('');
    const legend=usable.map((r,i)=>{const a=r.analytics||{},stage=stageKey(a.maturity);return `<button class="trend-legend-item" data-trend-index="${i+1}"><span class="trend-index">${i+1}</span><span class="trend-legend-name">${esc(r.name)}</span><span class="trend-stage stage-${stage}">${esc(stageLabel(a.maturity))}</span><span class="trend-legend-metrics"><span title="Momentum: velocidad de avance observada"><b>M</b> ${Math.round(+a.momentum||0)}</span><span title="Urgencia: presión de compra/adopción observada"><b>U</b> ${Math.round(+a.buyer_urgency||0)}</span></span></button>`}).join('');
    const howTo=`<div class="chart-howto"><div><b>Posición</b><span>Indica la fase de madurez. Se avanza por el recorrido desde Emergente hasta Consolidación.</span></div><div><b>Momentum (M)</b><span>Velocidad con la que crecen señales, oferta, inversión y conversación de mercado.</span></div><div><b>Tamaño / Urgencia (U)</b><span>Cuanto mayor es el nodo, mayor presión de compra o adopción observada.</span></div></div>`;
    const stages=`<div class="stage-guide"><div class="emerging"><b>Emergente</b><span>Señales tempranas; casos y oferta todavía fragmentados.</span></div><div class="accelerating"><b>Aceleración</b><span>Crece la demanda y se multiplican productos, proyectos y mensajes de mercado.</span></div><div class="scaling"><b>Escala</b><span>Adopción comercial activa; se consolidan categorías, arquitecturas y compras.</span></div><div class="consolidating"><b>Consolidación</b><span>Mercado más maduro; el valor se desplaza a integración, eficiencia y renovación.</span></div></div>`;
    life.innerHTML=`<div class="chart-title"><div><span>WESTCON TREND LOOP</span><h3>¿En qué fase está cada tendencia y con qué velocidad avanza?</h3><p>Vista de ciclo de vida propia de Westcon. Sirve para comparar madurez, velocidad y urgencia sin convertirlas en una instrucción de actuación.</p></div></div>${howTo}${stages}<div class="trend-loop-layout"><div class="trend-loop-canvas"><svg viewBox="0 0 490 270" aria-hidden="true"><defs><linearGradient id="trendLoopGradient" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#12c7c0"/><stop offset="46%" stop-color="#3195bb"/><stop offset="76%" stop-color="#f09e0d"/><stop offset="100%" stop-color="#e5007d"/></linearGradient></defs><path class="loop-track-shadow" d="M45 188 C28 95 98 25 210 33 C338 42 456 105 440 189 C426 257 319 253 253 213 C190 175 139 150 99 173 C62 194 80 231 134 235"/><path class="loop-track" d="M45 188 C28 95 98 25 210 33 C338 42 456 105 440 189 C426 257 319 253 253 213 C190 175 139 150 99 173 C62 194 80 231 134 235"/><text x="37" y="211">EMERGENTE</text><text x="125" y="48">ACELERACIÓN</text><text x="321" y="64">ESCALA</text><text x="354" y="232">CONSOLIDACIÓN</text></svg>${nodes}</div><div class="trend-loop-legend">${legend}</div></div>`;
    const actors=trendActorData(26),maxT=Math.max(1,...actors.map(a=>a.trends.size)),maxE=Math.max(1,...actors.map(a=>a.evidence));
    const points=actors.map((a,i)=>{const x=8+84*(a.trends.size/maxT),y=91-80*(a.evidence/maxE),cls=a.portfolio?'westcon':'external';return `<button class="actor-point ${cls}" data-actor-index="${i+1}" style="left:${x}%;top:${y}%" title="${esc(a.name)} · ${a.trends.size} tendencias · ${a.evidence} evidencias"><b>${i+1}</b></button>`}).join('');
    const actorLegend=actors.map((a,i)=>`<button class="actor-legend-item" data-actor-index="${i+1}"><span class="actor-index ${a.portfolio?'westcon':'external'}">${i+1}</span><span class="actor-name">${esc(a.name)}</span><span class="actor-meta">${a.trends.size} tendencias · ${a.evidence} evid.</span></button>`).join('');
    const actorHowTo=`<div class="chart-howto"><div><b>Eje horizontal</b><span>Cuántas tendencias del radar contienen evidencia pública de ese fabricante.</span></div><div><b>Eje vertical</b><span>Cuántas evidencias trazables sustentan su presencia en esas tendencias.</span></div><div><b>Color</b><span>Azul = portfolio Westcon. Blanco/rosa = otros fabricantes observados.</span></div></div>`;
    map.innerHTML=`<div class="chart-title"><div><span>WESTCON VENDOR ARENA</span><h3>¿Qué fabricantes aparecen de forma más amplia y mejor documentada?</h3><p>Mapa de cobertura temática y evidencia pública. No representa cuota de mercado, liderazgo comercial ni una clasificación propietaria de Gartner, IDC o Forrester.</p></div><div class="chart-legend"><i class="portfolio-dot"></i> Westcon · <i class="external-dot"></i> otros</div></div>${actorHowTo}<div class="vendor-arena-layout"><div><div class="actor-y">Más evidencia pública ↑</div><div class="actor-plot actor-plot-clean"><span class="quadrant-label q1">Amplio + documentado</span><span class="quadrant-label q2">Nicho + documentado</span><span class="quadrant-label q3">Nicho + señal limitada</span><span class="quadrant-label q4">Amplio + señal limitada</span>${points}</div><div class="actor-x">Menor amplitud temática ← · → Mayor amplitud temática</div><div class="actor-axis-note"><div><b>Utilidad:</b> identifica actores recurrentes en varias tendencias y separa amplitud de mera cantidad de menciones.</div><div><b>Precaución:</b> una posición alta/derecha significa mayor presencia documentada en este dataset, no «mejor fabricante».</div></div></div><div class="actor-legend-list">${actorLegend}</div></div>`;
  }

  function renderArchitectures(){
    const q=norm($('#architectureSearch')?.value), all=state.data.architectures||[], rows=all.filter(r=>!q||rowBlob(r).includes(q));
    $('#architectureGrid').innerHTML=cardGrid(rows,state.data.schemas.architectures)||'<div class="empty-state">No hay arquitecturas con ese filtro.</div>';
    setCount('#architectureCount',rows.length,all.length,'arquitecturas');
  }

  function localDateTime(value){
    if(!value) return 'Sin fecha';
    try{return new Intl.DateTimeFormat('es-ES',{timeZone:'Europe/Madrid',day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'}).format(new Date(value));}catch(_){return String(value);}
  }
  function ageText(value){
    if(!value) return 'antigüedad desconocida';
    const ms=Date.now()-new Date(value).getTime(); if(!Number.isFinite(ms)) return 'antigüedad desconocida';
    const mins=Math.max(0,Math.round(ms/60000)); if(mins<60)return `hace ${mins} min`; const hours=Math.round(mins/60); if(hours<48)return `hace ${hours} h`; return `hace ${Math.round(hours/24)} días`;
  }
  function updateProfileLabel(profile){return ({daily:'diaria',deep:'semanal profunda',exhaustive:'mensual exhaustiva',snapshot:'snapshot incluida'})[profile]||profile||'desconocida';}
  function renderUpdateStatus(){
    const run=state.lastRun||{}, meta=state.data?.meta||{}, finished=run.finished_at||meta.generated_at||'', ageHours=finished?Math.max(0,(Date.now()-new Date(finished).getTime())/36e5):9999;
    const btn=$('#dataStatusBtn'),label=$('#dataStatusLabel');
    if(btn){btn.classList.remove('fresh','stale');btn.classList.add(ageHours<=36?'fresh':'stale');}
    if(label) label.textContent=finished?`Datos · ${updateProfileLabel(run.profile)} · ${ageText(finished)}`:`Datos · estado no disponible`;
    const body=$('#updateStatusBody'); if(!body)return;
    const status=run.status==='published'?'Publicado correctamente':(run.status||'Estado no disponible');
    const counts=[['Fabricantes',run.manufacturers??state.data?.manufacturers?.length??0],['Mayoristas',run.distributors??state.data?.distributors?.length??0],['Integradores',run.integrators??state.data?.integrators?.length??0],['Clientes',run.clients??((state.data?.clients_public?.length??0)+(state.data?.clients_private?.length??0))],['Tendencias',run.trends??state.data?.trends?.length??0],['Arquitecturas',run.architectures??state.data?.architectures?.length??0]];
    body.innerHTML=`<div class="update-hero"><div class="update-stat primary"><b>${esc(status)}</b><span>Última publicación: ${esc(localDateTime(finished))} · ${esc(ageText(finished))} · ciclo ${esc(updateProfileLabel(run.profile))}</span></div><div class="update-stat"><b>${esc(run.sources??meta.source_count??0)}</b><span>fuentes / familias activas</span></div><div class="update-stat"><b>${esc(run.traceable_fields??'Por investigar')}</b><span>campos trazables publicados</span></div><div class="update-stat"><b>${esc(run.research_gaps??'Por investigar')}</b><span>huecos que el motor volverá a investigar</span></div></div><div class="update-cycles"><div class="update-cycle"><b>DIARIA · incremental</b><strong>06:23</strong><span>Todos los días, hora de Madrid. Busca cambios recientes, nuevas relaciones, señales, empleo, casos y evidencias que puedan modificar confianza.</span></div><div class="update-cycle"><b>SEMANAL · profunda</b><strong>Domingo 04:47</strong><span>Amplía partner locators, webs de integradores, mayoristas, clientes públicos/privados, contratación, certificaciones, servicios, casos, portales de empleo y fuentes de mercado.</span></div><div class="update-cycle"><b>MENSUAL · exhaustiva</b><strong>Día 1 · 03:17</strong><span>Revisa long-tail, huecos persistentes, nuevas entidades, tendencias, arquitecturas, evidencias envejecidas y cobertura general.</span></div></div><div class="update-scope"><div><b>Qué datos pueden cambiar</b><span>Fabricante↔integrador, fabricante↔mayorista, fabricantes de cada integrador, servicios, especializaciones, verticales, casos, certificaciones, empleo, competidores, métricas y actores de tendencias, encaje de arquitecturas, fuentes, fechas y confianza.</span></div><div><b>Cómo comprobarlo</b><span>Este botón muestra la última publicación y el tipo de ciclo. En GitHub → Actions puedes verificar research-daily, research-weekly y research-monthly y comprobar si finalizaron correctamente.</span></div><div><b>Qué ocurre con una celda vacía</b><span>No se da por buena: entra en la cola de investigación y genera nuevas rutas de búsqueda. Si aparece una señal débil puede publicarse en rojo; si se corrobora, la confianza puede subir a amarillo o verde.</span></div><div><b>Qué ocurre con evidencia antigua</b><span>El motor conserva fecha y vigencia, vuelve a sondear la relación y puede mantener, degradar o elevar su confianza según la nueva evidencia encontrada.</span></div></div><div class="update-note">Los horarios mostrados son hora local de Madrid y el workflow incluye guardia de horario de verano/invierno. La automatización actualiza inteligencia pública y trazabilidad; no genera salidas prescriptivas.</div><div class="update-scope">${counts.map(([k,v])=>`<div><b>${esc(k)}</b><span>${esc(v)} entidades en la fotografía publicada</span></div>`).join('')}</div>`;
  }

  function renderConfidenceGuide(){
    const el=$('#confidenceDistribution'); if(!el||!state.data)return;
    const counts={high:0,medium:0,low:0};
    let total=0;
    for(const section of ['manufacturers','distributors','integrators','clients_public','clients_private','trends','architectures']){
      for(const row of state.data[section]||[]){
        for(const f of Object.values(row.fields||{})){
          const items=f?.items||[];
          if(items.length){ for(const it of items){ const b=it.confidence_band||'low'; counts[b]=(counts[b]||0)+1; total++; } }
          else if(f?.confidence_band){ const b=f.confidence_band; counts[b]=(counts[b]||0)+1; total++; }
        }
      }
    }
    const pct=n=>total?Math.round(n*100/total):0;
    el.innerHTML=`<div><b>Distribución publicada actual</b><span>La mezcla cambia automáticamente cuando se incorporan o revalidan evidencias.</span></div><div class="confidence-dist-bars"><span class="high" style="--pct:${pct(counts.high)}%"><b>${counts.high}</b><small>Alta · ${pct(counts.high)}%</small></span><span class="medium" style="--pct:${pct(counts.medium)}%"><b>${counts.medium}</b><small>Media · ${pct(counts.medium)}%</small></span><span class="low" style="--pct:${pct(counts.low)}%"><b>${counts.low}</b><small>Baja · ${pct(counts.low)}%</small></span></div>`;
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
    distributors:{label:'Mayoristas de la competencia',eyebrow:'CANAL COMPETITIVO',desc:'Linecards, solape, servicios y capacidades de los mayoristas competidores con evidencia pública.',accent:'E5007D'},
    integrators:{label:'Integradores',eyebrow:'ECOSISTEMA IBERIA',desc:'Partners, integradores, instaladores, VAR, MSP/MSSP, consultoras y service providers vinculados a nuestros fabricantes.',accent:'F09E0D'},
    clients_public:{label:'Clientes públicos',eyebrow:'CLIENTES · ADMINISTRACIÓN PÚBLICA',desc:'Pliegos, perfiles del contratante, estrategias digitales y oportunidades tratadas como pipeline comercial trazable.',accent:'3195BB'},
    clients_private:{label:'Clientes privados',eyebrow:'CLIENTES · GRANDES CUENTAS',desc:'Grandes cuentas ES/PT con señales públicas de tecnología, talento y ventanas de renovación compatibles con Westcon.',accent:'159B7F'},
    trends:{label:'Tendencias',eyebrow:'TENDENCIAS 2026–2030',desc:'Mercado, crecimiento, drivers, demanda y actores relevantes observados en analistas y fuentes sectoriales.',accent:'3195BB'},
    architectures:{label:'Arquitecturas',eyebrow:'ARQUITECTURAS',desc:'Marcos funcionales basados en analistas y estándares, con encaje explícito del portfolio Westcon por capa.',accent:'159B7F'}
  };
  function exportSections(modules){
    const sections=[];
    if(modules.has('manufacturers')) sections.push(['manufacturers',state.data.manufacturers,state.data.schemas.manufacturers]);
    if(modules.has('distributors')) sections.push(['distributors',state.data.distributors,state.data.schemas.distributors]);
    if(modules.has('integrators')) sections.push(['integrators',state.data.integrators,state.data.schemas.integrators]);
    if(modules.has('clients')){
      sections.push(['clients_public',state.data.clients_public||[],state.data.schemas.clients_public]);
      sections.push(['clients_private',state.data.clients_private||[],state.data.schemas.clients_private]);
    }
    if(modules.has('trends')) sections.push(['trends',state.data.trends,state.data.schemas.trends]);
    if(modules.has('architectures')) sections.push(['architectures',state.data.architectures,state.data.schemas.architectures]);
    return sections.filter(([,rows])=>Array.isArray(rows));
  }
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
  function reportFooter(label){return `<footer class="r-footer"><span>${esc(label)}</span><span>v${esc(state.data.meta.version||'3.15.0')} · ${esc(state.data.meta.scope||'Iberia')} · inteligencia trazable</span></footer>`;}
  function numericAmountMillions(value){
    const raw=valueText(value).replace(/\s/g,'').replace(',','.');const m=raw.match(/(\d+(?:\.\d+)?)([mk])?€/i)||raw.match(/(\d+(?:\.\d+)?)([mk])?/i);if(!m)return 0;let n=Number(m[1])||0;const unit=(m[2]||'').toLowerCase();if(unit==='k')n/=1000;else if(unit!=='m'&&n>1000)n/=1e6;return n;
  }
  function fieldArray(row,id){const v=row?.fields?.[id]?.value;return Array.isArray(v)?v:(hasValue(v)?[v]:[]);}
  function rowSignalScore(row){return Object.values(row?.fields||{}).reduce((sum,f)=>sum+(Array.isArray(f?.value)?f.value.length:(hasValue(f?.value)?1:0))+Math.min(4,(f?.evidence||[]).length),0);}
  function executiveInsights(){
    const publicRows=state.data.clients_public||[],privateRows=state.data.clients_private||[],trends=state.data.trends||[],manufacturers=state.data.manufacturers||[],integrators=state.data.integrators||[],distributors=state.data.distributors||[];
    const publicRank=[...publicRows].map(r=>({...r,_amount:numericAmountMillions(r.fields?.estimated_amount?.value)})).sort((a,b)=>(b._amount-a._amount)||(rowSignalScore(b)-rowSignalScore(a)));
    const privateRank=[...privateRows].sort((a,b)=>rowSignalScore(b)-rowSignalScore(a));
    const trendRank=[...trends].sort((a,b)=>(+(b.analytics?.buyer_urgency||0)+ +(b.analytics?.momentum||0))-(+(a.analytics?.buyer_urgency||0)+ +(a.analytics?.momentum||0)));
    const vendorRank=[...manufacturers].map(r=>({row:r,breadth:fieldArray(r,'integrators').length+fieldArray(r,'competitors').length+fieldArray(r,'distributors').length})).sort((a,b)=>b.breadth-a.breadth);
    const totalAmount=publicRank.reduce((s,r)=>s+r._amount,0),hotTrends=trends.filter(r=>+(r.analytics?.buyer_urgency||0)>=70).length;
    return {publicRank,privateRank,trendRank,vendorRank,totalAmount,hotTrends,counts:{manufacturers:manufacturers.length,distributors:distributors.length,integrators:integrators.length,publicClients:publicRows.length,privateClients:privateRows.length,trends:trends.length,architectures:(state.data.architectures||[]).length}};
  }
  function executiveBulletPublic(row){const amount=valueText(row.fields?.estimated_amount?.value||'importe no publicado'),area=compactValue(row.fields?.opportunity_area?.value||'',3,80),date=valueText(row.fields?.milestone_date?.value||'fecha por investigar');return `<li><b>${esc(row.name)}</b> · ${esc(amount)} · ${esc(date)}<br><span>${esc(area)}</span></li>`;}
  function reportExecutivePage(){
    const x=executiveInsights(),amount=x.totalAmount?`${x.totalAmount.toLocaleString('es-ES',{maximumFractionDigits:1})} M€`: 'Por investigar',topPrivate=x.privateRank.slice(0,5),topTrends=x.trendRank.slice(0,5),topVendors=x.vendorRank.slice(0,5);
    return `<section class="report-page r-section-page r-executive-page" style="--accent:#${exportTheme.cyan}"><div class="r-page-head"><div>${reportBrand()}<div class="r-eyebrow">LECTURA EJECUTIVA</div><h2>Qué destaca en la fotografía actual</h2><p>Síntesis calculada sobre la inteligencia seleccionada: oportunidades públicas, grandes cuentas, momentum tecnológico y amplitud de ecosistema. No es una clasificación comercial automática.</p></div><div class="r-page-count"><b>${esc(state.data.meta.source_count||0)}</b><span>fuentes/familias</span></div></div><div class="r-executive-grid"><div class="r-executive-kpi"><b>${x.counts.publicClients}</b><span>oportunidades públicas</span></div><div class="r-executive-kpi"><b>${esc(amount)}</b><span>monto observable agregado</span></div><div class="r-executive-kpi"><b>${x.counts.privateClients}</b><span>grandes cuentas privadas</span></div><div class="r-executive-kpi"><b>${x.hotTrends}</b><span>tendencias con urgencia ≥70</span></div></div><div class="r-executive-columns"><div class="r-exec-card"><h3>Oportunidades públicas con mayor señal económica</h3><ol>${x.publicRank.slice(0,5).map(executiveBulletPublic).join('')||'<li>Sin datos suficientes</li>'}</ol></div><div class="r-exec-card"><h3>Grandes cuentas con mayor densidad de señales</h3><ol>${topPrivate.map(r=>`<li><b>${esc(r.name)}</b> · ${esc(compactValue(r.fields?.technology_signals?.value||'',3,95))}<br><span>Encaje: ${esc(compactValue(r.fields?.westcon_fit?.value||'',3,95))}</span></li>`).join('')}</ol></div><div class="r-exec-card"><h3>Momentum tecnológico</h3><ol>${topTrends.map(r=>`<li><b>${esc(r.name)}</b> · ${esc(stageLabel(r.analytics?.maturity))}<br><span>Momentum ${Math.round(+r.analytics?.momentum||0)} · urgencia ${Math.round(+r.analytics?.buyer_urgency||0)}</span></li>`).join('')}</ol></div><div class="r-exec-card"><h3>Fabricantes con ecosistema más amplio en el dataset</h3><ol>${topVendors.map(v=>`<li><b>${esc(v.row.name)}</b> · ${v.breadth} relaciones/señales de ecosistema<br><span>${fieldArray(v.row,'integrators').length} partners · ${fieldArray(v.row,'competitors').length} peers · ${fieldArray(v.row,'distributors').length} mayoristas</span></li>`).join('')}</ol></div></div>${reportFooter('Lectura ejecutiva')}</section>`;
  }
  function reportCover(title,modules){
    const stats=[
      ['manufacturers','Fabricantes',state.data.manufacturers.length],['distributors','Mayoristas',state.data.distributors.length],['integrators','Integradores',state.data.integrators.length],['clients','Clientes',((state.data.clients_public||[]).length+(state.data.clients_private||[]).length)],['trends','Tendencias',state.data.trends.length],['architectures','Arquitecturas',state.data.architectures.length]
    ].filter(x=>modules.has(x[0]));
    return `<section class="report-page report-cover">
      <div class="r-cover-top">${reportBrand()}<span class="r-version">v${esc(state.data.meta.version||'3.15.0')}</span></div>
      <div class="r-cover-main"><div class="r-kicker">INTELIGENCIA DE NEGOCIO · ESPAÑA + PORTUGAL</div><h1>${esc(title)}</h1><p>Informe ejecutivo construido desde la evidencia trazable: primero síntesis y hallazgos, después detalle y fuentes.</p></div>
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
    const sections=[reportCover(title,modules),reportExecutivePage()];
    const order=exportSections(modules);
    order.forEach(([key,rows,schema])=>{if(!rows?.length)return; if(key==='trends'||key==='architectures') rows.forEach((r,i)=>sections.push(reportCardPage(key,r,i,rows.length,schema))); else sections.push(reportTablePages(key,rows,schema)); if(key==='trends')sections.push(reportTrendAnalyticsPage()); sections.push(reportSourcesPages(key,rows));});
    return `<div class="report-export">${sections.join('')}</div>`;
  }
  function pdfRgb(hex){const h=String(hex||'000000').replace('#','');return [parseInt(h.slice(0,2),16),parseInt(h.slice(2,4),16),parseInt(h.slice(4,6),16)];}
  function pdfFill(pdf,hex){pdf.setFillColor(...pdfRgb(hex));}
  function pdfStroke(pdf,hex){pdf.setDrawColor(...pdfRgb(hex));}
  function pdfTextColor(pdf,hex){pdf.setTextColor(...pdfRgb(hex));}
  function pdfBrand(pdf,dark=false){
    const base=dark?exportTheme.white:exportTheme.navy,sub=dark?'C9D7DE':exportTheme.muted;
    [exportTheme.orange,exportTheme.pink,exportTheme.cyan].forEach((c,i)=>{pdfFill(pdf,c);pdf.rect(12+i*2.3,9,1.6,8,'F');});
    pdf.setFont('helvetica','bold');pdf.setFontSize(10);pdfTextColor(pdf,base);pdf.text('WESTCON IBERIA',21,13);
    pdf.setFont('helvetica','normal');pdf.setFontSize(6);pdfTextColor(pdf,sub);pdf.text('BUSINESS INTELLIGENCE',21,17);
  }
  function pdfFooter(pdf,label,dark=false){const w=pdf.internal.pageSize.getWidth(),h=pdf.internal.pageSize.getHeight();pdfStroke(pdf,dark?'315267':exportTheme.line);pdf.setLineWidth(.25);pdf.line(12,h-11,w-12,h-11);pdf.setFontSize(6);pdf.setFont('helvetica','normal');pdfTextColor(pdf,dark?'AFC1CA':exportTheme.muted);pdf.text(label,12,h-6);pdf.text(`v${state.data.meta.version||'3.15.0'} · ${state.data.meta.scope||'Iberia'} · inteligencia trazable`,w-12,h-6,{align:'right'});}
  function pdfPageTitle(pdf,title,subtitle='',accent=exportTheme.cyan){pdfBrand(pdf,false);pdfFill(pdf,accent);pdf.rect(12,25,2,15,'F');pdf.setFont('helvetica','bold');pdf.setFontSize(22);pdfTextColor(pdf,exportTheme.navy);pdf.text(title,18,34);pdf.setFont('helvetica','normal');pdf.setFontSize(8);pdfTextColor(pdf,exportTheme.muted);const lines=pdf.splitTextToSize(subtitle,250);pdf.text(lines,18,41);}
  function pdfKpi(pdf,x,y,w,label,value,accent){pdfFill(pdf,exportTheme.white);pdfStroke(pdf,exportTheme.line);pdf.roundedRect(x,y,w,24,3,3,'FD');pdfFill(pdf,accent);pdf.rect(x,y,2,24,'F');pdf.setFont('helvetica','bold');pdf.setFontSize(17);pdfTextColor(pdf,exportTheme.navy);pdf.text(String(value),x+6,y+10);pdf.setFont('helvetica','normal');pdf.setFontSize(6.5);pdfTextColor(pdf,exportTheme.muted);pdf.text(label.toUpperCase(),x+6,y+17);}
  function pdfListCard(pdf,x,y,w,h,title,items,accent){pdfFill(pdf,exportTheme.white);pdfStroke(pdf,exportTheme.line);pdf.roundedRect(x,y,w,h,3,3,'FD');pdfFill(pdf,accent);pdf.rect(x,y,w,1.5,'F');pdf.setFont('helvetica','bold');pdf.setFontSize(9);pdfTextColor(pdf,exportTheme.navy);pdf.text(title,x+5,y+8);let yy=y+15;pdf.setFont('helvetica','normal');pdf.setFontSize(6.4);for(const item of items.slice(0,5)){pdfFill(pdf,accent);pdf.circle(x+6,yy-1.4,1.3,'F');pdf.setFont('helvetica','bold');pdfTextColor(pdf,exportTheme.ink);const titleLines=pdf.splitTextToSize(String(item.title||''),w-16).slice(0,2);pdf.text(titleLines,x+10,yy);yy+=titleLines.length*3.2;pdf.setFont('helvetica','normal');pdfTextColor(pdf,exportTheme.muted);const metaLines=pdf.splitTextToSize(String(item.meta||''),w-16).slice(0,2);pdf.text(metaLines,x+10,yy);yy+=metaLines.length*3.1+3;if(yy>y+h-5)break;}}
  function pdfAddCover(pdf,title,modules){const w=pdf.internal.pageSize.getWidth(),h=pdf.internal.pageSize.getHeight();pdfFill(pdf,exportTheme.navy);pdf.rect(0,0,w,h,'F');pdfBrand(pdf,true);pdfFill(pdf,exportTheme.cyan);pdf.rect(w-17,0,4,h,'F');pdfFill(pdf,exportTheme.pink);pdf.rect(w-12,0,4,h,'F');pdfFill(pdf,exportTheme.orange);pdf.rect(w-7,0,4,h,'F');pdf.setFont('helvetica','bold');pdf.setFontSize(8);pdfTextColor(pdf,exportTheme.cyan);pdf.text('INTELIGENCIA DE NEGOCIO · ESPAÑA + PORTUGAL',16,48);pdf.setFontSize(29);pdfTextColor(pdf,exportTheme.white);const tl=pdf.splitTextToSize(title,230).slice(0,3);pdf.text(tl,16,65);pdf.setFont('helvetica','normal');pdf.setFontSize(11);pdfTextColor(pdf,'D2E0E6');pdf.text('Lectura ejecutiva · oportunidades · cuentas · ecosistema · tendencias · arquitecturas',16,93);const stats=[['manufacturers','FAB',state.data.manufacturers.length],['distributors','MAY',state.data.distributors.length],['integrators','INT',state.data.integrators.length],['clients','CLI',(state.data.clients_public||[]).length+(state.data.clients_private||[]).length],['trends','TEN',state.data.trends.length],['architectures','ARQ',state.data.architectures.length]].filter(x=>modules.has(x[0]));stats.slice(0,6).forEach((s,i)=>{const x=16+i*30;pdfFill(pdf,'113A50');pdfStroke(pdf,'315267');pdf.roundedRect(x,120,25,18,2,2,'FD');pdf.setFont('helvetica','bold');pdf.setFontSize(13);pdfTextColor(pdf,exportTheme.white);pdf.text(String(s[2]),x+12.5,128,{align:'center'});pdf.setFontSize(5.5);pdfTextColor(pdf,'AFC1CA');pdf.text(s[1],x+12.5,134,{align:'center'});});pdf.setFont('helvetica','normal');pdf.setFontSize(7);pdfTextColor(pdf,'9EB8C5');pdf.text(`${state.data.meta.source_count||0} fuentes/familias públicas · generado ${state.data.meta.generated_at||''}`,16,h-23);pdfFooter(pdf,'Westcon Iberia · Business Intelligence',true);}
  function pdfAddExecutive(pdf){pdf.addPage('a4','landscape');pdfPageTitle(pdf,'Lectura ejecutiva','Qué destaca en la fotografía actual. Síntesis calculada sobre la inteligencia publicada; no es una clasificación comercial automática.',exportTheme.cyan);const x=executiveInsights(),amount=x.totalAmount?`${x.totalAmount.toLocaleString('es-ES',{maximumFractionDigits:1})} M€`: 'Por investigar';pdfKpi(pdf,12,54,62,'Oportunidades públicas',x.counts.publicClients,exportTheme.cyan);pdfKpi(pdf,79,54,62,'Monto observable',amount,exportTheme.orange);pdfKpi(pdf,146,54,62,'Grandes cuentas',x.counts.privateClients,exportTheme.pink);pdfKpi(pdf,213,54,72,'Tendencias urgencia ≥70',x.hotTrends,exportTheme.blue);pdfListCard(pdf,12,84,132,47,'Oportunidades públicas con mayor señal económica',x.publicRank.map(r=>({title:r.name,meta:`${valueText(r.fields?.estimated_amount?.value||'importe por investigar')} · ${valueText(r.fields?.milestone_date?.value||'fecha por investigar')} · ${compactValue(r.fields?.opportunity_area?.value||'',2,70)}`})),exportTheme.cyan);pdfListCard(pdf,151,84,134,47,'Grandes cuentas con mayor densidad de señales',x.privateRank.map(r=>({title:r.name,meta:`${compactValue(r.fields?.technology_signals?.value||'',2,70)} · Encaje: ${compactValue(r.fields?.westcon_fit?.value||'',2,65)}`})),exportTheme.orange);pdfListCard(pdf,12,137,132,47,'Momentum tecnológico',x.trendRank.map(r=>({title:r.name,meta:`${stageLabel(r.analytics?.maturity)} · momentum ${Math.round(+r.analytics?.momentum||0)} · urgencia ${Math.round(+r.analytics?.buyer_urgency||0)}`})),exportTheme.blue);pdfListCard(pdf,151,137,134,47,'Fabricantes con ecosistema más amplio',x.vendorRank.map(v=>({title:v.row.name,meta:`${v.breadth} relaciones/señales · ${fieldArray(v.row,'integrators').length} partners · ${fieldArray(v.row,'competitors').length} peers`})),exportTheme.green);pdfFooter(pdf,'Lectura ejecutiva');}
  function pdfAddDomain(pdf,key,rows){if(!rows?.length)return;const info=domainCopy[key],rank=domainTopRows(key,rows);pdf.addPage('a4','landscape');pdfPageTitle(pdf,info.label,info.desc,info.accent);const avg=Math.round(rows.reduce((s,r)=>s+rowEvidenceCount(r),0)/Math.max(1,rows.length));pdfKpi(pdf,12,54,62,'Entidades',rows.length,info.accent);pdfKpi(pdf,79,54,62,'Evidencias medias',avg,exportTheme.blue);pdfKpi(pdf,146,54,62,'Fuentes/familias',state.data.meta.source_count||0,exportTheme.green);const cleanup=key==='distributors'?(state.data.meta?.distribution_cleanup?.removed_manufacturer_rows||0):0;pdfKpi(pdf,213,54,72,key==='distributors'?'Fabricantes excluidos':'Cobertura',key==='distributors'?cleanup:'ES + PT',exportTheme.orange);const items=rank.slice(0,10).map(r=>({title:r.name,meta:domainMetaLine(key,r)}));pdfListCard(pdf,12,84,132,94,'Principales entidades / elementos',items.slice(0,5),info.accent);pdfListCard(pdf,151,84,134,94,'Continuación',items.slice(5,10),info.accent);pdfFooter(pdf,`${info.label} · lectura ejecutiva`);}
  function pdfAddMethodology(pdf,rows){pdf.addPage('a4','landscape');pdfPageTitle(pdf,'Fuentes, confianza y gobernanza','Cómo leer el informe y entender la solidez de la evidencia pública.',exportTheme.green);const classes=new Map();for(const s of state.data.source_catalog||[])classes.set(s.class||'otras',(classes.get(s.class||'otras')||0)+1);const top=[...classes.entries()].sort((a,b)=>b[1]-a[1]).slice(0,10);pdfListCard(pdf,12,58,132,115,'Principales clases de fuente',top.map(([k,v])=>({title:k,meta:`${v} fuentes / familias`})),exportTheme.green);pdfListCard(pdf,151,58,134,115,'Reglas de lectura',[{title:'Evidencia pública',meta:'Cada campo conserva fuente, fecha, tipo, vigencia y nivel de confianza.'},{title:'Confianza',meta:'Alta 80–99% · Media 60–79% · Baja 35–59% · por debajo de 35% no se publica.'},{title:'Separación de roles',meta:'Fabricantes y mayoristas se clasifican de forma excluyente; la venta directa se marca en Fabricantes.'},{title:'Trazabilidad',meta:`${uniqueEvidence(rows,9999).length} evidencias únicas en las áreas seleccionadas.`}],exportTheme.blue);pdfFooter(pdf,'Metodología y gobernanza');}
  async function exportPdf(){
    const modules=selectedModules();if(!modules.size){toast('Selecciona al menos un área');return;}if(!window.jspdf?.jsPDF){toast('El motor PDF no está disponible');return;}
    const title=$('#reportTitle')?.value.trim()||'Westcon Iberia · Business Intelligence';closeModal('exportModal');toast('Generando PDF ejecutivo…');
    try{const pdf=new window.jspdf.jsPDF({orientation:'landscape',unit:'mm',format:'a4',compress:true});pdf.setProperties({title,subject:'Westcon Iberia Business Intelligence',author:'Westcon Iberia'});pdfAddCover(pdf,title,modules);pdfAddExecutive(pdf);const selected=[];for(const [key,rows] of exportSections(modules)){if(!rows?.length)continue;selected.push(...rows);pdfAddDomain(pdf,key,rows);}pdfAddMethodology(pdf,selected);pdf.save('Westcon_Iberia_Business_Intelligence_v3.15.0.pdf');toast('PDF ejecutivo generado');}catch(err){console.error(err);toast('No se pudo generar el PDF');}
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
    slide.addText(`v${state.data.meta.version||'3.15.0'} · ${state.data.meta.scope||'Iberia'} · trazabilidad en la aplicación`,{x:7.0,y:7.1,w:5.75,h:.14,fontFace:'Aptos',fontSize:6.6,color,align:'right',margin:0});
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
  function pptAddKpi(slide,pptx,x,y,w,label,value,accent){
    slide.addShape(pptx.ShapeType.roundRect,{x,y,w,h:.86,rectRadius:.05,fill:{color:exportTheme.white},line:{color:exportTheme.line,pt:.8}});
    slide.addShape(pptx.ShapeType.rect,{x,y,w:.07,h:.86,fill:{color:accent},line:{color:accent}});
    slide.addText(String(value),{x:x+.18,y:y+.17,w:w-.32,h:.28,fontFace:'Aptos Display',fontSize:20,bold:true,color:exportTheme.navy,margin:0,fit:'shrink'});
    slide.addText(label.toUpperCase(),{x:x+.18,y:y+.55,w:w-.32,h:.12,fontFace:'Aptos',fontSize:5.8,bold:true,color:exportTheme.muted,margin:0,charSpacing:.5,fit:'shrink'});
  }
  function pptAddExecutiveList(slide,pptx,title,items,x,y,w,h,accent){
    slide.addShape(pptx.ShapeType.roundRect,{x,y,w,h,rectRadius:.04,fill:{color:exportTheme.white},line:{color:exportTheme.line,pt:.8}});
    slide.addShape(pptx.ShapeType.rect,{x,y,w,h:.065,fill:{color:accent},line:{color:accent}});
    slide.addText(title,{x:x+.18,y:y+.18,w:w-.36,h:.25,fontFace:'Aptos Display',fontSize:12.5,bold:true,color:exportTheme.navy,margin:0,fit:'shrink'});
    let yy=y+.58;items.slice(0,5).forEach((it,i)=>{slide.addShape(pptx.ShapeType.ellipse,{x:x+.18,y:yy+.02,w:.22,h:.22,fill:{color:'E8F3F6'},line:{color:'B8D4DF',pt:.5}});slide.addText(String(i+1),{x:x+.18,y:yy+.075,w:.22,h:.07,fontFace:'Aptos',fontSize:4.7,bold:true,color:exportTheme.navy,align:'center',margin:0});slide.addText(it.title,{x:x+.5,y:yy,w:w-.68,h:.16,fontFace:'Aptos',fontSize:7.2,bold:true,color:exportTheme.ink,margin:0,fit:'shrink'});slide.addText(it.meta||'',{x:x+.5,y:yy+.18,w:w-.68,h:.20,fontFace:'Aptos',fontSize:5.8,color:exportTheme.muted,margin:0,fit:'shrink'});yy+=.49;});
  }
  function pptAddExecutiveSummary(pptx,modules){
    const x=executiveInsights(), amount=x.totalAmount?`${x.totalAmount.toLocaleString('es-ES',{maximumFractionDigits:1})} M€`: 'Por investigar';
    let slide=pptx.addSlide();slide.background={color:exportTheme.bg};pptAddSlideTitle(slide,pptx,'Lectura ejecutiva','Síntesis de la fotografía actual · foco en oportunidades, cuentas, tendencias y ecosistema',exportTheme.cyan);
    const kpis=[['Oportunidades públicas',x.counts.publicClients,exportTheme.cyan],['Monto observable',amount,exportTheme.orange],['Grandes cuentas privadas',x.counts.privateClients,exportTheme.pink],['Tendencias urgencia ≥70',x.hotTrends,exportTheme.green]];
    kpis.forEach((k,i)=>pptAddKpi(slide,pptx,.58+i*3.03,1.72,2.75,k[0],k[1],k[2]));
    const pub=x.publicRank.slice(0,5).map(r=>({title:r.name,meta:`${valueText(r.fields?.estimated_amount?.value||'importe por investigar')} · ${valueText(r.fields?.milestone_date?.value||'fecha por investigar')} · ${compactValue(r.fields?.opportunity_area?.value||'',2,55)}`}));
    const tr=x.trendRank.slice(0,5).map(r=>({title:r.name,meta:`${stageLabel(r.analytics?.maturity)} · momentum ${Math.round(+r.analytics?.momentum||0)} · urgencia ${Math.round(+r.analytics?.buyer_urgency||0)}`}));
    pptAddExecutiveList(slide,pptx,'Oportunidades públicas con mayor señal',pub,.58,2.92,6.0,3.75,exportTheme.blue);
    pptAddExecutiveList(slide,pptx,'Momentum tecnológico',tr,6.78,2.92,6.0,3.75,exportTheme.orange);
    pptAddFooter(slide,pptx,'Lectura ejecutiva',false);

    slide=pptx.addSlide();slide.background={color:exportTheme.bg};pptAddSlideTitle(slide,pptx,'Cuentas y ecosistema','Dónde se concentra la densidad de señales públicas del dataset',exportTheme.pink);
    const priv=x.privateRank.slice(0,5).map(r=>({title:r.name,meta:`${compactValue(r.fields?.technology_signals?.value||'',2,58)} · encaje ${compactValue(r.fields?.westcon_fit?.value||'',2,58)}`}));
    const vendors=x.vendorRank.slice(0,5).map(v=>({title:v.row.name,meta:`${fieldArray(v.row,'integrators').length} partners · ${fieldArray(v.row,'competitors').length} peers · ${fieldArray(v.row,'distributors').length} mayoristas`}));
    pptAddExecutiveList(slide,pptx,'Grandes cuentas con más señales',priv,.58,1.82,6.0,4.85,exportTheme.pink);
    pptAddExecutiveList(slide,pptx,'Fabricantes con ecosistema más amplio',vendors,6.78,1.82,6.0,4.85,exportTheme.cyan);
    pptAddFooter(slide,pptx,'Cuentas y ecosistema',false);
  }
  function domainTopRows(key,rows){
    const score=r=>{if(key==='clients_public')return numericAmountMillions(r.fields?.estimated_amount?.value)*10+rowSignalScore(r);if(key==='clients_private')return rowSignalScore(r);if(key==='manufacturers')return fieldArray(r,'integrators').length*3+fieldArray(r,'competitors').length*2+rowEvidenceCount(r);if(key==='integrators')return fieldArray(r,'vendor_relations').length*4+rowEvidenceCount(r);if(key==='distributors')return fieldArray(r,'vendor_relations').length*3+fieldArray(r,'westcon_overlap').length*3+rowEvidenceCount(r);return rowSignalScore(r);};return [...rows].sort((a,b)=>score(b)-score(a));
  }
  function domainMetaLine(key,row){
    if(key==='clients_public')return `${valueText(row.fields?.estimated_amount?.value||'importe por investigar')} · ${valueText(row.fields?.milestone_date?.value||'fecha por investigar')} · ${compactValue(row.fields?.opportunity_area?.value||'',2,55)}`;
    if(key==='clients_private')return `${compactValue(row.fields?.technology_signals?.value||'',2,60)} · ${compactValue(row.fields?.westcon_fit?.value||'',2,60)}`;
    if(key==='manufacturers')return `${fieldArray(row,'integrators').length} partners · ${fieldArray(row,'competitors').length} peers · ${fieldArray(row,'distributors').length} mayoristas alternativos`;
    if(key==='integrators')return `${fieldArray(row,'vendor_relations').length} fabricantes Westcon · ${compactValue(row.fields?.services?.value||'',2,60)}`;
    if(key==='distributors')return `${fieldArray(row,'westcon_overlap').length} fabricantes solapados · ${fieldArray(row,'vendor_relations').length} linecard detectado`;
    return `${rowEvidenceCount(row)} evidencias`;
  }
  function pptAddDomainExecutive(pptx,key,rows){
    if(!rows?.length||key==='trends'||key==='architectures')return;const info=domainCopy[key],rank=domainTopRows(key,rows),avg=Math.round(rows.reduce((s,r)=>s+rowEvidenceCount(r),0)/Math.max(1,rows.length)),direct=key==='manufacturers'?rows.filter(r=>r.direct_sales).length:0;
    const slide=pptx.addSlide();slide.background={color:exportTheme.bg};pptAddSlideTitle(slide,pptx,info.label,info.desc,info.accent);
    pptAddKpi(slide,pptx,.58,1.72,2.65,'Entidades',rows.length,info.accent);pptAddKpi(slide,pptx,3.45,1.72,2.65,'Evidencias medias',avg,exportTheme.blue);pptAddKpi(slide,pptx,6.32,1.72,2.65,key==='manufacturers'?'Venta directa':'Cobertura',key==='manufacturers'?direct:'ES + PT',exportTheme.orange);pptAddKpi(slide,pptx,9.19,1.72,3.58,'Fuentes/familias',state.data.meta.source_count||0,exportTheme.green);
    let y=2.95;rank.slice(0,8).forEach((r,i)=>{const left=i<4,x=left?.58:6.78,yy=2.95+(i%4)*.9,w=6.0;slide.addShape(pptx.ShapeType.roundRect,{x,y:yy,w,h:.72,rectRadius:.04,fill:{color:exportTheme.white},line:{color:exportTheme.line,pt:.65}});slide.addText(`${i+1}`,{x:x+.16,y:yy+.22,w:.28,h:.13,fontFace:'Aptos',fontSize:7,bold:true,color:info.accent,align:'center',margin:0});slide.addText(r.name,{x:x+.52,y:yy+.13,w:w-.72,h:.16,fontFace:'Aptos',fontSize:8.2,bold:true,color:exportTheme.navy,margin:0,fit:'shrink'});slide.addText(domainMetaLine(key,r),{x:x+.52,y:yy+.34,w:w-.72,h:.18,fontFace:'Aptos',fontSize:6,color:exportTheme.muted,margin:0,fit:'shrink'});});
    slide.addText('Orden: densidad de señales y/o magnitud observable según el área. Es una lectura del dataset, no una clasificación comercial automática.',{x:.65,y:6.62,w:11.9,h:.18,fontFace:'Aptos',fontSize:6.1,italic:true,color:exportTheme.muted,align:'center',margin:0});pptAddFooter(slide,pptx,`${info.label} · lectura ejecutiva`,false);
  }
  function pptAddMethodology(pptx,rows){
    const slide=pptx.addSlide();slide.background={color:exportTheme.bg};pptAddSlideTitle(slide,pptx,'Fuentes, confianza y gobernanza','Cómo leer el informe y entender la solidez de la evidencia pública',exportTheme.green);
    const classes=new Map();for(const s of state.data.source_catalog||[])classes.set(s.class||'otras',(classes.get(s.class||'otras')||0)+1);const top=[...classes.entries()].sort((a,b)=>b[1]-a[1]).slice(0,10);
    pptAddExecutiveList(slide,pptx,'Principales clases de fuente',top.map(([k,v])=>({title:k,meta:`${v} fuentes / familias`})),.58,1.82,5.9,4.95,exportTheme.green);
    const notes=[{title:'Evidencia pública',meta:'Cada campo conserva fuente, fecha, tipo, vigencia y nivel de confianza.'},{title:'Confianza',meta:'Alta 80–99% · Media 60–79% · Baja 35–59% · por debajo de 35% no se publica.'},{title:'Trazabilidad',meta:`${uniqueEvidence(rows,9999).length} evidencias únicas en las áreas seleccionadas.`},{title:'Separación de roles',meta:'Fabricantes y mayoristas se clasifican de forma excluyente; la venta directa se marca en Fabricantes.'}];
    pptAddExecutiveList(slide,pptx,'Reglas de lectura',notes,6.72,1.82,6.05,4.95,exportTheme.blue);pptAddFooter(slide,pptx,'Metodología y gobernanza',false);
  }
  async function exportPptx(){
    if(!window.PptxGenJS){toast('PptxGenJS no está disponible');return;}
    const modules=selectedModules(); if(!modules.size){toast('Selecciona al menos un área');return;}
    const title=$('#reportTitle')?.value.trim()||'Westcon Iberia · Business Intelligence',appendix=Boolean($('#exportDetailedAppendix')?.checked),pptx=new window.PptxGenJS();pptx.layout='LAYOUT_WIDE';pptx.author='Westcon Iberia';pptx.company='Westcon Iberia';pptx.subject='Business Intelligence';pptx.title=title;pptx.lang='es-ES';
    let slide=pptx.addSlide();slide.background={color:exportTheme.navy};pptAddBrand(slide,pptx,true);
    slide.addShape(pptx.ShapeType.rect,{x:12.56,y:0,w:.18,h:7.5,fill:{color:exportTheme.cyan},line:{color:exportTheme.cyan}});slide.addShape(pptx.ShapeType.rect,{x:12.78,y:0,w:.18,h:7.5,fill:{color:exportTheme.pink},line:{color:exportTheme.pink}});slide.addShape(pptx.ShapeType.rect,{x:13.0,y:0,w:.18,h:7.5,fill:{color:exportTheme.orange},line:{color:exportTheme.orange}});
    slide.addText('INTELIGENCIA DE NEGOCIO · ESPAÑA + PORTUGAL',{x:.72,y:1.62,w:7.8,h:.22,fontFace:'Aptos',fontSize:9,bold:true,color:exportTheme.cyan,margin:0,charSpacing:1.4});
    slide.addText(title,{x:.72,y:2.05,w:10.7,h:1.2,fontFace:'Aptos Display',fontSize:31,bold:true,color:exportTheme.white,margin:0,fit:'shrink'});
    slide.addText('Lectura ejecutiva · oportunidades · cuentas · ecosistema · tendencias · arquitecturas',{x:.74,y:3.55,w:10.7,h:.32,fontFace:'Aptos',fontSize:11.5,color:'D2E0E6',margin:0});
    const stats=[['manufacturers','FAB',state.data.manufacturers.length],['distributors','MAY',state.data.distributors.length],['integrators','INT',state.data.integrators.length],['clients','CLI',((state.data.clients_public||[]).length+(state.data.clients_private||[]).length)],['trends','TEN',state.data.trends.length],['architectures','ARQ',state.data.architectures.length]].filter(x=>modules.has(x[0]));
    stats.slice(0,6).forEach((item,i)=>{const v=item[2],lab=item[1],x=.72+i*1.42;slide.addShape(pptx.ShapeType.roundRect,{x,y:4.55,w:1.24,h:.78,rectRadius:.04,fill:{color:'113A50'},line:{color:'315267',pt:.7}});slide.addText(String(v),{x:x+.08,y:4.72,w:1.08,h:.25,fontFace:'Aptos Display',fontSize:16,bold:true,color:exportTheme.white,align:'center',margin:0});slide.addText(lab,{x:x+.08,y:5.06,w:1.08,h:.11,fontFace:'Aptos',fontSize:5.6,bold:true,color:'AFC1CA',align:'center',margin:0,charSpacing:.6});});
    slide.addText(`${state.data.meta.source_count||0} fuentes/familias · generado ${state.data.meta.generated_at||''}`,{x:.72,y:6.35,w:8.5,h:.2,fontFace:'Aptos',fontSize:7.5,color:'9EB8C5',margin:0});pptAddFooter(slide,pptx,'Westcon Iberia · Business Intelligence',true);

    pptAddExecutiveSummary(pptx,modules);
    const order=exportSections(modules),selectedRows=[];
    order.forEach(([key,rows,schema])=>{if(!rows?.length)return;selectedRows.push(...rows);pptAddDomainExecutive(pptx,key,rows);if(key==='trends')pptAddTrendAnalytics(pptx);if(key==='architectures'){const top=domainTopRows(key,rows).slice(0,6);const s=pptx.addSlide();s.background={color:exportTheme.bg};pptAddSlideTitle(s,pptx,'Arquitecturas · lectura ejecutiva','Marcos funcionales y cobertura del portfolio por capas',exportTheme.green);pptAddExecutiveList(s,pptx,'Arquitecturas con mayor densidad de evidencia',top.map(r=>({title:r.name,meta:`${fieldArray(r,'vendors').length} fabricantes Westcon · ${rowEvidenceCount(r)} evidencias`})),.65,1.85,12.05,4.9,exportTheme.green);pptAddFooter(s,pptx,'Arquitecturas · lectura ejecutiva',false);}});
    pptAddMethodology(pptx,selectedRows);
    if(appendix){
      const divider=pptx.addSlide();divider.background={color:exportTheme.navy};pptAddBrand(divider,pptx,true);divider.addText('ANEXO DE DETALLE',{x:.75,y:2.35,w:10.5,h:.25,fontFace:'Aptos',fontSize:9,bold:true,color:exportTheme.cyan,margin:0,charSpacing:1.5});divider.addText('Fichas y fuentes',{x:.75,y:2.78,w:10.7,h:.75,fontFace:'Aptos Display',fontSize:34,bold:true,color:exportTheme.white,margin:0});divider.addText('Detalle trazable para consulta posterior; la parte anterior está optimizada para presentar.',{x:.77,y:3.72,w:10.2,h:.35,fontFace:'Aptos',fontSize:12,color:'C9D7DE',margin:0});pptAddFooter(divider,pptx,'Anexo',true);
      order.forEach(([key,rows,schema])=>{if(!rows?.length)return;pptAddDomainDivider(pptx,key,rows.length);if(key==='trends'||key==='architectures')pptAddDetailSlides(pptx,key,rows,schema);else pptAddEntitySlides(pptx,key,rows,schema);});
      pptAddSources(pptx,selectedRows);
    }
    await pptx.writeFile({fileName:'Westcon_Iberia_Business_Intelligence_v3.15.0.pptx'});closeModal('exportModal');toast(appendix?'PowerPoint ejecutivo + anexo generado':'PowerPoint ejecutivo generado');
  }

  function renderAll(){
    populateIntegratorVendorFilter();
    renderManufacturers(); renderDistributors(); renderIntegrators(); renderClients(); renderTrends(); renderArchitectures(); renderSourceCatalog(); renderUpdateStatus(); renderConfidenceGuide();
    const meta=state.data.meta||{}; const status=$('#footerStatus'); if(status) status.textContent=`App v3.15.0 · dataset v${meta.version||'3.15.0'} · ${meta.source_count||0} fuentes/familias · ${meta.scope||'Iberia'}`;
  }

  load().catch(err => { console.error(err); const main=document.querySelector('main'); if(main) main.innerHTML=`<div class="fatal"><h1>No se pudo cargar la inteligencia</h1><p>${esc(err.message)}</p></div>`; });
})();
