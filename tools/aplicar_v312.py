#!/usr/bin/env python3
from __future__ import annotations
import shutil
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = Path.cwd().resolve()
FILES = [
    "scripts/research_supervisor_v31.py",
    "scripts/v31/discovery.py",
]


def _same_file(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except Exception:
        return False


def main():
    if not (REPO / ".git").exists():
        print("ERROR: ejecuta este comando desde la raíz del repositorio (donde está .git).")
        return 2
    changed = 0
    verified = 0
    for rel in FILES:
        src = PACKAGE / rel
        dst = REPO / rel
        if not src.exists():
            print(f"ERROR: falta {rel} en el hotfix.")
            return 3
        dst.parent.mkdir(parents=True, exist_ok=True)
        if _same_file(src, dst):
            verified += 1
            continue
        if dst.exists():
            bak = dst.with_suffix(dst.suffix + ".v311.bak")
            if not bak.exists():
                shutil.copy2(dst, bak)
        shutil.copy2(src, dst)
        changed += 1
    (REPO / "VERSION").write_text("3.1.2\n", encoding="utf-8")
    print(f"v3.1.2 lista · {changed} archivos copiados · {verified} ya estaban en destino.")
    print("Incluye queries compactas OR, aliases, fair-share real, Google/GDELT intercalados, concurrencia acotada y diagnósticos raw/accepted/rejected.")
    print("Prueba: python scripts/research_supervisor_v31.py --profile daily --max-runtime 180 --skip-legacy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
