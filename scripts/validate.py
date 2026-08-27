#!/usr/bin/env python3
"""Preflight validation for the public-intelligence static dataset."""
from __future__ import annotations
import json, pathlib, sys

ROOT=pathlib.Path(__file__).resolve().parents[1]

def load(rel):
    p=ROOT/rel
    try: return json.loads(p.read_text(encoding='utf-8'))
    except Exception as e: raise AssertionError(f'{rel}: JSON inválido: {e}')

def walk_keys(obj,path=''):
    if isinstance(obj,dict):
        for k,v in obj.items():
            yield f'{path}.{k}' if path else k
            yield from walk_keys(v,f'{path}.{k}' if path else k)
    elif isinstance(obj,list):
        for i,v in enumerate(obj): yield from walk_keys(v,f'{path}[{i}]')

def main():
    base=load('data/base.json'); vi=load('data/vendor_intelligence.json'); research=load('data/research.latest.json'); reality=load('data/market_reality.json'); graph=load('data/intelligence_graph.json')
    engine=load('config/strategy_engine.json'); decision=load('config/decision_intelligence.json'); cap=load('config/capability_intelligence.json'); load('config/research_queries.json'); load('config/source_registry.json'); deep=load('config/deep_research.json'); universe=load('config/source_universe.json'); schedule=load('config/update_schedule.json'); proc_tax=load('config/procurement_taxonomy.json'); load('data/ecosystem.json')
    load('data/source_health.json'); load('data/discovered_entities.json'); load('data/research_errors.json'); load('data/run_manifest.latest.json'); load('data/supervisor.latest.json')
    active=[x['name'] for x in base.get('vendors',[])]
    vint=[x['name'] for x in vi.get('vendors',[])]
    assert len(active)==len(set(active)), 'Fabricantes activos duplicados'
    assert set(active)==set(vint), f'Desalineación base/vendor_intelligence: {set(active)^set(vint)}'
    facts=reality.get('facts',[]); plans=reality.get('vendors',{})
    assert len(facts)>=25, 'Capa de realidad pública insuficiente'
    sources=graph.get('sources',[]); claims=graph.get('claims',[]); source_ids={x.get('id') for x in sources}
    assert graph.get('policy',{}).get('actionThreshold')==100, 'El umbral de acción debe ser 100'
    assert len(sources)>=25 and len(claims)>=28, 'Grafo de inteligencia pública insuficiente'
    assert len(graph.get('distributors',[]))>=6 and len(graph.get('integrators',[]))>=8 and len(graph.get('architectures',[]))>=8, 'Faltan perfiles o arquitecturas'
    assert len(universe.get('analysts',[]))>=20 and len(universe.get('distributors',[]))>=25 and len(universe.get('integrators',[]))>=55, 'Universo de fuentes/actores v3 insuficiente'
    assert 'free' in deep.get('policy','').lower() and 'brave' not in deep.get('engines',{}), 'El motor debe ser gratuito y sin buscadores de pago'
    assert universe.get('discoveryPolicy',{}).get('dynamic') and 'gratuit' in universe.get('generatedPolicy','').lower(), 'La política de universo público/gratuito no está declarada'
    assert schedule.get('timezone') and set(schedule.get('profiles',{}))=={'daily','deep','exhaustive'}, 'Calendario automático incompleto'
    for kind in ['analysts','distributors','integrators']:
        names=[x.get('name') for x in universe.get(kind,[])]; assert len(names)==len(set(names)) and all(names), f'Entidades duplicadas o sin nombre: {kind}'
        assert all(x.get('domain') for x in universe.get(kind,[])), f'Dominios incompletos: {kind}'
    for c in claims:
        assert c.get('sourceIds') and set(c['sourceIds']).issubset(source_ids), f'Claim sin fuente válida: {c.get("id")}'
        assert c.get('scope') and c.get('summary') and 0<=int(c.get('confidence',0))<=100, f'Claim incompleto: {c.get("id")}'
    assert any(a.get('classification')=='CONFLICT' for a in graph.get('architectures',[])), 'No se modelan conflictos de plataforma'
    assert len(plans)>=10 and set(plans).issubset(set(active)), 'Planes verificables insuficientes o fabricante inválido'
    fact_ids=[x.get('id') for x in facts]; assert len(fact_ids)==len(set(fact_ids)) and all(fact_ids), 'IDs de realidad pública inválidos/duplicados'
    for e in facts:
        assert e.get('url') and e.get('source') and e.get('summary') and e.get('implication'), f'Realidad incompleta: {e.get("id")}'
        assert e.get('sourceTier') in {'official-company','regulator','analyst-public','public-open-data','industry-press'}, f'Tier inválido: {e.get("id")}'
        assert 0<=int(e.get('confidence',0))<=100, f'Confianza inválida: {e.get("id")}'
    for vendor,plan in plans.items():
        action=plan.get('action',{})
        assert plan.get('decision') in {'ACELERAR','CONSTRUIR','DEFENDER','OPTIMIZAR','INVESTIGAR'}, f'Decisión inválida: {vendor}'
        assert all(x in fact_ids for x in plan.get('evidenceIds',[])) and len(plan.get('evidenceIds',[]))>=2, f'Fuentes insuficientes: {vendor}'
        assert all(action.get(k) for k in ['owner','objective','day30','day60','day90','kpis','goNoGo','internalQuestions']), f'Contrato ejecutivo incompleto: {vendor}'
    assert 'Juniper Networks' not in active, 'Juniper no debe contarse como vendor activo en el scope actual'
    assert any(x.get('name')=='Juniper Networks' for x in base.get('externalCompetitors',[])), 'Juniper debe seguirse como competidor'
    extreme=next(x for x in vi['vendors'] if x['name']=='Extreme Networks')
    assert any(x.get('name')=='TD SYNNEX' and x.get('country')=='ES' for x in extreme.get('channelCompetitors',[])), 'Falta TD SYNNEX España en presión de canal Extreme'
    for r in research.get('channelHistorySignals',[]):
        assert r.get('vendor') and r.get('distributor'), f'Histórico de canal incompleto: {r}'
        if r.get('country'): assert r['country'] in {'ES','PT','IBERIA'}, f'País histórico inválido: {r}'
        assert r.get('active') is False or r.get('status') in {'ended-public-signal','historical'}, f'Histórico de canal no marcado como terminado: {r}'
    for group,key_name in [(research.get('channelSignals',[]),'distributor'),(research.get('integratorSignals',[]),'name'),(research.get('customerSignals',[]),'name')]:
        for r in group:
            assert r.get('vendor') and r.get(key_name), f'Relación incompleta: {r}'
            if r.get('country'): assert r['country'] in {'ES','PT','IBERIA'}, f'País inválido: {r}'
            if 'confidence' in r: assert 0<=int(r.get('confidence',0))<=100, f'Confianza inválida: {r}'
    for e in research.get('evidence',[]):
        if int(e.get('confidence',0))>=80: assert e.get('url'), f'Evidencia fuerte sin URL: {e.get("title")}'
    for row in research.get('procurementMarket',[]):
        assert row.get('country') in {'ES','PT'}, f'Procurement market país inválido: {row}'
        assert row.get('technologyId'), f'Procurement market sin tecnología: {row}'
        assert 0<=int(row.get('demandIndex',0))<=100, f'Demand index inválido: {row}'
        assert float(row.get('knownValueEUR',0) or 0)>=0, f'Valor contratación inválido: {row}'
    bucket_ids=[x.get('id') for x in proc_tax.get('technologyBuckets',[])]
    assert len(bucket_ids)==len(set(bucket_ids)) and bucket_ids, 'Taxonomía contratación inválida/duplicada'
    for e in research.get('evidence',[]):
        if e.get('evidenceType')=='procurement':
            assert e.get('country') in {'ES','PT'} or 'Spain' in str(e.get('scope')) or 'Portugal' in str(e.get('scope')), f'Procurement sin geografía: {e.get("title")}'
            assert all((t.get('id') if isinstance(t,dict) else t) in bucket_ids for t in (e.get('technologyMatches') or [])), f'Tecnología contratación no reconocida: {e.get("technologyMatches")}'
    for key in ['opportunityWeights','riskWeights','attackOpportunityWeights']:
        total=sum(float(x) for x in engine.get(key,{}).values())
        assert 0.95<=total<=1.05, f'{key} suma {total:.3f}, debe aproximar 1'
    qmix=deep.get('query_mix',{})
    assert qmix and 0.95<=sum(float(x) for x in qmix.values())<=1.05, 'query_mix debe sumar aproximadamente 1'
    resilience=deep.get('resilience',{}); learning=deep.get('adaptive_learning',{})
    assert int(resilience.get('batch_size',0))>0 and int(resilience.get('circuit_breaker_failures',0))>0, 'Resiliencia de búsqueda incompleta'
    assert learning.get('enabled') and float(learning.get('minimum_exploration_share',0))>=.1, 'Aprendizaje adaptativo sin exploración suficiente'
    sens=engine.get('sensitivityModel',{})
    assert int(sens.get('runs',0))>=16 and 0<float(sens.get('maxPerturbation',0))<=20, 'Modelo de estabilidad de decisión inválido'
    roles=decision.get('roles',[]); actions=decision.get('actions',[]); archetypes=decision.get('archetypes',[])
    role_ids=[r.get('id') for r in roles]; action_ids=[a.get('id') for a in actions]; archetype_ids=[a.get('id') for a in archetypes]
    assert len(roles)>=10 and len(role_ids)==len(set(role_ids)) and all(role_ids), 'Roles Decision Intelligence inválidos/duplicados'
    assert len(actions)>=40 and len(action_ids)==len(set(action_ids)) and all(action_ids), 'Catálogo de acciones insuficiente o duplicado'
    assert len(archetypes)>=8 and len(archetype_ids)==len(set(archetype_ids)), 'Arquetipos estratégicos inválidos'
    assert all(set(a.get('roles',[])).issubset(set(role_ids)) and a.get('roles') for a in actions), 'Acción con rol inexistente o sin rol'
    assert all(a.get('name') and a.get('category') and a.get('factors') for a in actions), 'Acción Decision Intelligence incompleta'
    assert any(a.get('id')=='flex' for a in actions) and any(a.get('id')=='3d-lab' for a in actions), 'Faltan palancas Westcon básicas'
    assert any(a.get('category') in {'Logística','Supply Chain'} for a in actions) and any(a.get('category')=='Marketing' for a in actions) and any(a.get('category')=='Preventa' for a in actions), 'Cobertura funcional insuficiente'
    # Capability Intelligence: mandatory compatibility layer.
    progs=cap.get('programmes',[]); prog_ids=[x.get('id') for x in progs]
    assert len(progs)>=15 and len(prog_ids)==len(set(prog_ids)), 'Catálogo de capacidades Westcon insuficiente/duplicado'
    assert set(active).issubset(set(cap.get('vendorApplicability',{}))), 'Faltan fabricantes en vendorApplicability'
    ti=cap.get('vendorApplicability',{})
    assert ti['UiPath'].get('3d-lab') is None, 'UiPath no debe quedar habilitado para 3D Lab sin evidencia'
    for vn in ['AttackIQ','Check Point','CrowdStrike','F5','Fortanix','Palo Alto Networks','Proofpoint','Vectra AI','Zscaler']:
        assert ti.get(vn,{}).get('tech-insights',{}).get('status') in {'VERIFIED_SOURCE','VERIFIED_PUBLIC','USER_CONFIRMED'}, f'Tech Insights no verificado para {vn}'
    for vn in ['AttackIQ','Check Point','Cisco','Claroty','CrowdStrike','EfficientIP','F5','Ivanti','Extreme Networks','NETSCOUT','Okta','Palo Alto Networks','Proofpoint','Vectra AI','Zscaler']:
        assert ti.get(vn,{}).get('3d-lab',{}).get('status') in {'VERIFIED_SOURCE','VERIFIED_PUBLIC'}, f'3D Lab no verificado para {vn}'
    for vn in ['Palo Alto Networks','F5','CrowdStrike','Zscaler','Extreme Networks']:
        assert ti.get(vn,{}).get('local-presales',{}).get('status')=='USER_CONFIRMED', f'Preventa local no reflejada para {vn}'
    assert any(x.get('id')=='extreme-juniper-displacement' for x in cap.get('specialOpportunities',[])), 'Falta oportunidad de displacement Juniper→Extreme'
    assert all((not a.get('capabilityId')) or a.get('capabilityId') in prog_ids for a in actions), 'Acción mapeada a capacidad inexistente'
    modules=decision.get('exportModules',[]); module_ids=[m.get('id') for m in modules]
    assert len(modules)>=8 and len(module_ids)==len(set(module_ids)), 'Módulos de exportación inválidos'
    forbidden_key_fragments=['internalrevenue','internalmargin','pipeline','crmdata','employeeid','psmowner','vsmowner','solutionarchitectowner']
    for rel in ['data/base.json','data/vendor_intelligence.json','data/ecosystem.json','data/curated_evidence.json','data/research.latest.json']:
        obj=load(rel)
        for k in walk_keys(obj):
            nk=''.join(ch for ch in k.lower() if ch.isalnum())
            assert not any(f in nk for f in forbidden_key_fragments), f'Posible dato interno no permitido en {rel}: {k}'
    for wf in ['.github/workflows/research-daily.yml','.github/workflows/research-weekly.yml','.github/workflows/research-monthly.yml']:
        assert (ROOT/wf).exists(), f'Falta workflow: {wf}'
        text=(ROOT/wf).read_text(encoding='utf-8')
        assert 'research_supervisor.py' in text and 'upload-artifact@v4' in text, f'Workflow sin supervisor/diagnóstico: {wf}'
        assert 'schedule_guard.py' in text and 'BEGIN CONFIGURABLE_SCHEDULE' in text, f'Workflow sin calendario configurable: {wf}'
        assert 'BRAVE_SEARCH_API_KEY' not in text and 'BASE_API_TOKEN' not in text, f'Workflow depende de una clave o suscripción: {wf}'
        assert 'run: python scripts/research.py' not in text and 'research.py --profile=' not in text, f'Workflow conserva el reintento monolítico defectuoso: {wf}'
    collector=(ROOT/'scripts/research.py').read_text(encoding='utf-8')
    assert 'BRAVE_SEARCH_API_KEY' not in collector and 'BASE_API_TOKEN' not in collector, 'El colector conserva dependencias de pago o tokenizadas'
    for script in ['research_supervisor.py','configure_updates.py','schedule_guard.py','test_schedule.py']:
        assert (ROOT/'scripts'/script).exists(), f'Falta script operativo: {script}'
    print(f'OK · {len(active)} vendors · {len(claims)} claims nuevos · {len(graph.get("distributors",[]))} perfiles mayoristas consolidados · {len(graph.get("integrators",[]))} perfiles integradores consolidados · {len(graph.get("architectures",[]))} arquitecturas · motor v11 validado')

if __name__=='__main__':
    try: main()
    except AssertionError as e:
        print('ERROR:',e,file=sys.stderr); sys.exit(1)
