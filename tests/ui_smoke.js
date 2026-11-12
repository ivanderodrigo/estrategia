const fs = require('fs');

const js = fs.readFileSync('assets/app/intelligence.js', 'utf8');
const css = fs.readFileSync('assets/app/intelligence.css', 'utf8');

for (const token of [
  'data/public/manifest.json', 'ensureSection', 'ensureViewData', 'clients_public',
  'clients_private', 'reorderColumn', 'columnChooser', 'currentColumnWidth', 'App v6.4.0',
  'atomic-evidence-missing', 'el sistema no muestra fuentes de otros elementos',
  'analysisPanel', 'WestconFilters.apply', 'sessionStorage', 'savedFilters',
  'openFilteredReport', 'WestconReports.build', 'generateFilteredCsv', 'window.print',
  'Pendiente de verificación', 'Fuente documental Westcon', 'Fuente pública primaria',
]) {
  if (!js.includes(token)) throw new Error(`missing JS capability: ${token}`);
}
if (js.includes('data/current/intelligence.json')) throw new Error('frontend exposes internal intelligence');
if (js.includes('items[index]')) throw new Error('traceability can fall back to an unrelated list item');
if (js.includes('historicalBlock')) throw new Error('historical lineage is mixed into the normal source UI');

for (const token of [
  'table.data-table thead{position:sticky;top:0;z-index:20}',
  'table.data-table thead th{position:sticky;top:0;z-index:21',
  'table.data-table th.name-col{z-index:24',
  '.column-menu label[data-column-option]:has(input:checked)',
  '.column-menu label[data-column-option]:focus-within',
  '.analysis-panel',
  '.filter-rule',
  '@media(max-width:560px)',
  'body.filtered-report-print>.filtered-report-sheet.ready',
]) {
  if (!css.includes(token)) throw new Error(`sticky table regression: ${token}`);
}

if (js.includes('data-col-toggle data-view=')) throw new Error('column chooser contains duplicate data-col-toggle attribute');
if (!js.includes('data-view="${esc(view)}" data-col-toggle="${esc(c.id)}"')) throw new Error('column chooser does not expose the selected column id');

const html = fs.readFileSync('index.html', 'utf8');
if (html.includes('data-view="observatorio"')) throw new Error('legacy Hoy en Westcon tab is still primary navigation');
for (const label of ['Fabricantes','Mayoristas','Integradores','Clientes','Tendencias','Arquitecturas']) {
  if (!html.includes('>'+label+'</button>')) throw new Error('missing primary observatory area: '+label);
}

console.log('UI smoke v4.4.0 PASS');

// v6.1: all data values use badges; unsupported ones must never inherit proof.
for (const token of ['function atomicCurrentProof(', 'function pendingTagHtml(', 'confidence-tag unverified', 'elements=value.map(', 'return sourcedScalarForTable(field)?traceable(', 'f&&hasValue(f.value)?renderValue(']) {
  if (!js.includes(token)) throw new Error('business-evidence UI regression: '+token);
}
if (js.includes('unverified-clues')) throw new Error('legacy disclosure remains instead of uniform tags');
if (!['manufacturerNews','integratorNews','clientNews','distributorNews','trendNews','architectureNews','manufacturerNewsSearch','integratorNewsSearch','clientNewsSearch','distributorNewsSearch','trendNewsSearch','architectureNewsSearch','distributorIncludeUnconfirmed','procurementDownloadCsv'].every(id => html.includes('id="'+id+'"'))) throw new Error('v6.1 news or procurement downloads missing');

for(const label of [
 "CATEGORICAL_FIELDS=new Set(['domain'",
 "CATEGORICAL_FIELDS.has(columnId)",
 "renderValue(f,null,'table',col.id)",
 "renderEntityNews('distributors',relevant)",
 "distributorIncludeUnconfirmed",
 "context(row,manufacturers)",
]){
 if(!js.includes(label))throw new Error('v6.3 business curation/category badge regression: '+label);
}
for(const label of ['.categorical-tags .confidence-tag','.distributor-curation-controls']){
 if(!css.includes(label))throw new Error('v6.3 category/curation visual regression: '+label);
}
