#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from engine.storage import read_json

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    errors: list[str] = []
    gaps = read_json('data/current/research_gaps.json', {})
    rows = list(gaps.get('gaps') or [])
    priority = gaps.get('business_priority') or {}
    model = str(priority.get('model') or '')
    if model != 'business-value-x-researchability-opportunity-v2':
        errors.append(f'unexpected business-priority model: {model}')

    public_rows = [g for g in rows if g.get('section') == 'clients_public']
    public_high = [g for g in public_rows if g.get('priority_tier') in {'P0', 'P1'}]
    contextual = [g for g in public_rows if float(g.get('opportunity_context_multiplier') or 1.0) > 1.15]
    if contextual and not public_high:
        errors.append('context-rich public opportunities exist but none can reach P0/P1')

    wrong_family = [
        g for g in public_rows
        if g.get('field') in {'technology_signals','request_or_need','estimated_amount','procurement_stage','milestone_date','identified_vendors','identified_integrators'}
        and g.get('source_family') != 'procurement'
    ]
    if wrong_family:
        errors.append(f'{len(wrong_family)} public procurement gaps are routed away from procurement sources')

    schema = read_json('config/current/business_intelligence_schema.json', {})
    sections = schema.get('sections') if isinstance(schema, dict) else {}
    if not isinstance(sections, dict):
        sections = {}
    manufacturer_rows = sections.get('manufacturers') or schema.get('manufacturers') or []
    manufacturer = {row.get('id'): row for row in manufacturer_rows if isinstance(row, dict)}
    for field in ('westcon_spain', 'westcon_portugal'):
        help_text = str((manufacturer.get(field) or {}).get('help') or '').casefold()
        if 'fuente pública' not in help_text or 'westcon vigente' not in help_text or 'pista' not in help_text:
            errors.append(f'{field} help does not expose the v4.2.2 current-public/current-Westcon-owned contract')

    print('v4.2.1 opportunity-aware research audit:', 'PASS' if not errors else 'FAIL')
    print(' - model:', model)
    print(' - clients-public gaps:', len(public_rows))
    print(' - clients-public P0/P1:', len(public_high))
    print(' - clients-public share of P0/P1 %:', priority.get('clients_public_share_of_p0_p1_pct'))
    print(' - context-rich public gaps:', len(contextual))
    print(' - procurement-routed public gaps:', sum(1 for g in public_rows if g.get('source_family') == 'procurement'))
    if public_high:
        top = sorted(public_high, key=lambda g: float(g.get('priority_score') or 0), reverse=True)[:10]
        print(' - top public opportunities:')
        for gap in top:
            print('   ', gap.get('priority_tier'), gap.get('priority_score'), '|', gap.get('entity'), '|', gap.get('field'), '| x', gap.get('opportunity_context_multiplier'))
    for error in errors:
        print(' - ERROR:', error)
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
