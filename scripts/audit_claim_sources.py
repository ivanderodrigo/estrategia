"""Conservative claim-to-source audit of published observatory evidence.

Three distinct checks: reference resolves, evidence explicitly binds the claim,
and extracted source metadata mentions the exact claim value. This is NOT a
substitute for re-fetching and reading the original document.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any


SECTIONS = ("manufacturers", "distributors", "integrators", "clients_public",
            "clients_private", "trends", "architectures")


def normal(text: Any) -> str:
    value = unicodedata.normalize("NFKD", str(text or "").casefold())
    value = "".join(c for c in value if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+", value))


def text_mentions(haystack: str, needle: str) -> bool:
    n = normal(needle)
    return bool(n and len(n) >= 3 and f" {n} " in f" {normal(haystack)} ")


def check_reference(
    evidence: dict[str, Any], *,
    entity: str, field_name: str, item_value: Any,
) -> str:
    """Return validation level, never claim that a page was visited."""
    url = str(evidence.get("url") or "")
    kind = str(evidence.get("provenance_origin") or "").upper()
    if not url.startswith(("https://", "http://")) and kind not in {
        "WESTCON_DOCUMENT_CURRENT", "WESTCON_FIRST_PARTY_CURRENT",
    }:
        return "unverifiable_locator"
    declared_entity = evidence.get("researched_entity") or evidence.get("subject_entity")
    if declared_entity and normal(declared_entity) != normal(entity):
        return "entity_mismatch"
    declared_field = evidence.get("field")
    if declared_field and str(declared_field) != field_name:
        return "field_mismatch"
    declared_item = evidence.get("item_value")
    if declared_item is not None and normal(declared_item) != normal(item_value):
        return "item_mismatch"
    if not declared_field or declared_item in (None, ""):
        return "generic_not_atomic"
    excerpt = " ".join(str(evidence.get(key) or "") for key in
                       ("description", "snippet", "quote", "matched_text"))
    if isinstance(item_value, str) and text_mentions(excerpt, item_value):
        return "metadata_text_support"
    return "bound_text_unconfirmed"


def audit_section(payload: dict[str, Any], *, sample_limit: int = 20) -> dict[str, Any]:
    registry = payload.get("evidence") or {}
    counters: Counter[str] = Counter()
    examples: list[dict[str, Any]] = []
    for row in payload.get("rows") or []:
        if not isinstance(row, dict):
            continue
        entity = str(row.get("name") or "")
        for field_name, field in (row.get("fields") or {}).items():
            if not isinstance(field, dict):
                continue
            claims = field.get("items") if isinstance(field.get("value"), list) else [field]
            if not isinstance(claims, list):
                claims = [field]
            for claim in claims:
                if not isinstance(claim, dict) or claim.get("value") in (None, "", [], {}):
                    continue
                counters["claims"] += 1
                refs = claim.get("evidence_ids") or []
                if not refs:
                    counters["without_source"] += 1
                    continue
                statuses = []
                for ref in refs:
                    ev = registry.get(ref)
                    if not isinstance(ev, dict):
                        statuses.append("broken_reference")
                    else:
                        statuses.append(check_reference(ev, entity=entity,
                            field_name=field_name, item_value=claim["value"]))
                for status in set(statuses):
                    counters["references_" + status] += 1
                if "metadata_text_support" in statuses:
                    outcome = "metadata_text_support"
                elif "bound_text_unconfirmed" in statuses:
                    outcome = "bound_text_unconfirmed"
                elif "generic_not_atomic" in statuses:
                    outcome = "generic_not_atomic"
                else:
                    outcome = "mismatch_or_broken"
                counters[outcome] += 1
                if outcome != "metadata_text_support" and len(examples) < sample_limit:
                    examples.append({"entity": entity, "field": field_name,
                                     "value": str(claim["value"])[:120],
                                     "outcome": outcome, "references": refs[:3]})
    return {"counts": dict(counters), "examples": examples,
            "source_page_content_verified": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("data/public"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = {"method": "offline-claim-binding-and-excerpt-audit",
              "disclaimer": "A source link or snippet does not prove the live document supports the claim.",
              "sections": {}}
    for section in SECTIONS:
        path = args.root / "sections" / (section + ".json")
        if path.exists():
            report["sections"][section] = audit_section(json.loads(path.read_text(encoding="utf-8")))
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
