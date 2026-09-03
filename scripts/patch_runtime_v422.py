#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding='utf-8')
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor in {path}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding='utf-8')


def patch_pipeline() -> None:
    p = ROOT / 'engine/pipeline.py'
    replace_once(
        p,
        'from .publication import public_payloads\n',
        'from .publication import public_payloads\nfrom .westcon_current_evidence import apply_westcon_current_evidence\n',
        'pipeline current-Westcon import',
    )
    replace_once(
        p,
        '    public_evidence_migration_final = apply_public_evidence_migrations(\n        data, read_json("config/current/public_evidence_migrations.json", {})\n    )\n    _sync_source_catalog(data)\n',
        '    public_evidence_migration_final = apply_public_evidence_migrations(\n        data, read_json("config/current/public_evidence_migrations.json", {})\n    )\n    westcon_current_evidence = apply_westcon_current_evidence(\n        data, read_json("config/current/westcon_fy27_document_facts.json", {})\n    )\n    _sync_source_catalog(data)\n',
        'pipeline current-Westcon evidence application',
    )
    replace_once(
        p,
        '        "claims_westcon_supported": 0,\n        "claims_westcon_and_public": 0,\n',
        '        "claims_westcon_supported": int(source_rationalization.get("targets_supported_westcon_only") or 0),\n        "claims_westcon_and_public": int(source_rationalization.get("targets_supported_westcon_and_public") or 0),\n',
        'pipeline current-Westcon metrics',
    )
    replace_once(
        p,
        '        "archive_apply": archive_apply_final,\n        "document_apply": document_apply_final,\n        "schema": schema_stats,\n',
        '        "archive_apply": archive_apply_final,\n        "document_apply": document_apply_final,\n        "westcon_current_evidence": westcon_current_evidence,\n        "schema": schema_stats,\n',
        'pipeline current-Westcon last-run stats',
    )
    replace_once(
        p,
        '            "document_apply": document_apply_final,\n            "source_intelligence": source_rationalization,\n',
        '            "document_apply": document_apply_final,\n            "westcon_current_evidence": westcon_current_evidence,\n            "source_intelligence": source_rationalization,\n',
        'pipeline current-Westcon provenance report',
    )


def patch_frontend() -> None:
    index = ROOT / 'index.html'
    text = index.read_text(encoding='utf-8')
    text = text.replace('4.2.1', '4.2.2').replace('4.1.0', '4.2.2')
    index.write_text(text, encoding='utf-8')

    js = ROOT / 'assets/app/intelligence.js'
    text = js.read_text(encoding='utf-8')
    text = text.replace('4.2.1', '4.2.2').replace('4.1.0', '4.2.2')
    text = text.replace("s.class==='WESTCON_DOCUMENT'", "String(s.class||'').includes('Westcon') || String(s.class||'').startsWith('WESTCON_DOCUMENT')")
    js.write_text(text, encoding='utf-8')

    css = ROOT / 'assets/app/intelligence.css'
    text = css.read_text(encoding='utf-8')
    text = text.replace('/* v4.2.1 · professional table analysis surface */', '/* v4.2.2 · professional table analysis surface */')
    text = text.replace('/* v4.1 · professional table analysis surface */', '/* v4.2.2 · professional table analysis surface */')
    marker = '/* v4.2.2 · ergonomic atomic tags */'
    if marker not in text:
        text = text.rstrip() + '''\n\n/* v4.2.2 · ergonomic atomic tags */\n.data-table td.col-capabilities,.data-table td.col-vendor_relations,.data-table td.col-westcon_overlap,.data-table td.col-competitor_vendor_overlap,.data-table td.col-differential_capabilities,.data-table td.col-technology_signals{min-width:230px!important}\n.tag-list{display:grid!important;grid-template-columns:minmax(0,1fr);gap:7px!important;align-items:stretch!important;max-height:none!important;overflow:visible!important}\n.tag-entry{display:block!important;width:100%;max-width:none!important;min-width:0}\n.tag-entry.tag-overflow{display:none!important}.tag-list.expanded .tag-entry.tag-overflow{display:block!important}\n.tag-entry>.traceable{display:block!important;width:100%!important;max-width:none!important;min-width:0!important;border-radius:10px}\n.tag-entry>.traceable:hover{background:rgba(18,199,192,.055)}\n.tag-entry>.traceable .trace-value{display:grid;gap:4px;width:100%;padding-right:28px!important}\n.tag-entry .confidence-tag{display:flex!important;width:100%!important;max-width:none!important;min-height:30px!important;align-items:center!important;justify-content:space-between!important;gap:8px!important;padding:6px 8px!important;border-radius:9px!important;white-space:normal!important;line-height:1.15!important}\n.tag-entry .confidence-tag .tag-label{display:block;min-width:0;max-width:none!important;overflow:visible!important;text-overflow:clip!important;white-space:normal!important;overflow-wrap:anywhere}\n.tag-entry .confidence-tag small{flex:0 0 auto;white-space:nowrap;font-size:.72em}\n.tag-entry .pending-verification{display:flex!important;width:max-content;max-width:100%;margin:0;padding:3px 7px;border-radius:7px;line-height:1.2;white-space:normal}\n.tag-entry .trace-mark{right:5px!important;top:6px!important;width:18px!important;height:18px!important;font-size:9px!important;z-index:2}\n.tag-list>.more-tags{justify-self:start;margin-top:1px}\n@media(max-width:620px){.data-table td.col-capabilities,.data-table td.col-vendor_relations,.data-table td.col-westcon_overlap,.data-table td.col-competitor_vendor_overlap,.data-table td.col-differential_capabilities,.data-table td.col-technology_signals{min-width:210px!important}.tag-entry .confidence-tag{min-height:34px!important}}\n'''
    css.write_text(text, encoding='utf-8')


def patch_schema_help() -> None:
    p = ROOT / 'config/current/business_intelligence_schema.json'
    text = p.read_text(encoding='utf-8')
    text = text.replace(
        'Presencia en el portfolio de España, validada mediante fuente pública actual; la documentación interna se conserva solo como pista de investigación.',
        'Presencia en el portfolio de España, acreditable mediante fuente pública actual o documentación Westcon vigente y específica; el histórico se conserva solo como pista.'
    )
    text = text.replace(
        'Presencia en el portfolio de Portugal, validada mediante fuente pública actual; la documentación interna se conserva solo como pista de investigación.',
        'Presencia en el portfolio de Portugal, acreditable mediante fuente pública actual o regla/documentación Westcon vigente y específica; el histórico se conserva solo como pista.'
    )
    p.write_text(text, encoding='utf-8')


def main() -> int:
    patch_pipeline()
    patch_frontend()
    patch_schema_help()
    print('v4.2.2 runtime/frontend patch: PASS')
    print(' - pipeline: current Westcon evidence reapplied on every canonical build')
    print(' - frontend: atomic tags are full-width, separated and easier to click')
    print(' - schema: current Westcon first-party evidence allowed only for owned claims')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
