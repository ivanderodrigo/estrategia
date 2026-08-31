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
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FOUNDATION_GENERATED_PATHS = [
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
    "data/v39",
]

def current_version() -> tuple[str, str]:
    raw=(ROOT/"VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+",raw):
        raise RuntimeError(f"VERSION inválida: {raw!r}")
    major,minor,patch=raw.split(".")
    return raw,"v"+major+minor+(patch if patch!="0" else "")

def generated_paths() -> list[str]:
    _,tag=current_version()
    return [*FOUNDATION_GENERATED_PATHS,f"data/{tag}"]


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, text=True, check=check)


def snapshot_generated(tmp: Path, paths: list[str]) -> list[str]:
    present=[]
    for rel in paths:
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
    version,tag=current_version();validator=ROOT/f"scripts/{tag}/validate_{tag}.py"
    if not validator.is_file():raise RuntimeError(f"Falta el validador de la versión activa {version}: {validator.relative_to(ROOT)}")
    run(sys.executable,str(validator.relative_to(ROOT)))
    if shutil.which("node"):
        js=ROOT/f"assets/{tag}/intelligence.js";smoke=ROOT/f"tests/ui_smoke_{tag}.js"
        if js.is_file():run("node","--check",str(js.relative_to(ROOT)))
        if smoke.is_file():run("node",str(smoke.relative_to(ROOT)))


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--message",default="chore: actualizar inteligencia pública")
    ap.add_argument("--attempts",type=int,default=3)
    args=ap.parse_args()
    if not (ROOT/".git").exists():
        print("No es un checkout Git; no se publica.",file=sys.stderr);return 2
    run("git","config","user.name",os.getenv("GIT_BOT_NAME","westcon-strategy-bot"))
    run("git","config","user.email",os.getenv("GIT_BOT_EMAIL","actions@users.noreply.github.com"))
    with tempfile.TemporaryDirectory(prefix="westcon-research-") as td:
        tmp=Path(td)
        paths=generated_paths();present=snapshot_generated(tmp,paths)
        if not present:
            print("No hay salidas generadas que publicar.");return 0
        for attempt in range(1,max(1,args.attempts)+1):
            print(f"publish attempt {attempt}/{args.attempts}",flush=True)
            run("git","fetch","origin","main")
            # Safe in Actions: ephemeral checkout. Never use this script as a local installer.
            run("git","reset","--hard","origin/main")
            restore_generated(tmp,present)
            validate()
            run("git","add","-A",*paths)
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
