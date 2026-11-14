'use strict';
const fs=require('fs'),assert=require('assert'),vm=require('vm');
const audit=require('../assets/app/audit-intelligence.js');
const script=fs.readFileSync('assets/app/command-center.js','utf8');
const manifest=JSON.parse(fs.readFileSync('data/public/manifest.json','utf8'));
const debt=JSON.parse(fs.readFileSync('data/public/debt_overview.json','utf8'));
async function render(failDebt=false){
 const nodes=Object.fromEntries(['commandCenter','homeNav','ccMetrics','ccDebt','ccAudit','ccFreshness'].map(id=>[id,{id,innerHTML:'',textContent:'',addEventListener(){},classList:{add(){},remove(){},toggle(){}}}]));
 const document={
  getElementById:id=>nodes[id]||null,
  querySelectorAll:()=>[],
  body:{classList:{add(){},remove(){}}},
 };
 const fetch=async path=>{
  if(failDebt&&path.includes('debt_overview'))throw Error('offline');
  return {ok:true,json:async()=>path.includes('manifest')?manifest:path.includes('audit_integrity')
   ?{status:'PASS',snapshot_generated_at:manifest.generated_at}:debt};
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
 assert.ok(ok.ccAudit.innerHTML.includes('Desglose conciliado'));
 assert.ok(!ok.ccAudit.innerHTML.includes('Auditoría integral fallida'));
 const degraded=await render(true);
 assert.ok(degraded.ccAudit.innerHTML.includes('no disponible'),'Missing debt must show a message, never an empty audit');
 assert.ok(degraded.ccDebt.innerHTML.includes('sin datos consistentes'));
 console.log('COMMAND_CENTER_AUDIT_V64 PASS');
})().catch(e=>{console.error(e);process.exitCode=1;});
