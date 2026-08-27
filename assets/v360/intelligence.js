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
      const shown=v.slice(0,6); return `<div class="r-tags">${shown.map(x=>`<span>${esc(typeof x==='object'?JSON.stringify(x):x)}</span>`).join('')}${v.length>shown.length?`<span class="more">+${v.length-shown.length}</span>`:''}</div>`;
    }
    return `<span>${esc(shortText(v,190))}</span>`;
  }
  function reportBrand(){return `<div class="r-brand"><span class="r-mark"><i></i><i></i><i></i></span><b>WESTCON IBERIA</b><small>BUSINESS INTELLIGENCE</small></div>`;}
  function reportFooter(label){return `<footer class="r-footer"><span>${esc(label)}</span><span>v${esc(state.data.meta.version||'3.6.1')} · ${esc(state.data.meta.scope||'Iberia')} · inteligencia trazable</span></footer>`;}
  function reportCover(title,modules){
    const stats=[
      ['manufacturers','Fabricantes',state.data.manufacturers.length],['integrators','Integradores',state.data.integrators.length],['distributors','Mayoristas',state.data.distributors.length],['trends','Tendencias',state.data.trends.length],['architectures','Arquitecturas',state.data.architectures.length]
    ].filter(x=>modules.has(x[0]));
    return `<section class="report-page report-cover">
      <div class="r-cover-top">${reportBrand()}<span class="r-version">v${esc(state.data.meta.version||'3.6.1')}</span></div>
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
  function reportHtml(title,modules){
    const sections=[reportCover(title,modules)];
    const order=[['manufacturers',state.data.manufacturers,state.data.schemas.manufacturers],['integrators',state.data.integrators,state.data.schemas.integrators],['distributors',state.data.distributors,state.data.schemas.distributors],['trends',state.data.trends,state.data.schemas.trends],['architectures',state.data.architectures,state.data.schemas.architectures]];
    order.forEach(([key,rows,schema])=>{if(!modules.has(key))return; if(key==='trends'||key==='architectures') rows.forEach((r,i)=>sections.push(reportCardPage(key,r,i,rows.length,schema))); else sections.push(reportTablePages(key,rows,schema)); sections.push(reportSourcesPages(key,rows));});
    return `<div class="report-export">${sections.join('')}</div>`;
  }
  async function exportPdf(){
    const modules=selectedModules(); if(!modules.size){toast('Selecciona al menos un área');return;}
    const title=$('#reportTitle')?.value.trim()||'Westcon Iberia · Business Intelligence'; const sheet=$('#reportSheet'); sheet.innerHTML=reportHtml(title,modules); sheet.setAttribute('aria-hidden','false'); sheet.classList.add('rendering'); closeModal('exportModal');
    try{
      if(window.html2pdf){ await window.html2pdf().set({margin:0,filename:'Westcon_Iberia_Business_Intelligence_v3.6.1.pdf',image:{type:'jpeg',quality:.98},html2canvas:{scale:2,useCORS:true,backgroundColor:'#ffffff',logging:false},jsPDF:{unit:'mm',format:'a4',orientation:'landscape'},pagebreak:{mode:['css']}}).from(sheet.firstElementChild).save(); toast('PDF generado con diseño Westcon'); }
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
    slide.addText(`v${state.data.meta.version||'3.6.1'} · ${state.data.meta.scope||'Iberia'} · trazabilidad en la aplicación`,{x:7.0,y:7.1,w:5.75,h:.14,fontFace:'Aptos',fontSize:6.6,color,align:'right',margin:0});
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
  function pptAddEntityCard(slide,pptx,row,schema,x,y,w,h,accent){
    slide.addShape(pptx.ShapeType.roundRect,{x,y,w,h,rectRadius:.04,fill:{color:exportTheme.white},line:{color:exportTheme.line,pt:.8}});
    slide.addShape(pptx.ShapeType.rect,{x,y,w,h:.07,fill:{color:accent},line:{color:accent}});
    slide.addText(row.name,{x:x+.16,y:y+.18,w:w-1.15,h:.25,fontFace:'Aptos Display',fontSize:12.5,bold:true,color:exportTheme.navy,margin:0,fit:'shrink'});
    slide.addShape(pptx.ShapeType.roundRect,{x:x+w-.88,y:y+.17,w:.7,h:.27,rectRadius:.05,fill:{color:'EDF3F5'},line:{color:'EDF3F5'}});
    slide.addText(`${rowEvidenceCount(row)} src`,{x:x+w-.84,y:y+.225,w:.62,h:.13,fontFace:'Aptos',fontSize:5.7,bold:true,color:'42606F',align:'center',margin:0});
    const cols=activeColumns(schema,[row]).filter(c=>c.id!=='scope').slice(0,3); let yy=y+.58;
    cols.forEach(c=>{const f=row.fields?.[c.id];slide.addText(c.label.toUpperCase(),{x:x+.16,y:yy,w:1.35,h:.13,fontFace:'Aptos',fontSize:5.5,bold:true,color:exportTheme.muted,margin:0,charSpacing:.4});slide.addText(pptCompact(f?.value,92),{x:x+1.52,y:yy-.01,w:w-1.7,h:.28,fontFace:'Aptos',fontSize:7.2,color:exportTheme.ink,margin:0,fit:'shrink',valign:'top'});yy+=.31;});
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
    const draw=(list,xx,ww)=>{let yy=y+.72;list.forEach(c=>{const f=row.fields?.[c.id];slide.addText(c.label.toUpperCase(),{x:xx,y:yy,w:ww,h:.13,fontFace:'Aptos',fontSize:5.8,bold:true,color:exportTheme.muted,margin:0,charSpacing:.45});slide.addText(pptCompact(f?.value,255),{x:xx,y:yy+.17,w:ww,h:.72,fontFace:'Aptos',fontSize:7.7,color:exportTheme.ink,margin:0,fit:'shrink',valign:'top'});yy+=1.02;});};
    draw(left,x+.25,(w-.7)/2);draw(right,x+w/2+.1,(w-.7)/2);
    const src=pptEvidenceNames(row,3); if(src.length)slide.addText(`Fuentes: ${src.join(' · ')}`,{x:x+.25,y:y+h-.28,w:w-.5,h:.13,fontFace:'Aptos',fontSize:5.8,color:'758994',italic:true,margin:0,fit:'shrink'});
  }
  function pptAddDetailSlides(pptx,key,rows,schema){
    const info=domainCopy[key]; rows.forEach((row,gi)=>{const slide=pptx.addSlide(); slide.background={color:exportTheme.bg}; pptAddSlideTitle(slide,pptx,info.label,`${gi+1}/${rows.length} · ficha completa con el lenguaje visual de la web`,info.accent); pptAddDetailCard(slide,pptx,row,schema,.55,1.78,12.22,4.98,info.accent); pptAddFooter(slide,pptx,info.label,false);});
  }
  function pptAddSources(pptx,selectedRows){
    const all=uniqueEvidence(selectedRows,72); if(!all.length)return; const groups=chunk(all,9); groups.forEach((group,gi)=>{const slide=pptx.addSlide(); slide.background={color:exportTheme.bg}; pptAddSlideTitle(slide,pptx,'Fuentes principales',`${all.length} evidencias únicas seleccionadas · página ${gi+1}/${groups.length}`,exportTheme.cyan); let y=1.78; group.forEach((ev,i)=>{slide.addShape(pptx.ShapeType.roundRect,{x:.55,y,w:12.22,h:.52,rectRadius:.03,fill:{color:exportTheme.white},line:{color:exportTheme.line,pt:.6}});slide.addShape(pptx.ShapeType.roundRect,{x:.72,y:y+.13,w:.33,h:.25,rectRadius:.04,fill:{color:'E7F4F5'},line:{color:'E7F4F5'}});slide.addText(String(gi*9+i+1),{x:.75,y:y+.19,w:.27,h:.1,fontFace:'Aptos',fontSize:5.8,bold:true,color:'0A7280',align:'center',margin:0});slide.addText(ev.source||'Fuente pública',{x:1.18,y:y+.1,w:2.2,h:.15,fontFace:'Aptos',fontSize:7.4,bold:true,color:exportTheme.navy,margin:0,fit:'shrink'});slide.addText(shortText(ev.title||'Evidencia',115),{x:3.42,y:y+.08,w:7.75,h:.18,fontFace:'Aptos',fontSize:6.9,color:exportTheme.ink,margin:0,fit:'shrink'});slide.addText([ev.date,ev.type].filter(Boolean).join(' · '),{x:3.42,y:y+.3,w:6.7,h:.12,fontFace:'Aptos',fontSize:5.5,color:exportTheme.muted,margin:0});if(ev.url)slide.addText('Abrir ↗',{x:11.32,y:y+.18,w:1.05,h:.13,fontFace:'Aptos',fontSize:6.2,bold:true,color:'177E9F',align:'right',margin:0,hyperlink:{url:ev.url}});y+=.58;}); pptAddFooter(slide,pptx,'Fuentes principales',false);});
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
    order.forEach(([key,rows,schema])=>{if(!modules.has(key))return;pptAddDomainDivider(pptx,key,rows.length);if(key==='trends'||key==='architectures')pptAddDetailSlides(pptx,key,rows,schema);else pptAddEntitySlides(pptx,key,rows,schema);selectedRows.push(...rows);});
    pptAddSources(pptx,selectedRows);
    await pptx.writeFile({fileName:'Westcon_Iberia_Business_Intelligence_v3.6.1.pptx'}); closeModal('exportModal'); toast('PowerPoint generado con diseño Westcon');
  }

  function renderAll(){
    populateIntegratorVendorFilter();
    renderManufacturers(); renderIntegrators(); renderDistributors(); renderTrends(); renderArchitectures(); renderSourceCatalog();
    const meta=state.data.meta||{}; const status=$('#footerStatus'); if(status) status.textContent=`v${meta.version||'3.6.0'} · ${meta.source_count||0} fuentes/familias · ${meta.scope||'Iberia'}`;
  }

  load().catch(err => { console.error(err); const main=document.querySelector('main'); if(main) main.innerHTML=`<div class="fatal"><h1>No se pudo cargar la inteligencia</h1><p>${esc(err.message)}</p></div>`; });
})();
