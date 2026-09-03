const assert = require('assert');
const F = require('../assets/app/filter_engine.js');
const R = require('../assets/app/report_engine.js');

const schema = [
  {id:'name_text',label:'Nombre',type:'text'},
  {id:'vendors',label:'Fabricantes',type:'list'},
  {id:'revenue',label:'Facturación',type:'number'},
  {id:'verified',label:'Verificado',type:'date'},
  {id:'managed',label:'Managed Services',type:'boolean'},
  {id:'confidence',label:'Confianza',type:'confidence'},
];
const evidence = {
  source:'Entidad oficial',title:'Página acreditativa',date:'2026-08-20',
  description:'La página identifica el dato.',url:'https://example.com/evidence',
  official:true,source_grade:'A',provenance_origin:'PUBLIC_PRIMARY'
};
const historical = {
  source:'Histórico',title:'Linaje',date:'2024-01-01',description:'Memoria',
  url:'https://old.example.com',provenance_origin:'HISTORICAL_RECOVERED',intelligence_tier:'H'
};
const rows = [
  {name:'Alpha',fields:{
    name_text:{value:'Banco Iberia',evidence:[evidence]},
    vendors:{value:['Check Point','Juniper'],evidence:[evidence]},
    revenue:{value:'1.250,5',evidence:[evidence]},
    verified:{value:'2026-08-20',evidence:[evidence]},
    managed:{value:true,evidence:[evidence]},confidence:{value:'high',evidence:[evidence]},
  }},
  {name:'Beta',fields:{
    name_text:{value:'Industria Norte',evidence:[historical]},vendors:{value:['Cisco'],evidence:[historical]},
    revenue:{value:410,evidence:[historical]},verified:{value:'2025-01-10',evidence:[historical]},
    managed:{value:false,evidence:[historical]},confidence:{value:'low',evidence:[historical]},
  }},
  {name:'Gamma',fields:{
    name_text:{value:'Banco Atlántico',evidence:[evidence]},vendors:{value:['Check Point'],evidence:[evidence]},
    revenue:{value:900,evidence:[evidence]},verified:{value:'2026-07-15',evidence:[evidence]},
    managed:{value:true,evidence:[evidence]},confidence:{value:'medium',evidence:[evidence]},
  }},
];
const accessor = (row,id) => row.fields[id]?.value;
const rule = (field,operator,value='',value2='') => ({field,operator,value,value2});

const andTree = {logic:'AND',groups:[{logic:'AND',rules:[
  rule('name_text','contains','banco'),rule('vendors','contains_all','Check Point'),
  rule('revenue','gte','900'),rule('managed','yes'),
]}]};
assert.deepStrictEqual(F.apply(rows,andTree,schema,accessor).map(x=>x.name),['Alpha','Gamma']);

const orTree = {logic:'OR',groups:[
  {logic:'AND',rules:[rule('confidence','low')]},
  {logic:'AND',rules:[rule('revenue','gt','1000')]},
]};
assert.deepStrictEqual(F.apply(rows,orTree,schema,accessor).map(x=>x.name),['Alpha','Beta']);

assert.strictEqual(F.matches(rule('name_text','starts_with','Banco'),rows[0],schema[0],accessor),true);
assert.strictEqual(F.matches(rule('name_text','not_contains','norte'),rows[0],schema[0],accessor),true);
assert.strictEqual(F.matches(rule('vendors','contains_any','Cisco, Juniper'),rows[0],schema[1],accessor),true);
assert.strictEqual(F.matches(rule('revenue','between','1000','1300'),rows[0],schema[2],accessor),true);
assert.strictEqual(F.matches(rule('verified','between','2026-08-01','2026-08-31'),rows[0],schema[3],accessor),true);
assert.strictEqual(F.matches(rule('verified','last_n_days','20'),rows[0],schema[3],accessor,new Date('2026-09-02')),true);
assert.strictEqual(F.matches(rule('managed','no'),rows[1],schema[4],accessor),true);
assert.strictEqual(F.matches(rule('confidence','medium'),rows[2],schema[5],accessor),true);

const restored = F.deserialize(F.serialize(andTree));
assert.deepStrictEqual(restored,andTree);
assert.strictEqual(F.apply(rows,restored,schema,accessor).length,2);

const report = R.build({rows,tree:andTree,schema,columns:['vendors','revenue'],accessor,title:'Informe exacto',generatedAt:'2026-09-02T00:00:00Z'});
assert.deepStrictEqual(report.rows.map(x=>x.name),['Alpha','Gamma']);
assert.strictEqual(report.entityCount,2);
assert.strictEqual(report.sources.length,1);
assert.strictEqual(report.sources[0].url,evidence.url);
assert.ok(!report.sources.some(source=>source.url===historical.url));

console.log('Filter builder and exact-subset report v4.1.0 PASS');
