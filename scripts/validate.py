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
    base=load('data/base.json'); vi=load('data/vendor_intelligence.json'); research=load('data/research.latest.json')
    engine=load('config/strategy_engine.json'); load('config/research_queries.json'); load('config/source_registry.json'); load('config/deep_research.json'); load('data/ecosystem.json')
    active=[x['name'] for x in base.get('vendors',[])]
    vint=[x['name'] for x in vi.get('vendors',[])]
    assert len(active)==len(set(active)), 'Fabricantes activos duplicados'
    assert set(active)==set(vint), f'Desalineación base/vendor_intelligence: {set(active)^set(vint)}'
    assert 'Juniper Networks' not in active, 'Juniper no debe contarse como vendor activo en el scope actual'
    assert any(x.get('name')=='Juniper Networks' for x in base.get('externalCompetitors',[])), 'Juniper debe seguirse como competidor'
    extreme=next(x for x in vi['vendors'] if x['name']=='Extreme Networks')
    assert any(x.get('name')=='TD SYNNEX' and x.get('country')=='ES' for x in extreme.get('channelCompetitors',[])), 'Falta TD SYNNEX España en presión de canal Extreme'
    for group,key_name in [(research.get('channelSignals',[]),'distributor'),(research.get('integratorSignals',[]),'name'),(research.get('customerSignals',[]),'name')]:
        for r in group:
            assert r.get('vendor') and r.get(key_name), f'Relación incompleta: {r}'
            if r.get('country'): assert r['country'] in {'ES','PT','IBERIA'}, f'País inválido: {r}'
            if 'confidence' in r: assert 0<=int(r.get('confidence',0))<=100, f'Confianza inválida: {r}'
    for e in research.get('evidence',[]):
        if int(e.get('confidence',0))>=80: assert e.get('url'), f'Evidencia fuerte sin URL: {e.get("title")}'
    for key in ['opportunityWeights','riskWeights']:
        total=sum(float(x) for x in engine.get(key,{}).values())
        assert 0.95<=total<=1.05, f'{key} suma {total:.3f}, debe aproximar 1'
    forbidden_key_fragments=['internalrevenue','internalmargin','pipeline','crmdata','employeeid','psmowner','vsmowner','solutionarchitectowner']
    for rel in ['data/base.json','data/vendor_intelligence.json','data/ecosystem.json','data/curated_evidence.json','data/research.latest.json']:
        obj=load(rel)
        for k in walk_keys(obj):
            nk=''.join(ch for ch in k.lower() if ch.isalnum())
            assert not any(f in nk for f in forbidden_key_fragments), f'Posible dato interno no permitido en {rel}: {k}'
    for wf in ['.github/workflows/research-daily.yml','.github/workflows/research-weekly.yml']:
        assert (ROOT/wf).exists(), f'Falta workflow: {wf}'
    print(f'OK · {len(active)} vendors activos · {len(research.get("evidence",[]))} evidencias · dataset público validado')

if __name__=='__main__':
    try: main()
    except AssertionError as e:
        print('ERROR:',e,file=sys.stderr); sys.exit(1)
