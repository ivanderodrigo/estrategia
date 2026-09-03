#!/usr/bin/env python3
"""Apply narrowly-scoped v4.2 compatibility hooks to the validated v4.1/HF11 runtime.

The upgrader refuses to continue when expected semantic anchors are absent. This avoids
blindly overwriting a newer/unknown engine while still allowing data-only research commits.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str, *, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new and new in text:
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one patch anchor in {path}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_storage() -> None:
    path = ROOT / "engine/storage.py"
    text = path.read_text(encoding="utf-8")
    marker = "# v4.2 transparent canonical-intelligence store"
    if marker in text:
        return
    hook = r'''

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
'''
    path.write_text(text.rstrip() + hook.rstrip() + "\n", encoding="utf-8")


def patch_pipeline() -> None:
    path = ROOT / "engine/pipeline.py"
    replace_once(
        path,
        "from .storage import atomic_write_many, json_bytes, read_json\n",
        "from .storage import atomic_write_many, json_bytes, read_json\nfrom .intelligence_store import cleanup_stale_shards, intelligence_files\n",
        label="pipeline storage import",
    )
    replace_once(
        path,
        '        "unknown_research_gaps": int(gaps.get("unknown_research_gaps") or 0),\n',
        '        "unknown_research_gaps": int(gaps.get("unknown_research_gaps") or 0),\n'
        '        "business_weighted_coverage_pct": float((gaps.get("business_priority") or {}).get("business_weighted_coverage_pct") or 0),\n'
        '        "priority_gaps_p0": int(((gaps.get("business_priority") or {}).get("tiers") or {}).get("P0") or 0),\n'
        '        "priority_gaps_p1": int(((gaps.get("business_priority") or {}).get("tiers") or {}).get("P1") or 0),\n',
        label="pipeline gap metrics",
    )
    replace_once(
        path,
        "    last_run = {\n",
        "    internal_files, internal_store = intelligence_files(data)\n\n    last_run = {\n",
        label="pipeline prepare shard serialization",
    )
    replace_once(
        path,
        "    internal_data = json_bytes(data, pretty=False)\n",
        "",
        label="pipeline remove monolith serialization",
    )
    replace_once(
        path,
        '        "internal_intelligence_bytes": len(internal_data),\n',
        '        "internal_intelligence_bytes": internal_store["logical_bytes"],\n'
        '        "internal_storage_bytes": sum(len(value) for value in internal_files.values()),\n'
        '        "internal_storage_shards": internal_store["shards"],\n'
        '        "internal_largest_shard_bytes": internal_store["largest_shard_bytes"],\n'
        '        "internal_stub_bytes": internal_store["stub_bytes"],\n',
        label="pipeline storage metrics",
    )
    replace_once(
        path,
        '        "data/current/intelligence.json": internal_data,\n',
        "",
        label="pipeline remove monolith file",
    )
    replace_once(
        path,
        "    files.update(public_files)\n    atomic_write_many(files)\n",
        "    files.update(public_files)\n    files.update(internal_files)\n    atomic_write_many(files)\n    cleanup_stale_shards(internal_store[\"active_files\"])\n",
        label="pipeline sharded publication",
    )
    replace_once(
        path,
        '        "knowledge_preservation": preservation,\n',
        '        "knowledge_preservation": preservation,\n'
        '        "gap_priority": gaps.get("business_priority") or {},\n'
        '        "intelligence_storage": {\n'
        '            "format": internal_store.get("format"),\n'
        '            "logical_bytes": internal_store.get("logical_bytes"),\n'
        '            "shards": internal_store.get("shards"),\n'
        '            "largest_shard_bytes": internal_store.get("largest_shard_bytes"),\n'
        '        },\n',
        label="pipeline last_run intelligence",
    )


def patch_web_research() -> None:
    path = ROOT / "engine/research/web_intelligence.py"
    # Patch the semantic call itself rather than its surrounding assignment/expression.
    # HF11/c2b1e54 calls seeds_for(...) inside _merge_source_seeds(...), while some
    # earlier v4.1 builds assigned it to a local variable. Both are equivalent targets.
    replace_once(
        path,
        'seeds_for(row, target["fields"])',
        'seeds_for(row, target["fields"], target=target)',
        label="web research gap-aware source seeds",
    )
    # Same principle for the family selector: do not depend on the local variable name.
    replace_once(
        path,
        'relevant_families(target["fields"])',
        'relevant_families(target["fields"]) | set(target.get("source_families") or [])',
        label="web research source-playbook traversal",
    )


def main() -> int:
    patch_storage()
    patch_pipeline()
    patch_web_research()
    print("v4.2 runtime patch: PASS")
    print(" - storage.py: transparent sharded canonical intelligence")
    print(" - pipeline.py: direct shard publication + business-priority metrics")
    print(" - web_intelligence.py: gap-aware source seeds + source-playbook traversal")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
