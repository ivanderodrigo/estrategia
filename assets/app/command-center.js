(() => {
'use strict';
const home=document.getElementById('commandCenter'),homeNav=document.getElementById('homeNav');
if(!home||!homeNav)return;
const fmt=v=>Number.isFinite(Number(v))?Number(v).toLocaleString('es-ES'):'N/D';
const clean=v=>String(v??'').replace(/[&<>"']/g,k=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[k]));
const showHome=()=>{document.body.classList.add('cc-home');document.querySelectorAll('#tabs button').forEach(b=>b.classList.toggle('active',b===homeNav));window.scrollTo?.(0,0);};
homeNav.addEventListener('click',showHome);
document.querySelectorAll('[data-cc-go]').forEach(b=>b.addEventListener('click',()=>{
 const t=document.querySelector('#tabs [data-view="'+b.dataset.ccGo+'"]');if(t)t.click();
}));
document.querySelectorAll('#tabs [data-view]').forEach(b=>b.addEventListener('click',()=>{document.body.classList.remove('cc-home');homeNav.classList.remove('active');}));
showHome();
const getJson=async path=>{const response=await fetch(path,{cache:'no-store'});if(!response.ok)throw Error('HTTP '+response.status);return response.json();};
const metrics=document.getElementById('ccMetrics'),debt=document.getElementById('ccDebt'),audit=document.getElementById('ccAudit');
const dateLabel=v=>v?String(v).slice(0,16).replace('T',' ')+' UTC':'fecha no disponible';
Promise.allSettled([getJson('data/public/manifest.json'),getJson('data/public/debt_overview.json'),getJson('data/public/audit_integrity.json'),getJson('data/public/last_run.json')]).then(([mr,dr,ir,rr])=>{
 const m=mr.status==='fulfilled'?mr.value:null;
 const d=dr.status==='fulfilled'?dr.value:null;
 const integrity=ir.status==='fulfilled'?ir.value:null;
 const lastRun=rr.status==='fulfilled'?rr.value:null;
 if(m?.counts){
  const c=m.counts,totalClients=Number(c.clients_public||0)+Number(c.clients_private||0);
  const tiles=[['Fabricantes',c.manufacturers],['Mayoristas',c.distributors],['Integradores',c.integrators],['Clientes',totalClients],['Tendencias y arquitecturas',Number(c.trends||0)+Number(c.architectures||0)]];
  metrics.innerHTML=tiles.map(([label,val])=>'<div class="cc-metric"><strong>'+fmt(val)+'</strong><span>'+clean(label)+'</span></div>').join('');
  const publishedAt=Date.parse(m.generated_at||'');
  const days=Number.isFinite(publishedAt)?Math.max(0,(Date.now()-publishedAt)/86400000):null;
  const stale=days!==null&&days>4?' · Advertencia: publicación sin renovar desde hace más de cuatro días.':'';
  const researchAt=lastRun?.research_finished_at||null;
  const researchLabel=researchAt?' · Última investigación real: '+dateLabel(researchAt):' · Fecha de la última búsqueda: no disponible';
  const sameRun=lastRun?.generated_at===m.generated_at;
  const provenanceWarning=sameRun?'':' · Advertencia: registro de investigación de otro corte.';
  document.getElementById('ccFreshness').textContent='Fotografía publicada: '+dateLabel(m.generated_at)+researchLabel+
    ' · Calidad de integridad '+(m.meta?.quality_score??'N/D')+'/100 (NO es cobertura de evidencia).'+stale+provenanceWarning;
 }else{
  metrics.textContent='No se han podido cargar las métricas verificables del dataset.';
  document.getElementById('ccFreshness').textContent='Estado de la publicación: no disponible; revisar manifest.json.';
 }
 const r=window.WestconAudit?.evaluate(m,d,integrity);
 audit.innerHTML=window.WestconAudit?.render(m,d,integrity)||
  '<p class="cc-audit-warning">La herramienta de auditoría no se ha cargado. Consulta data/public/debt_overview.json.</p>';
 if(r?.hasData){
  const c=d.debt_breakdown||{};
  const categories=[['Afirmaciones por acreditar',c.claims_awaiting_evidence,'evidence'],['Derivaciones pendientes',c.derived_support,'derived'],['Campos sin información',c.empty_schema_fields,'empty']];
  debt.innerHTML=categories.map(([label,n,type])=>'<div class="cc-debt-item '+type+'"><strong>'+fmt(n)+'</strong><span>'+label+'</span></div>').join('')+
   '<p>Inventario íntegro: '+fmt(d.total_open_gaps)+' tareas distintas. La suma se concilia: '+(r.consistent?'sí':'NO, consultar alerta en la auditoría')+'.</p>';
 }else debt.innerHTML='<p class="cc-audit-warning">Diagnóstico sin datos consistentes. No se sustituye información ausente por cero; consulta la auditoría.</p>';
}).catch(e=>{
 console.error('Command center audit:',e);
 debt.innerHTML='<p class="cc-audit-warning">Error al verificar el inventario. Consulta los archivos de publicación.</p>';
 audit.innerHTML='<p class="cc-audit-warning">No ha sido posible construir el desglose. No se presentan datos no comprobados.</p>';
});
})();
