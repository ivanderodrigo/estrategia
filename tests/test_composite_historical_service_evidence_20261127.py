"""Historical service templates require literal, local relationship evidence."""

from __future__ import annotations

import unittest

from engine.research.documents import Document
from engine.research.sources import SourceSeed
from engine.research.web_intelligence import (
    _candidate_items,
    _exact_historical_candidate,
    _explicit_composite_service_quote,
    _focus_candidates,
    _promotable_candidate_items,
)


INTEGRATION = "Integración de soluciones · Check Point"
RESALE = "Suministro / reventa · AWS"
MANAGED = "Servicios gestionados · Microsoft Azure"


def document(text: str, url: str = "https://www.acme.com/services") -> Document:
    return Document(url, "Acme services", text, (), "f" * 64)


class CompositeHistoricalServiceEvidenceTests(unittest.TestCase):
    def test_first_party_explicit_integration_proves_template(self):
        doc = document("En Acme integramos soluciones de Check Point para nuestros clientes.")
        candidate = _exact_historical_candidate(doc, [INTEGRATION], True, "Acme", "services")
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.values, (INTEGRATION,))
        self.assertIn("integramos soluciones de check point", candidate.matched_terms[0])
        self.assertNotIn("integracion de soluciones", candidate.matched_terms[0])

    def test_first_party_supplier_relation_proves_resale_template(self):
        doc = document("Acme supplies AWS cloud subscriptions to enterprises.")
        candidate = _exact_historical_candidate(doc, [RESALE], True, "Acme", "services")
        self.assertIsNotNone(candidate)
        self.assertIn("supplies aws", candidate.matched_terms[0])

    def test_first_party_explicit_management_proves_managed_service(self):
        doc = document("Acme administra Microsoft Azure y presta soporte 24x7.")
        candidate = _exact_historical_candidate(doc, [MANAGED], True, "Acme", "services")
        self.assertIsNotNone(candidate)
        self.assertIn("administra microsoft azure", candidate.matched_terms[0])

    def test_managed_service_marketing_and_vendor_logos_are_not_enough(self):
        doc = document("Acme provides managed cloud services. Vendors: Microsoft Azure, AWS.")
        self.assertIsNone(_exact_historical_candidate(doc, [MANAGED], True, "Acme", "services"))

    def test_strict_historical_target_keeps_atomically_bound_original_value(self):
        doc = document("Acme provides and implements Check Point solutions for enterprises.")
        target = {
            "entity": "Acme", "section": "integrators",
            "gap_kinds": ["historical-revalidation"],
            "target_values": {"services": [INTEGRATION]},
        }
        focused = _focus_candidates({}, target, doc, True)
        self.assertEqual(focused["services"].values, (INTEGRATION,))
        seed = SourceSeed(doc.url, "services", True, "A", "official", "Acme")
        items = _candidate_items(seed, doc, "services", focused["services"], "Acme", "ES")
        promoted, rejected = _promotable_candidate_items(items, entity="Acme", field_id="services")
        self.assertEqual(rejected, [])
        self.assertEqual([item["value"] for item in promoted], [INTEGRATION])
        ev = promoted[0]["evidence"][0]
        self.assertEqual(ev["item_value"], INTEGRATION)
        self.assertEqual(ev["researched_entity"], "Acme")
        self.assertIn("implements check point", ev["matched_terms"][0])

    def test_bare_vendor_catalogue_is_not_evidence(self):
        doc = document("Acme integrates cloud and networking systems. Partners: Check Point, AWS, Cisco.")
        self.assertEqual(_explicit_composite_service_quote("Acme", INTEGRATION, doc, field_id="services"), "")
        self.assertIsNone(_exact_historical_candidate(doc, [INTEGRATION], True, "Acme", "services"))

    def test_vendor_in_different_sentence_is_not_evidence(self):
        doc = document("Acme integrates solutions. We work with Check Point in a separate context.")
        self.assertIsNone(_exact_historical_candidate(doc, [INTEGRATION], True, "Acme", "services"))

    def test_denial_does_not_accredit(self):
        doc = document("Acme does not integrate Check Point. We specialize in cybersecurity.")
        self.assertIsNone(_exact_historical_candidate(doc, [INTEGRATION], True, "Acme", "services"))

    def test_third_party_page_requires_explicit_entity_in_local_phrase(self):
        doc = document("Our team integrates Check Point security products.", "https://press.example.net/news")
        self.assertIsNone(_exact_historical_candidate(doc, [INTEGRATION], False, "Acme", "services"))
        named = document("Acme integrates Check Point security products.", "https://press.example.net/news")
        self.assertIsNotNone(_exact_historical_candidate(named, [INTEGRATION], False, "Acme", "services"))

    def test_cannot_infer_different_vendor_or_other_field(self):
        doc = document("Acme integrates Palo Alto solutions and distributes AWS subscriptions.")
        self.assertIsNone(_exact_historical_candidate(doc, [INTEGRATION], True, "Acme", "services"))
        self.assertIsNotNone(_exact_historical_candidate(doc, [RESALE], True, "Acme", "services"))
        self.assertEqual(_explicit_composite_service_quote("Acme", RESALE, doc, field_id="verticals"), "")

    def test_unformatted_service_description_is_not_mistaken_for_template(self):
        doc = document("Acme integrates managed cloud solutions.")
        self.assertEqual(_explicit_composite_service_quote("Acme", "Servicios gestionados de cloud", doc, field_id="services"), "")


if __name__ == "__main__":
    unittest.main()
