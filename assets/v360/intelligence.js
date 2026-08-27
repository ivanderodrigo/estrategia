(() => {
  'use strict';
  const state = {data:null, view:'fabricantes', fontScale: Number(localStorage.getItem('westcon-font-scale') || 1)};
  const $ = s => document.querySelector(s);
  const $$ = s => [...document.querySelectorAll(s)];
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const norm = v => String(v ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  const hasValue = v => !(v == null || v === '' || v === false || (Array.isArray(v) && !v.length) || (typeof v === 'object' && !Array.isArray(v) && !Object.keys(v).length));
  const toast = msg => { const el=$('#toast'); if(!el) return; el.textContent=msg; el.classList.add('show'); clearTimeout(el._t); el._t=setTimeout(()=>el.classList.remove('show'),2600); };

  async function load(){
    const res = await fetch('data/v36/intelligence.json', {cache:'no-store'});
    if(!res.ok) throw new Error(`No se pudo cargar data/v36/intelligence.json (${res.status})`);
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
  function sourceItem(ev){
    const title=esc(ev.title || ev.source || 'Evidencia');
    const source=esc(ev.source || 'Fuente pública');
    const meta=[ev.date, ev.type].filter(Boolean).map(esc).join(' · ');
    return `<div class="source-item"><b>${source}</b><span>${title}</span>${meta?`<small>${meta}</small>`:''}${ev.note?`<small>${esc(ev.note)}</small>`:''}${ev.url?`<a href="${esc(ev.url)}" target="_blank" rel="noopener">Abrir fuente ↗</a>`:''}</div>`;
  }
  function traceable(field, inner){
    const evidence=(field?.evidence||[]).slice(0,8);
    const qualifier=field?.qualifier ? `<span class="qualifier">${esc(field.qualifier)}</span>` : '';
    const sources=evidence.map(sourceItem).join('');
    return `<div class="traceable" tabindex="0"><div class="trace-value">${inner}</div><span class="trace-mark" aria-hidden="true">i</span><div class="trace-popover"><strong>FUENTES DEL DATO</strong>${qualifier}${sources}</div></div>`;
  }
  function renderValue(field){
    const value=field?.value;
    if(Array.isArray(value)){
      if(value.length && typeof value[0]==='object' && value[0].layer){
        return `<div class="layer-list">${value.map(x=>`<div class="layer"><b>${esc(x.layer)}</b><div>${(x.vendors||[]).map(v=>`<span class="tag emphasis">${esc(v)}</span>`).join('')}</div>${x.note?`<small>${esc(x.note)}</small>`:''}</div>`).join('')}</div>`;
      }
      if(value.length<=5) return value.map(v=>`<span class="tag">${esc(v)}</span>`).join('');
      return `<div class="stack">${value.map(v=>`<div class="line">${esc(v)}</div>`).join('')}</div>`;
    }
    if(typeof value==='number' && field.confidence != null){
      const cls=value>=75?'':value>=55?'mid':'low'; return `<span class="confidence-number ${cls}"><i></i>${esc(value)}%</span>`;
    }
    return esc(value);
  }
  function headerCell(col){
    return `<th><span class="help-wrap"><span>${esc(col.label)}</span>${col.clarify?`<button class="help-icon" type="button" aria-label="Aclaración de ${esc(col.label)}">?</button><span class="help-tip">${esc(col.help||'')}</span>`:''}</span></th>`;
  }
  function activeColumns(schema, rows){ return schema.filter(col => rows.some(row => hasValue(row.fields?.[col.id]?.value))); }
  function tableHtml(rows, schema, emptyText){
    if(!rows.length) return `<div class="empty-state">${esc(emptyText)}</div>`;
    const cols=activeColumns(schema, rows);
    return `<table><thead><tr><th>Entidad</th>${cols.map(headerCell).join('')}</tr></thead><tbody>${rows.map(row=>{const identity={value:row.name,evidence:row.evidence||[]}; return `<tr><td class="name-cell">${traceable(identity,`<b>${esc(row.name)}</b><small>Identidad trazable</small>`)}</td>${cols.map(col=>{const f=row.fields?.[col.id]; return `<td>${f&&hasValue(f.value)?traceable(f,renderValue(f)):'—'}</td>`}).join('')}</tr>`}).join('')}</tbody></table>`;
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
    $('#manufacturerTable').innerHTML=tableHtml(rows,state.data.schemas.manufacturers,'No hay fabricantes con esos filtros.');
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
    $('#integratorTable').innerHTML=tableHtml(rows,state.data.schemas.integrators,'No hay partners/integradores con esos filtros.');
    setCount('#integratorCount',rows.length,all.length,'partners / integradores');
  }
  function renderDistributors(){
    const q=norm($('#distributorSearch')?.value), scope=$('#distributorScope')?.value||'all';
    const all=state.data.distributors||[];
    const rows=all.filter(r=>(!q||rowBlob(r).includes(q))&&scopeMatch(r,scope));
    $('#distributorTable').innerHTML=tableHtml(rows,state.data.schemas.distributors,'No hay mayoristas con esos filtros.');
    setCount('#distributorCount',rows.length,all.length,'mayoristas competidores');
  }

  function cardField(col, f){ if(!f||!hasValue(f.value)) return ''; const help=col.clarify?`<span class="help-wrap card-help"><span>${esc(col.label)}</span><button class="help-icon" type="button" aria-label="Aclaración de ${esc(col.label)}">?</button><span class="help-tip">${esc(col.help||'')}</span></span>`:esc(col.label); return `<div class="card-field"><label>${help}</label>${traceable(f,renderValue(f))}</div>`; }
  function cardGrid(rows, schema){
    const cols=activeColumns(schema,rows);
    return rows.map(row=>`<article class="intel-card"><div class="eyebrow">INTELIGENCIA TRAZABLE</div><div class="card-title">${traceable({value:row.name,evidence:row.evidence||[]},`<h3>${esc(row.name)}</h3>`)}</div>${cols.map(c=>cardField(c,row.fields?.[c.id])).join('')}</article>`).join('');
  }
  function renderTrends(){
    const q=norm($('#trendSearch')?.value), all=state.data.trends||[], rows=all.filter(r=>!q||rowBlob(r).includes(q));
    $('#trendGrid').innerHTML=cardGrid(rows,state.data.schemas.trends)||'<div class="empty-state">No hay tendencias con ese filtro.</div>';
    setCount('#trendCount',rows.length,all.length,'tendencias');
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
  function reportSourcesFor(rows, limit=35){
    const map=new Map(); rows.forEach(r=>{(r.evidence||[]).forEach(ev=>{const k=ev.url||`${ev.source}|${ev.title}`; if(!map.has(k)) map.set(k,ev)}); Object.values(r.fields||{}).forEach(f=>(f.evidence||[]).forEach(ev=>{const k=ev.url||`${ev.source}|${ev.title}`; if(!map.has(k)) map.set(k,ev)}));});
    return [...map.values()].slice(0,limit);
  }
  function reportTable(rows, schema, limit=40){
    const sample=rows.slice(0,limit), cols=activeColumns(schema,sample).slice(0,7);
    return `<table><thead><tr><th>Entidad</th>${cols.map(c=>`<th>${esc(c.label)}</th>`).join('')}</tr></thead><tbody>${sample.map(r=>`<tr><td><b>${esc(r.name)}</b></td>${cols.map(c=>`<td>${esc(valueText(r.fields?.[c.id]?.value||''))}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
  }
  function reportHtml(title, modules){
    const sections=[];
    const add=(key,label,rows,schema)=>{if(!modules.has(key))return; const src=reportSourcesFor(rows); sections.push(`<section class="report-section"><h2>${esc(label)}</h2>${reportTable(rows,schema)}<h3>Fuentes principales</h3><div class="report-sources">${src.map((s,i)=>`${i+1}. ${esc(s.source)} · ${esc(s.title)}${s.date?` · ${esc(s.date)}`:''}${s.url?` · ${esc(s.url)}`:''}`).join('<br>')}</div></section>`)};
    add('manufacturers','Fabricantes',state.data.manufacturers,state.data.schemas.manufacturers);
    add('integrators','Integradores',state.data.integrators,state.data.schemas.integrators);
    add('distributors','Mayoristas de la competencia',state.data.distributors,state.data.schemas.distributors);
    add('trends','Tendencias',state.data.trends,state.data.schemas.trends);
    add('architectures','Arquitecturas',state.data.architectures,state.data.schemas.architectures);
    return `<div class="report-export"><section class="report-cover"><div class="eyebrow">WESTCON IBERIA · BUSINESS INTELLIGENCE</div><h1>${esc(title)}</h1><p>Fabricantes · Integradores · Mayoristas competidores · Tendencias · Arquitecturas</p><p>${esc(state.data.meta.generated_at||'')}</p></section>${sections.join('')}</div>`;
  }
  async function exportPdf(){
    const modules=selectedModules(); if(!modules.size){toast('Selecciona al menos un área');return;}
    const title=$('#reportTitle')?.value.trim()||'Westcon Iberia · Business Intelligence'; const sheet=$('#reportSheet'); sheet.innerHTML=reportHtml(title,modules); sheet.setAttribute('aria-hidden','false'); closeModal('exportModal');
    try{
      if(window.html2pdf){ await window.html2pdf().set({margin:0,filename:'Westcon_Iberia_Business_Intelligence_v3.6.0.pdf',image:{type:'jpeg',quality:.97},html2canvas:{scale:1.5,useCORS:true},jsPDF:{unit:'mm',format:'a4',orientation:'landscape'},pagebreak:{mode:['css','legacy']}}).from(sheet.firstElementChild).save(); toast('PDF generado'); }
      else { window.print(); }
    } finally { sheet.setAttribute('aria-hidden','true'); }
  }
  function flatSummary(row,schema){
    const cols=activeColumns(schema,[row]).slice(0,4); return cols.map(c=>`${c.label}: ${valueText(row.fields?.[c.id]?.value||'')}`).join('\n');
  }
  async function exportPptx(){
    if(!window.PptxGenJS){toast('PptxGenJS no está disponible');return;}
    const modules=selectedModules(); if(!modules.size){toast('Selecciona al menos un área');return;}
    const title=$('#reportTitle')?.value.trim()||'Westcon Iberia · Business Intelligence'; const pptx=new window.PptxGenJS(); pptx.layout='LAYOUT_WIDE'; pptx.author='Westcon Iberia'; pptx.subject='Business Intelligence'; pptx.title=title;
    const addTitle=(s,t,sub='')=>{s.addText(t,{x:.55,y:.35,w:12.2,h:.5,fontFace:'Aptos Display',fontSize:24,bold:true,color:'082335'});if(sub)s.addText(sub,{x:.55,y:.9,w:12.2,h:.3,fontFace:'Aptos',fontSize:9,color:'647986'});};
    let s=pptx.addSlide(); s.background={color:'082335'}; s.addText('WESTCON IBERIA',{x:.7,y:.6,w:5,h:.35,fontFace:'Aptos',fontSize:12,bold:true,color:'12C7C0'}); s.addText(title,{x:.7,y:2.3,w:11.4,h:1.1,fontFace:'Aptos Display',fontSize:30,bold:true,color:'FFFFFF'}); s.addText('Fabricantes · Integradores · Mayoristas competidores · Tendencias · Arquitecturas',{x:.7,y:3.65,w:11.4,h:.4,fontFace:'Aptos',fontSize:12,color:'D2E0E6'}); s.addText(`v3.6.0 · ${state.data.meta.source_count} fuentes/familias públicas`,{x:.7,y:6.55,w:5,h:.25,fontFace:'Aptos',fontSize:9,color:'9EB8C5'});
    const addDomain=(key,label,rows,schema)=>{if(!modules.has(key))return; const chunks=[]; for(let i=0;i<Math.min(rows.length,24);i+=8) chunks.push(rows.slice(i,i+8)); chunks.forEach((chunk,ci)=>{const slide=pptx.addSlide(); addTitle(slide,`${label}${chunks.length>1?` · ${ci+1}/${chunks.length}`:''}`,`${rows.length} entidades/elementos · datos trazables en la aplicación`); chunk.forEach((r,i)=>{const y=1.35+i*.72; slide.addText(r.name,{x:.55,y,w:2.7,h:.3,fontFace:'Aptos',fontSize:10,bold:true,color:'113A50'}); slide.addText(flatSummary(r,schema),{x:3.05,y,w:9.5,h:.55,fontFace:'Aptos',fontSize:7.4,color:'425B69',breakLine:true,margin:0});}); slide.addText('El PPT resume. Para la trazabilidad campo a campo, consultar la aplicación y sus fuentes al pasar el ratón.',{x:.55,y:7.05,w:12,h:.22,fontFace:'Aptos',fontSize:6.5,color:'758994'});});};
    addDomain('manufacturers','Fabricantes',state.data.manufacturers,state.data.schemas.manufacturers);
    addDomain('integrators','Integradores',state.data.integrators,state.data.schemas.integrators);
    addDomain('distributors','Mayoristas de la competencia',state.data.distributors,state.data.schemas.distributors);
    addDomain('trends','Tendencias',state.data.trends,state.data.schemas.trends);
    addDomain('architectures','Arquitecturas',state.data.architectures,state.data.schemas.architectures);
    await pptx.writeFile({fileName:'Westcon_Iberia_Business_Intelligence_v3.6.0.pptx'}); closeModal('exportModal'); toast('PowerPoint generado');
  }

  function renderAll(){
    populateIntegratorVendorFilter();
    renderManufacturers(); renderIntegrators(); renderDistributors(); renderTrends(); renderArchitectures(); renderSourceCatalog();
    const meta=state.data.meta||{}; const status=$('#footerStatus'); if(status) status.textContent=`v${meta.version||'3.6.0'} · ${meta.source_count||0} fuentes/familias · ${meta.scope||'Iberia'}`;
  }

  load().catch(err => { console.error(err); const main=document.querySelector('main'); if(main) main.innerHTML=`<div class="fatal"><h1>No se pudo cargar la inteligencia</h1><p>${esc(err.message)}</p></div>`; });
})();
