#!/usr/bin/env python3
from __future__ import annotations

import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
REPO = Path.cwd().resolve()

COPY_DIRS = ["scripts/v31", "config/v31", "assets/v31", "tests"]
COPY_FILES = ["scripts/research_supervisor_v31.py", "README_V31.md", "VERSION"]


def copy_overlay():
    if PACKAGE.resolve() == REPO.resolve():
        return
    for rel in COPY_DIRS:
        src = PACKAGE / rel; dst = REPO / rel
        if dst.exists(): shutil.rmtree(dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst)
    for rel in COPY_FILES:
        src = PACKAGE / rel; dst = REPO / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def inject_frontend():
    index = REPO / "index.html"
    if not index.exists():
        return "index.html not found; frontend injection skipped"
    text = index.read_text(encoding="utf-8")
    backup = index.with_suffix(f".html.v30-{datetime.now().strftime('%Y%m%d%H%M%S')}.bak")
    shutil.copy2(index, backup)
    css = '<link rel="stylesheet" href="assets/v31/entity-intelligence.css?v=3.1">'
    js = '<script src="assets/v31/entity-intelligence.js?v=3.1" defer></script>'
    if "assets/v31/entity-intelligence.css" not in text:
        text = re.sub(r"</head>", f"  {css}\n</head>", text, count=1, flags=re.I)
    if "assets/v31/entity-intelligence.js" not in text:
        text = re.sub(r"</body>", f"  {js}\n</body>", text, count=1, flags=re.I)
    index.write_text(text, encoding="utf-8")
    return f"frontend injected; backup {backup.name}"


def patch_workflows():
    wf_dir = REPO / ".github" / "workflows"
    changed = []
    if not wf_dir.exists(): return changed
    for path in list(wf_dir.glob("*.yml")) + list(wf_dir.glob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        if "research_supervisor.py" not in text: continue
        backup = path.with_suffix(path.suffix + ".v30.bak")
        if not backup.exists(): shutil.copy2(path, backup)
        new = text.replace("scripts/research_supervisor.py", "scripts/research_supervisor_v31.py")
        if new != text:
            path.write_text(new, encoding="utf-8"); changed.append(path.name)
    return changed


def update_gitignore():
    p = REPO / ".gitignore"
    text = p.read_text(encoding="utf-8") if p.exists() else ""
    lines = [".v31_snapshots/", ".v31_state/", "*.v30.bak", "*.v30-*.bak"]
    changed = False
    for line in lines:
        if line not in text.splitlines():
            text += ("\n" if text and not text.endswith("\n") else "") + line + "\n"
            changed = True
    if changed:
        p.write_text(text, encoding="utf-8")


def main():
    if not (REPO / ".git").exists():
        print("AVISO: no veo .git en la carpeta actual; asegúrate de ejecutar esto en la raíz del repo.")
    copy_overlay()
    update_gitignore()
    print(inject_frontend())
    changed = patch_workflows()
    print("workflows actualizados:", ", ".join(changed) if changed else "ninguno")
    print("v3.1 aplicada. Ejecuta: python scripts/research_supervisor_v31.py --profile daily --max-runtime 180 --skip-legacy")
    print("Después: git add . && git commit -m \"Westcon Decision Intelligence v3.1\" && git push")

if __name__ == "__main__": main()
