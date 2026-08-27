#!/usr/bin/env python3
from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

VERSION_VALUE = "3.2.6"
MARKER = "V326_WORKFLOW_HIERARCHY_COMPAT"


def backup(path: Path, tag: str = "v325") -> Path:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    bak = path.with_name(path.name + f".{tag}-{stamp}.bak")
    shutil.copy2(path, bak)
    return bak


def patch_validate_text(text: str) -> tuple[str, bool]:
    if MARKER in text:
        return text, False

    old_pattern = re.compile(
        r"(?m)^(?P<indent>\s*)assert\s+'research_supervisor\.py'\s+in\s+text\s+and\s+'upload-artifact@v4'\s+in\s+text,\s*f'Workflow sin supervisor/diagnóstico: \{wf\}'\s*$"
    )
    m = old_pattern.search(text)
    if not m:
        # A slightly more permissive fallback for quote/spacing changes.
        old_pattern = re.compile(
            r"(?m)^(?P<indent>\s*)assert\s+.*research_supervisor\.py.*upload-artifact@v4.*Workflow sin supervisor/diagnóstico.*$"
        )
        m = old_pattern.search(text)
    if not m:
        raise RuntimeError("No se ha localizado la validación legacy de workflows en scripts/validate.py")

    ind = m.group('indent')
    replacement = (
        f"{ind}# {MARKER}\n"
        f"{ind}supervisors=('research_supervisor_v32.py','research_supervisor_v31.py','research_supervisor.py')\n"
        f"{ind}assert any(name in text for name in supervisors) and 'upload-artifact@v4' in text, f'Workflow sin supervisor/diagnóstico: {{wf}}'\n"
        f"{ind}if (ROOT/'scripts/research_supervisor_v32.py').exists():\n"
        f"{ind}    assert 'research_supervisor_v32.py' in text, f'Workflow no apunta al supervisor v3.2: {{wf}}'\n"
        f"{ind}    assert 'data/v31/' in text and 'data/v32/' in text, f'Workflow no persiste datasets v3.1/v3.2: {{wf}}'"
    )
    text = text[:m.start()] + replacement + text[m.end():]

    # The operational-script existence check should know the complete supervisor chain.
    pattern = re.compile(r"for script in \[(?P<body>[^\]]+)\]:")
    sm = pattern.search(text)
    if sm and 'research_supervisor.py' in sm.group('body'):
        body = sm.group('body')
        for name in ['research_supervisor_v31.py', 'research_supervisor_v32.py']:
            if name not in body:
                body = body.rstrip() + f",'{name}'"
        text = text[:sm.start('body')] + body + text[sm.end('body'):]

    compile(text, 'scripts/validate.py', 'exec')
    return text, True


def _ensure_artifact_paths(lines: list[str]) -> list[str]:
    text = ''.join(lines)
    if 'upload-artifact@v4' not in text:
        return lines
    if 'data/v31/' in text and 'data/v32/' in text:
        return lines

    # Insert the two versioned data directories in the upload-artifact path block.
    upload_idx = next((i for i,l in enumerate(lines) if 'uses: actions/upload-artifact@v4' in l), None)
    if upload_idx is None:
        return lines
    path_idx = next((i for i in range(upload_idx+1, min(len(lines), upload_idx+20)) if lines[i].strip() == 'path: |'), None)
    if path_idx is None:
        return lines
    indent = lines[path_idx][:len(lines[path_idx]) - len(lines[path_idx].lstrip())] + '  '
    insert = []
    if 'data/v31/' not in text:
        insert.append(indent + 'data/v31/\n')
    if 'data/v32/' not in text:
        insert.append(indent + 'data/v32/\n')
    return lines[:path_idx+1] + insert + lines[path_idx+1:]


def patch_workflow_text(text: str) -> tuple[str, bool]:
    original = text
    # v3.2 is the public orchestrator. Older wrapper references are upgraded.
    text = re.sub(
        r"(?m)^(\s*run:\s*python\s+)scripts/research_supervisor_v31\.py(\s+--profile\b)",
        r"\1scripts/research_supervisor_v32.py\2",
        text,
    )
    text = re.sub(
        r"(?m)^(\s*run:\s*python\s+)scripts/research_supervisor\.py(\s+--profile\b)",
        r"\1scripts/research_supervisor_v32.py\2",
        text,
    )

    lines = text.splitlines(keepends=True)

    # Preflight compiles the entire supervisor chain, not only the outer wrapper.
    for i, line in enumerate(lines):
        if 'python -m py_compile' in line:
            for script in ['scripts/research_supervisor.py', 'scripts/research_supervisor_v31.py', 'scripts/research_supervisor_v32.py']:
                if script not in line:
                    stripped_nl = '\n' if line.endswith('\n') else ''
                    core = line[:-1] if stripped_nl else line
                    core += ' ' + script
                    line = core + stripped_nl
            lines[i] = line
            break

    lines = _ensure_artifact_paths(lines)

    # Persist all v3.1/v3.2 outputs. Do it as a separate git-add line to avoid
    # depending on the exact legacy data file list.
    has_versioned_git_add = any(
        l.strip().startswith('git add ') and 'data/v31/' in l and 'data/v32/' in l
        for l in lines
    )
    if not has_versioned_git_add:
        git_idx = next((i for i,l in enumerate(lines) if l.strip().startswith('git add ')), None)
        if git_idx is not None:
            indent = lines[git_idx][:len(lines[git_idx]) - len(lines[git_idx].lstrip())]
            lines.insert(git_idx+1, indent + 'git add data/v31/ data/v32/\n')

    return ''.join(lines), ''.join(lines) != original


def patch_v32_version_text(text: str) -> tuple[str, bool]:
    original = text
    text = text.replace('"version":"3.2.5"', '"version":"3.2.6"')
    text = text.replace('v3.2.5 foundation', 'v3.2.6 foundation')
    text = text.replace('v3.2.5 evidence & event intelligence', 'v3.2.6 evidence & event intelligence')
    text = text.replace('v3.2.5 warning', 'v3.2.6 warning')
    text = text.replace('v3.2.5 published', 'v3.2.6 published')
    text = text.replace('v3.2.5 rollback', 'v3.2.6 rollback')
    compile(text, 'scripts/research_supervisor_v32.py', 'exec')
    return text, text != original


def apply(repo: Path) -> dict:
    repo = repo.resolve()
    if not (repo/'.git').exists():
        raise RuntimeError('Ejecuta el instalador desde la raíz del repositorio (donde está .git).')

    changes = {'validate': False, 'workflows': [], 'v32': False, 'backups': []}

    validate = repo/'scripts/validate.py'
    if not validate.exists():
        raise RuntimeError('No existe scripts/validate.py')
    old = validate.read_text(encoding='utf-8')
    new, changed = patch_validate_text(old)
    if changed:
        changes['backups'].append(str(backup(validate)))
        validate.write_text(new, encoding='utf-8')
        changes['validate'] = True

    wfdir = repo/'.github/workflows'
    if not wfdir.exists():
        raise RuntimeError('No existe .github/workflows')
    workflows = sorted(list(wfdir.glob('research-*.yml')) + list(wfdir.glob('research-*.yaml')))
    if not workflows:
        raise RuntimeError('No se han encontrado workflows research-*.yml/.yaml')
    for path in workflows:
        old = path.read_text(encoding='utf-8')
        new, changed = patch_workflow_text(old)
        if changed:
            changes['backups'].append(str(backup(path)))
            path.write_text(new, encoding='utf-8')
            changes['workflows'].append(path.name)

    v32 = repo/'scripts/research_supervisor_v32.py'
    if v32.exists():
        old = v32.read_text(encoding='utf-8')
        new, changed = patch_v32_version_text(old)
        if changed:
            changes['backups'].append(str(backup(v32)))
            v32.write_text(new, encoding='utf-8')
            changes['v32'] = True

    (repo/'VERSION').write_text(VERSION_VALUE + '\n', encoding='utf-8')

    # Compile exactly the files whose orchestration contract changed.
    for rel in ['scripts/validate.py','scripts/research_supervisor.py','scripts/research_supervisor_v31.py','scripts/research_supervisor_v32.py']:
        p=repo/rel
        if not p.exists():
            raise RuntimeError(f'Falta script operativo: {rel}')
        compile(p.read_text(encoding='utf-8'), str(p), 'exec')

    return changes


def main() -> int:
    try:
        changes = apply(Path.cwd())
    except Exception as exc:
        print(f'ERROR: {exc}')
        return 2
    print('v3.2.6 aplicada: validación jerárquica + persistencia GitHub v31/v32.')
    print('validate.py:', 'actualizado' if changes['validate'] else 'ya compatible')
    print('workflows:', ', '.join(changes['workflows']) or 'ya compatibles')
    print('supervisor v32:', 'etiquetado 3.2.6' if changes['v32'] else 'sin cambios')
    print('Prueba validación: python scripts/validate.py')
    print('Prueba legacy corta: python scripts/research_supervisor.py --profile daily --max-runtime 60')
    print('Prueba integral final: python scripts/research_supervisor_v32.py --profile daily --max-runtime 720')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
