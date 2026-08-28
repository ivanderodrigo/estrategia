#!/usr/bin/env python3
"""Publish generated intelligence without rebasing generated data in-place.

GitHub Actions runs in an ephemeral clone. We snapshot only generated data,
refresh the checkout to the latest origin/main, restore the snapshot, validate,
commit and push. If main moves again before the push, the process retries.
This avoids the common modify/modify conflicts produced by `git pull --rebase`
on machine-generated JSON while preserving the newest application code.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

GENERATED_PATHS = [
    "data/research.latest.json",
    "data/research_status.json",
    "data/research_learning.json",
    "data/research_queue.json",
    "data/changes.latest.json",
    "data/source_health.json",
    "data/discovered_entities.json",
    "data/research_errors.json",
    "data/run_manifest.latest.json",
    "data/supervisor.latest.json",
    "data/history",
    "data/v31",
    "data/v32",
    "data/v33",
    "data/v34",
    "data/v37",
    "data/v38",
]


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, text=True, check=check)


def snapshot_generated(tmp: Path) -> list[str]:
    present=[]
    for rel in GENERATED_PATHS:
        src=ROOT/rel
        if not src.exists():
            continue
        dst=tmp/rel
        dst.parent.mkdir(parents=True,exist_ok=True)
        if src.is_dir():
            shutil.copytree(src,dst,dirs_exist_ok=True)
        else:
            shutil.copy2(src,dst)
        present.append(rel)
    return present


def restore_generated(tmp: Path, present: list[str]) -> None:
    for rel in present:
        src=tmp/rel; dst=ROOT/rel
        if not src.exists():
            continue
        dst.parent.mkdir(parents=True,exist_ok=True)
        if src.is_dir():
            # Replace the generated directory so deleted/obsolete outputs do not resurrect.
            if dst.exists(): shutil.rmtree(dst)
            shutil.copytree(src,dst)
        else:
            shutil.copy2(src,dst)


def validate() -> None:
    run(sys.executable,"scripts/v38/validate_v38.py")
    if shutil.which("node"):
        run("node","--check","assets/v380/intelligence.js")
        run("node","tests/ui_smoke_v380.js")


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--message",default="chore: actualizar inteligencia pública v3.8")
    ap.add_argument("--attempts",type=int,default=3)
    args=ap.parse_args()
    if not (ROOT/".git").exists():
        print("No es un checkout Git; no se publica.",file=sys.stderr);return 2
    run("git","config","user.name",os.getenv("GIT_BOT_NAME","westcon-strategy-bot"))
    run("git","config","user.email",os.getenv("GIT_BOT_EMAIL","actions@users.noreply.github.com"))
    with tempfile.TemporaryDirectory(prefix="westcon-research-") as td:
        tmp=Path(td)
        present=snapshot_generated(tmp)
        if not present:
            print("No hay salidas generadas que publicar.");return 0
        for attempt in range(1,max(1,args.attempts)+1):
            print(f"publish attempt {attempt}/{args.attempts}",flush=True)
            run("git","fetch","origin","main")
            # Safe in Actions: ephemeral checkout. Never use this script as a local installer.
            run("git","reset","--hard","origin/main")
            restore_generated(tmp,present)
            validate()
            run("git","add","-A",*GENERATED_PATHS)
            diff=run("git","diff","--cached","--quiet",check=False)
            if diff.returncode==0:
                print("La inteligencia generada ya coincide con origin/main.");return 0
            run("git","commit","-m",args.message)
            pushed=run("git","push","origin","HEAD:main",check=False)
            if pushed.returncode==0:
                print("Inteligencia publicada sobre la última versión de main.");return 0
            print("main avanzó durante la publicación; reintentando sobre el nuevo origin/main",flush=True)
        print("No se pudo publicar tras los reintentos; los artefactos del workflow conservan el resultado.",file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
