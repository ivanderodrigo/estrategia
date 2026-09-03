(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else root.WestconFilters=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  const norm=v=>String(v??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim();
  const values=v=>Array.isArray(v)?v:(v==null||v===''?[]:[v]);
  const text=v=>values(v).map(x=>typeof x==='object'?JSON.stringify(x):String(x)).join(' · ');
  const hasValue=v=>!(v==null||v===''||(Array.isArray(v)&&!v.length)||(typeof v==='object'&&!Array.isArray(v)&&!Object.keys(v).length));
  const typeOf=column=>column?.type||'text';
  const operators={
    text:[['contains','contiene'],['not_contains','no contiene'],['equals','igual'],['not_equals','distinto'],['starts_with','empieza por'],['empty','está vacío'],['not_empty','no está vacío']],
    list:[['contains_any','contiene alguno'],['contains_all','contiene todos'],['not_contains','no contiene'],['empty','está vacía'],['not_empty','no está vacía']],
    number:[['eq','='],['gt','>'],['gte','>='],['lt','<'],['lte','<='],['between','entre'],['empty','está vacío'],['not_empty','no está vacío']],
    date:[['before','antes'],['after','después'],['between','entre'],['last_n_days','últimos N días'],['last_n_months','últimos N meses'],['empty','está vacía'],['not_empty','no está vacía']],
    boolean:[['yes','sí'],['no','no']],
    confidence:[['high','alta'],['medium','media'],['low','baja']]
  };
  function operatorsFor(column){return operators[typeOf(column)]||operators.text;}
  function splitWanted(value){return String(value??'').split(/[,;|]/).map(norm).filter(Boolean);}
  function numberValue(value){
    const raw=values(value)[0];if(typeof raw==='number')return raw;
    const match=String(raw??'').replace(/\s/g,'').replace(/\.(?=\d{3}(?:\D|$))/g,'').replace(',','.').match(/-?\d+(?:\.\d+)?/);
    return match?Number(match[0]):NaN;
  }
  function dateValue(value){const raw=values(value)[0];const d=new Date(raw);return Number.isFinite(d.getTime())?d:null;}
  function boolValue(value){const v=norm(values(value)[0]);return ['si','yes','true','1','activo','disponible'].includes(v)?true:['no','false','0'].includes(v)?false:null;}
  function defaultAccessor(row,field){return field==='entity'?row?.name:row?.fields?.[field]?.value;}
  function matches(rule,row,column,accessor=defaultAccessor,now=new Date()){
    const value=accessor(row,rule.field,column),op=rule.operator||operatorsFor(column)[0][0],wanted=norm(rule.value),wanted2=norm(rule.value2);
    if(op==='empty')return !hasValue(value);if(op==='not_empty')return hasValue(value);
    const type=typeOf(column);
    if(type==='text'){
      const actual=norm(text(value));
      if(op==='contains')return actual.includes(wanted);
      if(op==='not_contains')return !actual.includes(wanted);
      if(op==='equals')return actual===wanted;
      if(op==='not_equals')return actual!==wanted;
      if(op==='starts_with')return actual.startsWith(wanted);
    }
    if(type==='list'){
      const actual=values(value).map(norm),need=splitWanted(rule.value);
      if(op==='contains_any')return need.some(x=>actual.some(v=>v.includes(x)));
      if(op==='contains_all')return need.every(x=>actual.some(v=>v.includes(x)));
      if(op==='not_contains')return need.every(x=>actual.every(v=>!v.includes(x)));
    }
    if(type==='number'){
      const actual=numberValue(value),a=numberValue(rule.value),b=numberValue(rule.value2);if(!Number.isFinite(actual))return false;
      if(op==='eq')return actual===a;if(op==='gt')return actual>a;if(op==='gte')return actual>=a;if(op==='lt')return actual<a;if(op==='lte')return actual<=a;
      if(op==='between')return actual>=Math.min(a,b)&&actual<=Math.max(a,b);
    }
    if(type==='date'){
      const actual=dateValue(value);if(!actual)return false;const a=dateValue(rule.value),b=dateValue(rule.value2);
      if(op==='before')return Boolean(a&&actual<a);if(op==='after')return Boolean(a&&actual>a);
      if(op==='between')return Boolean(a&&b&&actual>=new Date(Math.min(a,b))&&actual<=new Date(Math.max(a,b)));
      const n=Math.max(0,Number(rule.value)||0),days=op==='last_n_months'?n*30.4375:n,threshold=new Date(now.getTime()-days*86400000);
      if(op==='last_n_days'||op==='last_n_months')return actual>=threshold&&actual<=now;
    }
    if(type==='boolean'){const actual=boolValue(value);return op==='yes'?actual===true:actual===false;}
    if(type==='confidence')return norm(value)===op;
    return true;
  }
  function validRules(group){return (group?.rules||[]).filter(r=>r&&r.field&&r.operator);}
  function matchesGroup(row,group,schemaById,accessor,now){
    const rules=validRules(group);if(!rules.length)return true;const results=rules.map(r=>matches(r,row,schemaById[r.field]||{id:r.field,type:'text'},accessor,now));return (group.logic||'AND')==='OR'?results.some(Boolean):results.every(Boolean);
  }
  function apply(rows,tree,schema,accessor,now){
    const groups=(tree?.groups||[]).filter(g=>validRules(g).length);if(!groups.length)return [...rows];const byId=Object.fromEntries((schema||[]).map(c=>[c.id,c]));
    return rows.filter(row=>{const results=groups.map(g=>matchesGroup(row,g,byId,accessor,now));return (tree.logic||'AND')==='OR'?results.some(Boolean):results.every(Boolean);});
  }
  function create(){return {logic:'AND',groups:[{id:'g1',logic:'AND',rules:[]}]};}
  function serialize(tree){return JSON.stringify(tree||create());}
  function deserialize(raw){try{const tree=typeof raw==='string'?JSON.parse(raw):raw;return tree&&Array.isArray(tree.groups)?tree:create();}catch(_){return create();}}
  function describe(tree,schema){const labels=Object.fromEntries((schema||[]).map(c=>[c.id,c.label||c.id]));const parts=[];(tree?.groups||[]).forEach((g,gi)=>{const rules=validRules(g).map(r=>`${labels[r.field]||r.field} ${r.operator} ${[r.value,r.value2].filter(hasValue).join(' y ')}`);if(rules.length)parts.push(`${gi?'(':'('}${rules.join(` ${g.logic||'AND'} `)})`);});return parts.join(` ${tree?.logic||'AND'} `)||'Sin filtros dinámicos';}
  return {norm,values,text,hasValue,operatorsFor,matches,apply,create,serialize,deserialize,describe,numberValue,dateValue,boolValue};
});
