const assert=require('assert');
const fs=require('fs');
const hygiene=require('../assets/app/vendor-hygiene.js');

const policy=JSON.parse(fs.readFileSync('config/current/non_vendor_labels.json','utf8'));
const labels=hygiene.labelsFromPolicy(policy);
for(const value of ['Marketing','Infinigate Group','Poland','image.svg','Privacy Policy','Partner Portal']){
  assert(hygiene.nonVendor(value,labels),`Non-vendor survived: ${value}`);
}
for(const vendor of ['Check Point','Proofpoint','Rackmount.IT','CrowdStrike']){
  assert(!hygiene.nonVendor(vendor,labels),`Real vendor wrongly excluded: ${vendor}`);
}

const evidence=value=>({field:'vendor_relations',item_value:value,url:'https://example.com/'+value,
  source:'Distributor',title:'Official listing of '+value,date:'2026-11-27',
  description:'Distributor lists '+value,source_binding:'atomic-item',atomic:true});
const item=value=>({value,evidence:[evidence(value)],confidence:0.9,evidence_color:'green'});
const rows=[{name:'Distributor',fields:{vendor_relations:{
  value:['Marketing','Check Point','proofpoint.svg'],
  items:['Marketing','Check Point','proofpoint.svg'].map(item),
  evidence:['Marketing','Check Point','proofpoint.svg'].map(evidence),
  confidence:0.9,evidence_color:'green',assertion_status:'CONFIRMADO',
}},evidence:['Marketing','Check Point','proofpoint.svg'].map(evidence)}];
const archived=[{value:'Marketing',url:'https://historical.example/original'}];
assert.strictEqual(hygiene.quarantinePublicRows(rows,labels),2);
assert.deepStrictEqual(rows[0].fields.vendor_relations.value,['Check Point']);
assert.deepStrictEqual(rows[0].fields.vendor_relations.items.map(x=>x.value),['Check Point']);
assert.deepStrictEqual(rows[0].fields.vendor_relations.evidence.map(x=>x.item_value),['Check Point']);
assert.deepStrictEqual(rows[0].evidence.map(x=>x.item_value),['Check Point']);
assert.strictEqual(rows[0].fields.vendor_relations.items[0].evidence_color,'green');
assert.strictEqual(archived[0].value,'Marketing');
assert.strictEqual(hygiene.downgradeUnboundVendorItems(rows),0);
assert.strictEqual(rows[0].fields.vendor_relations.items[0].evidence_color,'green');

const fakeGeneric={...evidence('Zscaler'),source_binding:'relationship-source'};
const wrongBound={...evidence('CrowdStrike'),item_value:'Palo Alto Networks'};
const unsupported=[{fields:{vendor_relations:{
  value:['Zscaler','CrowdStrike','Check Point'],
  items:[
    {...item('Zscaler'),evidence:[fakeGeneric]},
    {...item('CrowdStrike'),evidence:[wrongBound]},
    item('Check Point'),
  ],evidence:[fakeGeneric,wrongBound,evidence('Check Point')],confidence:.9,evidence_color:'green',
}}}];
assert.strictEqual(hygiene.downgradeUnboundVendorItems(unsupported),2);
assert.deepStrictEqual(unsupported[0].fields.vendor_relations.items.map(x=>x.evidence_color),['red','red','green']);
assert.deepStrictEqual(unsupported[0].fields.vendor_relations.items.map(x=>x.evidence.length),[0,0,1]);
assert.strictEqual(unsupported[0].fields.vendor_relations.evidence.length,1);

const onlyBad=[{fields:{vendor_relations:{value:['Marketing'],confidence:0.99,
  assertion_status:'CONFIRMADO',evidence_color:'green',evidence:[evidence('Marketing')]}}}];
assert.strictEqual(hygiene.quarantinePublicRows(onlyBad,labels),1);
assert.strictEqual(onlyBad[0].fields.vendor_relations.evidence_color,'red');
assert.strictEqual(onlyBad[0].fields.vendor_relations.assertion_status,'PENDIENTE_DE_CONTRASTAR_AFIRMACION');
assert(onlyBad[0].fields.vendor_relations.confidence<=0.38);

(async()=>{
  const fallback=await hygiene.loadPolicy(async()=>{throw Error('offline');});
  assert(hygiene.nonVendor('Marketing',fallback));
  console.log('VENDOR_HYGIENE_BROWSER PASS');
})().catch(e=>{console.error(e);process.exitCode=1});
