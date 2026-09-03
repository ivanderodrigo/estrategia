from __future__ import annotations

import json
import unittest
from pathlib import Path

from engine.enrichment import normalize_fields
from engine.knowledge_provenance import apply_westcon_document_provenance, provenance_kind

ROOT = Path(__file__).resolve().parents[1]
DOC = "Westcon_Comstor_Espana_FY27_completa.pptx"


def _doc_evidence(rows):
    return [
        ev for ev in (rows or [])
        if isinstance(ev, dict)
        and provenance_kind(ev) == "WESTCON_DOCUMENT"
        and ev.get("document") == DOC
    ]


class DocumentProvenanceV404(unittest.TestCase):
    def test_document_coexists_with_public_evidence_and_is_atomic(self) -> None:
        public = {
            "source": "1Password",
            "title": "Enterprise password management",
            "url": "https://example.com/1password",
            "date": "2026-01-01",
            "description": "Official product information.",
            "source_type": "official",
            "official": True,
            "source_grade": "A",
        }
        data = {
            "manufacturers": [{
                "id": "mfr-1password",
                "name": "1Password",
                "fields": {
                    "domain": {"value": "Cybersecurity", "evidence": [public], "confidence": 0.88},
                    "capabilities": {
                        "value": ["Password Management", "Secrets", "Access"],
                        "evidence": [public],
                        "items": [
                            {"value": "Password Management", "evidence": [public], "confidence": 0.88},
                            {"value": "Secrets", "evidence": [], "confidence": 0.49},
                            {"value": "Access", "evidence": [], "confidence": 0.49},
                        ],
                    },
                },
            }]
        }
        stats = apply_westcon_document_provenance(data)
        row = data["manufacturers"][0]
        field = row["fields"]["capabilities"]
        self.assertTrue(_doc_evidence(field["evidence"]))
        self.assertGreaterEqual(stats["manufacturer_capability_items_documented"], 3)
        for item in field["items"]:
            docs = _doc_evidence(item.get("evidence"))
            self.assertTrue(docs, item["value"])
            self.assertEqual(docs[0].get("item_value"), item["value"])
            self.assertEqual(docs[0].get("field"), "capabilities")
            self.assertTrue(docs[0].get("atomic"))
            self.assertGreaterEqual(float(item.get("confidence") or 0), 0.90)
            self.assertEqual(item.get("confidence_band"), "high")
        password = next(x for x in field["items"] if x["value"] == "Password Management")
        self.assertTrue(any(str(ev.get("url") or "").startswith("http") for ev in password["evidence"]))
        apply_westcon_document_provenance(data)
        for item in field["items"]:
            self.assertEqual(len(_doc_evidence(item.get("evidence"))), 1)

    def test_release_manufacturer_capabilities_show_westcon_document(self) -> None:
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

    def test_normalizer_preserves_atomic_westcon_document_without_url(self) -> None:
        data = {
            "manufacturers": [{
                "name": "1Password",
                "fields": {
                    "capabilities": {
                        "value": ["Password Management"],
                        "items": [{
                            "value": "Password Management",
                            "evidence": [{
                                "source": "Westcon Comstor España",
                                "title": "FY27 · slide 29",
                                "url": "",
                                "date": "FY2027",
                                "description": "Documento corporativo Westcon.",
                                "scope": "ES",
                                "source_grade": "A-WESTCON",
                                "source_type": "westcon-document",
                                "document_id": "westcon-corporate-fy27",
                                "document": DOC,
                                "slide": 29,
                                "field": "capabilities",
                                "item_value": "Password Management",
                                "atomic": True,
                                "provenance_origin": "WESTCON_DOCUMENT",
                            }],
                        }],
                        "evidence": [],
                    },
                },
            }]
        }
        normalize_fields(data)
        item = data["manufacturers"][0]["fields"]["capabilities"]["items"][0]
        self.assertTrue(_doc_evidence(item.get("evidence")))

    def test_document_registry_is_current(self) -> None:
        registry = json.loads((ROOT / "config/current/document_source_registry.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(registry.get("version"), "4.0.6")
        self.assertEqual(registry.get("policy"), "typed-provenance-atomic-document")
        docs = {row.get("filename") for row in registry.get("documents") or []}
        self.assertIn(DOC, docs)


if __name__ == "__main__":
    unittest.main()
