#!/usr/bin/env node
/* Deterministic v3.4 UI/data contract smoke test; no browser or network. */
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8');
const json = relative => JSON.parse(read(relative));
const fail = message => { throw new Error(message); };

const index = read('index.html');
const app = read('assets/app.js');
const v34 = read('assets/v340/business-intelligence.js');
const css = read('assets/v340/business-intelligence.css');
const recommendations = json('data/v34/recommendations.json').recommendations || [];
const entities = json('data/v34/entities.json');
const relationships = json('data/v34/relationships.json');
const architectures = json('data/v34/architectures.json').architectures || [];
const tableConfig = json('config/v34/table_config.json');
const motion = json('data/v34/ecosystem_motion_intelligence.json');
const catalog = json('data/v34/source_catalog.json');

['executiveDecisionBrief', 'historicalIntelligence', 'sourceLearningV340', 'business-intelligence.js'].forEach(token => {
  if (!index.includes(token)) fail(`Falta superficie v3.4: ${token}`);
});
['data/v34/recommendations.json', 'data/v34/ecosystem_motion_intelligence.json', 'config/v34/table_config.json'].forEach(token => {
  if (!app.includes(token)) fail(`La aplicación no carga ${token}`);
});
['ACCIÓN', 'POR QUÉ', 'POR QUÉ AHORA', 'INFORMACIÓN PENDIENTE', 'FABRICANTES QUE MUEVE', 'PERFILES QUE BUSCA', 'exportPptx', 'reportHtml'].forEach(token => {
  if (!v34.includes(token)) fail(`La UI v3.4 no contiene ${token}`);
});
if (css.length < 8000) fail('La capa visual v3.4 parece incompleta');
if (!recommendations.length || recommendations.some(row => !row.evidence?.length)) fail('Recomendaciones sin evidencia');
if (!entities.integrators?.length || !entities.distributors?.length) fail('Tablas de ecosistema vacías');
if (!relationships.integrator_vendor?.every(row => row.relationship_intensity !== undefined && row.fact_confidence)) fail('Relaciones sin intensidad/confianza separadas');
if (architectures.length < 12 || architectures.some(row => !row.layers?.length || !row.westcon_services?.length)) fail('Arquitecturas v3.4 incompletas');
if (tableConfig.behavior.minimum_population_ratio < 0.15) fail('El auto-ocultado permite columnas casi vacías');
for (const type of ['integrators', 'distributors']) {
  const tier = tableConfig.entities[type].columns.find(column => column.field === 'entity_tier');
  if (!tier || tier.user_visible !== false) fail('La prioridad interna aparece como columna de usuario');
}
if (!motion.entities?.length || !motion.relationship_source_playbook?.evidence_order?.length) fail('Falta inteligencia de fabricantes/perfiles');
if (catalog.sources?.length < 100 || catalog.sources?.length > 150) fail('Catálogo de fuentes fuera del rango 100-150');
console.log(`OK · UI v3.4 · ${recommendations.length} recomendaciones · ${entities.integrators.length} integradores · ${entities.distributors.length} mayoristas · ${architectures.length} arquitecturas · ${catalog.sources.length} fuentes`);
