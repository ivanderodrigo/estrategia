'use strict';
const assert=require('assert');
const bi=require('../assets/app/business-intelligence.js');
const ev={url:'https://ted.europa.eu/en/notice/-/detail/1234',source:'TED',date:'2026-11-12',accrediting:true,provenance_origin:'PUBLIC_PRIMARY'};
const field=(value,proof=true)=>({value,evidence:proof?[ev]:[]});
const notice=(title,proof=true)=>({id:'n-1234',name:'Organismo Público',fields:{request_or_need:field(title,proof),notice_id:field('1234',proof)}});
assert.strictEqual(bi.classifyNeed('Renovación de infraestructura LAN y switches').fit,true);
assert.strictEqual(bi.classifyNeed('Ciberseguridad y soluciones SASE cloud').fit,true);
assert.strictEqual(bi.classifyNeed('Compra de impresoras Wi-Fi y tóner').fit,false);
assert.strictEqual(bi.classifyNeed('Redes de abastecimiento de agua').fit,false);
assert.strictEqual(bi.classifyNeed('Seguridad física y control de edificios').fit,false);
assert.strictEqual(bi.classifyNeed('Servicios genéricos de informática').fit,false);
assert.strictEqual(bi.classifyNotice(notice('Servicio gestionado de cloud y Zero Trust')).fit,true);
assert.strictEqual(bi.classifyNotice(notice('Servicio gestionado de cloud y Zero Trust',false)).fit,false);
assert.strictEqual(bi.classifyNotice(notice('Suministro de portátiles y equipos de escritorio')).fit,false);
assert.strictEqual(bi.classifyNotice(notice('Renovación Wi-Fi 802.11 para edificios')).official,ev.url);
const news=bi.uniqueNews([{name:'Proveedor A',fields:{recent_signals:{value:['Lanzamiento producto'],items:[{value:'Lanzamiento producto',evidence:[{...ev,url:'https://example.org/news/lanzamiento-producto-a',title:'Lanzamiento del nuevo producto A'}]}]}}}]);
assert.strictEqual(news.length,1);
assert.strictEqual(news[0].vendor,'Proveedor A');
const fake=bi.uniqueNews([{name:'Proveedor B',fields:{recent_signals:field(['Rumor'],false)}}]);
assert.strictEqual(fake.length,0);
// A generic technology procurement must not be promoted just because its
// separately extracted technology signals contain a portfolio term.
const generic=notice('Servicio de mantenimiento de sistemas informáticos');
generic.fields.technology_signals=field('firewall y cloud');
assert.strictEqual(bi.classifyNotice(generic).fit,false);
const specific=notice('Renovación de infraestructura de red corporativa');
specific.fields.technology_signals=field('switches y SD-WAN');
assert.strictEqual(bi.classifyNotice(specific).fit,true);
const noPublicationDate=bi.uniqueNews([{name:'Proveedor C',fields:{recent_signals:{value:['Actualización'],items:[{value:'Actualización',evidence:[{...ev,date:undefined,retrieved_at:'2026-11-12',url:'https://example.org/announcements/actualizacion-plataforma-2026',title:'Actualización de la plataforma'}]}]}}}]);
assert.strictEqual(noPublicationDate[0].date,0,'Crawl date must never become news publication date');

const integratorFeed=bi.uniqueNews([{name:'Partner Ejemplo',fields:{public_cases:{value:['Despliegue de red segura'],items:[{value:'Despliegue de red segura',evidence:[{...ev,title:'Partner Ejemplo moderniza la red de un hospital',url:'https://example.org/case-studies/hospital-seguro'}]}]}}}],'integrators');
assert.strictEqual(integratorFeed.length,1,'Integrator case article must be discoverable as news');
assert.strictEqual(integratorFeed[0].vendor,'Partner Ejemplo');
const clientFeed=bi.uniqueNews([{name:'Empresa Ejemplo',fields:{investment_signals:{value:['Inversion en cloud para reducir riesgo'],items:[{value:'Inversion en cloud para reducir riesgo',evidence:[{...ev,title:'Empresa Ejemplo invierte en ciberseguridad cloud',url:'https://example.org/noticias/inversion-cloud-segura'}]}]}}}],'clients');
assert.strictEqual(clientFeed.length,1,'Client technology investment article must be discoverable');
const nonArticle=bi.uniqueNews([{name:'Empresa Ejemplo',fields:{recent_signals:{value:['Novedades'],items:[{value:'Novedades',evidence:[{...ev,title:'Portal de noticias',url:'https://example.org/noticias'}]}]}}}],'clients');
assert.strictEqual(nonArticle.length,0,'News section index is not a publication');

const verifiedList=value=>({value:[value],items:[{value,evidence:[ev]}],evidence:[ev]});
const unverifiableList=value=>({value:[value],items:[{value,evidence:[]}],evidence:[]});
const verifiedManufacturers=[{
 name:'Extreme Networks',
 fields:{
   westcon_spain:field(true),
   distributors:verifiedList('Distribuidor Verificado'),
   competitors:verifiedList('Cisco'),
 }
}];
const direct={name:'Distribuidor Verificado',fields:{vendor_relations:unverifiableList('Cisco')}};
assert.strictEqual(bi.distributorContext(direct,verifiedManufacturers).relevant,true,
 'Evidence-backed reciprocal manufacturer directory keeps the distributor visible');
const rival={name:'Mayorista Rival',fields:{vendor_relations:verifiedList('Cisco')}};
assert.strictEqual(bi.distributorContext(rival,verifiedManufacturers).relevant,true,
 'A supported vendor relationship to a supported Westcon competitor is competitive context');
const unsupported={name:'Mayorista Sin Contexto',fields:{vendor_relations:unverifiableList('Cisco')}};
assert.strictEqual(bi.distributorContext(unsupported,verifiedManufacturers).relevant,false,
 'Unverified co-mentions must not promote irrelevant entities into business intelligence');
const unrelated={name:'Mayorista Al Azar',fields:{vendor_relations:verifiedList('Impresoras Genéricas')}};
assert.strictEqual(bi.distributorContext(unrelated,verifiedManufacturers).relevant,false,
 'Even a verified vendor is irrelevant if no business relationship to Westcon is established');
const distributorNews=bi.uniqueNews([{name:'Mayorista Rival',fields:{
 recent_signals:{value:['Mayorista Rival anuncia nuevas soluciones cloud'],
 items:[{value:'Mayorista Rival anuncia nuevas soluciones cloud',
 evidence:[{...ev,url:'https://example.org/noticias/nueva-distribucion-cloud-2026',
 title:'Mayorista Rival anuncia nuevas soluciones cloud'}]}]}
}}],'distributors');
assert.strictEqual(distributorNews.length,1,'Official distributor news should be visible as a publication card');
const detailedRelation=(value,support=true)=>({value:[value],items:[{value,evidence:support?[ev]:[]}]});
const integratorOfficial={name:'Integrador del Canal',fields:{vendor_relations:detailedRelation('Cisco')}};
const westconOfficial={name:'Extreme Networks',fields:{westcon_spain:field(true),competitors:detailedRelation('Cisco')}};
const competition=bi.verifiedCompetitionFor(integratorOfficial,[westconOfficial]);
assert.deepStrictEqual(competition.value,['Cisco'],'Both source-backed relationships must map exact competitor');
assert.strictEqual(competition.items[0].competes_with_westcon[0],'Extreme Networks');
// A current Westcon peer is NOT an external competitor in the partner lens.
const bothWestcon=[
 {name:'Extreme Networks',fields:{westcon_spain:field(true),competitors:detailedRelation('Cisco')}},
 {name:'Cisco',fields:{westcon_spain:field(true),competitors:detailedRelation('Extreme Networks')}}
];
const westconPeerIntegrator={name:'Integrator peer',fields:{vendor_relations:detailedRelation('Cisco')}};
assert.deepStrictEqual(bi.verifiedCompetitionFor(westconPeerIntegrator,bothWestcon).value,[],
 'Active Westcon manufacturer must not be counted as external rival even if an active peer competes with it');
const westconPeerDistributor={name:'Distributor peer',fields:{
 vendor_relations:detailedRelation('Cisco'),
 competitor_vendor_overlap:detailedRelation('Cisco')
}};
const peerContext=bi.distributorContext(westconPeerDistributor,bothWestcon);
assert.ok(!peerContext.reasons.some(reason=>/competidor/i.test(reason)),
 'Distributor competitive context must not label a current Westcon manufacturer as external');
assert.strictEqual(peerContext.relevant,true,'Proven existing portfolio relationship remains visible');
const mixed={name:'Distributor with two brands',fields:{vendor_relations:{
 value:['Cisco','Arista Networks'],
 items:[{value:'Cisco',evidence:[ev]},{value:'Arista Networks',evidence:[ev]}],
 evidence:[ev]
}}};
const mixedManufacturers=[
 ...bothWestcon.slice(0,1),
 bothWestcon[1]
];
mixedManufacturers[0].fields.competitors={
 value:['Cisco','Arista Networks'],
 items:[{value:'Cisco',evidence:[ev]},{value:'Arista Networks',evidence:[ev]}],
 evidence:[ev]
};
assert.deepStrictEqual(bi.verifiedCompetitionFor(mixed,mixedManufacturers).value,['Arista Networks'],
 'External proven competitor survives; active Westcon peer is excluded');
const retired={name:'Ruckus Networks',fields:{westcon_spain:field(false),competitors:detailedRelation('Cisco')}};
assert.deepStrictEqual(bi.verifiedCompetitionFor(integratorOfficial,[retired]).value,[],
 'A retired manufacturer must never produce a Westcon competitor mapping');
assert.strictEqual(bi.distributorContext(rival,[retired]).relevant,false,
 'Retired manufacturers must not make a distributor a Westcon rival');
assert.strictEqual(bi.verifiedCompetitionFor(integratorOfficial,[
  {name:'Extreme Networks',fields:{westcon_spain:field(true),competitors:detailedRelation('Cisco',false)}}
]).value.length,0,'Unsourced competitor mapping is not proof');
const trending=bi.uniqueNews([{name:'SASE adoption',fields:{sources:detailedRelation('SASE report'),}}],'trends');
assert.ok(Array.isArray(trending));
assert.strictEqual(bi.isPublicationUrl('https://news.example.org/2026/11/sase-adoption-report-2026'),true);
assert.strictEqual(bi.isPublicationUrl('https://news.example.org/noticias'),false);
assert.strictEqual(bi.isPublicationUrl('https://news.example.org/research/sase-market-2026'),true);

assert.strictEqual(bi.technicalNews({title:'Premios de medio ambiente convocados por la ciudad',summary:'La entidad también utiliza cloud y cybersecurity'}),false,'Parent technology signal must not turn an unrelated article into tech news');
assert.strictEqual(bi.technicalNews({title:'La entidad invierte en servicios de ciberseguridad y Zero Trust',summary:''}),true);
console.log('Business Intelligence v6.4: relevant procurement and accredited news OK');
