'use strict';
// Verify that entity-level confidence cannot contradict atomic colored badges.
const assert=require('assert'),fs=require('fs'),vm=require('vm');
const js=fs.readFileSync('assets/app/intelligence.js','utf8');
const start=js.indexOf('function rowConfidence(row){');
const end=js.indexOf('function virtualField(',start);
assert(start>=0&&end>start,'Missing entity confidence reducer');
const context={
 hasValue:v=>v!==undefined&&v!==null&&v!==''&&(!Array.isArray(v)||v.length>0),
 norm:v=>String(v||'').toLowerCase(),
 itemFor:(f,v)=>f.items?.find(x=>String(x.value).toLowerCase()===String(v).toLowerCase())
                ||{value:v,confidence:f.confidence,evidence:[]},
 atomicCurrentProof:ev=>Array.isArray(ev)&&ev.some(x=>/^https:\/\//.test(x.url||'')
            &&x.accrediting!==false&&x.freshness_status!=='stale'),
};
vm.runInNewContext(js.slice(start,end)+';this.rowConfidence=rowConfidence;',context);
const source={url:'https://vendor.example/product',source_binding:'claim-specific'};
const green={value:'Green',confidence:.99,evidence:[source]};
const purple={value:'Unverified',confidence:.99,evidence:[]};
const fields=items=>({fields:{vendors:{value:items.map(x=>x.value),items,confidence:.99}}});
const no=context.rowConfidence(fields([purple]));
assert.strictEqual(no.band,'low','Unverified 99% value must not turn entity green');
const yes=context.rowConfidence(fields([green]));
assert.strictEqual(yes.band,'high','Confirmed values should remain green');
const mixed=context.rowConfidence(fields([green,purple]));
assert.strictEqual(mixed.band,'medium','A mixed record cannot be all green');
assert.strictEqual(mixed.unsourced,1);
const layers=context.rowConfidence({fields:{layers:{value:[{layer:'SASE',vendors:['Green','Unverified'],
  vendor_items:[green,purple]}],confidence:.99}}});
assert.strictEqual(layers.band,'medium','Layers must use their own vendor evidence');
console.log('CONFIDENCE_COLOR_CONSISTENCY PASS');
