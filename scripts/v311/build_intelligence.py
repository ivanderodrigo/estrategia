#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

from v38.build_intelligence import dedupe_evidence, load, write
from v39.build_intelligence import build as build_v39, merge_source_catalog as merge_source_catalog_v39


def norm(value: Any) -> str:
    text = str(value or '').casefold()
    text = re.sub(r'[^a-z0-9áéíóúüñçãõâêôàèìòùäëïöü]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def canonical(value: Any) -> str:
    text = norm(value)
    aliases = {
        'akamai noname': 'akamai noname',
        'akamai noname security': 'akamai noname',
        'microsoft azure': 'microsoft azure',
        'amazon web services': 'aws',
        'amazon aws': 'aws',
        'aws': 'aws',
    }
    return aliases.get(text, text)


def merge_source_catalog() -> list[dict[str, Any]]:
    # v3.11 deliberately returns to the public-source universe. Manual/document
    # ingestion sources introduced in v3.10 are not active in this release.
    excluded = {'manual_intelligence_contributions', 'repository_document_intelligence'}
    return [row for row in merge_source_catalog_v39() if row.get('id') not in excluded]



def has_direct_sales_signal(row: dict[str, Any]) -> bool:
    phrases = (
        'venta directa', 'ventas directas', 'vende directamente', 'venta al cliente final',
        'direct sales', 'sells direct', 'sell direct', 'direct to customer', 'direct-to-customer',
        'direct channel', 'buy direct', 'purchase direct', 'direct procurement',
    )
    parts=[]
    for ev in row.get('evidence') or []:
        parts.extend(str(ev.get(k) or '') for k in ('source','title','description','note','type','method','url'))
    for field in (row.get('fields') or {}).values():
        parts.append(str(field.get('value') or ''))
        for ev in field.get('evidence') or []:
            parts.extend(str(ev.get(k) or '') for k in ('source','title','description','note','type','method','url'))
    blob=norm(' '.join(parts))
    return any(norm(phrase) in blob for phrase in phrases)

def clean_distributors_and_mark_direct_sales(data: dict[str, Any]) -> dict[str, int]:
    manufacturers = data.get('manufacturers') or []
    distributors = data.get('distributors') or []
    by_key = {canonical(row.get('name')): row for row in manufacturers if row.get('name')}
    kept: list[dict[str, Any]] = []
    direct_sales = 0
    removed_manufacturers = 0

    for row in distributors:
        key = canonical(row.get('name'))
        manufacturer = by_key.get(key)
        if manufacturer:
            removed_manufacturers += 1
            if has_direct_sales_signal(row):
                manufacturer['direct_sales'] = True
                manufacturer['direct_sales_label'] = 'Venta directa detectada'
                manufacturer['direct_sales_evidence'] = dedupe_evidence(row.get('evidence') or [], 8)
                direct_sales += 1
            continue
        # Westcon/Comstor are internal units, never competitor distributors.
        if key in {'westcon', 'westcon comstor', 'comstor'} or key.startswith('westcon comstor '):
            continue
        kept.append(row)

    # Keep canonical manufacturer names stable; the frontend adds a visible badge
    # next to the name instead of mutating the identity field.
    for row in manufacturers:
        row.setdefault('direct_sales', False)

    data['distributors'] = kept
    return {
        'removed_manufacturer_rows': removed_manufacturers,
        'direct_sales_manufacturers': direct_sales,
        'competitor_distributors': len(kept),
    }


def build() -> dict[str, Any]:
    data = copy.deepcopy(build_v39())
    data['meta']['version'] = '3.11.0'
    data['meta']['generated_at'] = datetime.now(timezone.utc).isoformat()
    data['meta']['principle'] = 'Inteligencia descriptiva y trazable para fabricantes, mayoristas competidores, integradores, clientes, tendencias y arquitecturas.'
    data['meta']['traceability'] = 'Cada dato visible conserva su evidencia pública. Los fabricantes se excluyen de Mayoristas; cuando existe una señal de venta directa se identifica junto al nombre del fabricante.'
    data['source_catalog'] = merge_source_catalog()
    data['meta']['source_count'] = len(data['source_catalog'])
    data['meta']['distribution_cleanup'] = clean_distributors_and_mark_direct_sales(data)
    return data


if __name__ == '__main__':
    data = build()
    write('data/v311/intelligence.json', data)
    legacy_gaps = load('data/v39/research_gaps.json', {}) or load('data/v38/research_gaps.json', {}) or {}
    write('data/v311/research_gaps.json', {
        **legacy_gaps,
        'version': '3.11.0',
        'note': 'v3.11 hereda la investigación pública y refuerza la separación fabricante/mayorista.',
    })
    traceable_fields = sum(
        1
        for section in ('manufacturers','distributors','integrators','clients_public','clients_private','trends','architectures')
        for row in data.get(section, []) or []
        for value in (row.get('fields') or {}).values()
        if value and value.get('evidence')
    )
    cleanup = data['meta'].get('distribution_cleanup') or {}
    write('data/v311/last_run.json', {
        'version': '3.11.0',
        'generated_at': data['meta']['generated_at'],
        'finished_at': data['meta']['generated_at'],
        'profile': 'snapshot',
        'status': 'published',
        'manufacturers': len(data.get('manufacturers') or []),
        'distributors': len(data.get('distributors') or []),
        'integrators': len(data.get('integrators') or []),
        'clients': len(data.get('clients_public') or []) + len(data.get('clients_private') or []),
        'clients_public': len(data.get('clients_public') or []),
        'clients_private': len(data.get('clients_private') or []),
        'trends': len(data.get('trends') or []),
        'architectures': len(data.get('architectures') or []),
        'source_count': len(data.get('source_catalog') or []),
        'traceable_fields': traceable_fields,
        'research_gaps': legacy_gaps.get('total_gaps', 0),
        'high_priority_research_gaps': legacy_gaps.get('high_priority_gaps', 0),
        'distribution_cleanup': cleanup,
    })
    print(json.dumps(load('data/v311/last_run.json', {}), ensure_ascii=False))
