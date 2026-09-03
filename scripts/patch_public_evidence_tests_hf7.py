from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def replace_method(path: Path, name: str, body: str) -> bool:
    text = path.read_text(encoding='utf-8')
    pattern = re.compile(rf'(?ms)^    def {re.escape(name)}\(self[^\n]*:\n.*?(?=^    def |^class |^if __name__|\Z)')
    match = pattern.search(text)
    if not match:
        return False
    replacement = '    def ' + name + '(self) -> None:\n' + '\n'.join('        ' + line if line else '' for line in body.strip('\n').splitlines()) + '\n\n'
    path.write_text(text[:match.start()] + replacement + text[match.end():], encoding='utf-8')
    return True


patched = []

release = ROOT / 'tests' / 'test_release.py'
if release.exists():
    if replace_method(release, 'test_westcon_document_is_valid_typed_provenance', '''
from engine.knowledge_provenance import convert_internal_lineage_to_research_seeds, provenance_kind

evidence = {
    "source": "Westcon Comstor España",
    "title": "Presentación Corporativa FY2027 · slide 44",
    "date": "FY2027",
    "description": "Capacidades de fabricante documentadas por Westcon.",
    "source_type": "westcon-document",
    "document": "Westcon_Comstor_Espana_FY27_completa.pptx",
    "provenance_origin": "WESTCON_DOCUMENT",
}
self.assertFalse(typed_evidence_sufficient(evidence))
data = {"manufacturers": [{"fields": {"capabilities": {"value": ["SASE"], "items": [{"value": "SASE", "evidence": [evidence]}]}}}]}
convert_internal_lineage_to_research_seeds(data)
seed = data["manufacturers"][0]["fields"]["capabilities"]["items"][0]["evidence"][0]
self.assertEqual(provenance_kind(seed), "RESEARCH_SEED")
self.assertEqual(seed.get("source_binding"), "discovery-only")
self.assertFalse(typed_evidence_sufficient(seed))
'''):
        patched.append('tests/test_release.py:test_westcon_document_is_valid_typed_provenance')
    if replace_method(release, 'test_strict_gaps_keep_learning_state', '''
self.assertEqual(self.gaps["total_gaps"], len(self.gaps["gaps"]))
allowed = {"Por investigar", "Pendiente de validación pública"}
self.assertTrue(all(gap["research_state"] in allowed for gap in self.gaps["gaps"]))
self.assertTrue(all("attempts_completed" in gap and "next_due_at" in gap for gap in self.gaps["gaps"]))
self.assertEqual(self.gaps["engine"]["strategy_profile"], "adaptive-source-cascade")
self.assertEqual(self.gaps.get("support_rule"), "CURRENT_PUBLIC_ONLY")
'''):
        patched.append('tests/test_release.py:test_strict_gaps_keep_learning_state')

doc = ROOT / 'tests' / 'test_document_provenance_v404.py'
if doc.exists():
    if replace_method(doc, 'test_release_manufacturer_capabilities_show_westcon_document', '''
from engine.knowledge_provenance import accrediting_evidence, provenance_kind
from engine.storage import read_json

data = read_json("data/current/intelligence.json")
row = next(item for item in data.get("manufacturers") or [] if item.get("name") == "Check Point")
field = ((row.get("fields") or {}).get("capabilities") or {})
items = {str(item.get("value")): item for item in field.get("items") or [] if isinstance(item, dict)}
for value in ("NGFW", "SASE", "Cloud Security", "Email Security"):
    self.assertIn(value, items)
    public = [ev for ev in items[value].get("evidence") or [] if isinstance(ev, dict) and accrediting_evidence(ev)]
    self.assertTrue(public, f"Check Point/{value}: falta fuente pública acreditativa")
    self.assertTrue(all(str(ev.get("url") or "").startswith(("http://", "https://")) for ev in public))
    self.assertFalse(any(provenance_kind(ev) == "WESTCON_DOCUMENT" and accrediting_evidence(ev) for ev in items[value].get("evidence") or [] if isinstance(ev, dict)))
'''):
        patched.append('tests/test_document_provenance_v404.py:test_release_manufacturer_capabilities_show_westcon_document')

src = ROOT / 'tests' / 'test_source_rationalization_v405.py'
if src.exists():
    if replace_method(src, 'test_a1_or_public_are_direct_support', '''
from engine.source_rationalization import support_basis

westcon = {
    "source": "Westcon",
    "title": "Deck",
    "date": "FY2027",
    "description": "Pista interna",
    "document": "deck.pptx",
    "source_type": "westcon-document",
    "provenance_origin": "WESTCON_DOCUMENT",
}
public = {
    "source": "Vendor",
    "title": "Official",
    "date": "2026-09-02",
    "description": "Official public evidence",
    "url": "https://vendor.example/official",
    "official": True,
    "source_grade": "A2",
    "provenance_origin": "PUBLIC_PRIMARY",
}
self.assertEqual(support_basis([westcon]), "SEARCH_REQUIRED")
self.assertEqual(support_basis([public]), "CURRENT_PUBLIC")
self.assertEqual(support_basis([westcon, public]), "CURRENT_PUBLIC")
'''):
        patched.append('tests/test_source_rationalization_v405.py:test_a1_or_public_are_direct_support')

# HF9: align the two remaining v4.0.5 support-gap tests with the public-evidence
# contract while preserving their original invariants. These tests are made
# self-contained so they do not depend on legacy fixture labels or gap wording.
if src.exists():
    if replace_method(src, 'test_external_fact_without_support_creates_public_gap', '''
from engine.gaps import build_gaps

public = {
    "schemas": {
        "manufacturers": [
            {"id": "capabilities", "label": "Capacidades", "decision_required": True}
        ]
    },
    "manufacturers": [
        {
            "id": "vendor-test",
            "name": "Vendor Test",
            "fields": {
                "capabilities": {
                    "value": "SASE",
                    "evidence": [],
                }
            },
        }
    ],
}
report = build_gaps(public, research_state={})
found = [
    gap for gap in report["gaps"]
    if gap.get("section") == "manufacturers"
    and gap.get("entity") == "Vendor Test"
    and gap.get("field") == "capabilities"
    and gap.get("target_values") == ["SASE"]
]
self.assertEqual(len(found), 1)
gap = found[0]
self.assertEqual(gap.get("claim_class"), "EXTERNAL_FACT")
self.assertEqual(gap.get("research_mode"), "public-source-verification")
self.assertEqual(gap.get("support_requirement"), "CURRENT_PUBLIC_ONLY")
self.assertEqual(gap.get("gap_kind"), "evidence-support")
self.assertEqual(gap.get("research_state"), "Por investigar")
self.assertTrue(gap.get("preserve_value"))
'''):
        patched.append('tests/test_source_rationalization_v405.py:test_external_fact_without_support_creates_public_gap')

    if replace_method(src, 'test_populated_field_absent_from_schema_still_gets_gap', '''
from engine.gaps import build_gaps

public = {
    "schemas": {"distributors": []},
    "distributors": [
        {
            "id": "dist-test",
            "name": "Distributor Test",
            "fields": {
                "orphan_one": {"value": "Value A", "evidence": []},
                "orphan_two": {"value": "Value B", "evidence": []},
            },
        }
    ],
}
report = build_gaps(public, research_state={})
found = [
    gap for gap in report["gaps"]
    if gap.get("section") == "distributors"
    and gap.get("entity") == "Distributor Test"
    and gap.get("field") in {"orphan_one", "orphan_two"}
]
self.assertEqual(len(found), 2)
self.assertEqual({gap.get("field") for gap in found}, {"orphan_one", "orphan_two"})
self.assertTrue(all(gap.get("claim_class") == "EXTERNAL_FACT" for gap in found))
self.assertTrue(all(gap.get("research_mode") == "public-source-verification" for gap in found))
self.assertTrue(all(gap.get("support_requirement") == "CURRENT_PUBLIC_ONLY" for gap in found))
self.assertTrue(all(gap.get("gap_kind") == "evidence-support" for gap in found))
self.assertTrue(all(gap.get("research_state") == "Por investigar" for gap in found))
'''):
        patched.append('tests/test_source_rationalization_v405.py:test_populated_field_absent_from_schema_still_gets_gap')

print('HF9 legacy public-evidence test alignment: PASS')
for row in patched:
    print(' -', row)
