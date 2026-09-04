#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_exact(path: Path, old: str, new: str, *, expected: int = 1, label: str = "patch") -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count == 0 and new in text:
        return
    if count != expected:
        raise RuntimeError(f"{label}: expected {expected} anchor(s) in {path}, found {count}")
    path.write_text(text.replace(old, new, expected), encoding="utf-8", newline="\n")


def patch_version_and_frontend() -> None:
    version = ROOT / "VERSION"
    current = version.read_text(encoding="utf-8").strip()
    if current not in {"4.2.2", "4.3.0"}:
        raise RuntimeError(f"VERSION must be 4.2.2 before upgrade, found {current}")
    version.write_text("4.3.0\n", encoding="utf-8", newline="\n")

    for rel in ("index.html", "assets/app/intelligence.js"):
        path = ROOT / rel
        text = path.read_text(encoding="utf-8")
        text = text.replace("4.2.2", "4.3.0")
        path.write_text(text, encoding="utf-8", newline="\n")

    css = ROOT / "assets/app/intelligence.css"
    text = css.read_text(encoding="utf-8")
    text = text.replace("/* v4.2.2 · professional table analysis surface */", "/* v4.3.0 · professional table analysis surface */")
    css.write_text(text, encoding="utf-8", newline="\n")

    smoke = ROOT / "tests/ui_smoke.js"
    if smoke.exists():
        text = smoke.read_text(encoding="utf-8").replace("4.2.2", "4.3.0")
        smoke.write_text(text, encoding="utf-8", newline="\n")

    validate = ROOT / "scripts/validate.py"
    text = validate.read_text(encoding="utf-8").replace("v4.2.2 canonical validation", "v4.3.0 canonical validation")
    validate.write_text(text, encoding="utf-8", newline="\n")

    readme = ROOT / "README.md"
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        text = text.replace("# Westcon Iberia Decision Intelligence — v4.0.0", "# Westcon Iberia Decision Intelligence — v4.3.0")
        if "## v4.3.0 — Research ROI & Controlled Growth" not in text:
            text += "\n\n## v4.3.0 — Research ROI & Controlled Growth\nLa investigación prioriza rendimiento por intento y limita el crecimiento estructurado por perfil para evitar que nuevas entidades generen más deuda de la que la plataforma puede resolver.\n"
        readme.write_text(text, encoding="utf-8", newline="\n")


def patch_policy() -> None:
    path = ROOT / "config/current/research_policy.json"
    policy = json.loads(path.read_text(encoding="utf-8"))
    policy["version"] = 2
    policy["structured_growth_limits"] = {"daily": 24, "deep": 100, "exhaustive": 220}
    policy["research_roi_policy"] = {
        "enabled": True,
        "principle": "close valuable debt before expanding breadth; transport success is not intelligence success",
        "primary_metrics": [
            "accepted_evidence_per_fetch_attempt",
            "candidate_acceptance_rate",
            "values_per_accepted_evidence",
            "structured_entities_added",
            "low_context_public_gaps",
            "public_validation_gaps",
        ],
        "low_context_public_tier_ceiling": "P2",
    }
    policy["entity_growth_policy"] = (
        "structured TED growth is bounded per research profile; unstructured external entities remain candidates until corroborated"
    )
    path.write_text(json.dumps(policy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    priority_path = ROOT / "config/current/research_priority_v420.json"
    if priority_path.exists():
        config = json.loads(priority_path.read_text(encoding="utf-8"))
        config["version"] = "4.3.0"
        config["controlled_growth"] = {
            "structured_entity_budget": {"daily": 24, "deep": 100, "exhaustive": 220},
            "low_context_public_tier_ceiling": "P2",
            "learning_signal": "accepted evidence per attempted page, relevance and transport success",
        }
        config["principle"] = (
            "Priorizar inteligencia que cambie decisiones de negocio, cerrar deuda valiosa antes de ampliar cobertura y "
            "hacer crecer el universo solo con señales estructuradas y presupuestos explícitos."
        )
        priority_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def patch_planner() -> None:
    path = ROOT / "engine/research/planner.py"
    old = '''def _learning_yield(learning: dict[str, Any], section: str, family: str) -> float:\n    stats = (learning.get("families") or {}).get(f"{section}:{family}") or {}\n    relevant = int(stats.get("pages_relevant") or 0)\n    accepted = int(stats.get("accepted_evidence") or 0)\n    if relevant <= 0:\n        return 0.62\n    return min(1.15, 0.30 + accepted / max(1, relevant))\n'''
    new = '''def _learning_yield(learning: dict[str, Any], section: str, family: str) -> float:\n    \"\"\"Reward source families that turn attempts into accepted evidence, not merely HTTP success.\"\"\"\n    stats = (learning.get("families") or {}).get(f"{section}:{family}") or {}\n    attempts = int(stats.get("attempts") or 0)\n    successes = int(stats.get("fetch_successes") or 0)\n    relevant = int(stats.get("pages_relevant") or 0)\n    accepted = int(stats.get("accepted_evidence") or 0)\n    if attempts <= 0:\n        return 0.66\n    evidence_per_attempt = accepted / max(1, attempts)\n    relevance_per_attempt = relevant / max(1, attempts)\n    transport_success = successes / max(1, attempts)\n    score = (\n        0.34\n        + min(0.48, evidence_per_attempt * 4.0)\n        + min(0.20, relevance_per_attempt * 0.8)\n        + min(0.12, transport_success * 0.2)\n    )\n    return max(0.35, min(1.18, score))\n'''
    replace_exact(path, old, new, label="planner ROI learning")


def patch_gap_intelligence() -> None:
    path = ROOT / "engine/gap_intelligence.py"
    old = '''    score = round(min(100.0, raw / 3.5 * 100), 1)\n    family = family_for(field, section)\n'''
    new = '''    score = round(min(100.0, raw / 3.5 * 100), 1)\n    # v4.3 controlled-growth guard: a newly discovered public buyer with little\n    # opportunity context must not become high-priority merely because the schema\n    # contains valuable fields. Exact public-validation debt is exempt.\n    low_context_public = (\n        section == "clients_public"\n        and gap.get("gap_kind") != "public-validation"\n        and opportunity_multiplier <= 1.05\n    )\n    if low_context_public:\n        score = min(score, 57.9)  # P2 ceiling; no artificial section quota.\n    family = family_for(field, section)\n'''
    replace_exact(path, old, new, label="gap low-context guard")

    old2 = '''    p0p1 = [gap for gap in gaps if gap.get("priority_tier") in {"P0", "P1"}]\n    public_p0p1 = sum(1 for gap in p0p1 if gap.get("section") == "clients_public")\n    return {\n'''
    new2 = '''    p0p1 = [gap for gap in gaps if gap.get("priority_tier") in {"P0", "P1"}]\n    public_p0p1 = sum(1 for gap in p0p1 if gap.get("section") == "clients_public")\n    low_context_public = [\n        gap for gap in gaps\n        if gap.get("section") == "clients_public"\n        and float(gap.get("opportunity_context_multiplier") or 1.0) <= 1.05\n    ]\n    context_rich_public = [\n        gap for gap in gaps\n        if gap.get("section") == "clients_public"\n        and float(gap.get("opportunity_context_multiplier") or 1.0) > 1.15\n    ]\n    low_context_public_high = [gap for gap in low_context_public if gap.get("priority_tier") in {"P0", "P1"}]\n    return {\n'''
    replace_exact(path, old2, new2, label="gap ROI counters")

    old3 = '''        "clients_public_share_of_p0_p1_pct": round(public_p0p1 * 100 / max(1, len(p0p1)), 2),\n    }\n'''
    new3 = '''        "clients_public_share_of_p0_p1_pct": round(public_p0p1 * 100 / max(1, len(p0p1)), 2),\n        "low_context_public_gaps": len(low_context_public),\n        "low_context_public_p0_p1": len(low_context_public_high),\n        "context_rich_public_gaps": len(context_rich_public),\n        "controlled_growth_policy": "bounded-structured-growth-v1",\n    }\n'''
    replace_exact(path, old3, new3, label="gap ROI report")


def _patch_web_text(text: str) -> str:
    """Upgrade the v4.2.2 TED block without depending on a deadline wrapper.

    The production runner has existed in more than one surrounding layout.  The
    stable contract is the legacy TED limit itself plus the fetch_notices call
    and the upsert line.  Patch those semantic anchors only.
    """
    policy_marker = 'structured_growth_limits = RESEARCH_POLICY.get("structured_growth_limits")'
    legacy_limit = 'limit={"daily": 80, "deep": 150, "exhaustive": 250}[profile],'
    legacy_upsert = 'stats["entities_added"] += upsert_notices(data, notices)'

    had_final_newline = text.endswith("\n")
    lines = text.splitlines()

    if policy_marker not in text:
        limit_matches = [i for i, line in enumerate(lines) if line.strip() == legacy_limit]
        upsert_matches = [i for i, line in enumerate(lines) if line.strip() == legacy_upsert]
        if len(limit_matches) != 1:
            raise RuntimeError(f"web legacy TED limit count={len(limit_matches)}")
        if len(upsert_matches) != 1:
            raise RuntimeError(f"web legacy TED upsert count={len(upsert_matches)}")

        limit_idx = limit_matches[0]
        upsert_idx = upsert_matches[0]
        if upsert_idx <= limit_idx:
            raise RuntimeError(f"web TED anchor order invalid: limit={limit_idx}, upsert={upsert_idx}")

        # Locate the owning fetch_notices call by scanning backwards from the
        # stable limit argument.  Do not assume an outer deadline/try/comment.
        call_candidates = [
            i for i in range(max(0, limit_idx - 30), limit_idx)
            if lines[i].strip() == 'notices = fetch_notices('
        ]
        if not call_candidates:
            raise RuntimeError("web TED fetch_notices call not found before legacy limit")
        call_idx = call_candidates[-1]

        call_indent = lines[call_idx][: len(lines[call_idx]) - len(lines[call_idx].lstrip())]
        limit_indent = lines[limit_idx][: len(lines[limit_idx]) - len(lines[limit_idx].lstrip())]
        upsert_indent = lines[upsert_idx][: len(lines[upsert_idx]) - len(lines[upsert_idx].lstrip())]
        budget = [
            call_indent + 'structured_growth_defaults = {"daily": 24, "deep": 100, "exhaustive": 220}',
            call_indent + 'structured_growth_limits = RESEARCH_POLICY.get("structured_growth_limits") or {}',
            call_indent + 'structured_growth_budget = max(',
            call_indent + '    0, int(structured_growth_limits.get(profile, structured_growth_defaults[profile]))',
            call_indent + ')',
            call_indent + 'stats["structured_entity_budget"] = structured_growth_budget',
        ]

        out: list[str] = []
        for i, line in enumerate(lines):
            if i == call_idx:
                out.extend(budget)
            if i == limit_idx:
                out.append(limit_indent + 'limit=structured_growth_budget,')
            elif i == upsert_idx:
                out.append(upsert_indent + 'structured_added = upsert_notices(data, notices)')
                out.append(upsert_indent + 'stats["entities_added"] += structured_added')
                out.append(upsert_indent + 'stats["structured_entities_added"] = structured_added')
            else:
                out.append(line)
        lines = out
        text = "\n".join(lines) + ("\n" if had_final_newline else "")
    else:
        if legacy_limit in text:
            raise RuntimeError("web structured-growth policy coexists with legacy TED limit")
        if 'limit=structured_growth_budget,' not in text:
            raise RuntimeError("web structured-growth policy present but fetch_notices is not budgeted")
        if 'stats["structured_entities_added"] = structured_added' not in text:
            raise RuntimeError("web structured-growth policy present but structured-added metric is missing")

    if 'stats["accepted_evidence_per_fetch_attempt"]' not in text:
        had_final_newline = text.endswith("\n")
        lines = text.splitlines()
        matches = [
            i for i, line in enumerate(lines)
            if line.strip().startswith('stats["elapsed_s"] =')
        ]
        if len(matches) != 1:
            raise RuntimeError(f"web ROI elapsed anchor count={len(matches)}")
        idx = matches[0]
        indent = lines[idx][: len(lines[idx]) - len(lines[idx].lstrip())]
        elapsed_line = lines[idx].strip()
        roi_lines = [
            indent + 'stats["accepted_evidence_per_fetch_attempt"] = round(',
            indent + '    stats["accepted_evidences"] / max(1, stats["fetch_attempts"]), 4',
            indent + ')',
            indent + 'stats["candidate_acceptance_rate"] = round(',
            indent + '    stats["accepted_evidences"] / max(1, stats["candidate_evidences"]), 4',
            indent + ')',
            indent + 'stats["values_per_accepted_evidence"] = round(',
            indent + '    stats["values_added"] / max(1, stats["accepted_evidences"]), 4',
            indent + ')',
            indent + 'stats["growth_pressure_ratio"] = round(',
            indent + '    stats["entities_added"] / max(1, stats["values_added"]), 4',
            indent + ')',
            indent + elapsed_line,
        ]
        lines = lines[:idx] + roi_lines + lines[idx + 1:]
        text = "\n".join(lines) + ("\n" if had_final_newline else "")

    return text

def patch_web_intelligence() -> None:
    path = ROOT / "engine/research/web_intelligence.py"
    text = path.read_text(encoding="utf-8")
    patched = _patch_web_text(text)
    path.write_text(patched, encoding="utf-8", newline="\n")


def patch_current_westcon_capability_atomicity() -> None:
    # Prevent aggregate/current Westcon capability evidence from bleeding across atomic items.
    path = ROOT / "engine/westcon_current_evidence.py"
    text = path.read_text(encoding="utf-8")
    marker = "# v4.3.0 · current Westcon capability atomicity guard"
    if marker in text:
        return

    anchor = '''    items = [dict(x) for x in (field.get("items") or []) if isinstance(x, Mapping)]

    value_index = {_norm_capability(v): i for i, v in enumerate(value)}
'''
    if text.count(anchor) != 1:
        raise RuntimeError(f"current-Westcon capability atomicity anchor count={text.count(anchor)}")

    replacement = '''    items = [dict(x) for x in (field.get("items") or []) if isinstance(x, Mapping)]

    # v4.3.0 · current Westcon capability atomicity guard
    # Aggregate capability evidence may list every documented item, but an atomic
    # item may retain current-Westcon evidence only when that item is documented
    # for this manufacturer and evidence.item_value matches it exactly.
    documented_keys = {_norm_capability(capability) for capability in capabilities}
    for item in items:
        item_key = _norm_capability(item.get("value"))
        clean_evidence: list[dict[str, Any]] = []
        for raw_ev in item.get("evidence") or []:
            if not isinstance(raw_ev, Mapping):
                continue
            ev = dict(raw_ev)
            origin = str(ev.get("provenance_origin") or "")
            if origin in CURRENT_KINDS and str(ev.get("field") or "") == "capabilities":
                evidence_key = _norm_capability(ev.get("item_value"))
                if item_key not in documented_keys or evidence_key != item_key:
                    continue
            clean_evidence.append(ev)
        item["evidence"] = _dedupe_evidence(clean_evidence)

    value_index = {_norm_capability(v): i for i, v in enumerate(value)}
'''
    text = text.replace(anchor, replacement, 1)
    path.write_text(text, encoding="utf-8", newline="\n")

def patch_preservation_relationship_policy() -> None:
    # Protect confirmed relationships, while treating explicit provisional signals
    # as recalculable telemetry. This is deliberately narrow and defaults to
    # preserving every relationship unless it is explicitly provisional.
    path = ROOT / "engine/preservation.py"
    text = path.read_text(encoding="utf-8")

    helper_marker = "def _relationship_is_hard_protected(rel: Mapping[str, Any]) -> bool:"
    if helper_marker not in text:
        anchor = "\ndef _relation_key("
        if text.count(anchor) != 1:
            raise RuntimeError(f"preservation relation-key anchor count={text.count(anchor)}")
        helper = """

def _relationship_is_hard_protected(rel: Mapping[str, Any]) -> bool:
    # Relations remain hard-protected by default. Explicitly provisional
    # or low-confidence derived signals are recalculable telemetry.
    validity = str(rel.get("validity") or "").strip().casefold().replace("_", "-")
    status = str(rel.get("status") or "").strip().casefold()
    try:
        confidence = float(rel.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    if validity in {"needs-corroboration", "needs corroboration", "provisional", "candidate"}:
        return False
    if bool(rel.get("derived")) and status in {"señal", "senal", "signal"} and confidence < 0.65:
        return False
    return True
"""
        text = text.replace(anchor, helper + anchor, 1)

    # Do not carry provisional signals forward as if they were confirmed relations.
    if 'relations_skipped_provisional' not in text:
        old = '''    restored = 0
    skipped_unresolved = 0
    for raw in baseline_graph.get("relationships") or []:
        if not isinstance(raw, Mapping):
            continue
        key = _relation_key(raw, lookup)
'''
        new = '''    restored = 0
    skipped_unresolved = 0
    skipped_provisional = 0
    for raw in baseline_graph.get("relationships") or []:
        if not isinstance(raw, Mapping):
            continue
        if not _relationship_is_hard_protected(raw):
            skipped_provisional += 1
            continue
        key = _relation_key(raw, lookup)
'''
        if text.count(old) != 1:
            raise RuntimeError(f"preservation restore-relation anchor count={text.count(old)}")
        text = text.replace(old, new, 1)
        old_return = '''        "relations_restored": restored,
        "relations_skipped_unresolved_endpoints": skipped_unresolved,
        "relations_after": len(relationships),
'''
        new_return = '''        "relations_restored": restored,
        "relations_skipped_unresolved_endpoints": skipped_unresolved,
        "relations_skipped_provisional": skipped_provisional,
        "relations_after": len(relationships),
'''
        if text.count(old_return) != 1:
            raise RuntimeError(f"preservation restore stats anchor count={text.count(old_return)}")
        text = text.replace(old_return, new_return, 1)

    # Snapshot confirmed/hard relations separately from provisional relationship signals.
    if 'provisional_relations = set()' not in text:
        old = '''    relations = set()
    relation_lookup = _entity_lookup(data)
    for rel in (graph or {}).get("relationships") or []:
        if not isinstance(rel, Mapping):
            continue
        relations.add(_relation_key(rel, relation_lookup))
'''
        new = '''    relations = set()
    provisional_relations = set()
    relation_lookup = _entity_lookup(data)
    for rel in (graph or {}).get("relationships") or []:
        if not isinstance(rel, Mapping):
            continue
        key = _relation_key(rel, relation_lookup)
        if _relationship_is_hard_protected(rel):
            relations.add(key)
        else:
            provisional_relations.add(key)
'''
        if text.count(old) != 1:
            raise RuntimeError(f"preservation snapshot relation anchor count={text.count(old)}")
        text = text.replace(old, new, 1)
        old_return = '        "relations": sorted(relations),\n'
        new_return = '        "relations": sorted(relations),\n        "provisional_relations": sorted(provisional_relations),\n'
        if text.count(old_return) != 1:
            raise RuntimeError(f"preservation snapshot return anchor count={text.count(old_return)}")
        text = text.replace(old_return, new_return, 1)

    # Report provisional-signal counts as telemetry, never as hard loss.
    if '"provisional_relations": len(before.get("provisional_relations") or [])' not in text:
        before_line = '            "relations": len(before.get("relations") or []),\n'
        after_line = '            "relations": len(after.get("relations") or []),\n'
        if text.count(before_line) != 1 or text.count(after_line) != 1:
            raise RuntimeError("preservation report relation-count anchors not found")
        text = text.replace(
            before_line,
            before_line + '            "provisional_relations": len(before.get("provisional_relations") or []),\n',
            1,
        )
        text = text.replace(
            after_line,
            after_line + '            "provisional_relations": len(after.get("provisional_relations") or []),\n',
            1,
        )

    if 'provisional_relationship_signals_before' not in text:
        anchor = '            "derived_values_before": before_derived,\n'
        if text.count(anchor) != 1:
            raise RuntimeError(f"preservation semantic-change anchor count={text.count(anchor)}")
        text = text.replace(
            anchor,
            anchor
            + '            "provisional_relationship_signals_before": len(before.get("provisional_relations") or []),\n'
            + '            "provisional_relationship_signals_after": len(after.get("provisional_relations") or []),\n',
            1,
        )

    path.write_text(text, encoding="utf-8", newline="\n")

def patch_v422_regressions() -> None:
    # Release-integrity test must follow the canonical release version.  v4.2.2
    # intentionally hard-coded its own release number; v4.3.0 updates that
    # contract rather than weakening/removing the test.
    release_test = ROOT / "tests/test_release.py"
    if release_test.exists():
        text = release_test.read_text(encoding="utf-8")
        old = '        self.assertEqual(VERSION, "4.2.2")\n'
        new = '        self.assertEqual(VERSION, "4.3.0")\n'
        count = text.count(old)
        if count == 0 and new in text:
            pass
        elif count == 1:
            text = text.replace(old, new, 1)
        else:
            raise RuntimeError(f"release canonical-version anchor count={count}")
        release_test.write_text(text, encoding="utf-8", newline="\n")

    audit = ROOT / "scripts/audit_v422.py"
    if audit.exists():
        text = audit.read_text(encoding="utf-8")
        old = '''    if '4.2.2' not in index_html or '4.2.2' not in js:\n        errors.append('frontend version is not 4.2.2')\n'''
        new = '''    current_version = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()\n    if current_version not in index_html or current_version not in js:\n        errors.append(f'frontend version is not current VERSION={current_version}')\n'''
        if old in text:
            text = text.replace(old, new, 1)
        audit.write_text(text, encoding="utf-8", newline="\n")

    test = ROOT / "tests/test_v422_tag_ergonomics.py"
    if test.exists():
        text = test.read_text(encoding="utf-8")
        old = '''        self.assertIn('4.2.2',html)\n        self.assertIn('4.2.2',js)\n'''
        new = '''        version=(ROOT/'VERSION').read_text(encoding='utf-8').strip()\n        self.assertIn(version,html)\n        self.assertIn(version,js)\n'''
        if old in text:
            text = text.replace(old, new, 1)
        test.write_text(text, encoding="utf-8", newline="\n")


def patch_workflow() -> None:
    path = ROOT / ".github/workflows/research-run.yml"
    text = path.read_text(encoding="utf-8")
    marker = "          python -m scripts.audit_v430"
    if marker not in text:
        anchor = "          python -m scripts.audit_v422\n"
        count = text.count(anchor)
        if count != 2:
            raise RuntimeError(f"research-run v422 audit anchor count={count}")
        text = text.replace(anchor, anchor + marker + "\n")
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_changelog() -> None:
    path = ROOT / "CHANGELOG.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    marker = "## 4.3.0 — Research ROI & Controlled Growth"
    if marker not in text:
        entry = '''\n## 4.3.0 — Research ROI & Controlled Growth\n- Limita el crecimiento estructurado TED por perfil: 24 / 100 / 220.\n- El planner aprende por evidencia aceptada por intento, no por mero transporte HTTP.\n- Los clientes públicos sin contexto de oportunidad no pueden escalar artificialmente a P0/P1.\n- Añade KPIs de ROI de investigación y presión de crecimiento.\n- Mantiene como regresiones obligatorias FY27, Portugal=España+Check Point, evidencia atómica y preservación.\n'''
        text = text.rstrip() + "\n" + entry
        path.write_text(text, encoding="utf-8", newline="\n")


def main() -> int:
    patch_version_and_frontend()
    patch_policy()
    patch_planner()
    patch_gap_intelligence()
    patch_web_intelligence()
    patch_current_westcon_capability_atomicity()
    patch_preservation_relationship_policy()
    patch_v422_regressions()
    patch_workflow()
    patch_changelog()
    print("v4.3.0 runtime patch: PASS")
    print(" - controlled structured growth: daily 24 / deep 100 / exhaustive 220")
    print(" - planner learning: accepted evidence per attempt + relevance + transport")
    print(" - low-context public opportunities capped at P2 unless exact public-validation debt")
    print(" - research ROI metrics emitted per run and in business-priority report")
    print(" - current Westcon capability evidence remains atomic per documented item")
    print(" - preservation distinguishes confirmed relations from provisional derived signals")
    print(" - release-integrity test follows canonical VERSION=4.3.0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
