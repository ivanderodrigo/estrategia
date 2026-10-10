from __future__ import annotations

import inspect
import unittest

from engine.preservation import restore_accredited_support, restore_research_seed_support
from engine.research.documents import Document
from engine.research.web_intelligence import _field_context_ok, _subject_value_match


def public_evidence(owner: str, value: str, field: str):
    # Must satisfy typed_evidence_sufficient(): source/title/date/description + URL.
    return {
        "source": "example.com",
        "title": f"{owner} {value}",
        "date": "2026-10-10",
        "description": f"{owner} works with {value}",
        "url": "https://example.com/relationship",
        "classification": "public",
        "provenance_origin": "PUBLIC_PRIMARY",
        "source_binding": "claim-specific",
        "researched_entity": owner,
        "item_value": value,
        "item_key": value.casefold(),
        "atomic": True,
        "field": field,
        "accrediting": True,
    }


class HF6R5RuntimeAndCleanup(unittest.TestCase):
    def test_field_context_revenue_has_no_free_runtime_names(self):
        source = inspect.getsource(_field_context_ok)
        self.assertNotIn("revenue_anchors", source)
        self.assertNotIn("target_positions", source)
        self.assertNotIn("entity_key", source)
        self.assertTrue(_field_context_ok(
            "revenue",
            "example reported total revenue of usd 12.4 billion in 2025",
            entity_owned=True,
        ))

    def test_existing_non_revenue_context_semantics_are_preserved(self):
        self.assertTrue(_field_context_ok(
            "capabilities", "we provide zero trust services", entity_owned=True
        ))
        self.assertTrue(_field_context_ok(
            "verticals", "industries financial services", entity_owned=False
        ))
        self.assertTrue(_field_context_ok(
            "technology_signals", "cloud security project", entity_owned=False
        ))
        self.assertTrue(_field_context_ok(
            "public_cases", "customer success case study", entity_owned=False
        ))

    def test_subject_revenue_rejects_non_financial_value_without_nameerror(self):
        doc = Document(
            url="https://example.com/investors",
            title="Example investors",
            text="Example announced a partnership in 2025.",
            links=(),
            content_digest="r5",
        )
        self.assertFalse(_subject_value_match(
            "Example", "partnership in 2025", doc, field_id="revenue"
        ))

    def test_restore_accredited_support_skips_build_owned_relationship_view(self):
        bad = public_evidence("1Password", "3Hold Technologies", "integrators")
        baseline = {
            "manufacturers": [{
                "name": "1Password",
                "fields": {
                    "integrators": {
                        "value": ["3Hold Technologies"],
                        "items": [{"value": "3Hold Technologies", "evidence": [bad]}],
                        "evidence": [bad],
                    }
                },
            }]
        }
        current = {
            "schemas": {"manufacturers": [{"id": "integrators"}]},
            "manufacturers": [{
                "name": "1Password",
                "fields": {
                    "integrators": {
                        "value": ["3Hold Technologies"],
                        "items": [{"value": "3Hold Technologies", "evidence": []}],
                        "evidence": [],
                    }
                },
            }],
        }
        stats = restore_accredited_support(current, baseline)
        item = current["manufacturers"][0]["fields"]["integrators"]["items"][0]
        self.assertEqual(item["evidence"], [])
        self.assertEqual(stats["item_evidence_restored"], 0)

    def test_restore_accredited_support_still_restores_normal_exact_claim(self):
        ev = public_evidence("Example", "Zero Trust", "capabilities")
        baseline = {
            "manufacturers": [{
                "name": "Example",
                "fields": {
                    "capabilities": {
                        "value": ["Zero Trust"],
                        "items": [{"value": "Zero Trust", "evidence": [ev]}],
                        "evidence": [ev],
                    }
                },
            }]
        }
        current = {
            "schemas": {"manufacturers": [{"id": "capabilities"}]},
            "manufacturers": [{
                "name": "Example",
                "fields": {
                    "capabilities": {
                        "value": ["Zero Trust"],
                        "items": [{"value": "Zero Trust", "evidence": []}],
                        "evidence": [],
                    }
                },
            }],
        }
        stats = restore_accredited_support(current, baseline)
        item = current["manufacturers"][0]["fields"]["capabilities"]["items"][0]
        self.assertTrue(item["evidence"])
        self.assertGreaterEqual(stats["item_evidence_restored"], 1)

    def test_research_seed_on_linecard_still_survives(self):
        seed = {
            "source": "Internal memory",
            "title": "Partner clue",
            "date": "baseline",
            "description": "research clue only",
            "source_type": "research-seed",
            "provenance_origin": "RESEARCH_SEED",
            "source_binding": "discovery-only",
            "classification": "research-seed",
            "accrediting": False,
        }
        before = {
            "integrators": [{
                "id": "partner-a",
                "name": "Partner A",
                "fields": {
                    "vendor_relations": {
                        "value": ["Fortinet · Expert"],
                        "items": [{"value": "Fortinet · Expert", "evidence": [seed]}],
                    }
                },
            }]
        }
        after = {
            "integrators": [{
                "id": "partner-a",
                "name": "Partner A",
                "fields": {
                    "vendor_relations": {
                        "value": ["Fortinet · Expert / Advanced"],
                        "items": [{"value": "Fortinet · Expert / Advanced", "evidence": []}],
                    }
                },
            }]
        }
        stats = restore_research_seed_support(after, before)
        item = after["integrators"][0]["fields"]["vendor_relations"]["items"][0]
        self.assertTrue(item["evidence"])
        self.assertGreaterEqual(stats["linecard_seed_rows_restored"], 1)


if __name__ == "__main__":
    unittest.main()
