#!/usr/bin/env python3
"""Independent release checks for the v4.1 public-evidence + preservation contract.

HF10 removes two frozen snapshot assumptions from the original v4.1.0 release audit:
- preservation counters do not have to be byte-for-byte/equality identical after additive research;
- the research ledger is not required to contain exactly eight accepted evidences.

The release still fails on any *real* preserved-knowledge loss, any regression below the
v4.1.0 public-acceptance floor, or any internal/historical evidence leaked as accreditation.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Mapping

ROOT = Path(__file__).resolve().parents[1]
BASELINE_ACCEPTED_PUBLIC_EVIDENCES = 8
PUBLIC_SOURCE_ROLES = {
    "Fuente pública primaria",
    "Fuente pública secundaria / analista",
    "Fuente documental Westcon vigente",
    "Fuente Westcon vigente",
}
CURRENT_WESTCON_ORIGINS = {"WESTCON_DOCUMENT_CURRENT", "WESTCON_FIRST_PARTY_CURRENT"}
BLOCKED_ORIGINS = {
    "WESTCON_DOCUMENT",
    "RESEARCH_SEED",
    "HISTORICAL_RECOVERED",
    "ARCHIVE_RECOVERED",
    "ARCHIVE_CORROBORATION",
    "REPORT_CORROBORATION",
    "LEGACY_UNRESOLVED",
}
PROTECTED_MISSING_CLASSES = (
    "entities",
    "values",
    "evidences",
    "relations",
    "research_seed_claims",
    "floor_failures",
)


def load(relative: str, root: Path = ROOT) -> Any:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def evaluate_release_contract(
    manifest: Mapping[str, Any],
    preservation: Mapping[str, Any],
    ledger: Mapping[str, Any],
    section_loader: Callable[[str], Mapping[str, Any]],
) -> tuple[list[str], dict[str, Any]]:
    """Return (errors, stats) for the current public-evidence release contract."""
    errors: list[str] = []
    visible_evidence = 0
    historical_or_internal_visible = 0

    for info in (manifest.get("sections") or {}).values():
        if not isinstance(info, Mapping) or not info.get("file"):
            errors.append("public manifest contains section without file")
            continue
        payload = section_loader(str(info["file"]))
        for evidence in (payload.get("evidence") or {}).values():
            if not isinstance(evidence, Mapping):
                continue
            visible_evidence += 1
            origin = str(evidence.get("provenance_origin") or "").strip().upper()
            role = str(evidence.get("source_role") or "").strip()
            url = str(evidence.get("url") or "").strip()
            if origin in BLOCKED_ORIGINS:
                historical_or_internal_visible += 1
                errors.append(f"internal/historical evidence exposed as accreditation: {info['file']}")
            if role not in PUBLIC_SOURCE_ROLES:
                errors.append(f"invalid visible source role: {role or '<missing>'}")
            is_current_westcon = origin in CURRENT_WESTCON_ORIGINS
            if not url.startswith(("http://", "https://")) and not (
                is_current_westcon and (evidence.get("document_id") or evidence.get("statement_id"))
            ):
                errors.append(f"visible accrediting evidence has no public URL or current Westcon identity: {info['file']}")

    source_catalog = manifest.get("source_catalog") or []
    for source in source_catalog:
        if not isinstance(source, Mapping):
            errors.append("invalid public source catalogue row")
            continue
        source_class = str(source.get("class") or "").strip()
        url = str(source.get("url") or "").strip()
        if source_class not in PUBLIC_SOURCE_ROLES:
            errors.append(f"non-public accrediting catalog class: {source_class or '<missing>'}")
        westcon_catalog = source_class in {"Fuente documental Westcon vigente", "Fuente Westcon vigente"}
        if not url.startswith(("http://", "https://")) and not (
            westcon_catalog and (source.get("document_id") or source.get("statement_id"))
        ):
            errors.append(f"public source catalogue entry has no public URL/current Westcon identity: {source.get('name') or '<unnamed>'}")

    if preservation.get("status") != "PASS" or preservation.get("errors"):
        errors.append("knowledge preservation gate did not pass")

    missing = preservation.get("missing") or {}
    for key in PROTECTED_MISSING_CLASSES:
        rows = missing.get(key) or []
        if rows:
            errors.append(f"preservation still reports missing {key}: {len(rows)}")

    # Additive research is expected. Raw before/after equality is *not* a release invariant.
    # We only reject count regressions that contradict a PASS preservation report.
    before = preservation.get("before") or {}
    after = preservation.get("after") or {}
    for key in ("values", "evidences", "relations", "research_seed_claims"):
        old = _int(before.get(key))
        new = _int(after.get(key))
        if new < old:
            errors.append(f"preserved {key} count regressed: {old}->{new}")
    before_entities = before.get("entities") or {}
    after_entities = after.get("entities") or {}
    for section, old_raw in before_entities.items():
        old = _int(old_raw)
        new = _int(after_entities.get(section))
        if new < old:
            errors.append(f"preserved entity count regressed for {section}: {old}->{new}")

    accepted = _int(ledger.get("accepted_evidences"))
    accepted_rows = sum(
        _int(row.get("accepted"))
        for row in (ledger.get("results") or [])
        if isinstance(row, Mapping)
    )
    if accepted < BASELINE_ACCEPTED_PUBLIC_EVIDENCES:
        errors.append(
            f"accepted public evidence ledger regressed below v4.1.0 floor: "
            f"{accepted}<{BASELINE_ACCEPTED_PUBLIC_EVIDENCES}"
        )
    if accepted_rows < BASELINE_ACCEPTED_PUBLIC_EVIDENCES:
        errors.append(
            f"accepted public evidence result rows regressed below v4.1.0 floor: "
            f"{accepted_rows}<{BASELINE_ACCEPTED_PUBLIC_EVIDENCES}"
        )

    stats = {
        "visible_source_families": len(source_catalog),
        "visible_atomic_evidence": visible_evidence,
        "historical_or_internal_visible": historical_or_internal_visible,
        "preservation_status": preservation.get("status"),
        "before": dict(before),
        "after": dict(after),
        "accepted_evidences": accepted,
        "accepted_result_rows": accepted_rows,
        "baseline_floor": BASELINE_ACCEPTED_PUBLIC_EVIDENCES,
    }
    return errors, stats


def main(root: Path = ROOT) -> int:
    manifest = load("data/public/manifest.json", root)
    preservation = load("data/current/knowledge_preservation_v410.json", root)
    ledger = load("data/current/research_ledger.json", root)

    errors, stats = evaluate_release_contract(
        manifest,
        preservation,
        ledger,
        lambda relative: load(relative, root),
    )

    print("v4.1.0-HF10 release audit:", "PASS" if not errors else "FAIL")
    print(f" - visible public source families: {stats['visible_source_families']}")
    print(f" - visible atomic public evidence (section-deduplicated): {stats['visible_atomic_evidence']}")
    print(f" - internal/historical evidence exposed as accreditation: {stats['historical_or_internal_visible']}")
    print(f" - preservation: {stats['preservation_status']}")
    before = stats["before"]
    after = stats["after"]
    print(f" - values: {_int(before.get('values'))} -> {_int(after.get('values'))}")
    print(f" - public claim support: {_int(before.get('evidences'))} -> {_int(after.get('evidences'))}")
    print(f" - relations: {_int(before.get('relations'))} -> {_int(after.get('relations'))}")
    print(f" - research-seed claims: {_int(before.get('research_seed_claims'))} -> {_int(after.get('research_seed_claims'))}")
    print(
        " - accepted research evidences: "
        f"{stats['accepted_evidences']} (v4.1.0 floor >= {stats['baseline_floor']})"
    )
    for error in errors:
        print(" - ERROR:", error)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
