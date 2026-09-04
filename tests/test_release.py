from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from engine.provenance import evidence_for_relationship
from engine.archive_provenance import apply_archive_provenance, archive_registry_summary
from engine.knowledge_provenance import build_knowledge_baseline, restore_protected_knowledge, typed_evidence_sufficient
from engine.research.security import UnsafeUrl, validate_public_url
from engine.research.state import ResearchState
from engine.research.ted import parse_notice, upsert_notices
from engine.settings import SECTIONS, VERSION
from engine.storage import atomic_write_many, read_json


ROOT = Path(__file__).resolve().parents[1]


class ReleaseIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = read_json("data/current/intelligence.json")
        cls.gaps = read_json("data/current/research_gaps.json")
        cls.graph = read_json("data/current/relationship_graph.json")
        cls.quality = read_json("data/current/quality_report.json")
        cls.manifest = read_json("data/public/manifest.json")

    def test_one_canonical_version(self) -> None:
        self.assertEqual(VERSION, "4.3.0")
        self.assertEqual(self.data["meta"]["version"], VERSION)
        self.assertEqual(self.graph["version"], VERSION)
        self.assertEqual(self.gaps["version"], VERSION)

    def test_business_classification_invariants(self) -> None:
        manufacturers = {row["name"] for row in self.data["manufacturers"]}
        distributors = {row["name"] for row in self.data["distributors"]}
        self.assertNotIn("Comstor", distributors)
        self.assertNotIn("Forescout", manufacturers)
        self.assertFalse(manufacturers & distributors)
        self.assertNotIn("Arrow Electronics", distributors)
        self.assertNotIn("Digicomp", distributors)

    def test_graph_has_unique_evidenced_edges(self) -> None:
        relations = self.graph["relationships"]
        keys = [(row["entity_a_id"], row["relation"], row["entity_b_id"]) for row in relations]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertTrue(relations)
        for relation in relations:
            self.assertTrue(relation.get("evidence"), relation.get("id"))
            self.assertTrue(all(str(item.get("url") or "").startswith("http") for item in relation["evidence"]))

    def test_every_visible_relationship_has_atomic_evidence(self) -> None:
        atomic = {
            "manufacturers": {"distributors", "integrators"},
            "distributors": {"vendor_relations", "westcon_overlap", "competitor_vendor_overlap"},
            "integrators": {"vendor_relations", "westcon_overlap", "competitor_vendor_overlap"},
        }
        for section, field_ids in atomic.items():
            for row in self.data[section]:
                for field_id in field_ids:
                    field = (row.get("fields") or {}).get(field_id) or {}
                    if not isinstance(field.get("value"), list):
                        continue
                    items = {str(item.get("value")): item for item in field.get("items") or []}
                    for value in field["value"]:
                        self.assertIn(str(value), items, f"{section}/{row['name']}/{field_id}/{value}")
                        self.assertTrue(items[str(value)].get("evidence"), f"{section}/{row['name']}/{field_id}/{value}")

    def test_1password_ingram_click_is_not_field_wide(self) -> None:
        row = next(item for item in self.data["manufacturers"] if item["name"] == "1Password")
        field = row["fields"]["distributors"]
        item = next(item for item in field["items"] if item["value"] == "Ingram Micro")
        self.assertEqual(len(item["evidence"]), 1)
        blob = json.dumps(item["evidence"][0], ensure_ascii=False).casefold()
        self.assertIn("1password", blob)
        self.assertIn("ingram", blob)
        self.assertNotIn("uipath", blob)

    def test_strict_gaps_keep_learning_state(self) -> None:
        self.assertEqual(self.gaps["total_gaps"], len(self.gaps["gaps"]))
        allowed = {"Por investigar", "Pendiente de validación pública"}
        self.assertTrue(all(gap["research_state"] in allowed for gap in self.gaps["gaps"]))
        self.assertTrue(all("attempts_completed" in gap and "next_due_at" in gap for gap in self.gaps["gaps"]))
        self.assertEqual(self.gaps["engine"]["strategy_profile"], "business-value-x-researchability")
        self.assertEqual(self.gaps.get("support_rule"), "CURRENT_PUBLIC_ONLY")

    def test_public_site_exposes_only_projected_sections(self) -> None:
        self.assertEqual(set(self.manifest["sections"]), set(SECTIONS))
        js = (ROOT / "assets/app/intelligence.js").read_text(encoding="utf-8")
        pages = (ROOT / ".github/workflows/pages-deploy.yml").read_text(encoding="utf-8")
        self.assertIn("data/public/manifest.json", js)
        self.assertNotIn("data/current/intelligence.json", js)
        self.assertNotIn("cp data/current", pages)

    def test_quality_gate_is_clean(self) -> None:
        self.assertEqual(self.quality["errors"], [])
        self.assertEqual(self.quality["score"], 100)


class EngineBehaviour(unittest.TestCase):
    def test_relationship_scope_prefers_exact_assertion(self) -> None:
        exact = {"source": "1Password", "title": "Ingram Micro ↔ 1Password", "url": "https://example.com/exact"}
        broad = {"source": "Ingram Micro", "title": "Fabricantes", "description": "Directorio de marcas", "url": "https://example.com/catalog"}
        unrelated = {"source": "Ingram Micro", "title": "Ingram Micro ↔ UiPath", "url": "https://example.com/other"}
        self.assertEqual(evidence_for_relationship([unrelated, broad, exact], "1Password", "Ingram Micro"), [exact])

    def test_westcon_document_is_valid_typed_provenance(self) -> None:
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

    def test_knowledge_guard_restores_trend_content(self) -> None:
        original = {
            "trends": [{"id": "t1", "name": "Trend", "fields": {"drivers": {"value": ["A", "B"], "items": []}}}],
            "architectures": [],
            "manufacturers": [],
        }
        baseline = build_knowledge_baseline(original)
        damaged = {
            "trends": [{"id": "t1", "name": "Trend", "fields": {"drivers": {"value": ["A"], "items": []}}}],
            "architectures": [],
            "manufacturers": [],
        }
        restore_protected_knowledge(damaged, baseline)
        self.assertEqual(damaged["trends"][0]["fields"]["drivers"]["value"], ["A", "B"])

    def test_archive_registry_never_changes_current_values(self) -> None:
        data = {
            "manufacturers": [{"name": "Vendor X", "fields": {
                "capabilities": {
                    "value": ["A", "B"],
                    "items": [
                        {"value": "A", "evidence": [{
                            "source": "Histórico del proyecto Westcon Decision Intelligence",
                            "title": "pendiente", "date": "2026-09-01", "description": "pendiente",
                            "source_type": "legacy-unresolved", "provenance_origin": "LEGACY_UNRESOLVED",
                        }]},
                        {"value": "B", "evidence": []},
                    ],
                    "evidence": [],
                }
            }}],
            "distributors": [], "integrators": [], "clients_public": [], "clients_private": [],
            "trends": [], "architectures": [],
        }
        registry = {
            "matches": [{
                "section": "manufacturers", "entity": "Vendor X", "field": "capabilities",
                "value_hash": "0", "item_value_hash": None, "evidence": [],
            }],
            "url_classifications": {}, "stats": {},
        }
        before = json.dumps(data["manufacturers"][0]["fields"]["capabilities"]["value"], ensure_ascii=False)
        apply_archive_provenance(data, registry)
        after = json.dumps(data["manufacturers"][0]["fields"]["capabilities"]["value"], ensure_ascii=False)
        self.assertEqual(before, after)

    def test_archive_corroboration_cannot_close_gap(self) -> None:
        evidence = {
            "source": "Informe histórico", "title": "v3.9", "url": "https://example.com/source",
            "date": "2026-08-28", "description": "Coincide entidad y valor en informe histórico.",
            "provenance_origin": "REPORT_CORROBORATION",
        }
        self.assertFalse(typed_evidence_sufficient(evidence))

    def test_archive_registry_summary_is_stable(self) -> None:
        summary = archive_registry_summary({
            "policy": "exact", "generated_at": "x",
            "stats": {"archives_scanned": 3},
            "matches": [{"evidence": [{"provenance_origin": "ARCHIVE_RECOVERED"}]}],
            "url_classifications": {"https://example.com": {"provenance_origin": "PUBLIC_PRIMARY"}},
        })
        self.assertEqual(summary["archives_scanned"], 3)
        self.assertEqual(summary["archive_atomic_evidences"], 1)

    def test_url_guard_rejects_ssrf_targets(self) -> None:
        for url in (
            "http://localhost/admin", "http://127.0.0.1/", "http://169.254.169.254/latest",
            "https://user:pass@example.com/", "https://example.com:8443/",
        ):
            with self.subTest(url=url), self.assertRaises(UnsafeUrl):
                validate_public_url(url, resolve_dns=False)
        self.assertEqual(validate_public_url("https://example.com/path", resolve_dns=False), "https://example.com/path")

    def test_state_backoff_and_circuit_breaker(self) -> None:
        state = ResearchState({"version": "4.0.0"})
        self.assertEqual(state.raw["version"], VERSION)
        state.record_gap("g1", accepted=0)
        self.assertEqual(state.gap("g1")["attempts"], 1)
        self.assertEqual(state.gap("g1")["consecutive_no_yield"], 1)
        for _ in range(5):
            state.record_domain("https://example.com", ok=False)
        self.assertFalse(state.domain_available("https://example.com"))

    def test_ted_notice_parser_and_upsert(self) -> None:
        notice = {
            "publication-number": "123456-2026",
            "publication-date": "2026-08-31",
            "notice-title": {"spa": "Servicios de ciberseguridad"},
            "buyer-name": {"spa": "Ayuntamiento de Prueba"},
            "organisation-country-buyer": "ESP",
            "classification-cpv": ["72000000"],
            "estimated-value-proc": "100000",
            "estimated-value-cur-proc": "EUR",
        }
        parsed = parse_notice(notice)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["fields"]["scope"]["value"], "ES")
        data = {"clients_public": []}
        self.assertEqual(upsert_notices(data, [notice]), 1)
        self.assertEqual(upsert_notices(data, [notice]), 0)
        self.assertEqual(len(data["clients_public"]), 1)
        irrelevant = dict(notice, **{"publication-number": "999999-2026", "classification-cpv": ["39154000"]})
        self.assertIsNone(parse_notice(irrelevant))

    def test_transactional_writer(self) -> None:
        runtime = ROOT / ".runtime"
        runtime.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=runtime) as directory:
            first, second = Path(directory) / "a.json", Path(directory) / "b.json"
            atomic_write_many({first: b'{"a":1}\n', second: b'{"b":2}\n'})
            self.assertEqual(json.loads(first.read_text(encoding="utf-8")), {"a": 1})
            self.assertEqual(json.loads(second.read_text(encoding="utf-8")), {"b": 2})


if __name__ == "__main__":
    unittest.main()
