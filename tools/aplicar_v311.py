#!/usr/bin/env python3
from __future__ import annotations
import shutil
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = Path.cwd().resolve()
FILES = [
    "scripts/research_supervisor_v31.py",
    "scripts/v31/discovery.py",
]


def main():
    if not (REPO / ".git").exists():
        print("ERROR: ejecuta este comando desde la raíz del repositorio (donde está .git).")
        return 2
    for rel in FILES:
        src = PACKAGE / rel
        dst = REPO / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            bak = dst.with_suffix(dst.suffix + ".v310.bak")
            if not bak.exists():
                shutil.copy2(dst, bak)
        shutil.copy2(src, dst)
    (REPO / "VERSION").write_text("3.1.1\n", encoding="utf-8")
    print("v3.1.1 aplicada: discovery acotado, deuda por gap, circuit breaker por proveedor y preservación de señales previas.")
    print("Prueba: python scripts/research_supervisor_v31.py --profile daily --max-runtime 180 --skip-legacy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
