// Real-data regression: every SASE/SSE layer vendor must appear as a tab.
const fs=require('fs'),assert=require('assert'),vm=require('vm');
const js=fs.readFileSync('assets/app/intelligence.js','utf8');
const data=JSON.parse(fs.readFileSync('data/public/sections/architectures.json','utf8'));
const sase=data.rows.find(r=>r.name==='SASE / SSE');
assert(sase&&sase.fields.layers&&Array.isArray(sase.fields.layers.value));
const layers=sase.fields.layers.value;
const allVendors=[...new Set(layers.flatMap(x=>x.vendors||[]))];
assert(allVendors.length>=8,'SASE/SSE source data unexpectedly missing manufacturers');

const start=js.indexOf('function renderValue(');
const end=js.indexOf('function allRowEvidence(',start);
assert(start>0&&end>start,'renderer extraction anchors must remain available');
const body=js.slice(start,end);
const sandbox={
  norm:x=>String(x||'').toLowerCase(),
  atomicCurrentProof:ev=>Array.isArray(ev)&&ev.length>0,
  itemFor:(f,v)=>f.items?.find(x=>x.value===v)||{value:v,evidence:[]},
  tagHtml:(f,v)=>'<span class="tag confidence-tag high">'+v+'</span>',
  pendingTagHtml:(f,v)=>'<span class="tag confidence-tag unverified">'+v+'</span>',
  esc:x=>String(x||''),listLimit:()=>2,
};
vm.runInNewContext(body+';this.renderValue=renderValue;',sandbox);
const html=sandbox.renderValue(sase.fields.layers,null,'card','layers');
assert(html.includes('architecture-vendor-summary'),'Missing flat manufacturer summary');
assert(html.includes('architecture-vendor-tabs'),'Missing accessible badges');
assert(html.includes('layer-vendors'),'Missing layered manufacturer badges');
assert(html.includes('Fabricantes asociados ('+allVendors.length+')'),'Wrong roster count');
for(const vendor of allVendors) assert(html.includes('>'+vendor+'</span>'),'Manufacturer absent: '+vendor);
assert(html.includes('>Cisco</span>'));
assert(html.includes('>Zscaler</span>'));
assert(html.includes('>Palo Alto Networks</span>'));
assert(html.includes('>Check Point</span>'));
console.log('SASE/SSE real manufacturer render PASS, distinct manufacturers:',allVendors.length);
