from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable


def utc_id(prefix="r"):
    return datetime.now(timezone.utc).strftime(prefix + "%Y%m%dT%H%M%SZ")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class DatasetSnapshot:
    def __init__(self, repo_root: str | Path, data_dir: str = "data"):
        self.repo = Path(repo_root).resolve()
        self.data = self.repo / data_dir
        self.snapshots = self.repo / ".v31_snapshots"
        self.release_id = utc_id()
        self.snapshot_path = self.snapshots / self.release_id

    def create(self) -> Path:
        self.snapshots.mkdir(parents=True, exist_ok=True)
        if self.snapshot_path.exists():
            shutil.rmtree(self.snapshot_path)
        if self.data.exists():
            shutil.copytree(self.data, self.snapshot_path)
        else:
            self.snapshot_path.mkdir(parents=True)
        # Keep only the most recent snapshots in the runner workspace.
        old = sorted((p for p in self.snapshots.iterdir() if p.is_dir()), key=lambda p: p.name, reverse=True)
        for stale in old[4:]:
            shutil.rmtree(stale, ignore_errors=True)
        return self.snapshot_path

    def restore(self):
        if self.data.exists():
            shutil.rmtree(self.data)
        shutil.copytree(self.snapshot_path, self.data)

    def manifest(self) -> Dict[str, object]:
        files = []
        if self.data.exists():
            for p in sorted(self.data.rglob("*")):
                if p.is_file():
                    files.append({"path": str(p.relative_to(self.data)).replace(os.sep, "/"), "sha256": sha256_file(p), "bytes": p.stat().st_size})
        return {"release_id": self.release_id, "created_at": datetime.now(timezone.utc).isoformat(), "files": files}

    def write_release_manifest(self):
        target = self.data / "v31" / "release.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = self.manifest()
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload


def atomic_write_json(path: str | Path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
        tmp = Path(fh.name)
    os.replace(tmp, path)
