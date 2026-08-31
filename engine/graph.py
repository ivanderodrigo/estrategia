from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
import json,re
from .model import canonical,stable_id,values
from .entity_resolution import resolve
ROOT=Path(__file__).resolve().parents[1]

def _evidence(field):
    out=list(field.get('evidence') or [])
    for item in field.get('items') or []: out.extend(item.get('evidence') or [])
    seen={}
    for e in out:
        key=(e.get('url'),e.get('title'),e.get('scope'));seen[key]=e
    return list(seen.values())

def _target(name):
    s=str(name or '').strip()
    return re.split(r'\s+·\s+(?:Confirmada|Probable|Señal|Evidencia|ES|PT|IBERIA)',s,1,flags=re.I)[0].strip()

def _scopes(country):
    s=str(country or 'GLOBAL').upper().replace('+','/').replace(',','/')
    out=[]
    for part in re.split(r'[/; ]+',s):
        if part in {'ES','PT','IBERIA','GLOBAL'} and part not in out:out.append(part)
    return out or ['GLOBAL']

def build_graph(data):
    entities={};rels={}
    def ent(kind,name,country=''):
        name=resolve(_target(name));key=(kind,canonical(name))
        if key not in entities:entities[key]={'id':stable_id(kind,name),'canonical_name':name,'entity_type':kind,'country':country,'aliases':[],'historical_names':[]}
        return entities[key]
    def add(ak,a,rel,bk,b,country,evidence,status='CONFIRMADO',confidence=.84,derived=False,validity='current'):
        a=resolve(_target(a));b=resolve(_target(b))
        if not a or not b or canonical(a)==canonical(b):return
        ae=ent(ak,a,country);be=ent(bk,b,country);key=(ae['id'],rel,be['id'])
        clean=[e for e in (evidence or []) if e.get('url') and e.get('source')]
        if not clean:return
        if status=='CONFIRMED':status='CONFIRMADO'
        scopes=_scopes(country)
        if key not in rels:
            rels[key]={'id':'rel_'+stable_id('r','|'.join(key))[5:],'entity_a_id':ae['id'],'entity_a':a,'relation':rel,'entity_b_id':be['id'],'entity_b':b,'countries':scopes,'country':' + '.join(scopes),'evidence':clean,'source':clean[0].get('source'),'date':max([str(e.get('date') or '') for e in clean]),'confidence':confidence,'status':status,'validity':validity or 'current','derived':derived}
        else:
            item=rels[key]
            item['countries']=list(dict.fromkeys(item.get('countries',[])+scopes));item['country']=' + '.join(item['countries'])
            have={(e.get('url'),e.get('title'),e.get('scope')) for e in item['evidence']}
            item['evidence'] += [e for e in clean if (e.get('url'),e.get('title'),e.get('scope')) not in have]
            item['confidence']=max(float(item.get('confidence') or 0),float(confidence or 0))
            if status=='CONFIRMADO':item['status']='CONFIRMADO'
            item['derived']=bool(item.get('derived')) and bool(derived)
    seed_path=ROOT/'config/current/migrated_relationships.json'
    if seed_path.exists():
        for r in json.loads(seed_path.read_text(encoding='utf-8')).get('relationships',[]):
            rel=r.get('relation');kinds={'distributes':('distributor','manufacturer'),'partners_with':('integrator','manufacturer'),'technology_signal':('client','technology')}.get(rel)
            if kinds:add(kinds[0],r.get('entity_a'),rel,kinds[1],r.get('entity_b'),r.get('country'),r.get('evidence'),r.get('status','CONFIRMADO'),r.get('confidence',.84),r.get('derived',False),r.get('validity','current'))
    for section,kind in [('distributors','distributor'),('integrators','integrator')]:
        for row in data.get(section,[]):
            f=(row.get('fields') or {}).get('vendor_relations') or {};e=_evidence(f);scope=str(((row.get('fields') or {}).get('scope') or {}).get('value') or 'IBERIA')
            for raw in values(f.get('value')):
                name=_target(raw)
                if not name or any(x in canonical(name) for x in ['mas de','catalogo','fabricantes visibles','ver catalogo','marcas nacionales','hardware y software de marcas']):continue
                add(kind,row['name'],'distributes' if kind=='distributor' else 'partners_with','manufacturer',name,scope,e,'CONFIRMADO',.88)
    for section in ['clients_public','clients_private']:
        for row in data.get(section,[]):
            f=(row.get('fields') or {}).get('technology_signals') or {};e=_evidence(f);scope=str(((row.get('fields') or {}).get('scope') or {}).get('value') or 'IBERIA')
            for tech in values(f.get('value')):add('client',row['name'],'technology_signal','technology',str(tech),scope,e,'SEÑAL',.48,True)
    return {'version':'3.19.0','generated_at':datetime.now(timezone.utc).isoformat(),'entities':sorted(entities.values(),key=lambda x:(x['entity_type'],x['canonical_name'])),'relationships':list(rels.values()),'model':{'truth_source':'canonical relation graph','bidirectional_projection':True,'canonical_entity_ids':True,'single_edge_multi_scope':True,'weak_signals_do_not_promote':True,'v318_migrated_once':True}}
