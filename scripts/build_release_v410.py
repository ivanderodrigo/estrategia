#!/usr/bin/env python3
"""Build deterministic full and overlay upgrade archives for v4.1.0."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {".git", ".runtime", ".research_cache", ".upgrade-backups", "__pycache__"}
GENERATED_PREFIXES = ("data/current/", "data/public/")
PIPELINE_TARGETS = [
    "data/current/intelligence.json",
    "data/current/research_state.json",
    "data/current/relationship_graph.json",
    "data/current/research_gaps.json",
    "data/current/metrics_before_after.json",
    "data/current/coverage_report.json",
    "data/current/source_report.json",
    "data/current/provenance_report.json",
    "data/current/source_rationalization.json",
    "data/current/knowledge_preservation_v410.json",
    "data/current/quality_report.json",
    "data/current/last_run.json",
    "data/public/manifest.json",
    "data/public/last_run.json",
    "data/public/sections/manufacturers.json",
    "data/public/sections/distributors.json",
    "data/public/sections/integrators.json",
    "data/public/sections/clients_public.json",
    "data/public/sections/clients_private.json",
    "data/public/sections/trends.json",
    "data/public/sections/architectures.json",
]


def files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix == ".pyc":
            continue
        relative = path.relative_to(root)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        yield relative


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def changed_payload(baseline: Path) -> list[Path]:
    output = []
    for relative in files(ROOT):
        posix = relative.as_posix()
        if posix.startswith(GENERATED_PREFIXES) or posix.startswith("release/v410/"):
            continue
        current = ROOT / relative
        old = baseline / relative
        if not old.is_file() or digest(current) != digest(old):
            output.append(relative)
    return output


def add_file(archive: zipfile.ZipFile, source: Path, target: str) -> None:
    info = zipfile.ZipInfo(target, (2026, 9, 2, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, source.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def build(baseline: Path, output: Path) -> tuple[Path, Path]:
    output.mkdir(parents=True, exist_ok=True)
    upgrade = output / "westcon-decision-intelligence-v4.1.0-upgrade.zip"
    full = output / "westcon-decision-intelligence-v4.1.0-full.zip"
    payload = changed_payload(baseline)
    manifest = {
        "product": "Westcon Iberia Decision Intelligence",
        "baseline": "4.0.6-44abf7d",
        "target": "4.1.0",
        "policy": "overlay code/config/frontend, then rebuild target-owned current data transactionally",
        "payload_files": [
            {"path": row.as_posix(), "sha256": digest(ROOT / row)} for row in payload
        ],
        "pipeline_targets": PIPELINE_TARGETS,
    }

    with tempfile.TemporaryDirectory(prefix="westcon-v410-") as directory:
        manifest_path = Path(directory) / "upgrade-manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        with zipfile.ZipFile(upgrade, "w") as archive:
            for name in ("INSTALL_UPGRADE.ps1", "ROLLBACK.ps1", "README_INSTALL.txt"):
                add_file(archive, ROOT / "release/v410" / name, name)
            add_file(archive, manifest_path, "upgrade-manifest.json")
            for relative in payload:
                add_file(archive, ROOT / relative, f"payload/{relative.as_posix()}")

    prefix = "westcon-decision-intelligence-v4.1.0"
    with zipfile.ZipFile(full, "w") as archive:
        for relative in files(ROOT):
            add_file(archive, ROOT / relative, f"{prefix}/{relative.as_posix()}")
    return upgrade, full


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    baseline = args.baseline.resolve()
    if not (baseline / "VERSION").is_file() or (baseline / "VERSION").read_text(encoding="utf-8").strip() != "4.0.6":
        raise SystemExit("--baseline must point to the extracted v4.0.6 repository")
    upgrade, full = build(baseline, args.output.resolve())
    for path in (upgrade, full):
        print(f"{path.name}  {digest(path)}  {path.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
