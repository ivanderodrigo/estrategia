#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def validate(root: Path | None = None) -> list[str]:
    base = root or ROOT
    errors: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    version = (base / 'VERSION').read_text(encoding='utf-8').strip()
    check(version == '3.9.0', f'VERSION debe ser 3.9.0 y es {version!r}')

    data = json.loads((base / 'data/v39/intelligence.json').read_text(encoding='utf-8'))
    check(data.get('meta', {}).get('version') == '3.9.0', 'meta.version debe ser 3.9.0')
    for key in ['manufacturers', 'distributors', 'integrators', 'clients_public', 'clients_private', 'trends', 'architectures', 'source_catalog']:
        check(key in data, f'Falta la sección {key}')
    check(len(data.get('clients_public', [])) >= 8, 'clients_public debe contener al menos 8 oportunidades')
    check(len(data.get('clients_private', [])) >= 8, 'clients_private debe contener al menos 8 cuentas')
    check(len(data.get('source_catalog', [])) >= 235, 'source_catalog debe reflejar ampliación de fuentes')
    check('clients_public' in data.get('schemas', {}), 'Falta schema clients_public')
    check('clients_private' in data.get('schemas', {}), 'Falta schema clients_private')

    for row in data.get('clients_public', [])[:3] + data.get('clients_private', [])[:3]:
        check(bool(row.get('evidence')), f"{row.get('name')} debe tener evidencia")
        for fid, field in row.get('fields', {}).items():
            check(bool(field.get('evidence')), f"{row.get('name')}::{fid} debe ser trazable")

    last_run = json.loads((base / 'data/v39/last_run.json').read_text(encoding='utf-8'))
    check(last_run.get('version') == '3.9.0', 'last_run.version debe ser 3.9.0')
    check(last_run.get('clients') == (last_run.get('clients_public', 0) + last_run.get('clients_private', 0)), 'last_run clients inconsistente')

    index = (base / 'index.html').read_text(encoding='utf-8')
    check('assets/v390/intelligence.css?v=3.9.0' in index, 'index debe apuntar a CSS v390')
    check('assets/v390/intelligence.js?v=3.9.0' in index, 'index debe apuntar a JS v390')
    check('data-view="clientes"' in index, 'Falta pestaña de clientes')
    check('publicClientTable' in index and 'privateClientTable' in index, 'Faltan tablas de clientes')

    js = (base / 'assets/v390/intelligence.js').read_text(encoding='utf-8')
    for token in ['clients_public', 'clients_private', 'renderClients', 'exportSections(modules)', 'Westcon_Iberia_Business_Intelligence_v3.9.0.pdf', 'Westcon_Iberia_Business_Intelligence_v3.9.0.pptx']:
        check(token in js, f'Falta token en JS: {token}')

    css = (base / 'assets/v390/intelligence.css').read_text(encoding='utf-8')
    for token in ['client-blocks', 'subsection-head', 'appbar-actions', '@media(max-width:1380px)', '@media(max-width:720px)']:
        check(token in css, f'Falta token en CSS: {token}')

    return errors


def main() -> None:
    errors = validate(ROOT)
    if errors:
        raise SystemExit('VALIDACIÓN v3.9.0 · FAIL · ' + '; '.join(errors[:16]))
    print('VALIDACIÓN v3.9.0 · PASS')


if __name__ == '__main__':
    main()
