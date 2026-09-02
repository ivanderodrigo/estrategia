const fs = require('fs');

const js = fs.readFileSync('assets/app/intelligence.js', 'utf8');
const css = fs.readFileSync('assets/app/intelligence.css', 'utf8');

for (const token of [
  'data/public/manifest.json', 'ensureSection', 'ensureViewData', 'clients_public',
  'clients_private', 'reorderColumn', 'columnChooser', 'currentColumnWidth', 'App v4.0.6',
  'atomic-evidence-missing', 'el sistema no muestra fuentes de otros elementos',
]) {
  if (!js.includes(token)) throw new Error(`missing JS capability: ${token}`);
}
if (js.includes('data/current/intelligence.json')) throw new Error('frontend exposes internal intelligence');
if (js.includes('items[index]')) throw new Error('traceability can fall back to an unrelated list item');

for (const token of [
  'table.data-table thead{position:sticky;top:0;z-index:20}',
  'table.data-table thead th{position:sticky;top:0;z-index:21',
  'table.data-table th.name-col{z-index:24',
]) {
  if (!css.includes(token)) throw new Error(`sticky table regression: ${token}`);
}

console.log('UI smoke v4.0.6 PASS');
