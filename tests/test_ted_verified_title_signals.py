"""Exact TED title recovery must never certify a search snippet or installed stack."""

import unittest

from engine.knowledge_provenance import typed_evidence_sufficient
from engine.provenance import evidence_for_item
from engine.research.ted_title_signals import (
    literal_claims, recover_verified_title_signals, derive_verified_westcon_areas,
)
from scripts.backfill_ted_title_signals import backfill


NUMBER = "123456-2026"
BUYER = "Diputación de Barcelona"
TITLE = "Renovación de SASE y Microsoft 365 para servicios en la nube"


def record(title=TITLE, *, buyer=BUYER, number=NUMBER):
    proof = {
        "source": "TED", "url": f"https://ted.europa.eu/en/notice/-/detail/{number}",
        "title": f"{number} · {title}", "date": "2026-11-20",
        "description": f"{buyer} · {title}", "retrieved_at": "2026-11-27",
        "scope": "ES", "official": True, "source_grade": "A",
        "source_type": "official-procurement-api", "classification": "public",
        "method": "ted-exact-procedure", "source_binding": "claim-specific",
        "researched_entity": buyer, "field": "evidenced_needs",
        "item_value": title, "atomic": True,
    }
    return {
        "name": buyer,
        "fields": {
            "notice_id": {"value": number},
            "evidenced_needs": {"value": [title], "items": [{"value": title, "evidence": [proof]}]},
        },
    }


class VerifiedTedTitleExtraction(unittest.TestCase):
    def test_extracts_exact_signals_domains_and_named_vendor(self):
        buyer = record()
        counts = recover_verified_title_signals(buyer, checked_date="2026-11-27")
        self.assertEqual(counts["technology_signals"], 3)  # SASE, Microsoft 365, nube
        self.assertEqual(counts["technology_domains"], 2)
        self.assertEqual(counts["identified_vendors"], 1)
        signals = buyer["fields"]["technology_signals"]
        self.assertIn("SASE", signals["value"])
        for item in signals["items"]:
            evidence = item["evidence"][0]
            self.assertTrue(typed_evidence_sufficient(evidence))
            self.assertEqual(evidence["field"], "technology_signals")
            self.assertEqual(evidence["item_value"], item["value"])
            self.assertEqual(evidence["url"], f"https://ted.europa.eu/en/notice/-/detail/{NUMBER}")
            self.assertEqual(len(evidence_for_item(
                item["evidence"], BUYER, item["value"], field_id="technology_signals"
            )), 1)
        self.assertEqual(buyer["fields"]["identified_vendors"]["value"], ["Microsoft"])
        self.assertIn("no demuestra uso, compra ni adjudicación",
                      buyer["fields"]["identified_vendors"]["items"][0]["evidence"][0]["description"])

    def test_rejects_wider_meaning_and_social_networks(self):
        self.assertEqual(literal_claims("Gestión de redes sociales y seguridad de edificios"), [])
        self.assertEqual(literal_claims("Servicio integral de sistemas informáticos"), [])
        self.assertEqual(literal_claims("Servicios de compañía y sociedad municipal"), [])

    def test_does_not_accept_mismatched_buyer_notice_or_title(self):
        manipulations = (
            lambda r: r.update({"name": "Ayuntamiento de Murcia"}),
            lambda r: r["fields"]["notice_id"].update({"value": "654321-2026"}),
            lambda r: r["fields"]["evidenced_needs"]["items"][0]["evidence"][0].update({"item_value": "Otro título"}),
            lambda r: r["fields"]["evidenced_needs"]["items"][0]["evidence"][0].update({"url": "https://example.com/blog"}),
            lambda r: r["fields"]["evidenced_needs"]["items"][0]["evidence"][0].update({"method": "search-discovery"}),
            lambda r: r["fields"]["evidenced_needs"]["items"][0]["evidence"][0].update({"atomic": False}),
            lambda r: r["fields"]["evidenced_needs"]["items"][0]["evidence"][0].update({"source_binding": "discovery-only"}),
        )
        for change in manipulations:
            with self.subTest(change=change):
                buyer = record()
                change(buyer)
                self.assertFalse(recover_verified_title_signals(buyer, checked_date="2026-11-27"))

    def test_is_idempotent_and_preserves_other_claims(self):
        buyer = record()
        buyer["fields"]["technology_signals"] = {
            "value": ["PAM"], "items": [{"value": "PAM", "evidence": []}]
        }
        first = recover_verified_title_signals(buyer, checked_date="2026-11-27")
        self.assertGreater(sum(first.values()), 0)
        second = recover_verified_title_signals(buyer, checked_date="2026-11-28")
        self.assertEqual(sum(second.values()), 0)
        self.assertIn("PAM", buyer["fields"]["technology_signals"]["value"])
        pam = next(x for x in buyer["fields"]["technology_signals"]["items"] if x["value"] == "PAM")
        self.assertEqual(pam["evidence"], [])

    def test_offline_batch_never_fabricates_empty_clients(self):
        data = {"clients_public": [record(), {"name": "Sin fuentes", "fields": {}}]}
        first = backfill(data, checked_date="2026-11-27")
        self.assertEqual(first["buyers_with_new_atomic_claims"], 1)
        self.assertEqual(first["new_atomic_claims"], 8)
        self.assertFalse(backfill(data, checked_date="2026-11-27").get("new_atomic_claims"))

    def test_derived_westcon_area_requires_reproducible_official_title(self):
        buyer = record()
        buyer["fields"]["westcon_area"] = {
            "value": ["Cloud", "Networking"],
            "items": [{"value": "Cloud", "evidence": []},
                      {"value": "Networking", "evidence": []}],
        }
        counts = derive_verified_westcon_areas(buyer, checked_date="2026-11-27")
        self.assertEqual(counts["westcon_area"], 2)
        area = buyer["fields"]["westcon_area"]
        for item in area["items"]:
            if item["value"] == "Networking":
                self.assertEqual(item["evidence"], [])
                continue
            self.assertTrue(item["evidence"])
            proof = item["evidence"][0]
            self.assertEqual(proof["derivation_rule"], "official-TED-title ∩ TITLE_RULES.domain")
            self.assertEqual(proof["derived_from_field"], "evidenced_needs")
            self.assertEqual(proof["derived_from_value"], TITLE)
            self.assertEqual(proof["item_value"], item["value"])
            self.assertTrue(typed_evidence_sufficient(proof))
        self.assertNotIn("westcon_fit", buyer["fields"])
        self.assertEqual(sum(derive_verified_westcon_areas(buyer, checked_date="2026-11-28").values()), 0)

    def test_cannot_derive_area_from_unrelated_or_non_ted_page(self):
        buyer = record(title="Gestión de redes sociales y seguridad de edificios")
        self.assertFalse(derive_verified_westcon_areas(buyer, checked_date="2026-11-27"))
        other = record()
        other["fields"]["evidenced_needs"]["items"][0]["evidence"][0]["method"] = "search-discovery"
        self.assertFalse(derive_verified_westcon_areas(other, checked_date="2026-11-27"))


if __name__ == "__main__":
    unittest.main()
