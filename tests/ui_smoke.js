const fs = require('fs');

const js = fs.readFileSync('assets/app/intelligence.js', 'utf8');
const css = fs.readFileSync('assets/app/intelligence.css', 'utf8');

for (const token of [
  'data/public/manifest.json', 'ensureSection', 'ensureViewData', 'clients_public',
  'clients_private', 'reorderColumn', 'columnChooser', 'currentColumnWidth', 'App v4.3.0',
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

console.log('UI smoke v4.3.0 PASS');
