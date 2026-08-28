#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

from v38.build_intelligence import atomic_item, dedupe_evidence, evidence, load, write
from v39.build_intelligence import build as build_v39, merge_source_catalog as merge_source_catalog_v39
from v310.ingest_repo_inputs import scan as scan_repo_inputs


def norm(value: Any) -> str:
    text = str(value or '').lower()
    text = re.sub(r'[^a-z0-9áéíóúüñçãõâêôàèìòùäëïöü\s]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def merge_source_catalog() -> list[dict[str, Any]]:
    rows = {item.get('id'): dict(item) for item in merge_source_catalog_v39()}
    for raw in load('config/v310/source_additions.json', {}).get('sources', []) or []:
        sid = raw.get('source_id') or raw.get('id')
        if not sid:
            continue
        rows[sid] = {
            'id': sid,
            'name': raw.get('name'),
            'url': raw.get('url'),
            'class': raw.get('source_class') or raw.get('class'),
            'scope': raw.get('scope') or [],
            'dimensions': raw.get('dimensions') or [],
            'access_policy': raw.get('access_policy'),
        }
    return sorted(rows.values(), key=lambda x: (str(x.get('class') or ''), str(x.get('name') or '')))


def _manual_evidence(item: dict[str, Any]) -> dict[str, Any] | None:
    author = str(item.get('author') or 'Usuario').strip()
    title = str(item.get('source_title') or item.get('note') or item.get('value') or 'Aporte manual').strip()
    raw = {
        'source': f'Aporte manual · {author}',
        'title': title[:260],
        'url': item.get('source_url') or None,
        'date': item.get('source_date') or item.get('created_at') or datetime.now(timezone.utc).date().isoformat(),
        'type': 'manual-user-input',
        'description': str(item.get('note') or 'Inteligencia añadida manualmente sobre una evidencia pública o una cuenta.').strip()[:600],
        'note': 'Aporte interno/manual. Se presenta separado de la evidencia pública y debe revalidarse cuando proceda.',
    }
    return evidence(raw)


def _doc_evidence(doc: dict[str, Any]) -> dict[str, Any] | None:
    areas = ', '.join(doc.get('areas') or [])
    raw = {
        'source': 'Documento ingerido desde repositorio',
        'title': doc.get('name') or doc.get('file') or 'Documento',
        'date': (doc.get('modified_at') or '')[:10],
        'type': 'repository-document',
        'description': f"Documento procesado por el cron. Áreas detectadas: {areas or 'sin clasificar'}. Método: {doc.get('extract_method') or 'desconocido'}.",
        'note': 'Inteligencia documental interna. La mención de una entidad no prueba por sí sola relación comercial ni despliegue.',
    }
    return evidence(raw)


def _find_row(data: dict[str, Any], section: str, entity: str) -> dict[str, Any] | None:
    target = norm(entity)
    for row in data.get(section, []) or []:
        if norm(row.get('name')) == target:
            return row
    return None


def _repo_note(row: dict[str, Any], payload: dict[str, Any]) -> None:
    notes = row.setdefault('repo_intelligence', [])
    fingerprint = norm(f"{payload.get('kind')} {payload.get('value')} {payload.get('note')} {payload.get('source')}")
    if not any(norm(f"{x.get('kind')} {x.get('value')} {x.get('note')} {x.get('source')}") == fingerprint for x in notes):
        notes.append(payload)


def apply_manual_contributions(data: dict[str, Any], items: list[dict[str, Any]]) -> int:
    applied = 0
    for item in items:
        section = str(item.get('section') or '').strip()
        entity = str(item.get('entity') or '').strip()
        field_id = str(item.get('field') or '').strip()
        if not section or not entity:
            continue
        row = _find_row(data, section, entity)
        if not row:
            continue
        ev = _manual_evidence(item)
        if not ev:
            continue
        mode = str(item.get('mode') or 'note').lower()
        new_value = item.get('value')
        target_value = item.get('target_value')
        field_obj = (row.get('fields') or {}).get(field_id) if field_id else None
        appended = False
        if mode in {'add', 'append', 'add_value'} and field_obj and isinstance(field_obj.get('value'), list) and new_value not in (None, ''):
            existing = {norm(v) for v in field_obj.get('value') or []}
            if norm(new_value) not in existing:
                atom = atomic_item(new_value, [ev], item.get('confidence') or .64, 'Aporte manual; se mantiene separado conceptualmente de la evidencia pública capturada automáticamente.')
                if atom:
                    field_obj['value'].append(new_value)
                    field_obj.setdefault('items', []).append(atom)
                    field_obj['evidence'] = dedupe_evidence([*(field_obj.get('evidence') or []), ev], 12)
                    appended = True
        _repo_note(row, {
            'kind': 'manual',
            'field': field_id or None,
            'target_value': target_value,
            'value': new_value if new_value not in (None, '') else item.get('note'),
            'note': item.get('note'),
            'source': ev.get('source'),
            'date': ev.get('date'),
            'evidence': [ev],
            'applied_to_field': appended,
        })
        applied += 1
    return applied


def apply_document_signals(data: dict[str, Any], documents: list[dict[str, Any]]) -> int:
    lookup: dict[str, tuple[str, dict[str, Any]]] = {}
    for section in ('manufacturers','distributors','integrators','clients_public','clients_private','trends','architectures'):
        for row in data.get(section, []) or []:
            lookup[norm(row.get('name'))] = (section, row)
    applied = 0
    for doc in documents:
        if not doc.get('text_available'):
            continue
        ev = _doc_evidence(doc)
        if not ev:
            continue
        for entity in doc.get('entities') or []:
            hit = lookup.get(norm(entity))
            if not hit:
                continue
            section, row = hit
            _repo_note(row, {
                'kind': 'document',
                'field': None,
                'value': f"{doc.get('name')} · {', '.join(doc.get('areas') or []) or 'señal documental'}",
                'note': (doc.get('text_excerpt') or '')[:650],
                'source': ev.get('source'),
                'date': ev.get('date'),
                'document': doc.get('file'),
                'areas': doc.get('areas') or [],
                'evidence': [ev],
            })
            applied += 1
    return applied


def build(external_inputs: Path | None = None) -> dict[str, Any]:
    repo_inputs = scan_repo_inputs(ROOT, external_inputs)
    data = copy.deepcopy(build_v39())
    data['meta']['version'] = '3.10.0'
    data['meta']['generated_at'] = datetime.now(timezone.utc).isoformat()
    data['meta']['principle'] = 'Inteligencia descriptiva y trazable con capa pública, aportaciones manuales separadas y documentos ingeridos de forma gobernada.'
    data['meta']['traceability'] = 'La evidencia pública permanece diferenciada de las aportaciones manuales y documentales. Los documentos del repositorio se tratan como señales internas, no como hechos públicos.'
    data['source_catalog'] = merge_source_catalog()
    data['meta']['source_count'] = len(data['source_catalog'])
    manual_count = apply_manual_contributions(data, repo_inputs.get('manual') or [])
    document_mentions = apply_document_signals(data, repo_inputs.get('documents') or [])
    data['meta']['repo_inputs'] = {
        **(repo_inputs.get('stats') or {}),
        'manual_applied': manual_count,
        'document_mentions_applied': document_mentions,
    }
    return data


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--external-inputs', default='')
    args = parser.parse_args()
    external = Path(args.external_inputs).resolve() if args.external_inputs else None
    data = build(external)
    write('data/v310/intelligence.json', data)
    legacy_gaps = load('data/v39/research_gaps.json', {}) or load('data/v38/research_gaps.json', {}) or {}
    write('data/v310/research_gaps.json', {
        **legacy_gaps,
        'version': '3.10.0',
        'note': 'La cola v3.10 hereda la investigación pública y añade relectura de aportaciones/documentos del repositorio.',
    })
    traceable_fields = sum(
        1
        for section in ('manufacturers','distributors','integrators','clients_public','clients_private','trends','architectures')
        for row in data.get(section, []) or []
        for value in (row.get('fields') or {}).values()
        if value and value.get('evidence')
    )
    write('data/v310/last_run.json', {
        'version': '3.10.0',
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
        'repo_inputs': data['meta'].get('repo_inputs') or {},
    })
    print(json.dumps(load('data/v310/last_run.json', {}), ensure_ascii=False))
