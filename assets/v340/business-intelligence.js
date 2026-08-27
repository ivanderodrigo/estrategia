(function () {
  'use strict';

  const $ = (selector, root = document) => root.querySelector(selector);
  const esc = value => String(value ?? '').replace(/[&<>\"]/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '\"': '&quot;'}[char]));
  const norm = value => String(value || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, ' ').trim();
  const unique = values => [...new Set((values || []).filter(Boolean))];
  const score = value => Math.round(Number(value?.score ?? value ?? 0) * (Number(value?.score ?? value ?? 0) <= 1 ? 100 : 1));
  const fmtDate = value => {
    if (!value) return 'No publicada';
    if (String(value).toLowerCase().includes('no publicada')) return 'No publicada';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : new Intl.DateTimeFormat('es-ES', {day: '2-digit', month: 'short', year: 'numeric'}).format(date);
  };
  const actionClass = value => ({'ACTUAR': 'act', 'PREPARAR / VALIDAR': 'validate', 'INVESTIGAR': 'research', 'VIGILAR': 'watch'}[value] || 'research');
  const plainField = field => String(field || '').replaceAll('_', ' ').replace(/\b\w/g, char => char.toUpperCase());
  const tableState = {};

  function valueOf(row, field) {
    const value = row?.[field];
    if (value && typeof value === 'object' && !Array.isArray(value) && 'score' in value) return value.score;
    return value;
  }

  function hasValue(value) {
    if (value === false || value === null || value === undefined || value === '') return false;
    if (Array.isArray(value)) return value.length > 0;
    if (typeof value === 'object') return Object.keys(value).length > 0;
    return true;
  }

  function compact(value, limit = 4) {
    if (Array.isArray(value)) return value.slice(0, limit).map(item => typeof item === 'string' ? item : item.name || item.vendor || JSON.stringify(item)).join(' · ') || '—';
    if (value && typeof value === 'object' && 'score' in value) return `${Math.round(Number(value.score || 0))}/100`;
    if (typeof value === 'boolean') return value ? 'Confirmado' : 'Información pendiente';
    if (typeof value === 'number' && value > 0 && value <= 1) return `${Math.round(value * 100)}/100`;
    return value === 0 ? '0' : String(value || '—');
  }

  function evidenceLinks(evidence, limit = 5) {
    return (evidence || []).slice(0, limit).map(item => `<a href="${esc(item.url)}" target="_blank" rel="noopener"><b>${esc(item.source || 'Fuente pública')}</b><span>${esc(fmtDate(item.date))} · ${esc(item.fact || item.title || 'Evidencia vinculada')}</span></a>`).join('') || '<span class="v340-muted">Sin evidencia enlazada.</span>';
  }

  function renderBrief(state) {
    const root = $('#executiveDecisionBrief');
    if (!root) return;
    const brief = state.v34Brief?.executive_decision_brief || {};
    const recommendations = state.v34Recommendations?.recommendations || [];
    const distribution = recommendations.reduce((acc, item) => ((acc[item.action_type] = (acc[item.action_type] || 0) + 1), acc), {});
    const quality = state.v34Quality || {};
    root.innerHTML = `
      <section class="v340-brief-head">
        <div><span class="v340-kicker">QUÉ HA CAMBIADO</span><h2>${esc(brief.what_changed?.[0] || 'Acciones graduadas por evidencia y riesgo.')}</h2><p>${esc(brief.why_it_matters || '')}</p></div>
        <div class="v340-brief-score"><strong>${recommendations.length}</strong><span>recomendaciones trazables</span><small>Calidad ${esc(quality.status || 'pendiente')} · ${quality.summary?.warnings || 0} advertencias visibles</small></div>
      </section>
      <div class="v340-action-strip">${['ACTUAR', 'PREPARAR / VALIDAR', 'INVESTIGAR', 'VIGILAR'].map(type => `<div class="${actionClass(type)}"><b>${distribution[type] || 0}</b><span>${esc(type)}</span></div>`).join('')}</div>
      <div class="v340-brief-grid">
        <article><span>POR QUÉ IMPORTA</span><p>${esc(brief.why_it_matters || 'La acción se ajusta a la evidencia sin ocultar señales materiales.')}</p></article>
        <article><span>QUÉ HACER AHORA</span><ol>${(brief.what_to_do || []).slice(0, 3).map(item => `<li>${esc(item)}</li>`).join('')}</ol></article>
        <article><span>DEUDA DE CONOCIMIENTO</span><p>${esc(brief.knowledge_debt?.explanation || 'Los gaps elevan la prioridad de investigación, no se rellenan con inferencias.')}</p><b>${brief.knowledge_debt?.score ?? '—'}/100 pendiente</b></article>
      </div>`;
  }

  function recommendationCard(item, index) {
    return `<article class="v340-recommendation ${actionClass(item.action_type)}">
      <header><div><span class="v340-action-type">${esc(item.action_type)}</span><small>#${String(index + 1).padStart(2, '0')} · ${esc(item.horizon)} · ${esc(item.proposed_owner)}</small></div><div class="v340-impact"><b>${item.impact_potential?.score ?? '—'}</b><span>impacto relativo</span></div></header>
      <h3>${esc(item.title)}</h3><p class="v340-action"><b>ACCIÓN</b>${esc(item.action)}</p>
      <div class="v340-reason"><p><b>POR QUÉ</b>${esc(item.why)}</p><p><b>POR QUÉ AHORA</b>${esc(item.why_now)}</p></div>
      <div class="v340-confidence"><span><b>${score(item.fact_confidence)}</b>Hechos</span><span><b>${score(item.interpretation_confidence)}</b>Interpretación</span><span><b>${score(item.action_risk)}</b>Riesgo acción</span><span><b>${esc(item.urgency)}</b>Urgencia</span><span><b>${esc(item.effort)}</b>Esfuerzo</span></div>
      <details><summary>Evidencias, economics y condición de cambio</summary>
        <div class="v340-rec-details"><div><h4>EVIDENCIAS</h4>${evidenceLinks(item.evidence)}</div><div><h4>INFORMACIÓN PENDIENTE</h4><ul>${(item.missing_information || []).map(value => `<li>${esc(plainField(value))}</li>`).join('')}</ul><h4>QUÉ LA CAMBIARÍA</h4><p>${esc(item.evidence_that_would_change_recommendation)}</p></div></div>
        <div class="v340-meta-tags">${unique([...(item.vendors_involved || []), ...(item.integrators_involved || []), ...(item.distributors_involved || []), ...(item.potential_services || [])]).slice(0, 14).map(value => `<span>${esc(value)}</span>`).join('')}</div>
        <p class="v340-disclaimer">Recurrencia ${item.recurring_revenue_potential?.score ?? '—'}/100 · margen relativo ${item.relative_margin_potential?.score ?? '—'}/100. ${esc(item.economic_disclaimer)}</p>
      </details>
    </article>`;
  }

  function renderRecommendations(state) {
    const root = $('#decisionCards');
    if (!root) return;
    const rows = state.v34Recommendations?.recommendations || [];
    root.classList.add('v340-decision-grid');
    root.innerHTML = rows.slice(0, 12).map(recommendationCard).join('') || '<p>No hay recomendaciones publicables; consulte la auditoría.</p>';
  }

  function tableConfig(state, type) {
    return state.v34TableConfig?.entities?.[type]?.columns || [];
  }

  function activeColumns(state, type, rows) {
    const configured = tableConfig(state, type);
    const minimumRatio = Number(state.v34TableConfig?.behavior?.minimum_population_ratio || 0.2);
    const userColumns = configured.filter(column => column.user_visible !== false);
    const available = userColumns.filter(column => column.required || rows.filter(row => hasValue(valueOf(row, column.field))).length / Math.max(1, rows.length) >= minimumRatio);
    const autoHidden = userColumns.filter(column => !available.some(item => item.field === column.field));
    const key = `westcon-v340-${type}-columns`;
    let saved = [];
    try { saved = JSON.parse(localStorage.getItem(key) || '[]'); } catch (_) { saved = []; }
    const byField = new Map(available.map(column => [column.field, column]));
    const ordered = saved.map(field => byField.get(field)).filter(Boolean);
    available.forEach(column => { if (!ordered.some(item => item.field === column.field)) ordered.push(column); });
    const selectedKey = `westcon-v340-${type}-visible`;
    let visible = [];
    try { visible = JSON.parse(localStorage.getItem(selectedKey) || '[]'); } catch (_) { visible = []; }
    const defaults = type === 'integrators'
      ? ['name', 'scope', 'strategic_importance_score', 'vendors', 'managed_services', 'activation_priority', 'recurring_services_potential', 'momentum_90d', 'coverage', 'confidence', 'research_gaps']
      : ['name', 'scope', 'confirmed_linecard', 'westcon_overlap', 'training_enablement', 'competitive_pressure', 'competitive_response_priority', 'momentum_90d', 'coverage', 'confidence', 'research_gaps'];
    if (!visible.length) visible = defaults;
    const required = available.filter(column => column.required).map(column => column.field);
    visible = unique([...required, ...visible]).filter(field => byField.has(field));
    return {available: ordered, visible, key, selectedKey, autoHidden};
  }

  function exportCsv(type, rows, columns) {
    const quote = value => `"${String(value ?? '').replaceAll('"', '""')}"`;
    const csv = ['\ufeff' + columns.map(column => quote(column.label)).join(';'), ...rows.map(row => columns.map(column => quote(compact(valueOf(row, column.field), 20))).join(';'))].join('\r\n');
    const link = document.createElement('a');
    link.href = URL.createObjectURL(new Blob([csv], {type: 'text/csv;charset=utf-8'}));
    link.download = `Westcon_v340_${type}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  function entityDetail(row, relationships, type, motionDocument) {
    const relationRows = (type === 'integrators' ? relationships.integrator_vendor : relationships.distributor_vendor || []).filter(item => norm(item.integrator || item.distributor) === norm(row.name)).sort((a, b) => b.relationship_intensity - a.relationship_intensity).slice(0, 12);
    const motion = (motionDocument?.entities || []).find(item => norm(item.entity) === norm(row.name)) || {};
    const confirmed = motion.manufacturers_confirmed || [], probable = motion.manufacturers_probable || [], jobs = motion.manufacturers_in_job_profiles || [], profiles = motion.profiles_sought || [];
    return `<div class="v340-entity-detail"><div><span>${esc(row.scope)}</span><h3>${esc(row.name)}</h3><p>Relevancia para Westcon ${row.westcon_relevance ?? '—'}/100 · cobertura ${row.coverage?.score ?? '—'}/100 · confianza de hechos ${score(row.confidence)}/100.</p>${evidenceLinks(row.evidence, 4)}</div><div><h4>FABRICANTES QUE MUEVE</h4><p><b>Confirmados:</b> ${esc(confirmed.slice(0, 10).map(item => `${item.vendor} (${item.intensity}/100)`).join(' · ') || 'Pendiente')}</p><p><b>Probables:</b> ${esc(probable.slice(0, 10).map(item => item.vendor).join(' · ') || 'Ninguno con evidencia suficiente')}</p><p><b>Indicadores en perfiles buscados:</b> ${esc(jobs.map(item => `${item.vendor} (${item.signals})`).join(' · ') || 'Pendiente de capturar vacantes explícitas')}</p><h4>PERFILES QUE BUSCA</h4><p>${esc(profiles.map(item => `${plainField(item.family)} (${item.signals})`).join(' · ') || 'Información pendiente')}</p><small>Una mención en empleo indica demanda de competencia, no partnership ni ventas.</small></div><div><h4>RELACIONES PRIORIZADAS</h4>${relationRows.map(rel => `<div class="v340-relation"><b>${esc(rel.vendor)}</b><span>${esc(rel.status_label)} · intensidad ${rel.relationship_intensity}/100 · confianza ${score(rel.fact_confidence)}/100</span><small>${esc(rel.geography?.scope || 'Ámbito pendiente')} · ${esc(fmtDate(rel.last_verified))}</small></div>`).join('') || '<p class="v340-muted">Relaciones específicas pendientes de investigación.</p>'}<h4>INFORMACIÓN PENDIENTE</h4><p>${esc((row.research_gaps || []).map(plainField).join(' · ') || 'Sin gaps estructurales detectados.')}</p></div></div>`;
  }

  function renderEntityTable(state, type) {
    const isIntegrator = type === 'integrators';
    const root = $(isIntegrator ? '#integratorCards' : '#distributorCards');
    if (!root) return;
    const search = norm($(isIntegrator ? '#integratorSearch' : '#distributorSearch')?.value);
    const country = $(isIntegrator ? '#integratorCountry' : '#distributorCountry')?.value || 'all';
    const allRows = state.v34Entities?.[type] || [];
    const columns = activeColumns(state, type, allRows);
    const current = tableState[type] || {sort: isIntegrator ? 'activation_priority' : 'competitive_response_priority', direction: 'desc', selected: ''};
    tableState[type] = current;
    let rows = allRows.filter(row => (country === 'all' || row.scope === country || row.scope === 'IBERIA' || (row.operations || []).some(item => item.country === country)) && (!search || norm(JSON.stringify(row)).includes(search)));
    rows.sort((a, b) => {
      const av = valueOf(a, current.sort), bv = valueOf(b, current.sort);
      const result = typeof av === 'number' && typeof bv === 'number' ? av - bv : String(av || '').localeCompare(String(bv || ''), 'es');
      return current.direction === 'asc' ? result : -result;
    });
    const visible = columns.available.filter(column => columns.visible.includes(column.field));
    root.className = 'v340-table-shell';
    root.innerHTML = `<div class="v340-table-toolbar"><div><b>${rows.length}</b><span>${isIntegrator ? 'integradores' : 'mayoristas'} visibles</span></div><details><summary>Columnas</summary><div class="v340-column-picker">${columns.available.map(column => `<label><input type="checkbox" data-v340-column="${esc(column.field)}" ${columns.visible.includes(column.field) ? 'checked' : ''} ${column.required ? 'disabled' : ''}>${esc(column.label)}</label>`).join('')}</div></details><button type="button" data-v340-export>Exportar CSV</button><small>Ordenable · seleccionable · movible · preferencias persistentes · ${columns.autoHidden.length} columnas con cobertura insuficiente ocultas</small></div><div class="v340-table-scroll"><table class="v340-entity-table"><thead><tr>${visible.map(column => `<th draggable="true" data-field="${esc(column.field)}" title="${esc(column.help)}"><button type="button">${esc(column.label)} <i>?</i>${current.sort === column.field ? (current.direction === 'asc' ? ' ↑' : ' ↓') : ''}</button></th>`).join('')}</tr></thead><tbody>${rows.map(row => `<tr data-entity="${esc(row.entity_id)}" class="${current.selected === row.entity_id ? 'selected' : ''}">${visible.map(column => `<td>${esc(compact(valueOf(row, column.field)))}</td>`).join('')}</tr>${current.selected === row.entity_id ? `<tr class="v340-detail-row"><td colspan="${visible.length}">${entityDetail(row, state.v34Relationships || {}, type, state.v34EcosystemMotion || {})}</td></tr>` : ''}`).join('')}</tbody></table></div>`;
    const count = $(isIntegrator ? '#integratorCount' : '#distributorCount');
    if (count) count.textContent = `${rows.length} de ${allRows.length}`;
    root.querySelectorAll('th button').forEach(button => button.onclick = () => {
      const field = button.parentElement.dataset.field;
      current.direction = current.sort === field && current.direction === 'desc' ? 'asc' : 'desc';
      current.sort = field;
      renderEntityTable(state, type);
    });
    root.querySelectorAll('tbody tr[data-entity]').forEach(tr => tr.onclick = () => {
      current.selected = current.selected === tr.dataset.entity ? '' : tr.dataset.entity;
      renderEntityTable(state, type);
    });
    root.querySelectorAll('[data-v340-column]').forEach(input => input.onchange = () => {
      let selected = [...root.querySelectorAll('[data-v340-column]:checked')].map(item => item.dataset.v340Column);
      if (!selected.includes('name')) selected.unshift('name');
      localStorage.setItem(columns.selectedKey, JSON.stringify(selected));
      renderEntityTable(state, type);
    });
    $('[data-v340-export]', root).onclick = () => exportCsv(type, rows, visible);
    let dragged = '';
    root.querySelectorAll('th[draggable]').forEach(th => {
      th.ondragstart = () => { dragged = th.dataset.field; };
      th.ondragover = event => event.preventDefault();
      th.ondrop = event => {
        event.preventDefault();
        const target = th.dataset.field;
        const order = columns.available.map(column => column.field).filter(field => field !== dragged);
        order.splice(Math.max(0, order.indexOf(target)), 0, dragged);
        localStorage.setItem(columns.key, JSON.stringify(order));
        renderEntityTable(state, type);
      };
    });
  }

  function renderArchitectures(state) {
    const root = $('#architectureCards');
    if (!root) return;
    root.className = 'v340-architecture-grid';
    root.innerHTML = (state.v34Architectures?.architectures || []).map((item, index) => `<article class="v340-architecture"><header><span>${String(index + 1).padStart(2, '0')}</span><div><small>ARQUITECTURA ORIGINAL · READINESS ${score(item.readiness)}/100</small><h3>${esc(item.title)}</h3></div></header><div class="v340-arch-context"><p><b>PROBLEMA</b>${esc(item.problem)}</p><p><b>OPORTUNIDAD</b>${esc(item.opportunity)}</p></div><div class="v340-layers">${(item.layers || []).map(layer => `<div><span>${esc(layer.name)}</span><b>${esc((layer.vendors || []).map(vendor => vendor.vendor).join(' + ') || 'A seleccionar')}</b><small>${esc(layer.integration_status)}</small></div>`).join('')}</div><div class="v340-arch-meta"><p><b>INTEGRADORES</b>${esc((item.integrators || []).slice(0, 4).map(value => value.name).join(' · ') || 'Por validar')}</p><p><b>SERVICIOS WESTCON</b>${esc((item.westcon_services || []).join(' · '))}</p><p><b>MONETIZACIÓN</b>${esc((item.monetization || []).join(' · '))}</p></div><details><summary>Gaps, KPIs, riesgos y evidencia</summary><div class="v340-rec-details"><div><h4>GAPS</h4><ul>${(item.gaps || []).map(value => `<li>${esc(value)}</li>`).join('')}</ul><h4>KPIs</h4><p>${esc((item.kpis || []).join(' · '))}</p></div><div><h4>RIESGOS</h4><ul>${(item.risks || []).map(value => `<li>${esc(value)}</li>`).join('')}</ul>${evidenceLinks(item.evidence, 3)}</div></div></details></article>`).join('');
  }

  function renderHistory(state) {
    const root = $('#historicalIntelligence');
    if (!root) return;
    const windows = state.v34History?.windows || {};
    root.innerHTML = `<div class="section-title"><div><span>HISTÓRICO MÓVIL</span><h2>Qué está cambiando</h2><p>Ventanas basadas en fechas de evidencia; no se inventa una serie si no hay snapshots comparables.</p></div></div><div class="v340-window-grid">${['30', '90', '365'].map(days => { const item = windows[days] || {}; const topTech = Object.entries(item.technologies || {}).slice(0, 4); return `<article><header><strong>${item.events || 0}</strong><span>cambios · ${days} días</span></header><div>${topTech.map(([name, count]) => `<span><b>${esc(name)}</b>${count}</span>`).join('')}</div><ol>${(item.changes || []).slice(0, 3).map(change => `<li><a href="${esc(change.url)}" target="_blank" rel="noopener"><b>${esc(change.entity)}</b>${esc(change.title)}</a><small>${esc(change.scope)} · ${fmtDate(change.date)}</small></li>`).join('')}</ol></article>`; }).join('')}</div>`;
  }

  function renderSourceLearning(state) {
    const root = $('#sourceLearningV340');
    if (!root) return;
    const data = state.v34SourceCoverage || {};
    const meta = data.meta || {};
    const routes = data.audience_source_routes || [];
    const jobs = (data.source_expansion || []).filter(item => (item.dimensions || []).some(value => norm(value).includes('hiring')));
    const best = (data.coverage || []).slice(0, 6);
    root.innerHTML = `<div class="section-title"><div><span>SOURCE LEARNING</span><h2>Dónde aprende mejor el sistema</h2><p>Entidad × dimensión × país × tipo de fuente. Una fuente fallida reduce prioridad; no rompe la ejecución.</p></div></div><div class="v340-source-kpis"><div><b>${meta.total_public_source_candidates || 0}</b><span>fuentes/candidatos</span></div><div><b>${routes.length}</b><span>rutas por audiencia</span></div><div><b>${jobs.length}</b><span>fuentes de contratación</span></div><div><b>${meta.errors_last_run || 0}</b><span>errores última ejecución</span></div></div><div class="v340-learning-grid"><article><h3>Mejores rutas observadas</h3>${best.map(item => `<div><b>${esc(plainField(item.entity_type))} · ${esc(plainField(item.dimension))}</b><span>${esc(item.country)} · ${esc(item.source_type)}</span><strong>${Math.round(100 * Math.min(1, item.next_use_priority || 0))}% prioridad</strong></div>`).join('')}</article><article><h3>Fuentes que usa el ecosistema</h3>${routes.slice(0, 8).map(route => `<div><b>${esc(plainField(route.actor))} · ${esc(route.decision_stage)}</b><span>${esc((route.source_types || []).slice(0, 4).join(' · '))}</span><strong>${Math.round(100 * Number(route.priority || 0))}%</strong></div>`).join('')}</article></div><p class="v340-disclaimer">Empleo: una vacante es señal de demanda de capacidades, no headcount ni contrato. Se deduplican copias sindicadas y se revalida en el portal oficial del empleador.</p>`;
  }

  function reportHtml(state, title) {
    const brief = state.v34Brief?.executive_decision_brief || {};
    const recommendations = state.v34Recommendations?.recommendations || [];
    const entities = state.v34Entities || {};
    const architectures = state.v34Architectures?.architectures || [];
    const history = state.v34History?.windows || {};
    const quality = state.v34Quality || {};
    const section = (heading, body, cls = '') => `<section class="report-module v340-report-section ${cls}"><h2>${esc(heading)}</h2>${body}</section>`;
    const recBody = recommendations.slice(0, 12).map((item, index) => `<article class="v340-report-rec"><span>${index + 1} · ${esc(item.action_type)} · ${esc(item.horizon)}</span><h3>${esc(item.title)}</h3><p><b>Acción:</b> ${esc(item.action)}</p><p><b>Por qué / ahora:</b> ${esc(item.why)} ${esc(item.why_now)}</p><p><b>Confianza:</b> hechos ${score(item.fact_confidence)}/100 · interpretación ${score(item.interpretation_confidence)}/100 · riesgo ${score(item.action_risk)}/100 · impacto ${item.impact_potential?.score}/100.</p><p><b>Responsable:</b> ${esc(item.proposed_owner)} · <b>Información pendiente:</b> ${esc((item.missing_information || []).map(plainField).join(' · '))}</p><div>${evidenceLinks(item.evidence, 3)}</div></article>`).join('');
    const parts = [`<div class="report-export v340-report"><section class="report-cover v340-report-cover"><div class="eyebrow">WESTCON IBERIA · v3.4.0</div><h1>${esc(title)}</h1><p>Business + Technology Decision Intelligence</p><div class="cover-meta">Acción proporcional · evidencia trazable · economics relativos · ${fmtDate(state.v34Brief?.meta?.generated_at)}</div></section><div class="report-body">`];
    parts.push(section('Resumen ejecutivo', `<h3>Qué cambió</h3><ul>${(brief.what_changed || []).map(value => `<li>${esc(value)}</li>`).join('')}</ul><h3>Por qué importa</h3><p>${esc(brief.why_it_matters)}</p><h3>Qué debemos hacer</h3><ol>${(brief.what_to_do || []).slice(0, 7).map(value => `<li>${esc(value)}</li>`).join('')}</ol>`, 'page-break'));
    parts.push(section('Situación, tendencias e histórico', `<div class="v340-report-metrics">${['30', '90', '365'].map(days => `<div><b>${history[days]?.events || 0}</b><span>cambios · ${days} días</span></div>`).join('')}</div><p>Tecnologías en 90 días: ${esc(Object.entries(history['90']?.technologies || {}).slice(0, 10).map(([key, value]) => `${key} (${value})`).join(' · '))}.</p>`));
    parts.push(section('Portfolio y ecosistema', `<h3>Integradores a activar</h3><table><thead><tr><th>Integrador</th><th>Ámbito</th><th>Prioridad</th><th>Fabricantes</th><th>Información pendiente</th></tr></thead><tbody>${(entities.integrators || []).slice().sort((a, b) => b.activation_priority - a.activation_priority).slice(0, 12).map(row => `<tr><td>${esc(row.name)}</td><td>${esc(row.scope)}</td><td>${row.activation_priority}/100</td><td>${esc(compact(row.vendors, 6))}</td><td>${esc(compact((row.research_gaps || []).map(plainField), 5))}</td></tr>`).join('')}</tbody></table><h3>Presión de mayoristas</h3><table><thead><tr><th>Mayorista</th><th>Ámbito</th><th>Presión</th><th>Respuesta</th><th>Solape</th></tr></thead><tbody>${(entities.distributors || []).slice().sort((a, b) => b.competitive_response_priority - a.competitive_response_priority).slice(0, 10).map(row => `<tr><td>${esc(row.name)}</td><td>${esc(row.scope)}</td><td>${row.competitive_pressure}/100</td><td>${row.competitive_response_priority}/100</td><td>${esc(compact(row.westcon_overlap, 7))}</td></tr>`).join('')}</tbody></table>`, 'page-break'));
    parts.push(section('Oportunidades, amenazas y recomendaciones', recBody, 'page-break'));
    parts.push(section('Plays y arquitecturas', architectures.map(item => `<article class="v340-report-arch"><h3>${esc(item.title)} · readiness ${score(item.readiness)}/100</h3><p><b>Problema:</b> ${esc(item.problem)} <b>Oportunidad:</b> ${esc(item.opportunity)}</p><p><b>Capas:</b> ${esc((item.layers || []).map(layer => `${layer.name}: ${(layer.vendors || []).map(v => v.vendor).join(' + ') || 'por seleccionar'}`).join(' → '))}</p><p><b>Servicios:</b> ${esc((item.westcon_services || []).join(' · '))} · <b>Gaps:</b> ${esc((item.gaps || []).join(' · '))}</p></article>`).join(''), 'page-break'));
    parts.push(section('Roadmap, KPIs y riesgos', `<h3>Ahora</h3><p>Ejecutar únicamente acciones ACTUAR vigentes; asignar owner y fecha a cada VALIDAR.</p><h3>30 días</h3><p>Cerrar primero las relaciones de mayor relevancia, linecards por país, capacidades de servicios y contratación tecnológica recurrente.</p><h3>Trimestre</h3><p>Validar dos integradores, una cuenta, arquitectura, BOM, attach, margen y time-to-revenue por play priorizado.</p><h3>KPIs</h3><p>Recomendaciones validadas · evidencia primaria · relaciones confirmadas · integradores activados · attach de servicios · recurrencia influenciada · tiempo a primera oportunidad · deuda de conocimiento.</p><h3>Riesgos</h3><p>No confundir catálogo con presión, vacantes con headcount, alcance global con Iberia, complementariedad con integración ni potencial relativo con forecast.</p>`));
    parts.push(section('Metodología, calidad y fuentes', `<p>${esc(state.v34Brief?.methodology?.recommendation_governance || 'Confianza factual, interpretación y riesgo de acción se evalúan por separado.')}</p><p><b>Auditoría:</b> ${esc(quality.status)} · ${quality.summary?.passed || 0}/${quality.summary?.checks || 0} checks superados · ${quality.summary?.warnings || 0} advertencias. Las advertencias no se convierten artificialmente en PASS.</p><p><b>Fuentes:</b> prioridad primaria, secundaria de calidad y agregador. Se incluyen portales de empleo, ATS corporativos, partner locators, certificaciones, advisories, eventos, comunidades técnicas, marketplaces, contratación pública y prensa de canal; las señales de descubrimiento se revalidan.</p><p>${esc(state.v34Brief?.meta?.economic_disclaimer)}</p>`, 'page-break'));
    parts.push('</div></div>');
    return parts.join('');
  }

  async function exportPptx(state, title, toast) {
    if (!window.PptxGenJS) { toast?.('Librería PowerPoint no disponible'); return; }
    const pptx = new PptxGenJS();
    pptx.layout = 'LAYOUT_WIDE'; pptx.author = 'Westcon Iberia'; pptx.company = 'Westcon-Comstor'; pptx.title = title; pptx.subject = 'Business + Technology Decision Intelligence v3.4.0'; pptx.lang = 'es-ES';
    pptx.theme = {headFontFace: 'Aptos Display', bodyFontFace: 'Aptos', lang: 'es-ES'};
    pptx.defineSlideMaster({title: 'V340', background: {color: 'F5F7F9'}, objects: [{rect: {x: 0, y: 0, w: 13.333, h: .16, fill: {color: 'F09E0D'}, line: {color: 'F09E0D'}}}, {text: {text: 'WESTCON IBERIA · DECISION INTELLIGENCE v3.4', options: {x: .55, y: .28, w: 7, h: .24, fontFace: 'Aptos', fontSize: 9, bold: true, color: '147997'}}}], slideNumber: {x: 12.6, y: 7.1, color: '6B7E8C', fontSize: 8}});
    const addTitle = (slide, heading, subtitle = '') => { slide.addText(heading, {x: .55, y: .68, w: 12, h: .55, fontFace: 'Aptos Display', fontSize: 26, bold: true, color: '082335', margin: 0}); if (subtitle) slide.addText(subtitle, {x: .55, y: 1.28, w: 12, h: .35, fontFace: 'Aptos', fontSize: 10, color: '5B7180', margin: 0}); };
    const card = (slide, x, y, w, h, heading, body, accent = '17A3A0') => { slide.addShape(pptx.ShapeType.roundRect, {x, y, w, h, rectRadius: .04, fill: {color: 'FFFFFF'}, line: {color: 'DDE6EA', pt: .7}}); slide.addShape(pptx.ShapeType.rect, {x, y, w: .07, h, fill: {color: accent}, line: {color: accent}}); slide.addText(heading, {x: x + .22, y: y + .18, w: w - .4, h: .28, fontFace: 'Aptos', fontSize: 9, bold: true, color: accent, margin: 0}); slide.addText(body, {x: x + .22, y: y + .56, w: w - .42, h: h - .7, fontFace: 'Aptos', fontSize: 10.5, color: '17394A', breakLine: true, valign: 'top', margin: 0}); };
    const recs = state.v34Recommendations?.recommendations || [], brief = state.v34Brief?.executive_decision_brief || {}, entities = state.v34Entities || {}, architectures = state.v34Architectures?.architectures || [], history = state.v34History?.windows || {};
    let slide = pptx.addSlide('V340');
    slide.background = {color: '082335'}; slide.addShape(pptx.ShapeType.rect, {x: 0, y: 0, w: 13.333, h: .17, fill: {color: 'F09E0D'}, line: {color: 'F09E0D'}}); slide.addText('WESTCON IBERIA', {x: .65, y: .55, w: 5, h: .35, fontSize: 11, bold: true, color: '4FD7D1', margin: 0}); slide.addText(title, {x: .65, y: 1.55, w: 10.8, h: 1.35, fontFace: 'Aptos Display', fontSize: 34, bold: true, color: 'FFFFFF', margin: 0}); slide.addText('Business + Technology Decision Intelligence\nv3.4.0 Production Candidate', {x: .68, y: 3.25, w: 6.5, h: .9, fontSize: 16, color: 'C8D9E2', margin: 0}); slide.addText('Hechos · interpretación · riesgo · acción proporcional', {x: .68, y: 5.85, w: 9.2, h: .35, fontSize: 13, bold: true, color: 'F6B93B', margin: 0});
    slide = pptx.addSlide('V340'); addTitle(slide, 'Qué ha cambiado', 'La señal material ya no desaparece por debajo de un umbral absoluto.'); (brief.what_changed || []).slice(0, 3).forEach((text, index) => card(slide, .55 + index * 4.15, 1.85, 3.8, 2.0, `0${index + 1}`, text, ['17A3A0', 'F09E0D', '3F68B6'][index])); card(slide, .55, 4.25, 12.25, 1.45, 'POR QUÉ IMPORTA', brief.why_it_matters || '', '082335');
    slide = pptx.addSlide('V340'); addTitle(slide, 'Decisiones prioritarias', `${recs.length} recomendaciones trazables; potenciales relativos, no forecasts.`); recs.slice(0, 5).forEach((item, index) => card(slide, .55 + (index % 2) * 6.25, 1.7 + Math.floor(index / 2) * 1.67, 5.9, 1.42, `${item.action_type} · ${item.impact_potential?.score}/100`, item.action, item.action_type === 'VIGILAR' ? '6B7E8C' : item.action_type === 'INVESTIGAR' ? '3F68B6' : '17A3A0'));
    slide = pptx.addSlide('V340'); addTitle(slide, 'Integradores a activar', 'Mayor relevancia primero; la información pendiente determina la investigación.'); slide.addTable([['Integrador', 'Ámbito', 'Activación', 'Fabricantes', 'Información pendiente'], ...(entities.integrators || []).slice().sort((a, b) => b.activation_priority - a.activation_priority).slice(0, 10).map(row => [row.name, row.scope, String(row.activation_priority), compact(row.vendors, 4), compact((row.research_gaps || []).map(plainField), 3)])], {x: .4, y: 1.65, w: 12.5, h: 5.2, border: {type: 'solid', color: 'D7E1E6', pt: .5}, fontFace: 'Aptos', fontSize: 7.5, color: '17394A', fill: 'FFFFFF', margin: .035, colW: [1.8, .8, .8, 3.8, 5.3]});
    slide = pptx.addSlide('V340'); addTitle(slide, 'Presión competitiva de mayoristas', 'Solape público no equivale a presión comercial efectiva.'); slide.addTable([['Mayorista', 'Ámbito', 'Presión', 'Respuesta', 'Solape público', 'Servicios / gaps'], ...(entities.distributors || []).slice().sort((a, b) => b.competitive_response_priority - a.competitive_response_priority).slice(0, 10).map(row => [row.name, row.scope, String(row.competitive_pressure), String(row.competitive_response_priority), compact(row.westcon_overlap, 5), compact((row.research_gaps || []).map(plainField), 3)])], {x: .4, y: 1.65, w: 12.5, h: 5.2, border: {type: 'solid', color: 'D7E1E6', pt: .5}, fontFace: 'Aptos', fontSize: 7.5, color: '17394A', fill: 'FFFFFF', margin: .035, colW: [1.8, .7, .65, .7, 4.2, 4.45]});
    slide = pptx.addSlide('V340'); addTitle(slide, 'Qué está cambiando', '30 / 90 / 365 días sobre fechas de evidencia.'); ['30', '90', '365'].forEach((days, index) => { const item = history[days] || {}; card(slide, .55 + index * 4.15, 1.8, 3.8, 3.8, `${item.events || 0} CAMBIOS · ${days} DÍAS`, `Tecnologías\n${Object.entries(item.technologies || {}).slice(0, 6).map(([key, value]) => `${key}  ${value}`).join('\n')}\n\nÁmbitos\n${Object.entries(item.by_scope || {}).slice(0, 4).map(([key, value]) => `${key}  ${value}`).join(' · ')}`, ['17A3A0', '3F68B6', 'F09E0D'][index]); });
    architectures.slice(0, 2).forEach((item, architectureIndex) => { slide = pptx.addSlide('V340'); addTitle(slide, item.title, `${item.problem} · readiness ${score(item.readiness)}/100`); const layers = item.layers || []; layers.forEach((layer, index) => card(slide, .55 + index * 3.05, 1.75, 2.7, 2.0, layer.name.toUpperCase(), (layer.vendors || []).map(v => v.vendor).join('\n') || 'A seleccionar', '17A3A0')); card(slide, .55, 4.15, 5.9, 1.75, 'SERVICIOS Y MONETIZACIÓN', `${(item.westcon_services || []).join(' · ')}\n${(item.monetization || []).join(' · ')}`, 'F09E0D'); card(slide, 6.7, 4.15, 6.1, 1.75, 'GAPS Y RIESGOS', `${(item.gaps || []).slice(0, 4).join(' · ')}\n${(item.risks || []).slice(0, 3).join(' · ')}`, 'B84B5C'); });
    slide = pptx.addSlide('V340'); addTitle(slide, 'Roadmap de activación', 'La acción escala solo cuando mejora la evidencia y se validan los economics internos.'); card(slide, .55, 1.8, 3.8, 3.4, 'AHORA', 'Asignar owner y fecha.\nRevalidar señales urgentes.\nCalificar ACTUAR.\nNo convertir una hipótesis en mandato.', 'B84B5C'); card(slide, 4.75, 1.8, 3.8, 3.4, '30 DÍAS', 'Cerrar relaciones más relevantes.\nLinecard por ES/PT.\nCapacidad de servicios.\nContratación tecnológica recurrente.', 'F09E0D'); card(slide, 8.95, 1.8, 3.8, 3.4, 'TRIMESTRE', 'Dos integradores + una cuenta.\nArquitectura y BOM.\nAttach y margen.\nTime-to-revenue.', '17A3A0');
    slide = pptx.addSlide('V340'); addTitle(slide, 'Método, calidad y límites', 'Trazabilidad antes que cantidad.'); card(slide, .55, 1.75, 3.8, 3.9, 'TRES VARIABLES', '1. Confianza del hecho\n2. Confianza de la interpretación\n3. Riesgo de la acción\n\nResultado: Actuar · Validar · Investigar · Vigilar.', '17A3A0'); card(slide, 4.75, 1.75, 3.8, 3.9, 'FUENTES Y APRENDIZAJE', 'Primaria > secundaria > agregador.\nEntidad × dimensión × país × tipo.\nPortales de partner, empleo, eventos, comunidades, advisories y contratación pública.', '3F68B6'); card(slide, 8.95, 1.75, 3.8, 3.9, 'LÍMITES', 'Economics relativos, no forecasts.\nVacante ≠ headcount.\nSolape ≠ conflicto.\nAusencia de prueba ≠ ausencia de relación.\nRevisión humana obligatoria.', 'F09E0D');
    await pptx.writeFile({fileName: 'Westcon_Iberia_Decision_Intelligence_v3.4.0.pptx'});
    toast?.('Presentación ejecutiva v3.4 generada');
  }

  function render(state) {
    renderBrief(state);
    renderRecommendations(state);
    renderEntityTable(state, 'integrators');
    renderEntityTable(state, 'distributors');
    renderArchitectures(state);
    renderHistory(state);
    renderSourceLearning(state);
    const bindings = [
      ['#integratorSearch', 'integrators'], ['#integratorCountry', 'integrators'],
      ['#distributorSearch', 'distributors'], ['#distributorCountry', 'distributors'],
    ];
    bindings.forEach(([selector, type]) => { const input = $(selector); if (input && !input.dataset.v340Bound) { input.dataset.v340Bound = '1'; input.addEventListener('input', () => renderEntityTable(state, type)); input.addEventListener('change', () => renderEntityTable(state, type)); } });
  }

  window.WestconV340 = {render, reportHtml, exportPptx};
})();
