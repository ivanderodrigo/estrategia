from __future__ import annotations

import unittest

from engine.research.web_intelligence import _promotable_candidate_items


def _public_evidence(*, entity="Acme", field="verticals", value="Retail", binding="atomic-item", source_type="public-web"):
    return {
        "source": "example.com",
        "title": f"{entity} {value} case",
        "url": f"https://example.com/{entity.casefold().replace(' ', '-')}/{value.casefold().replace(' ', '-')}",
        "date": "2026-10-23",
        "description": f"{entity} works in {value}.",
        "scope": "GLOBAL",
        "source_grade": "A",
        "source_type": source_type,
        "official": True,
        "classification": "public",
        "researched_entity": entity,
        "source_binding": binding,
        "field": field,
        "item_value": value,
        "item_key": value.casefold(),
        "atomic": True,
    }


class CandidatePromotionGateR20(unittest.TestCase):
    def test_valid_atomic_public_candidate_is_promoted(self):
        items = [{"value": "Retail", "evidence": [_public_evidence()]}]
        promoted, rejected = _promotable_candidate_items(
            items, entity="Acme", field_id="verticals"
        )
        self.assertEqual([item["value"] for item in promoted], ["Retail"])
        self.assertEqual(rejected, [])

    def test_discovery_only_candidate_is_not_promoted(self):
        ev = _public_evidence(binding="discovery-only")
        items = [{"value": "Retail", "evidence": [ev]}]
        promoted, rejected = _promotable_candidate_items(
            items, entity="Acme", field_id="verticals"
        )
        self.assertEqual(promoted, [])
        self.assertEqual(rejected[0]["reason"], "typed-evidence-insufficient")

    def test_wrong_atomic_item_value_is_not_promoted(self):
        ev = _public_evidence(value="Healthcare")
        items = [{"value": "Retail", "evidence": [ev]}]
        promoted, rejected = _promotable_candidate_items(
            items, entity="Acme", field_id="verticals"
        )
        self.assertEqual(promoted, [])
        self.assertEqual(rejected[0]["reason"], "research-binding-metadata-failed")

    def test_wrong_researched_entity_is_not_promoted(self):
        ev = _public_evidence(entity="Other Corp")
        items = [{"value": "Retail", "evidence": [ev]}]
        promoted, rejected = _promotable_candidate_items(
            items, entity="Acme", field_id="verticals"
        )
        self.assertEqual(promoted, [])
        self.assertEqual(rejected[0]["reason"], "research-binding-metadata-failed")

    def test_relation_candidate_uses_endpoint_binding(self):
        ev = _public_evidence(field="distributors", value="PartnerCo")
        items = [{"value": "PartnerCo", "evidence": [ev]}]
        promoted, rejected = _promotable_candidate_items(
            items, entity="Acme", field_id="distributors"
        )
        self.assertEqual([item["value"] for item in promoted], ["PartnerCo"])
        self.assertEqual(rejected, [])


if __name__ == "__main__":
    unittest.main()
