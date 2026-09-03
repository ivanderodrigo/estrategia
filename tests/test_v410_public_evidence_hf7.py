from __future__ import annotations

import unittest

from engine.knowledge_provenance import (
    accrediting_evidence,
    apply_public_evidence_migrations,
    convert_internal_lineage_to_research_seeds,
    provenance_kind,
    typed_evidence_sufficient,
)


def doc():
    return {
        "source": "Westcon", "title": "Deck", "date": "FY2027", "description": "Internal clue",
        "document": "deck.pptx", "source_type": "westcon-document", "provenance_origin": "WESTCON_DOCUMENT",
    }


def public():
    return {
        "source": "Vendor", "title": "Official", "date": "2026-09-02", "description": "Public proof",
        "url": "https://vendor.example/capability", "official": True, "source_grade": "A2",
        "source_type": "official-vendor-web", "provenance_origin": "PUBLIC_PRIMARY",
    }


class PublicEvidenceHF7(unittest.TestCase):
    def test_internal_document_is_hint_not_proof(self):
        self.assertFalse(typed_evidence_sufficient(doc()))
        self.assertFalse(accrediting_evidence(doc()))
        self.assertTrue(accrediting_evidence(public()))

    def test_document_is_converted_without_losing_clue(self):
        data = {"manufacturers": [{"fields": {"capabilities": {"value": ["SASE"], "items": [{"value": "SASE", "evidence": [doc()]}]}}}]}
        stats = convert_internal_lineage_to_research_seeds(data)
        ev = data["manufacturers"][0]["fields"]["capabilities"]["items"][0]["evidence"][0]
        self.assertEqual(stats["document_rows_converted"], 1)
        self.assertEqual(provenance_kind(ev), "RESEARCH_SEED")
        self.assertEqual(ev["original_provenance_origin"], "WESTCON_DOCUMENT")
        self.assertFalse(accrediting_evidence(ev))

    def test_public_migration_never_creates_missing_value(self):
        data = {"manufacturers": [{"id": "check", "name": "Check Point", "fields": {"capabilities": {"value": ["SASE"], "items": [{"value": "SASE", "evidence": []}]}}}]}
        migrations = {"claims": [
            {"section": "manufacturers", "entity": "Check Point", "field": "capabilities", "value": "SASE", "evidence": public()},
            {"section": "manufacturers", "entity": "Check Point", "field": "capabilities", "value": "NOT PRESENT", "evidence": public()},
        ]}
        stats = apply_public_evidence_migrations(data, migrations)
        self.assertEqual(stats["matched"], 1)
        self.assertEqual(stats["unmatched"], 1)
        field = data["manufacturers"][0]["fields"]["capabilities"]
        self.assertEqual(field["value"], ["SASE"])
        self.assertTrue(accrediting_evidence(field["items"][0]["evidence"][0]))


if __name__ == "__main__":
    unittest.main()
