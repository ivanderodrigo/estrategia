"""Crash-safe JSON persistence and a cross-platform process lock."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, Iterable

from .settings import ROOT


_MISSING = object()


def resolve_path(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else ROOT / candidate


def read_json(path: str | Path, default: Any = _MISSING) -> Any:
    """Read UTF-8 JSON; malformed canonical files fail loudly."""

    target = resolve_path(path)
    try:
        return json.loads(target.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, json.JSONDecodeError, UnicodeError):
        if default is _MISSING:
            raise
        return default


def json_bytes(value: Any, *, pretty: bool = True) -> bytes:
    separators = None if pretty else (",", ":")
    text = json.dumps(
        value,
        ensure_ascii=False,
        indent=2 if pretty else None,
        separators=separators,
    )
    return (text + ("\n" if pretty else "")).encode("utf-8")


def atomic_write_bytes(path: str | Path, payload: bytes) -> None:
    target = resolve_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)


def atomic_write_json(path: str | Path, value: Any, *, pretty: bool = True) -> None:
    atomic_write_bytes(path, json_bytes(value, pretty=pretty))


def atomic_write_many(files: dict[str | Path, bytes]) -> None:
    """Prepare every file first and roll back if replacement fails."""

    if not files:
        return
    runtime = ROOT / ".runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    # Keep staging on the project filesystem: os.replace is then atomic even when the
    # operating system's global temporary directory lives on another volume.
    staging = Path(tempfile.mkdtemp(prefix="westcon-publish-", dir=runtime))
    prepared: list[tuple[Path, Path]] = []
    backups: list[tuple[Path, Path | None]] = []
    try:
        for index, (raw_target, payload) in enumerate(files.items()):
            target = resolve_path(raw_target)
            target.parent.mkdir(parents=True, exist_ok=True)
            staged = staging / f"new-{index:04d}"
            with staged.open("wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            prepared.append((target, staged))

        for index, (target, staged) in enumerate(prepared):
            backup = staging / f"old-{index:04d}" if target.exists() else None
            if backup:
                shutil.copy2(target, backup)
            backups.append((target, backup))
            os.replace(staged, target)
    except Exception:
        for target, backup in reversed(backups):
            if backup and backup.exists():
                os.replace(backup, target)
            elif backup is None:
                target.unlink(missing_ok=True)
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)


class ProcessLock(AbstractContextManager["ProcessLock"]):
    """One research/build process at a time on Linux, macOS and Windows."""

    def __init__(self, path: str | Path = ".runtime/research.lock", timeout_s: int = 30):
        self.path = resolve_path(path)
        self.timeout_s = max(0, timeout_s)
        self._handle: Any = None

    def __enter__(self) -> "ProcessLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a+b")
        deadline = time.monotonic() + self.timeout_s
        while True:
            try:
                if os.name == "nt":
                    import msvcrt

                    self._handle.seek(0)
                    msvcrt.locking(self._handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except (BlockingIOError, OSError):
                if time.monotonic() >= deadline:
                    self._handle.close()
                    raise TimeoutError(f"Another research process holds {self.path}")
                time.sleep(0.25)

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if not self._handle:
            return
        try:
            if os.name == "nt":
                import msvcrt

                self._handle.seek(0)
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._handle.close()


def prune_json_mapping(mapping: dict[str, Any], *, limit: int, timestamp_key: str) -> dict[str, Any]:
    ordered: Iterable[tuple[str, Any]] = sorted(
        mapping.items(),
        key=lambda item: float(item[1].get(timestamp_key, 0)) if isinstance(item[1], dict) else 0,
        reverse=True,
    )
    return dict(list(ordered)[:limit])

# v4.2 transparent canonical-intelligence store
# Existing code keeps using read_json/atomic_write_json. Only the canonical intelligence
# path is routed to bounded shards; all other storage semantics remain untouched.
_v420_base_read_json = read_json
_v420_base_atomic_write_json = atomic_write_json


def _v420_intelligence_path(path) -> bool:
    value = str(path).replace("\\", "/").lstrip("./")
    return value == "data/current/intelligence.json"


def read_json(path, default=None):
    if _v420_intelligence_path(path):
        from .intelligence_store import load_intelligence
        return load_intelligence(default)
    return _v420_base_read_json(path, default)


def atomic_write_json(path, data, pretty=True):
    if _v420_intelligence_path(path):
        from .intelligence_store import write_intelligence
        return write_intelligence(data)
    return _v420_base_atomic_write_json(path, data, pretty=pretty)
