from __future__ import annotations

import json

from engine.gaps import validate_gap_state_contract
from engine.knowledge_provenance import accrediting_evidence, provenance_kind
from engine.storage import read_json

EXPECTED = {
    "NGFW": "checkpoint.com",
    "SASE": "checkpoint.com",
    "Cloud Security": "checkpoint.com",
    "Email Security": "checkpoint.com",
}

data = read_json("data/current/intelligence.json")
gaps = read_json("data/current/research_gaps.json")
preservation = read_json("data/current/knowledge_preservation_v410.json")
manifest = read_json("data/public/manifest.json")
errors: list[str] = []

row = next((item for item in data.get("manufacturers") or [] if item.get("name") == "Check Point"), None)
if not row:
    errors.append("Check Point manufacturer row missing")
else:
    field = ((row.get("fields") or {}).get("capabilities") or {})
    items = {str(item.get("value")): item for item in field.get("items") or [] if isinstance(item, dict)}
    for value, host in EXPECTED.items():
        item = items.get(value)
        if not item:
            errors.append(f"Check Point/{value}: atomic item missing")
            continue
        public = [ev for ev in item.get("evidence") or [] if isinstance(ev, dict) and accrediting_evidence(ev)]
        if not public:
            errors.append(f"Check Point/{value}: public accreditation missing")
            continue
        if not any(host in str(ev.get("url") or "") for ev in public):
            errors.append(f"Check Point/{value}: expected official domain not found")

seed_count = 0
for section in ("manufacturers", "distributors", "integrators", "clients_public", "clients_private", "trends", "architectures"):
    for row in data.get(section) or []:
        targets = [row]
        for field in (row.get("fields") or {}).values():
            if isinstance(field, dict):
                targets.append(field)
                targets.extend(item for item in field.get("items") or [] if isinstance(item, dict))
        for target in targets:
            for ev in target.get("evidence") or []:
                if not isinstance(ev, dict):
                    continue
                kind = provenance_kind(ev)
                if kind in {"RESEARCH_SEED", "HISTORICAL_RECOVERED", "ARCHIVE_RECOVERED", "ARCHIVE_CORROBORATION", "REPORT_CORROBORATION", "LEGACY_UNRESOLVED"}:
                    seed_count += 1
                if kind == "RESEARCH_SEED" and accrediting_evidence(ev):
                    errors.append("RESEARCH_SEED is accrediting")

registry = [row for row in data.get("research_seed_registry") or [] if isinstance(row, dict)]
if not registry:
    errors.append("research_seed_registry is empty")
for record in registry:
    if record.get("accrediting") is not False:
        errors.append("research_seed_registry contains accrediting record")
        break
    if not record.get("claim_key"):
        errors.append("research_seed_registry contains record without claim_key")
        break

state_errors = validate_gap_state_contract(gaps)
errors.extend(f"gap-state: {error}" for error in state_errors)

# Historical/internal Westcon material must remain hidden. v4.2.2 deliberately allows
# only *current, claim-scoped* Westcon first-party evidence in the public source catalogue.
for source in manifest.get("source_catalog") or []:
    if not isinstance(source, dict):
        continue
    source_class = str(source.get("class") or "")
    if source_class in {"WESTCON_DOCUMENT", "Fuente documental Westcon"}:
        errors.append("historical/internal Westcon document leaked into public source catalogue")
    if source_class in {"Fuente documental Westcon vigente", "Fuente Westcon vigente"} and not (
        source.get("document_id") or source.get("statement_id")
    ):
        errors.append("current Westcon source catalogue entry lacks stable document/statement identity")
if gaps.get("support_rule") != "CURRENT_PUBLIC_ONLY":
    errors.append(f"unexpected support_rule={gaps.get('support_rule')}")
if preservation.get("status") != "PASS":
    errors.append("Preservation Gate is not PASS")

missing_seeds = (((preservation.get("missing") or {}).get("research_seed_claims")) or [])
if missing_seeds:
    errors.append(f"research seed claims still missing: {len(missing_seeds)}")

reconciliation = preservation.get("reconciliation") or {}
seed_registry_stats = reconciliation.get("research_seed_registry") or {}
seed_restore_stats = reconciliation.get("research_seed_reconciliation") or {}

print("HF8 public-evidence + research-memory audit:", "PASS" if not errors else "FAIL")
print(" - internal research/historical evidence rows:", seed_count)
print(" - persistent research-seed registry claims:", len(registry))
print(" - seed rows reattached to surviving claims:", int(seed_restore_stats.get("total_seed_rows_restored") or 0))
print(" - registry claims after reconciliation:", int(seed_registry_stats.get("registry_claims") or len(registry)))
print(" - public-validation gaps:", int(gaps.get("public_validation_gaps") or 0))
print(" - registry-origin public-validation gaps:", int(gaps.get("research_seed_registry_gaps") or 0))
print(" - unknown research gaps:", int(gaps.get("unknown_research_gaps") or 0))
print(" - public source catalogue entries:", len(manifest.get("source_catalog") or []))
for error in errors:
    print(" - ERROR:", error)
raise SystemExit(1 if errors else 0)
