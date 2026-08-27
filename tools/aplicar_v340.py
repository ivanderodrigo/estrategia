#!/usr/bin/env python3
"""Safe, idempotent v3.3.3a -> v3.4.0 migration and activation."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from v34.pipeline import run
from v34.validate_v34 import validate


DYNAMIC_FILES = [
    "data/research.latest.json", "data/research_status.json", "data/research_learning.json",
    "data/research_queue.json", "data/changes.latest.json", "data/source_health.json",
    "data/discovered_entities.json", "data/research_errors.json", "data/run_manifest.latest.json",
    "data/supervisor.latest.json", "config/update_schedule.json",
]
DYNAMIC_DIRECTORIES = ["data/history", "data/v31", "data/v32", "data/v33", "diagnostics", ".v32_state"]
MANIFEST = ROOT / ".v340_migration.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aplicar Westcon Iberia Decision Intelligence v3.4.0")
    parser.add_argument("--migrate-from", type=Path, help="Ruta a la copia preservada de v3.3.3a")
    parser.add_argument("--rollback-migration", action="store_true", help="Restaura los datos v3.4 previos a la última migración")
    return parser.parse_args()


def _version(root: Path) -> str:
    try:
        return (root / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _safe_source(source: Path) -> Path:
    source = source.expanduser().resolve()
    target = ROOT.resolve()
    if not source.is_dir():
        raise ValueError(f"La ruta de migración no es un directorio: {source}")
    if source == target or source in target.parents or target in source.parents:
        raise ValueError("La copia v3.3.3a debe estar en un directorio separado, no dentro de v3.4 ni al revés.")
    if _version(source) != "3.3.3a":
        raise ValueError(f"Se esperaba VERSION 3.3.3a en {source}; encontrado {_version(source) or 'sin VERSION'}.")
    return source


def _copy_item(source: Path, target: Path) -> None:
    if source.is_dir():
        target.mkdir(parents=True, exist_ok=True)
        for child in source.iterdir():
            _copy_item(child, target / child.name)
    elif source.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".v340tmp")
        shutil.copy2(source, temporary)
        temporary.replace(target)


def _backup_target(paths: list[str]) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = ROOT / ".local-backups" / f"v340-migration-{stamp}"
    backup.mkdir(parents=True, exist_ok=False)
    for relative in paths + ["VERSION"]:
        current = ROOT / relative
        if current.exists():
            _copy_item(current, backup / relative)
    return backup


def migrate(source: Path) -> dict[str, object]:
    paths = [relative for relative in DYNAMIC_FILES + DYNAMIC_DIRECTORIES if (source / relative).exists()]
    backup = _backup_target(paths)
    copied: list[str] = []
    for relative in paths:
        _copy_item(source / relative, ROOT / relative)
        copied.append(relative)
    manifest = {
        "version": "3.4.0", "migrated_from": str(source), "source_version": "3.3.3a",
        "backup": str(backup), "copied": copied, "created_at": datetime.now(timezone.utc).isoformat(),
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def rollback_migration() -> int:
    if not MANIFEST.exists():
        print("No existe manifiesto de migración v3.4; no se ha modificado nada.")
        return 1
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    backup = Path(str(manifest.get("backup") or "")).resolve()
    expected_root = (ROOT / ".local-backups").resolve()
    if expected_root not in backup.parents or not backup.is_dir():
        print("Backup de migración inválido; no se ha modificado nada.")
        return 1
    for relative in manifest.get("copied", []) + ["VERSION"]:
        source = backup / relative
        if source.exists():
            _copy_item(source, ROOT / relative)
    print(f"Datos previos a la migración restaurados desde {backup.name}. La aplicación sigue siendo v3.4; para volver a v3.3.3a use la carpeta preservada completa.")
    return 0


def main() -> int:
    args = parse_args()
    if args.rollback_migration:
        return rollback_migration()
    if _version(ROOT) not in {"3.4.0", "3.3.3a"}:
        print(f"ERROR · Versión de destino no compatible: {_version(ROOT) or 'sin VERSION'}", file=sys.stderr)
        return 2
    manifest = None
    if args.migrate_from:
        try:
            manifest = migrate(_safe_source(args.migrate_from))
        except (OSError, ValueError, json.JSONDecodeError) as error:
            print(f"ERROR · Migración cancelada de forma segura: {error}", file=sys.stderr)
            return 2
    (ROOT / "VERSION").write_text("3.4.0\n", encoding="utf-8")
    result = run(ROOT, "migration")
    errors = validate(ROOT)
    if errors:
        print("ERROR · v3.4 no supera validación: " + "; ".join(errors[:12]), file=sys.stderr)
        if manifest:
            print("Los datos previos siguen disponibles en el backup de migración; ejecute --rollback-migration si necesita restaurarlos.", file=sys.stderr)
        return 1
    print(
        "v3.4.0 aplicada correctamente · "
        f"{result.get('recommendations')} recomendaciones graduadas · {result.get('architectures')} arquitecturas · calidad {result.get('quality_status')}."
    )
    print("Siguiente paso: python tools/validar_v340.py")
    print("Tests: python -m unittest discover -s tests -p \"test*.py\" -v")
    print("UI: node scripts/ui_smoke.js && node tests/ui_smoke_v340.js")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
