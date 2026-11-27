'use strict';
const fs=require('fs'),assert=require('assert'),vm=require('vm');
const audit=require('../assets/app/audit-intelligence.js');
const script=fs.readFileSync('assets/app/command-center.js','utf8');
const manifest=JSON.parse(fs.readFileSync('data/public/manifest.json','utf8'));
const debt=JSON.parse(fs.readFileSync('data/public/debt_overview.json','utf8'));
async function render(failDebt=false,showHygiene=false){
 const visibleManifest=showHygiene?{...manifest,meta:{...manifest.meta,vendor_label_quarantine:{
  removed_from_public_views:3,by_section:{distributors:2,integrators:1},
  examples:[{entity:'Distributor',field:'vendor_relations',value:'Marketing',reason:'navigation'}],
 },vendor_relation_evidence_quarantine:{
  downgraded_from_unproven:2,by_section:{distributors:1,integrators:1},
  examples:[{entity:'Integrator',field:'vendor_relations',value:'Zscaler'}]
 },historical_semantic_misclassification:{
  excluded_claim_source_pairs:4,examples:[{entity:'Globomatik',value:'Placas Base Intel'}]
 }}}:manifest;
 const nodes=Object.fromEntries(['commandCenter','homeNav','ccMetrics','ccDebt','ccAudit','ccFreshness'].map(id=>[id,{id,innerHTML:'',textContent:'',addEventListener(){},classList:{add(){},remove(){},toggle(){}}}]));
 const document={
  getElementById:id=>nodes[id]||null,
  querySelectorAll:()=>[],
  body:{classList:{add(){},remove(){}}},
 };
 const fetch=async path=>{
  if(failDebt&&path.includes('debt_overview'))throw Error('offline');
  return {ok:true,json:async()=>path.includes('manifest')?visibleManifest:path.includes('audit_integrity')
   ?{status:'PASS',snapshot_generated_at:visibleManifest.generated_at}:path.includes('last_run')
   ?{generated_at:visibleManifest.generated_at,research_finished_at:'2026-11-13T11:31:21+00:00'}:debt};
 };
 vm.runInNewContext(script,{document,window:{WestconAudit:audit,scrollTo(){}},fetch,console});
 for(let i=0;i<5;i++)await Promise.resolve();
 await new Promise(resolve=>setTimeout(resolve,20));
 return nodes;
}
(async()=>{
 const ok=await render();
 assert.ok(ok.ccAudit.innerHTML.includes('Mayoristas'));
 assert.ok(ok.ccAudit.innerHTML.includes('Arquitecturas'));
 assert.ok(ok.ccDebt.innerHTML.includes('Afirmaciones por acreditar'));
 assert.ok(ok.ccFreshness.textContent.includes('Última investigación real'));
 assert.ok(ok.ccFreshness.textContent.includes('Fotografía publicada'));
 assert.ok(!ok.ccFreshness.textContent.includes('registro de investigación de otro corte'));
 assert.ok(ok.ccAudit.innerHTML.includes('Desglose conciliado'));
 assert.ok(!ok.ccAudit.innerHTML.includes('Auditoría integral fallida'));
 const hygiene=await render(false,true);
 assert.ok(hygiene.ccAudit.innerHTML.includes('Etiquetas no válidas como fabricantes'));
 assert.ok(hygiene.ccAudit.innerHTML.includes('Marketing'));
 assert.ok(hygiene.ccAudit.innerHTML.includes('no se computan como fabricantes acreditados')||
  hygiene.ccAudit.innerHTML.includes('No se computan como fabricantes acreditados'));
 assert.ok(hygiene.ccAudit.innerHTML.includes('Relaciones con fabricantes pendientes de fuente específica'));
 assert.ok(hygiene.ccAudit.innerHTML.includes('Zscaler'));
 assert.ok(hygiene.ccAudit.innerHTML.includes('Verificaciones históricas reclasificadas'));
 assert.ok(hygiene.ccAudit.innerHTML.includes('Placas Base Intel'));
 const degraded=await render(true);
 assert.ok(degraded.ccAudit.innerHTML.includes('no disponible'),'Missing debt must show a message, never an empty audit');
 assert.ok(degraded.ccDebt.innerHTML.includes('sin datos consistentes'));
 console.log('COMMAND_CENTER_AUDIT_V64 PASS');
})().catch(e=>{console.error(e);process.exitCode=1;});
