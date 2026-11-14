/* Westcon v6.4 — snapshot-consistent, source-transparent audit for every area. */
(function(root){
'use strict';
const order=['manufacturers','distributors','integrators','clients_public','clients_private','trends','architectures'];
const names={manufacturers:'Fabricantes',distributors:'Mayoristas',integrators:'Integradores',clients_public:'Clientes públicos',clients_private:'Clientes privados',trends:'Tendencias',architectures:'Arquitecturas'};
const safe=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number=v=>v===null||v===undefined||v===''?'N/D':Number.isFinite(Number(v))?Number(v).toLocaleString('es-ES'):'N/D';
function evaluate(manifest,debt,integrity=null){
 const published=String(manifest?.generated_at||''),diagnosed=String(debt?.generated_at||'');
 const dateMatch=Boolean(published&&diagnosed&&published===diagnosed);
 const summary=debt?.debt_breakdown||{};
 const bySection=debt?.by_section||{};
 const total=Number(debt?.total_open_gaps);
 const headline=Number(summary.empty_schema_fields||0)+Number(summary.claims_awaiting_evidence||0)+Number(summary.derived_support||0)+Number(summary.other_open_debt||0);
 const detail=order.reduce((sum,k)=>{const a=bySection[k]||{};return sum+Number(a.claims_awaiting_evidence||0)+Number(a.derivation_support||0)+Number(a.empty_schema_fields||0);},0);
 const hasData=Boolean(manifest?.counts&&debt?.by_section&&Number.isFinite(total));
 const integrityMatch=Boolean(integrity?.status==='PASS'&&integrity?.snapshot_generated_at===published);
 const consistent=hasData&&dateMatch&&headline===total&&detail===total&&(!integrity||integrityMatch);
 return {hasData,consistent,dateMatch,integrityAvailable:Boolean(integrity),integrityMatch,total,headline,detail,published,diagnosed,order:order.map(k=>{
   const section=bySection[k]||{},sources=manifest?.meta?.source_coverage?.[k]||{},meta=manifest?.sections?.[k]||{};
   const claims=Number(sources.claims),sourced=Number(sources.sourced);
   return {key:k,label:names[k],entities:manifest?.counts?.[k]??meta.rows??null,claims:sources.claims??null,sourced:sources.sourced??null,
    coverage:Number.isFinite(claims)&&claims>0&&Number.isFinite(sourced)?Math.round(sourced*100/claims):null,
    claimsPending:section.claims_awaiting_evidence??null,derived:section.derivation_support??null,empty:section.empty_schema_fields??null,
    evidenceRefs:meta.evidence??null
   };
 })};
}
function render(manifest,debt,integrity=null){
 const r=evaluate(manifest,debt,integrity);
 const details='<div class="cc-audit-meta"><b>Origen:</b> manifest.json · '+safe(r.published||'sin fecha')+
   ' | <b>Inventario:</b> debt_overview.json · '+safe(r.diagnosed||'sin fecha')+
   ' | <b>Fuente registrada:</b> '+number(manifest?.meta?.source_count)+' referencias</div>';
 if(!r.hasData){
  return '<p class="cc-audit-warning">Auditoría por área no disponible: faltan cifras verificables de la misma publicación. No se muestran ceros ficticios.</p>'+details+
  '<p><a href="data/public/debt_overview.json" target="_blank" rel="noopener">Consultar diagnóstico publicado</a></p>';
 }
 const alert=r.consistent?'<p class="cc-audit-ok">Desglose conciliado con el inventario publicado.</p>':
  '<p class="cc-audit-warning">Advertencia: fechas, totales o auditoría integral no coinciden. Los valores se muestran con su procedencia.</p>';
 const integrityWarning=!r.integrityAvailable?'<p class="cc-audit-warning">Control de integridad de las siete áreas aún no disponible para esta publicación.</p>':
   !r.integrityMatch?'<p class="cc-audit-warning">Auditoría integral fallida o correspondiente a otra publicación.</p>':'';
 const rows=r.order.map(a=>'<tr><th scope="row">'+safe(a.label)+'</th>'+
  '<td>'+number(a.entities)+'</td><td>'+number(a.sourced)+' / '+number(a.claims)+
  (a.coverage===null?'':' ('+a.coverage+'%)')+'</td>'+
  '<td>'+number(a.claimsPending)+'</td><td>'+number(a.derived)+'</td><td>'+number(a.empty)+'</td></tr>').join('');
 return alert+details+'<div class="cc-audit-scroll"><table class="cc-audit-table">'+
  '<caption>Auditoría del dataset completo; no depende de los filtros de las tablas</caption>'+
  '<thead><tr><th>Área</th><th>Entidades</th><th>Afirmaciones con fuente / total</th><th>Por acreditar</th><th>Derivación</th><th>Vacíos</th></tr></thead><tbody>'+
  rows+'</tbody></table></div>'+
  '<p class="cc-audit-method">Con fuente ≠ hecho verificado ni cobertura del mercado. Los huecos se clasifican por naturaleza; una derivación pendiente no es una afirmación falsa. Calidad de integridad y cobertura son métricas distintas.</p>';
}
const api={evaluate,render};
root.WestconAudit=api;
if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
