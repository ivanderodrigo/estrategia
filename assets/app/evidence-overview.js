(() => {
  'use strict';
  const root = document.getElementById('evidenceOverview');
  if (!root) return;
  const body = document.getElementById('evidenceOverviewBody');
  const details = document.getElementById('evidenceOverviewDetails');
  const toggle = document.getElementById('evidenceOverviewToggle');
  const format = n => Number(n || 0).toLocaleString('es-ES');
  const escape = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  toggle.addEventListener('click', () => {
    const show = details.hidden;
    details.hidden = !show;
    toggle.setAttribute('aria-expanded', String(show));
    toggle.textContent = show ? 'Ocultar auditoría' : 'Ver auditoría completa';
  });
  fetch('data/public/debt_overview.json', {cache:'no-store'})
    .then(r => {if(!r.ok) throw new Error(String(r.status)); return r.json();})
    .then(d => {
      const c = d.debt_breakdown || {};
      const claim = Number(c.claims_awaiting_evidence || 0);
      const derive = Number(c.derivation_support || 0);
      const empty = Number(c.empty_schema_fields || 0);
      const total = Number(d.total_open_gaps || 0);
      if (claim + derive + empty !== total) throw new Error('diagnóstico inconsistente');
      body.innerHTML = '<div class="evidence-overview__cards">' +
        [['Afirmaciones por acreditar',claim,'Se necesita evidencia pública específica.','is-evidence'],
         ['Derivaciones pendientes',derive,'Requieren reglas y datos de entrada fiables.','is-derived'],
         ['Campos sin información',empty,'No equivalen a afirmaciones sin acreditar.','is-empty']].map(x =>
          '<article class="evidence-overview__card '+x[3]+'"><strong>'+format(x[1])+'</strong><h2>'+x[0]+'</h2><p>'+x[2]+'</p></article>'
        ).join('')+'</div><p class="evidence-overview__footnote">Auditoría íntegra: '+format(total)+' elementos. Ninguna cifra equivale por sí sola a datos acreditados. Fecha del diagnóstico: '+escape((d.generated_at||'').slice(0,10))+'.</p>';
      const labels={manufacturers:'Fabricantes',distributors:'Mayoristas',integrators:'Integradores',clients_public:'Clientes públicos',clients_private:'Clientes privados',trends:'Tendencias',architectures:'Arquitecturas'};
      details.innerHTML='<h2>Auditoría por área</h2><div class="evidence-overview__table-wrap"><table><thead><tr><th>Área</th><th>Por acreditar</th><th>Derivaciones</th><th>Campos vacíos</th></tr></thead><tbody>'+
        Object.entries(d.by_section||{}).map(([section,v])=>'<tr><th>'+escape(labels[section]||section)+'</th><td>'+format(v.claims_awaiting_evidence)+'</td><td>'+format(v.derivation_support)+'</td><td>'+format(v.empty_schema_fields)+'</td></tr>').join('')+
        '</tbody></table></div><p>Los pendientes siguen visibles para auditoría; ningún registro se ha eliminado ni validado automáticamente.</p>';
    })
    .catch(() => {
      body.innerHTML='<p>No se ha podido cargar el diagnóstico actualizado. La información principal del observatorio sigue disponible; no se mostrarán cifras sin validar.</p>';
      toggle.disabled=true;
    });
})();
