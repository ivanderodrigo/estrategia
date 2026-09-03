"""Scalable, transparent storage for the canonical intelligence dataset.

v4.2 keeps ``data/current/intelligence.json`` as a tiny compatibility pointer while the
real dataset is split into deterministic, bounded JSON shards. Existing callers continue
to use ``engine.storage.read_json``/``atomic_write_json``; the v4.2 compatibility hooks in
``engine.storage`` route that one canonical path through this module.

Design goals:
- no Git LFS dependency;
- no single newly generated shard should approach GitHub's 100 MiB hard limit;
- preserve *all* top-level keys and list/dict ordering;
- atomic per-file replacement and a manifest with semantic hashes;
- legacy monoliths remain readable and can be migrated losslessly.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Mapping

FORMAT = "westcon-sharded-v1"
LEGACY_PATH = Path("data/current/intelligence.json")
STORE_DIR = Path("data/current/intelligence_store")
MANIFEST_PATH = STORE_DIR / "manifest.json"
DEFAULT_TARGET_BYTES = 8 * 1024 * 1024
MAX_SAFE_SHARD_BYTES = 25 * 1024 * 1024


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value).strip("-.")
    return cleaned or "key"


def _split_list(values: list[Any], target_bytes: int) -> list[list[Any]]:
    if not values:
        return [[]]
    chunks: list[list[Any]] = []
    current: list[Any] = []
    current_size = 2
    for item in values:
        encoded = _json_bytes(item)
        estimated = len(encoded) + (1 if current else 0)
        if current and current_size + estimated > target_bytes:
            chunks.append(current)
            current = []
            current_size = 2
        current.append(item)
        current_size += estimated
    if current:
        chunks.append(current)
    return chunks


def _split_dict(values: Mapping[str, Any], target_bytes: int) -> list[dict[str, Any]]:
    if not values:
        return [{}]
    chunks: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    current_size = 2
    for key, item in values.items():
        encoded = _json_bytes({str(key): item})
        estimated = max(1, len(encoded) - 1)
        if current and current_size + estimated > target_bytes:
            chunks.append(current)
            current = {}
            current_size = 2
        current[str(key)] = item
        current_size += estimated
    if current:
        chunks.append(current)
    return chunks


def intelligence_files(
    data: Mapping[str, Any],
    *,
    target_bytes: int = DEFAULT_TARGET_BYTES,
    legacy_path: Path = LEGACY_PATH,
    store_dir: Path = STORE_DIR,
) -> tuple[dict[str, bytes], dict[str, Any]]:
    """Serialize the dataset into bounded shards plus a tiny legacy compatibility stub.

    Returns a mapping suitable for ``atomic_write_many`` and a storage report. Paths are
    strings relative to the repository root when the default paths are used.
    """
    target_bytes = max(4 * 1024, int(target_bytes))
    files: dict[str, bytes] = {}
    entries: dict[str, Any] = {}
    key_order = list(data.keys())
    largest = 0
    logical_bytes = len(_json_bytes(dict(data)))

    for ordinal, key in enumerate(key_order):
        value = data[key]
        slug = f"{ordinal:02d}-{_slug(str(key))}"
        if isinstance(value, list):
            kind = "list"
            chunks: list[Any] = _split_list(value, target_bytes)
        elif isinstance(value, Mapping):
            kind = "dict"
            chunks = _split_dict(value, target_bytes)
        else:
            kind = "scalar"
            chunks = [value]

        part_files: list[str] = []
        part_hashes: list[str] = []
        for index, chunk in enumerate(chunks):
            relative = store_dir / f"{slug}.part-{index:04d}.json"
            encoded = _json_bytes(chunk)
            largest = max(largest, len(encoded))
            rel = relative.as_posix()
            files[rel] = encoded
            part_files.append(rel)
            part_hashes.append(hashlib.sha256(encoded).hexdigest())
        entries[str(key)] = {
            "kind": kind,
            "parts": part_files,
            "part_sha256": part_hashes,
            "items": len(value) if isinstance(value, (list, Mapping)) else 1,
            "semantic_sha256": _sha(value),
        }

    manifest = {
        "format": FORMAT,
        "version": 1,
        "logical_sha256": _sha(dict(data)),
        "logical_bytes": logical_bytes,
        "target_shard_bytes": target_bytes,
        "keys_order": key_order,
        "entries": entries,
    }
    manifest_bytes = _json_bytes(manifest)
    manifest_rel = (store_dir / "manifest.json").as_posix()
    files[manifest_rel] = manifest_bytes
    active_files = set(files)
    stub = {
        "storage_format": FORMAT,
        "manifest": manifest_rel,
        "logical_sha256": manifest["logical_sha256"],
        "note": "Canonical intelligence is stored in bounded shards; load through engine.storage.read_json.",
    }
    stub_bytes = _json_bytes(stub)
    files[legacy_path.as_posix()] = stub_bytes
    active_files.add(legacy_path.as_posix())

    report = {
        "format": FORMAT,
        "logical_bytes": logical_bytes,
        "stub_bytes": len(stub_bytes),
        "manifest_bytes": len(manifest_bytes),
        "shards": sum(len(entry["parts"]) for entry in entries.values()),
        "largest_shard_bytes": largest,
        "active_files": sorted(active_files),
        "logical_sha256": manifest["logical_sha256"],
    }
    return files, report


def _resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _read_json_file(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_intelligence(
    default: Any = None,
    *,
    root: Path | str = Path("."),
    legacy_path: Path = LEGACY_PATH,
) -> Any:
    root = Path(root)
    legacy = _resolve(root, legacy_path)
    raw = _read_json_file(legacy, default)
    if not isinstance(raw, Mapping) or raw.get("storage_format") != FORMAT:
        return raw
    manifest_ref = str(raw.get("manifest") or MANIFEST_PATH.as_posix())
    manifest_path = _resolve(root, manifest_ref)
    manifest = _read_json_file(manifest_path)
    if not isinstance(manifest, Mapping) or manifest.get("format") != FORMAT:
        raise ValueError(f"Invalid intelligence shard manifest: {manifest_path}")

    output: dict[str, Any] = {}
    entries = manifest.get("entries") or {}
    for key in manifest.get("keys_order") or []:
        entry = entries.get(key) or {}
        kind = entry.get("kind")
        parts = entry.get("parts") or []
        if kind == "list":
            value: Any = []
            for part in parts:
                chunk = _read_json_file(_resolve(root, part), [])
                if not isinstance(chunk, list):
                    raise ValueError(f"Invalid list intelligence shard: {part}")
                value.extend(chunk)
        elif kind == "dict":
            value = {}
            for part in parts:
                chunk = _read_json_file(_resolve(root, part), {})
                if not isinstance(chunk, Mapping):
                    raise ValueError(f"Invalid dict intelligence shard: {part}")
                value.update(chunk)
        elif kind == "scalar":
            if len(parts) != 1:
                raise ValueError(f"Invalid scalar shard count for {key}")
            value = _read_json_file(_resolve(root, parts[0]))
        else:
            raise ValueError(f"Unsupported intelligence shard kind for {key}: {kind}")
        output[str(key)] = value
    return output


def cleanup_stale_shards(
    active_files: list[str] | set[str],
    *,
    root: Path | str = Path("."),
    store_dir: Path = STORE_DIR,
) -> int:
    root = Path(root)
    active = {_resolve(root, value).resolve() for value in active_files}
    directory = _resolve(root, store_dir)
    if not directory.exists():
        return 0
    removed = 0
    for path in directory.glob("*.json"):
        if path.resolve() not in active:
            path.unlink()
            removed += 1
    return removed


def write_intelligence(
    data: Mapping[str, Any],
    *,
    root: Path | str = Path("."),
    target_bytes: int = DEFAULT_TARGET_BYTES,
) -> dict[str, Any]:
    root = Path(root)
    files, report = intelligence_files(data, target_bytes=target_bytes)
    # Shards and manifest first; compatibility pointer last.
    stub_key = LEGACY_PATH.as_posix()
    for relative, content in files.items():
        if relative == stub_key:
            continue
        _atomic_write(_resolve(root, relative), content)
    _atomic_write(_resolve(root, stub_key), files[stub_key])
    report["stale_shards_removed"] = cleanup_stale_shards(report["active_files"], root=root)
    return report


def migrate_legacy(
    *,
    root: Path | str = Path("."),
    target_bytes: int = DEFAULT_TARGET_BYTES,
) -> dict[str, Any]:
    root = Path(root)
    legacy = _resolve(root, LEGACY_PATH)
    raw = _read_json_file(legacy)
    if not isinstance(raw, Mapping):
        raise ValueError("Canonical intelligence.json is missing or invalid")
    if raw.get("storage_format") == FORMAT:
        report = audit_store(root=root)
        report["migrated"] = False
        return report
    before_hash = _sha(raw)
    report = write_intelligence(raw, root=root, target_bytes=target_bytes)
    loaded = load_intelligence(root=root)
    after_hash = _sha(loaded)
    if before_hash != after_hash:
        raise ValueError("Intelligence migration changed the semantic dataset")
    report["migrated"] = True
    return report


def audit_store(*, root: Path | str = Path("."), max_shard_bytes: int = MAX_SAFE_SHARD_BYTES) -> dict[str, Any]:
    root = Path(root)
    stub = _read_json_file(_resolve(root, LEGACY_PATH))
    errors: list[str] = []
    if not isinstance(stub, Mapping) or stub.get("storage_format") != FORMAT:
        return {"status": "FAIL", "errors": ["intelligence.json is not a v4.2 shard pointer"]}
    manifest_path = _resolve(root, str(stub.get("manifest") or MANIFEST_PATH.as_posix()))
    manifest = _read_json_file(manifest_path)
    if not isinstance(manifest, Mapping) or manifest.get("format") != FORMAT:
        return {"status": "FAIL", "errors": ["intelligence shard manifest missing or invalid"]}

    largest = 0
    total = 0
    shards = 0
    entries = manifest.get("entries") or {}
    for key in manifest.get("keys_order") or []:
        entry = entries.get(key) or {}
        parts = list(entry.get("parts") or [])
        hashes = list(entry.get("part_sha256") or [])
        if len(parts) != len(hashes):
            errors.append(f"shard hash list mismatch: {key}")
            continue
        for relative, expected_hash in zip(parts, hashes):
            path = _resolve(root, relative)
            if not path.exists():
                errors.append(f"missing intelligence shard: {relative}")
                continue
            payload = path.read_bytes()
            shards += 1
            total += len(payload)
            largest = max(largest, len(payload))
            if hashlib.sha256(payload).hexdigest() != expected_hash:
                errors.append(f"intelligence shard hash mismatch: {relative}")
            if len(payload) > max_shard_bytes:
                errors.append(f"intelligence shard exceeds safe limit: {relative} ({len(payload)} bytes)")

    loaded = load_intelligence(root=root)
    logical_hash = _sha(loaded)
    if logical_hash != manifest.get("logical_sha256"):
        errors.append("reconstructed intelligence semantic hash differs from manifest")
    stub_bytes = _resolve(root, LEGACY_PATH).stat().st_size
    if stub_bytes > 1024 * 1024:
        errors.append(f"intelligence.json compatibility pointer is unexpectedly large: {stub_bytes}")
    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "format": FORMAT,
        "stub_bytes": stub_bytes,
        "shards": shards,
        "stored_shard_bytes": total,
        "largest_shard_bytes": largest,
        "logical_bytes": int(manifest.get("logical_bytes") or 0),
        "logical_sha256": logical_hash,
    }
