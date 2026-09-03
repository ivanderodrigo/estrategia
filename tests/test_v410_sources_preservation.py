from __future__ import annotations

import copy
import json
import unittest

from engine.knowledge_provenance import accrediting_evidence, typed_evidence_sufficient
from engine.preservation import audit, snapshot
from engine.publication import public_payloads
from engine.settings import SECTIONS
from engine.storage import read_json


def public_evidence() -> dict:
    return {
        "source": "Fabricante oficial", "title": "Capability", "date": "2026-08-20",
        "description": "La fuente atribuye explícitamente el dato al sujeto.",
        "url": "https://vendor.example/capability", "official": True,
        "source_grade": "A", "source_type": "official-domain",
        "provenance_origin": "PUBLIC_PRIMARY",
    }


def westcon_evidence(source: str = "Presentación Westcon") -> dict:
    return {
        "source": source, "title": "Presentación Corporativa FY2027 · slide 44",
        "date": "FY2027", "description": "Capacidad documentada por Westcon.",
        "document": "Westcon_Comstor_Espana_FY27_completa.pptx", "slide": 44,
        "source_type": "westcon-document", "provenance_origin": "WESTCON_DOCUMENT",
        "official": True, "source_grade": "A-WESTCON",
    }


def historical_evidence() -> dict:
    return {
        "source": "Histórico del proyecto", "title": "Linaje recuperado", "date": "2025-01-01",
        "description": "Memoria de investigación.", "url": "https://old.example/source",
        "source_type": "legacy-unresolved", "provenance_origin": "HISTORICAL_RECOVERED",
    }


class SimplifiedSourceContract(unittest.TestCase):
    def test_public_projection_only_exposes_accrediting_sources(self) -> None:
        field = {
            "value": ["SASE"],
            "items": [{"value": "SASE", "evidence": [
                historical_evidence(), westcon_evidence("Portfolio Westcon"),
                westcon_evidence("Presentación Westcon"), public_evidence(),
            ]}],
        }
        data = {
            "meta": {"version": "4.1.0"}, "schemas": {section: [] for section in SECTIONS},
            "source_catalog": [],
            **{section: [] for section in SECTIONS},
        }
        data["manufacturers"] = [{"id": "vendor", "name": "Vendor", "fields": {"capabilities": field}}]
        data["schemas"]["manufacturers"] = [{"id": "capabilities", "label": "Capacidades"}]
        files, manifest = public_payloads(data)
        payload = json.loads(files["data/public/sections/manufacturers.json"].decode("utf-8"))
        evidence = list(payload["evidence"].values())
        self.assertEqual(len(evidence), 1)  # internal deck/history never reach public sources
        self.assertEqual({row["source_role"] for row in evidence}, {"Fuente pública primaria"})
        self.assertFalse(any("HISTORICAL" in str(row.get("provenance_origin")) for row in evidence))
        self.assertEqual(len(manifest["source_catalog"]), 1)

    def test_discovery_source_cannot_accredit(self) -> None:
        candidate = public_evidence() | {"source_binding": "discovery-only"}
        self.assertFalse(typed_evidence_sufficient(candidate))
        self.assertFalse(accrediting_evidence(candidate))
        self.assertTrue(accrediting_evidence(public_evidence()))
        self.assertFalse(typed_evidence_sufficient(westcon_evidence()))
        self.assertFalse(accrediting_evidence(westcon_evidence()))

    def test_internal_history_is_preserved(self) -> None:
        data = read_json("data/current/intelligence.json")
        blob = json.dumps(data, ensure_ascii=False)
        self.assertIn("HISTORICAL_", blob)


class KnowledgePreservationGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = read_json("data/current/intelligence.json")
        cls.graph = read_json("data/current/relationship_graph.json")
        cls.before = snapshot(cls.data, cls.graph)

    def test_unchanged_or_additive_result_passes(self) -> None:
        report = audit(self.before, copy.deepcopy(self.before), {})
        self.assertEqual(report["status"], "PASS")

    def test_each_loss_class_blocks_release(self) -> None:
        for key, message in (
            ("entities", "Entidades desaparecidas"),
            ("values", "Valores poblados desaparecidos"),
            ("evidences", "Soportes acreditativos desaparecidos"),
            ("relations", "Relaciones válidas desaparecidas"),
        ):
            with self.subTest(key=key):
                after = copy.deepcopy(self.before)
                if key in {"entities", "values"}:
                    bucket = next(name for name, rows in after[key].items() if rows)
                    after[key][bucket] = after[key][bucket][1:]
                else:
                    self.assertTrue(after[key])
                    after[key] = after[key][1:]
                report = audit(self.before, after, {})
                self.assertEqual(report["status"], "FAIL")
                self.assertTrue(any(message in error for error in report["errors"]))

    def test_existing_public_acceptances_are_monotonic(self) -> None:
        ledger = read_json("data/current/research_ledger.json")
        accepted = int(ledger.get("accepted_evidences") or 0)
        self.assertGreaterEqual(accepted, 8)
        self.assertGreaterEqual(sum(int(row.get("accepted") or 0) for row in ledger.get("results") or []), 8)


if __name__ == "__main__":
    unittest.main()
