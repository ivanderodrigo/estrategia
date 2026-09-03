#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from engine.model import canonical
from engine.storage import read_json
from engine.knowledge_provenance import provenance_kind, typed_evidence_sufficient
from engine.westcon_current_evidence import _norm_capability

ROOT=Path(__file__).resolve().parents[1]
CURRENT={"WESTCON_DOCUMENT_CURRENT","WESTCON_FIRST_PARTY_CURRENT"}
BLOCKED={"WESTCON_DOCUMENT","RESEARCH_SEED","HISTORICAL_RECOVERED","ARCHIVE_RECOVERED","ARCHIVE_CORROBORATION","REPORT_CORROBORATION","LEGACY_UNRESOLVED"}


def load(rel: str) -> Any:
    return json.loads((ROOT/rel).read_text(encoding='utf-8'))


def evidence_rows(target: Mapping[str,Any]) -> list[Mapping[str,Any]]:
    return [ev for ev in (target.get('evidence') or []) if isinstance(ev,Mapping)]


def has_current(target: Mapping[str,Any], *, field: str|None=None, value: Any=None) -> bool:
    for ev in evidence_rows(target):
        if provenance_kind(ev) not in CURRENT or not typed_evidence_sufficient(ev):
            continue
        if field is not None and str(ev.get('field') or '') != field:
            continue
        if value is not None and canonical(ev.get('item_value')) != canonical(value):
            continue
        return True
    return False


def main() -> int:
    errors=[]
    data=read_json('data/current/intelligence.json',{})
    cfg=load('config/current/westcon_fy27_document_facts.json')
    rows=[r for r in data.get('manufacturers') or [] if isinstance(r,dict)]
    index={canonical(r.get('name')):r for r in rows}
    aliases={}
    for name,fact in (cfg.get('portfolio_spain') or {}).items():
        for alias in [name]+list((fact or {}).get('aliases') or []):
            aliases[canonical(alias)]=canonical(name)

    es_ok=pt_ok=0
    current_cap_items=0
    missing_caps=[]
    for name,fact in (cfg.get('portfolio_spain') or {}).items():
        wanted=[canonical(name)]+[canonical(x) for x in ((fact or {}).get('aliases') or [])]
        row=next((index.get(k) for k in wanted if index.get(k)),None)
        if not row:
            errors.append(f'missing Spain portfolio manufacturer: {name}')
            continue
        fields=row.get('fields') or {}
        es=fields.get('westcon_spain') or {}
        pt=fields.get('westcon_portugal') or {}
        if es.get('value') is True and has_current(es,field='westcon_spain',value=True): es_ok+=1
        else: errors.append(f'{name}: westcon_spain not current-first-party accredited')
        if pt.get('value') is True and has_current(pt,field='westcon_portugal',value=True): pt_ok+=1
        else: errors.append(f'{name}: westcon_portugal not current-first-party accredited')
        cap=fields.get('capabilities') or {}
        items=[x for x in cap.get('items') or [] if isinstance(x,dict)]
        item_idx={_norm_capability(x.get('value')):x for x in items}
        for documented in (fact or {}).get('capabilities') or []:
            # tolerate slash-order variants already present in the dataset by checking evidence item_value too
            match=item_idx.get(_norm_capability(documented))
            if match is None:
                match=next((x for x in items if any(
                    provenance_kind(ev)=='WESTCON_DOCUMENT_CURRENT' and _norm_capability(ev.get('item_value'))==_norm_capability(documented)
                    for ev in evidence_rows(x)
                )),None)
            if match is None or not has_current(match,field='capabilities'):
                missing_caps.append(f'{name}: {documented}')
            else:
                current_cap_items+=1

    cp=index.get(canonical('Check Point'))
    if not cp:
        errors.append('Check Point row missing')
    else:
        f=cp.get('fields') or {}
        if (f.get('westcon_spain') or {}).get('value') is not False:
            errors.append('Check Point must not be in Spain portfolio')
        if (f.get('westcon_portugal') or {}).get('value') is not True or not has_current(f.get('westcon_portugal') or {},field='westcon_portugal',value=True):
            errors.append('Check Point must be current-first-party accredited in Portugal')

    if missing_caps:
        errors.extend('missing current FY27 capability support: '+x for x in missing_caps[:30])

    # Important negative control from the user's screenshot: ADC is not explicit in the supplied deck.
    f5=next((r for r in rows if canonical(r.get('name'))==canonical('F5')),None)
    adc_current=0
    if f5:
        for item in ((f5.get('fields') or {}).get('capabilities') or {}).get('items') or []:
            if isinstance(item,dict) and canonical(item.get('value'))=='adc':
                adc_current += sum(provenance_kind(ev) in CURRENT for ev in evidence_rows(item))
    if adc_current:
        errors.append('ADC was incorrectly accredited by the FY27 deck')

    raw=json.dumps(data,ensure_ascii=False)
    if 'Portugal incorpora además Proofpoint y Check Point' in raw or 'Portugal incorpora ademas Proofpoint y Check Point' in raw:
        errors.append('superseded Portugal rule still present')

    manifest=load('data/public/manifest.json')
    visible_current=0
    visible_blocked=0
    for info in (manifest.get('sections') or {}).values():
        if not isinstance(info,Mapping): continue
        payload=load(str(info.get('file')))
        for ev in (payload.get('evidence') or {}).values():
            if not isinstance(ev,Mapping): continue
            kind=provenance_kind(ev)
            visible_current += int(kind in CURRENT)
            visible_blocked += int(kind in BLOCKED)
    if visible_current == 0:
        errors.append('no current Westcon first-party evidence visible in public projection')
    if visible_blocked:
        errors.append(f'{visible_blocked} historical/internal seed rows leaked into public accreditation')

    css=(ROOT/'assets/app/intelligence.css').read_text(encoding='utf-8')
    js=(ROOT/'assets/app/intelligence.js').read_text(encoding='utf-8')
    index_html=(ROOT/'index.html').read_text(encoding='utf-8')
    for marker in ('v4.2.2 · ergonomic atomic tags','grid-template-columns:minmax(0,1fr)','min-width:230px!important'):
        if marker not in css: errors.append(f'UI ergonomic marker missing: {marker}')
    if '4.2.2' not in index_html or '4.2.2' not in js:
        errors.append('frontend version is not 4.2.2')

    gaps=load('data/current/research_gaps.json')
    summary={
        'spain_portfolio_current':es_ok,
        'portugal_base_current':pt_ok,
        'portugal_additional_check_point': bool(cp and (cp.get('fields') or {}).get('westcon_portugal',{}).get('value') is True),
        'fy27_capability_items_current':current_cap_items,
        'current_westcon_visible_evidence':visible_current,
        'blocked_historical_visible':visible_blocked,
        'gaps_total':len(gaps.get('gaps') or []),
        'public_validation_gaps':int(gaps.get('public_validation_gaps') or 0),
        'unknown_research_gaps':int(gaps.get('unknown_research_gaps') or 0),
    }
    print('v4.2.2 current-document + tag-ergonomics audit: '+('FAIL' if errors else 'PASS'))
    for k,v in summary.items(): print(f' - {k}: {v}')
    print(f' - negative control ADC accredited by deck: {adc_current}')
    if errors:
        for e in errors: print(' - ERROR:',e)
        return 1
    return 0

if __name__=='__main__':
    raise SystemExit(main())
