'use strict';
const fs=require('fs'),assert=require('assert');
const root=JSON.parse(fs.readFileSync('data/public/sections/distributors.json','utf8'));
const evidence=root.evidence||{};
const rows=root.rows||[];
const records=rows.map(row=>{
 const field=row.fields?.vendor_relations||{};
 const items=Array.isArray(field.value)?field.value:[field.value].filter(Boolean);
 const itemProof=(field.items||[]).filter(it=>(it.evidence_ids||[]).some(id=>Boolean(evidence[id]))||Array.isArray(it.evidence)&&it.evidence.length);
 return {name:row.name,brandCount:items.length,provedItems:itemProof.length,withLinecard:items.length>0};
});
const named=name=>records.find(x=>x.name.toLowerCase().includes(name.toLowerCase()))||null;
const output={
 publishedDistributors:rows.length,
 withNamedBrands:records.filter(x=>x.brandCount>0).length,
 withoutNamedBrands:records.filter(x=>x.brandCount===0).length,
 namedBrandsTotal:records.reduce((n,x)=>n+x.brandCount,0),
 important:{ajoomal:named('ajoomal'),infinigate:named('infinigate'),also:named('also')},
 zeroLinecard:records.filter(x=>!x.withLinecard).map(x=>x.name).slice(0,45),
 largest:records.sort((a,b)=>b.brandCount-a.brandCount).slice(0,10)
};
console.log('DISTRIBUTOR_LINECARD_AUDIT_V65 '+JSON.stringify(output));
assert.ok(rows.length>0);
assert.ok(output.withNamedBrands+output.withoutNamedBrands===rows.length);
