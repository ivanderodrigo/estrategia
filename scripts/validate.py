#!/usr/bin/env python3
"""Release validator for canonical data, runtime references and public projection."""

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.model import canonical  # noqa: E402
from engine.settings import SECTIONS, VERSION  # noqa: E402
from engine.storage import read_json  # noqa: E402


errors: list[str] = []


def error(message: str) -> None:
    errors.append(message)


required = (
    "engine/pipeline.py", "engine/provenance.py", "engine/research/web_intelligence.py",
    "engine/research/ted.py", "engine/archive_provenance.py",
    "config/current/research_policy.json", "config/current/archive_provenance_registry.json",
    "data/current/intelligence.json", "data/current/research_state.json",
    "data/current/provenance_report.json", "data/current/archive_provenance_report.json",
    "data/current/provenance_lineage.json",
    "data/current/quality_report.json", "data/public/manifest.json",
    "assets/app/intelligence.js", "assets/app/intelligence.css", "tests/ui_smoke.js",
)
for relative in required:
    if not (ROOT / relative).is_file():
        error(f"missing {relative}")

runtime_files = [
    ROOT / "index.html", ROOT / "assets/app/intelligence.js",
    ROOT / "scripts/research_supervisor.py", ROOT / "scripts/publish_research_update.py",
    ROOT / "engine/pipeline.py", *(ROOT / ".github/workflows").glob("*.yml"),
]
legacy_reference = re.compile(r"(?:assets|data|config|scripts)/v\d+", re.I)
for path in runtime_files:
    if path.is_file() and legacy_reference.search(path.read_text(encoding="utf-8")):
        error(f"legacy runtime reference: {path.relative_to(ROOT)}")
for directory in ("assets", "data", "config", "scripts"):
    for path in (ROOT / directory).glob("v[0-9]*"):
        error(f"legacy directory present: {path.relative_to(ROOT)}")

data = read_json("data/current/intelligence.json")
gaps = read_json("data/current/research_gaps.json")
graph = read_json("data/current/relationship_graph.json")
quality = read_json("data/current/quality_report.json")
manifest = read_json("data/public/manifest.json")
research_state = read_json("data/current/research_state.json")

for name, document in (
    ("dataset", data.get("meta") or {}), ("gaps", gaps), ("graph", graph),
    ("quality", quality), ("manifest", manifest), ("research state", research_state),
):
    if document.get("version") != VERSION:
        error(f"{name} version != {VERSION}")

if quality.get("errors") or int(quality.get("score") or 0) < 95:
    error(f"quality audit failed: {(quality.get('errors') or [])[:3]}")
if gaps.get("total_gaps") != len(gaps.get("gaps") or []):
    error("gap total is inconsistent")
RESEARCH_STATE = "Por investigar"
PUBLIC_VALIDATION_STATE = "Pendiente de validaci\u00f3n p\u00fablica"

def _normalized_state(value):
    return unicodedata.normalize("NFC", str(value or "")).strip()

for item in gaps.get("gaps") or []:
    state = _normalized_state(item.get("research_state"))
    gap_kind = str(item.get("gap_kind") or "").strip()

    if gap_kind == "public-validation":
        if state != PUBLIC_VALIDATION_STATE:
            error("public-validation gap has an invalid state")
    elif state != RESEARCH_STATE:
        error("open gap has an invalid state")
if set(manifest.get("sections") or {}) != set(SECTIONS):
    error("public manifest sections are invalid")

manufacturers = {canonical(row.get("name")) for row in data.get("manufacturers") or []}
distributors = {canonical(row.get("name")) for row in data.get("distributors") or []}
if canonical("Comstor") in distributors:
    error("Comstor classified as competitor distributor")
if canonical("Forescout") in manufacturers:
    error("Forescout incorrectly classified as a Westcon manufacturer")
if manufacturers & distributors:
    error("an entity is classified as both manufacturer and distributor")

edge_keys = []
for relation in graph.get("relationships") or []:
    edge_keys.append((relation.get("entity_a_id"), relation.get("relation"), relation.get("entity_b_id")))
    if not relation.get("evidence"):
        error(f"relationship without evidence: {relation.get('id')}")
    elif any(not str(item.get("url") or "").startswith(("http://", "https://")) for item in relation["evidence"]):
        error(f"relationship with invalid evidence URL: {relation.get('id')}")
if len(edge_keys) != len(set(edge_keys)):
    error("duplicate canonical relationship edges")

atomic_fields = {
    "manufacturers": {"distributors", "integrators"},
    "distributors": {"vendor_relations", "westcon_overlap", "competitor_vendor_overlap"},
    "integrators": {"vendor_relations", "westcon_overlap", "competitor_vendor_overlap"},
}
for section, field_ids in atomic_fields.items():
    for row in data.get(section) or []:
        for field_id in field_ids:
            field = ((row.get("fields") or {}).get(field_id) or {})
            values = field.get("value")
            if not isinstance(values, list):
                continue
            items = {canonical(item.get("value")): item for item in field.get("items") or [] if isinstance(item, dict)}
            for value in values:
                item = items.get(canonical(value))
                if not item or not item.get("evidence"):
                    error(f"atomic provenance missing: {section}/{row.get('name')}/{field_id}/{value}")

frontend = (ROOT / "assets/app/intelligence.js").read_text(encoding="utf-8")
pages = (ROOT / ".github/workflows/pages-deploy.yml").read_text(encoding="utf-8")
if "data/current/intelligence.json" in frontend:
    error("frontend loads the internal dataset")
if "items[index]" in frontend:
    error("frontend can map evidence by unrelated list position")
if "cp data/current" in pages:
    error("Pages publishes internal data")

print(f"v{VERSION} canonical validation:", "PASS" if not errors else "FAIL")
for item in errors:
    print(" -", item)
raise SystemExit(1 if errors else 0)
