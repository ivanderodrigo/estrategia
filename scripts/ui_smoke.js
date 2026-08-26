#!/usr/bin/env node
/* Deterministic runtime smoke test for the static UI; no browser or network. */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const elements = new Map();

class FakeElement {
  constructor(selector) {
    this.selector = selector;
    this.innerHTML = '';
    this.textContent = '';
    this.style = {setProperty() {}};
    this.classList = {add() {}, remove() {}, toggle() {}};
    this.value = selector === '#vendorSearch' || selector === '#sourceSearch' ? '' : 'all';
  }
  addEventListener() {}
  querySelector(selector) { return getElement(`${this.selector} ${selector}`); }
  querySelectorAll() { return []; }
  scrollIntoView() {}
}

function getElement(selector) {
  if (!elements.has(selector)) elements.set(selector, new FakeElement(selector));
  return elements.get(selector);
}

const storage = new Map();
const document = {
  querySelector: getElement,
  querySelectorAll() { return []; },
  body: getElement('body'),
  documentElement: getElement('html')
};

const context = {
  console,
  document,
  window: {innerWidth: 1440, scrollTo() {}},
  localStorage: {
    getItem(key) { return storage.has(key) ? storage.get(key) : null; },
    setItem(key, value) { storage.set(key, String(value)); }
  },
  fetch: async relative => {
    const file = path.join(root, String(relative));
    return {ok: fs.existsSync(file), json: async () => JSON.parse(fs.readFileSync(file, 'utf8'))};
  },
  setTimeout,
  clearTimeout,
  Intl,
  Date,
  Map,
  Set,
  Promise,
  JSON,
  Math,
  Number,
  String,
  Object,
  Array,
  RegExp
};
context.globalThis = context;
vm.createContext(context);

const app = fs.readFileSync(path.join(root, 'assets/app.js'), 'utf8');
vm.runInContext(`${app}\nglobalThis.__state=state;globalThis.__selectVendor=selectVendor;`, context, {filename: 'assets/app.js'});

async function waitForLoad() {
  for (let i = 0; i < 100; i += 1) {
    if (context.__state?.vendors?.length === 36) return;
    await new Promise(resolve => setTimeout(resolve, 10));
  }
  throw new Error('La aplicación no terminó de cargar los 36 fabricantes');
}

(async () => {
  await waitForLoad();
  if (context.__state.reality.facts.length !== 30) throw new Error('La capa de realidad no cargó 30 hechos');
  if (Object.keys(context.__state.reality.vendors).length !== 12) throw new Error('No cargaron los 12 contratos verificables');
  if (!getElement('#marketKpis').innerHTML.includes('91')) throw new Error('El KPI no unifica las 91 evidencias públicas');

  context.__selectVendor('Palo Alto Networks');
  const verified = getElement('#vendorDetail').innerHTML;
  if (!verified.includes('DECISIÓN EJECUTIVA VERIFICADA') || !verified.includes('GO / NO-GO') || !verified.includes('60 días')) throw new Error('Contrato verificable incompleto en detalle');

  context.__selectVendor('1Password');
  if (!getElement('#vendorDetail').innerHTML.includes('DECISIÓN BLOQUEADA')) throw new Error('El gate no bloquea una recomendación sin contrato público');

  console.log('OK · UI runtime · 36 vendors · 91 evidencias · 12 contratos · gate verificado');
})().catch(error => { console.error(error); process.exitCode = 1; });
