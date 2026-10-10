from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow direct execution as `python scripts/audit_atomic_provenance_hf6.py`
# from the repository root. In that mode Python places `scripts/` rather than
# the repository root on sys.path.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.model import canonical
from engine.provenance import evidence_for_item, evidence_for_relationship
from engine.storage import read_json

RELATION_FIELDS = {
    "manufacturers": {"distributors", "integrators"},
    "distributors": {"vendor_relations", "westcon_overlap", "competitor_vendor_overlap"},
    "integrators": {"vendor_relations", "westcon_overlap", "competitor_vendor_overlap"},
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()

    data = read_json("data/current/intelligence.json")
    graph = read_json("data/current/relationship_graph.json")

    bad_items = []
    web_cross = []
    for section in (
        "manufacturers", "distributors", "integrators",
        "clients_public", "clients_private", "trends", "architectures",
    ):
        for row in data.get(section) or []:
            owner = row.get("name")
            for field_id, field in (row.get("fields") or {}).items():
                raw = field.get("value")
                if not isinstance(raw, list):
                    continue
                item_map = {
                    canonical(item.get("value")): item
                    for item in field.get("items") or []
                    if isinstance(item, dict)
                }
                for value in raw:
                    item = item_map.get(canonical(value))
                    if not item:
                        continue
                    evidence = item.get("evidence") or []
                    if field_id in RELATION_FIELDS.get(section, set()):
                        if evidence and not evidence_for_relationship(evidence, owner, value):
                            bad_items.append((section, owner, field_id, value))
                    for ev in evidence:
                        if str(ev.get("method") or "").startswith("web-evidence:"):
                            if not evidence_for_item([ev], owner, value, field_id=field_id):
                                web_cross.append(
                                    (section, owner, field_id, value, ev.get("title") or ev.get("source"))
                                )

    bad_edges = []
    for rel in graph.get("relationships") or []:
        if rel.get("relation") not in {"distributes", "partners_with"}:
            continue
        if not evidence_for_relationship(
            rel.get("evidence") or [], rel.get("entity_a"), rel.get("entity_b")
        ):
            bad_edges.append((rel.get("entity_a"), rel.get("relation"), rel.get("entity_b")))

    print("HF6 atomic provenance audit")
    print(f" - mis-associated visible relationship items: {len(bad_items)}")
    print(f" - mis-associated web item evidences: {len(web_cross)}")
    print(f" - graph edges without endpoint-specific evidence: {len(bad_edges)}")

    examples = (
        [("item", row) for row in bad_items]
        + [("web", row) for row in web_cross]
        + [("edge", row) for row in bad_edges]
    )
    for kind, row in examples[: max(0, args.limit)]:
        print(f"   {kind}: " + " | ".join(str(x) for x in row))

    total = len(bad_items) + len(web_cross) + len(bad_edges)
    return 1 if args.strict and total else 0


if __name__ == "__main__":
    raise SystemExit(main())
