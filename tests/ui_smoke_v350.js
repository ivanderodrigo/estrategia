const fs = require('fs');
const path = require('path');
const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const js = fs.readFileSync(path.join(root, 'assets/v350/intelligence.js'), 'utf8');
const data = JSON.parse(fs.readFileSync(path.join(root, 'data/v35/intelligence.json'), 'utf8'));

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const views = [...html.matchAll(/data-view="([^"]+)"/g)].map(m => m[1]);
assert(JSON.stringify(views) === JSON.stringify(['fabricantes','integradores','mayoristas','tendencias','arquitecturas']), 'La navegación principal debe contener exactamente cinco áreas');
assert(html.includes('assets/v350/intelligence.js'), 'Falta JS v3.5');
assert(html.includes('assets/v350/intelligence.css'), 'Falta CSS v3.5');
assert(!/assets\/(v31|v32|v33|v333|v340)\//i.test(html), 'El frontend carga activos legacy');
assert(js.includes('activeColumns'), 'Falta ocultación dinámica de columnas sin datos');
assert(js.includes('trace-popover'), 'Falta popover de trazabilidad por dato');
assert(js.includes('help-icon'), 'Falta ayuda ? en cabeceras ambiguas');
for (const section of ['manufacturers','integrators','distributors','trends','architectures']) {
  assert(Array.isArray(data[section]) && data[section].length > 0, `Sin datos en ${section}`);
}
console.log('UI smoke v3.5.0 · PASS');
