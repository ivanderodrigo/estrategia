#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
SUPPORTED_TEXT = {'.txt', '.md', '.csv', '.json', '.yaml', '.yml'}
SUPPORTED_ZIP_XML = {'.pptx', '.docx'}
SUPPORTED_PDF = {'.pdf'}
MAX_TEXT = 120_000

TECH_LENSES = {
    'Ciberseguridad': ['cybersecurity','ciberseguridad','cibersegurança','security','seguridad','segurança','soc','siem','xdr','edr','firewall','zero trust','sase','iam','identity','identidad','mfa','pam','ransomware','threat'],
    'Networking': ['networking','network engineer','network architecture','rede','redes','switch','switching','wifi','wi-fi','lan','wan','sd-wan','campus','nac','routing','router'],
    'Cloud': ['cloud','nube','nuvem','aws','azure','saas','iaas','paas','kubernetes','container','hybrid cloud','multicloud'],
    'Data center': ['data center','datacenter','cpd','storage','backup','back-up','virtualization','virtualización','virtualização','hypervisor'],
    'Observabilidad': ['observability','observabilidad','observabilidade','apm','telemetry','telemetría','monitoring','monitorización'],
    'OT / IoT': ['ot security','industrial','ics','scada','iot','operational technology'],
    'IA / automatización': ['artificial intelligence','inteligencia artificial','ai ',' ia ','automation','automatización','automação','copilot','agentic'],
}


def norm(value: Any) -> str:
    text = str(value or '').lower()
    text = ''.join(ch for ch in text if ord(ch) < 128 or ch.isalnum() or ch.isspace())
    return re.sub(r'\s+', ' ', text).strip()


def _xml_text(blob: bytes) -> str:
    try:
        root = ET.fromstring(blob)
    except Exception:
        return ''
    parts = []
    for node in root.iter():
        if node.text and node.text.strip():
            parts.append(node.text.strip())
    return ' '.join(parts)


def extract_pptx(path: Path) -> str:
    chunks = []
    with zipfile.ZipFile(path) as zf:
        names = sorted(n for n in zf.namelist() if n.startswith('ppt/slides/slide') and n.endswith('.xml'))
        note_names = sorted(n for n in zf.namelist() if n.startswith('ppt/notesSlides/notesSlide') and n.endswith('.xml'))
        for name in [*names, *note_names]:
            try:
                chunks.append(_xml_text(zf.read(name)))
            except Exception:
                continue
    return '\n'.join(x for x in chunks if x)


def extract_docx(path: Path) -> str:
    chunks = []
    with zipfile.ZipFile(path) as zf:
        for name in ('word/document.xml', 'word/footnotes.xml', 'word/endnotes.xml'):
            if name in zf.namelist():
                chunks.append(_xml_text(zf.read(name)))
    return '\n'.join(x for x in chunks if x)


def extract_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        return ''
    try:
        reader = PdfReader(str(path))
        return '\n'.join((page.extract_text() or '') for page in reader.pages)
    except Exception:
        return ''


def extract_text(path: Path) -> tuple[str, str]:
    ext = path.suffix.lower()
    try:
        if ext in SUPPORTED_TEXT:
            return path.read_text(encoding='utf-8', errors='ignore')[:MAX_TEXT], 'text'
        if ext == '.pptx':
            return extract_pptx(path)[:MAX_TEXT], 'pptx-xml'
        if ext == '.docx':
            return extract_docx(path)[:MAX_TEXT], 'docx-xml'
        if ext == '.pdf':
            text = extract_pdf(path)[:MAX_TEXT]
            return text, 'pypdf' if text else 'pdf-unparsed'
        return '', 'unsupported'
    except Exception:
        return '', 'error'


def load_entity_names() -> list[str]:
    names: set[str] = set()
    for rel in ('data/v39/intelligence.json', 'data/v38/intelligence.json'):
        path = ROOT / rel
        if not path.exists():
            continue
        try:
            doc = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            continue
        for section in ('manufacturers','distributors','integrators','clients_public','clients_private','trends','architectures'):
            for row in doc.get(section, []) or []:
                if row.get('name'):
                    names.add(str(row['name']))
    return sorted(names, key=len, reverse=True)


def detect_entities(text: str, entity_names: list[str]) -> list[str]:
    low = norm(text)
    found = []
    for name in entity_names:
        key = norm(name)
        if len(key) < 3:
            continue
        if key in low:
            found.append(name)
        if len(found) >= 40:
            break
    return found


def detect_areas(text: str) -> list[str]:
    low = norm(text)
    out = []
    for area, terms in TECH_LENSES.items():
        if any(norm(term) in low for term in terms):
            out.append(area)
    return out


def load_manual_inputs(input_dirs: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for base in input_dirs:
        folder = base / 'manual'
        if not folder.exists():
            continue
        for path in sorted(folder.glob('*.json')):
            try:
                raw = json.loads(path.read_text(encoding='utf-8'))
            except Exception as exc:
                rows.append({'status':'error','file':str(path.relative_to(ROOT)) if ROOT in path.parents else str(path),'error':str(exc)})
                continue
            items = raw if isinstance(raw, list) else raw.get('contributions', [raw]) if isinstance(raw, dict) else []
            for item in items:
                if not isinstance(item, dict):
                    continue
                rows.append({**item, '_file': str(path.relative_to(ROOT)) if ROOT in path.parents else str(path)})
    return rows


def scan_documents(input_dirs: list[Path]) -> list[dict[str, Any]]:
    entities = load_entity_names()
    docs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for base in input_dirs:
        folder = base / 'documents'
        if not folder.exists():
            continue
        for path in sorted(p for p in folder.rglob('*') if p.is_file() and p.name != '.gitkeep'):
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            text, method = extract_text(path)
            stat = path.stat()
            rel = str(path.relative_to(ROOT)) if ROOT in path.parents else str(path)
            docs.append({
                'file': rel,
                'name': path.name,
                'extension': path.suffix.lower(),
                'size_bytes': stat.st_size,
                'modified_at': datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                'extract_method': method,
                'text_available': bool(text.strip()),
                'text_excerpt': re.sub(r'\s+', ' ', text).strip()[:4000],
                'entities': detect_entities(text, entities) if text else [],
                'areas': detect_areas(text) if text else [],
            })
    return docs


def scan(root: Path = ROOT, external_inputs: Path | None = None) -> dict[str, Any]:
    dirs = [root / 'inputs']
    if external_inputs and external_inputs.exists():
        dirs.append(external_inputs)
    result = {
        'version': '3.10.0',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'input_dirs': [str(x) for x in dirs],
        'manual': load_manual_inputs(dirs),
        'documents': scan_documents(dirs),
    }
    result['stats'] = {
        'manual_contributions': len(result['manual']),
        'documents': len(result['documents']),
        'documents_with_text': sum(1 for d in result['documents'] if d.get('text_available')),
        'document_entity_mentions': sum(len(d.get('entities') or []) for d in result['documents']),
    }
    out = root / 'data/v310/repo_inputs.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--external-inputs', default='')
    args = parser.parse_args()
    external = Path(args.external_inputs).resolve() if args.external_inputs else None
    print(json.dumps(scan(ROOT, external), ensure_ascii=False))
