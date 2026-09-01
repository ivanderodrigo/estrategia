from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from engine.provenance import evidence_for_relationship
from engine.client_intelligence import derive_client_intelligence
from engine.publication import _sanitize_public_field
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
        self.assertEqual(VERSION, "4.0.1")
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
            "clients_public": {"westcon_area", "westcon_fit"},
            "clients_private": {"westcon_area", "westcon_fit"},
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
        self.assertTrue(all(gap["research_state"] == "Por investigar" for gap in self.gaps["gaps"]))
        self.assertTrue(all("attempts_completed" in gap and "next_due_at" in gap for gap in self.gaps["gaps"]))
        self.assertEqual(self.gaps["engine"]["strategy_profile"], "adaptive-source-cascade")

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

    def test_public_projection_suppresses_unsupported_claims(self) -> None:
        field, removed = _sanitize_public_field("technology_signals", {"value": ["Zero Trust"], "items": [{"value": "Zero Trust", "evidence": []}], "evidence": []})
        self.assertEqual(field["value"], [])
        self.assertEqual(removed, 1)
        scalar, removed = _sanitize_public_field("revenue", {"value": "100 M€", "evidence": []})
        self.assertIsNone(scalar["value"])
        self.assertEqual(removed, 1)

    def test_client_area_and_vendor_fit_are_evidence_backed(self) -> None:
        client_ev = {"source": "Cliente", "title": "Zero Trust programme", "url": "https://client.example/security", "date": "2026-09-01", "description": "Zero Trust cybersecurity programme", "scope": "ES", "official": True}
        vendor_ev = {"source": "Vendor", "title": "Cybersecurity", "url": "https://vendor.example/security", "date": "2026-09-01", "description": "Cybersecurity platform", "scope": "IBERIA", "official": True}
        data = {
            "schemas": {"clients_private": [], "clients_public": []},
            "manufacturers": [{"name": "Vendor", "fields": {"domain": {"value": "Cybersecurity", "evidence": [vendor_ev]}}}],
            "clients_private": [{"name": "Cliente", "fields": {"technology_signals": {"value": ["Zero Trust"], "items": [{"value": "Zero Trust", "evidence": [client_ev]}], "evidence": [client_ev]}}}],
            "clients_public": [],
        }
        derive_client_intelligence(data)
        fields = data["clients_private"][0]["fields"]
        self.assertIn("Cybersecurity", fields["westcon_area"]["value"])
        self.assertIn("Vendor", fields["westcon_fit"]["value"])
        fit = next(item for item in fields["westcon_fit"]["items"] if item["value"] == "Vendor")
        self.assertTrue(all(str(ev.get("url") or "").startswith("http") for ev in fit["evidence"]))
        self.assertGreaterEqual(len(fit["evidence"]), 2)

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
