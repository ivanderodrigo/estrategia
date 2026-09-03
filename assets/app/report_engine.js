(function(root,factory){
  const filters=typeof module==='object'&&module.exports?require('./filter_engine.js'):root.WestconFilters;
  const api=factory(filters);
  if(typeof module==='object'&&module.exports)module.exports=api;
  else root.WestconReports=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(F){
  'use strict';
  const historical=ev=>/HISTORICAL|ARCHIVE|REPORT_CORROBORATION|LEGACY_UNRESOLVED/.test(String(ev?.provenance_origin||'').toUpperCase())||String(ev?.intelligence_tier||'')==='H';
  function fieldEvidence(field){return [...(field?.evidence||[]),...(field?.items||[]).flatMap(item=>item?.evidence||[])].filter(ev=>ev&&!historical(ev));}
  function uniqueEvidence(rows){const out=new Map();for(const row of rows){const all=[...(row.evidence||[]),...Object.values(row.fields||{}).flatMap(fieldEvidence)];for(const ev of all){if(historical(ev))continue;const key=ev.url||`${ev.document_id||ev.document||''}|${ev.slide||''}|${ev.field||''}|${ev.item_value||''}`;if(key&&!out.has(key))out.set(key,ev);}}return [...out.values()];}
  function pendingCount(rows,columns,accessor){let n=0;for(const row of rows)for(const col of columns){if(col.virtual)continue;const field=row.fields?.[col.id],value=accessor(row,col.id,col);if(F.hasValue(value)&&!fieldEvidence(field).length)n++;else if(!F.hasValue(value))n++;}return n;}
  function build({rows,tree,schema,columns,accessor,title,generatedAt=new Date().toISOString()}){
    const filtered=F.apply(rows,tree,schema,accessor);const selected=(columns||[]).map(id=>(schema||[]).find(c=>c.id===id)).filter(Boolean);
    return {title,generatedAt,criteria:F.describe(tree,schema),entityCount:filtered.length,rows:filtered,columns:selected,sources:uniqueEvidence(filtered),pending:pendingCount(filtered,selected,accessor)};
  }
  return {build,uniqueEvidence,fieldEvidence,historical};
});
