'use strict';
const assert=require('assert');
const fs=require('fs');
const a=require('../assets/app/audit-intelligence.js');
const m=JSON.parse(fs.readFileSync('data/public/manifest.json','utf8'));
const d=JSON.parse(fs.readFileSync('data/public/debt_overview.json','utf8'));
const now=a.evaluate(m,d);
assert.strictEqual(now.hasData,true,'Published audit must have both snapshots');
assert.strictEqual(now.consistent,true,'All per-section totals and dates must reconcile');
assert.strictEqual(now.order.length,7);
const html=a.render(m,d);
for(const area of ['Fabricantes','Mayoristas','Integradores','Clientes públicos','Clientes privados','Tendencias','Arquitecturas']){
 assert.ok(html.includes(area),'Missing area '+area);
}
assert.ok(html.includes('Afirmaciones con fuente / total'));
assert.ok(html.includes('Con fuente ≠ hecho verificado'));
const verified={status:'PASS',snapshot_generated_at:m.generated_at};
assert.strictEqual(a.evaluate(m,d,verified).consistent,true);
const obsolete={...verified,snapshot_generated_at:'2025-01-01'};
assert.strictEqual(a.evaluate(m,d,obsolete).consistent,false);
assert.ok(a.render(m,d,obsolete).includes('Auditoría integral fallida'));
assert.ok(a.render(m,d,null).includes('Control de integridad'));
const empty=a.render(m,null);
assert.ok(empty.includes('no disponible'));
assert.ok(!empty.includes('NaN'));
const altered={...d,generated_at:'2022-01-01T00:00:00+00:00'};
assert.strictEqual(a.evaluate(m,altered).consistent,false);
assert.ok(a.render(m,altered).includes('Advertencia'));
console.log('AUDIT_V64_OK '+JSON.stringify({date:now.published,total:now.total,areas:now.order.length,sourceCoverage:now.order.map(x=>[x.key,x.coverage])}));
