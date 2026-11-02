(() => {
'use strict';
const home=document.getElementById('commandCenter'),homeNav=document.getElementById('homeNav');
if(!home||!homeNav)return;
const fmt=v=>Number(v||0).toLocaleString('es-ES');
const clean=v=>String(v??'').replace(/[&<>"']/g,k=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[k]));
const showHome=()=>{document.body.classList.add('cc-home');document.querySelectorAll('#tabs button').forEach(b=>b.classList.toggle('active',b===homeNav));window.scrollTo?.(0,0);};
homeNav.addEventListener('click',showHome);
document.querySelectorAll('[data-cc-go]').forEach(b=>b.addEventListener('click',()=>{
 const t=document.querySelector('#tabs [data-view="'+b.dataset.ccGo+'"]');
 if(t)t.click();
}));
document.querySelectorAll('#tabs [data-view]').forEach(b=>b.addEventListener('click',()=>{document.body.classList.remove('cc-home');homeNav.classList.remove('active');}));
showHome();
Promise.allSettled([
 fetch('data/public/manifest.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error(r.status);return r.json()}),
 fetch('data/public/debt_overview.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error(r.status);return r.json()})
]).then(([mr,dr])=>{
 const metrics=document.getElementById('ccMetrics'),debt=document.getElementById('ccDebt'),audit=document.getElementById('ccAudit');
 if(mr.status==='fulfilled'){
  const m=mr.value,c=m.counts||{},totalClients=Number(c.clients_public||0)+Number(c.clients_private||0);
  const tiles=[['Fabricantes',c.manufacturers],['Mayoristas',c.distributors],['Integradores',c.integrators],['Clientes',totalClients],['Tendencias y arquitecturas',Number(c.trends||0)+Number(c.architectures||0)]];
  metrics.innerHTML=tiles.map(([label,val])=>'<div class="cc-metric"><strong>'+fmt(val)+'</strong><span>'+clean(label)+'</span></div>').join('');
  document.getElementById('ccFreshness').textContent='Última actualización del dataset: '+clean((m.generated_at||m.meta?.generated_at||'desconocida').slice(0,10))+' · Datos contrastables en cada ficha';
 }else metrics.textContent='No se ha podido consultar el universo de entidades.';
 if(dr.status==='fulfilled'){
  const d=dr.value,c=d.debt_breakdown||{};
  const categories=[['Afirmaciones por acreditar',c.claims_awaiting_evidence,'evidence'],['Derivaciones pendientes',c.derivation_support,'derived'],['Campos sin información',c.empty_schema_fields,'empty']];
  if(categories.reduce((n,row)=>n+Number(row[1]||0),0)!==Number(d.total_open_gaps))throw Error('Desglose inconsistente');
  debt.innerHTML=categories.map(([label,n,type])=>'<div class="cc-debt-item '+type+'"><strong>'+fmt(n)+'</strong><span>'+label+'</span></div>').join('')+'<p>Inventario íntegro: '+fmt(d.total_open_gaps)+' pendientes de distinta naturaleza. No son  '+fmt(d.total_open_gaps)+' afirmaciones desacreditadas.</p>';
  const names={architectures:'Arquitecturas',clients_private:'Clientes privados',clients_public:'Clientes públicos',distributors:'Mayoristas',integrators:'Integradores',manufacturers:'Fabricantes',trends:'Tendencias'};
  audit.innerHTML='<table class="cc-audit-table"><thead><tr><th>Área</th><th>Evidencia</th><th>Derivación</th><th>Vacíos</th></tr></thead><tbody>'+Object.entries(d.by_section||{}).map(([k,v])=>'<tr><th>'+clean(names[k]||k)+'</th><td>'+fmt(v.claims_awaiting_evidence)+'</td><td>'+fmt(v.derivation_support)+'</td><td>'+fmt(v.empty_schema_fields)+'</td></tr>').join('')+'</tbody></table>';
 }else{debt.textContent='La auditoría no está disponible; no se muestran cifras sin comprobación.';}
}).catch(e=>{console.error('Command center:',e);document.getElementById('ccDebt').textContent='Diagnóstico incompleto; comprobar el inventario antes de interpretar los pendientes.';});
})();
