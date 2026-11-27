"""v7.2: CPV accreditation requires fresh official TED notice evidence."""
import unittest
from pathlib import Path
from unittest.mock import Mock

from engine.provenance import evidence_for_item
from engine.knowledge_provenance import typed_evidence_sufficient
from scripts.revalidate_ted_cpv import (
    eligible_notices, reconcile_notice, reconcile_selected_winners,
    reconcile_eu_programmes, reconcile_description_technologies, retrieve_batch, _api_payload,
)


def row(code="30234000", owner="DIPUTACIÓN DE BARCELONA",
        number="123456-2026"):
    return {
        "name": owner,
        "fields": {
            "notice_id": {"value": number},
            "cpv_codes": {"value": [code], "items": [
                {"value": code, "evidence": []}
            ]},
        },
    }


def notice(code="30234000", number="123456-2026",
           buyer="DIPUTACIÓN DE BARCELONA"):
    return {
        "publication-number": number,
        "buyer-name": buyer,
        "notice-title": {"spa": "Compra de equipamiento de red"},
        "classification-cpv": [code],
        "publication-date": "2026-11-12",
    }


class TedExactCPVProvenance(unittest.TestCase):
    def test_cached_official_proofs_always_refresh_published_debt(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/ted-cpv-revalidate.yml").read_text(encoding="utf-8")
        self.assertIn("run: python -m engine.pipeline", workflow)
        self.assertLess(workflow.index("run: python -m engine.pipeline"),
                        workflow.index("name: Validate that reconstructed output"))

    def test_indexes_existing_notice_without_guessing_unknown_ids(self):
        source = row()
        skipped = row(number="unknown")
        idx = eligible_notices({"clients_public": [source, skipped]})
        self.assertEqual(list(idx), ["123456-2026"])
        self.assertEqual(idx["123456-2026"], [source])

    def test_exact_api_cpv_is_atomic_support_for_same_claim(self):
        source = row()
        n = reconcile_notice(
            source, notice(), claimed_number="123456-2026",
            checked_date="2026-11-13",
        )
        self.assertEqual(n, 1)
        item = source["fields"]["cpv_codes"]["items"][0]
        self.assertEqual(item["value"], "30234000")
        evidence = item["evidence"]
        self.assertEqual(len(evidence), 1)
        self.assertTrue(typed_evidence_sufficient(evidence[0]))
        self.assertEqual(len(evidence_for_item(
            evidence, source["name"], "30234000", field_id="cpv_codes",
        )), 1)
        self.assertFalse(evidence_for_item(
            evidence, source["name"], "30234100", field_id="cpv_codes",
        ))

    def test_rejects_old_code_not_on_official_notice(self):
        source = row()
        count = reconcile_notice(source, notice(code="30200000"),
                                 claimed_number="123456-2026", checked_date="2026-11-13")
        self.assertEqual(count, 0)
        self.assertEqual(source["fields"]["cpv_codes"]["items"][0]["evidence"], [])

    def test_rejects_wrong_notice_or_wrong_buyer(self):
        for actual in (
            notice(number="777777-2026"),
            notice(buyer="COMUNIDAD DE MADRID"),
        ):
            with self.subTest(actual=actual):
                source = row()
                self.assertEqual(reconcile_notice(
                    source, actual,
                    claimed_number="123456-2026", checked_date="2026-11-13",
                ), 0)

    def test_does_not_repeat_accreditation_on_second_run(self):
        source = row()
        first = reconcile_notice(source, notice(),
                                 claimed_number="123456-2026", checked_date="2026-11-13")
        second = reconcile_notice(source, notice(),
                                  claimed_number="123456-2026", checked_date="2026-11-13")
        self.assertEqual((first, second), (1, 0))

    def test_procedure_title_and_estimate_stay_bound_to_buyer_and_notice(self):
        from scripts.revalidate_ted_cpv import reconcile_procurement_facts
        source = row()
        record = dict(notice(), **{"title-proc":{"spa":"Equipamiento de red"},
            "estimated-value-proc":"1040.75", "estimated-value-cur-proc":"EUR"})
        self.assertEqual(reconcile_procurement_facts(source,record,"123456-2026","2026-11-27"), 2)
        self.assertEqual(reconcile_procurement_facts(source,record,"123456-2026","2026-11-27"), 0)
        self.assertIn("1040.75 EUR", source["fields"]["investment_signals"]["value"][0])
        record["buyer-name"] = "DIPUTACIÓN DE VALENCIA"
        self.assertEqual(reconcile_procurement_facts(row(),record,"123456-2026","2026-11-27"), 0)

    def test_api_scope_is_all_notices_including_closed(self):
        payload = _api_payload(["123456-2026", "234567-2025"])
        self.assertEqual(payload["scope"], "ALL")
        self.assertEqual(payload["query"],
                         "publication-number IN (123456-2026 234567-2025)")
        self.assertIn("classification-cpv", payload["fields"])
        self.assertIn("winner-name", payload["fields"])
        self.assertIn("eu-funds-programme-lot", payload["fields"])
        self.assertIn("eu-funds-name", payload["fields"])
        self.assertIn("description-lot", payload["fields"])
        self.assertIn("description-proc", payload["fields"])
        self.assertIn("title-lot", payload["fields"])

    def test_official_selected_winner_is_supplier_not_inferred_integrator(self):
        source = row()
        published = dict(notice(), **{"winner-name": ["Empresa Adjudicataria SL", "Proveedor PT Lda"]})
        first = reconcile_selected_winners(source, published, "123456-2026", "2026-11-27")
        self.assertEqual(first, 2)
        self.assertEqual(reconcile_selected_winners(source, published, "123456-2026", "2026-11-27"), 0)
        field = source["fields"]["identified_integrators"]
        self.assertIn("Proveedor PT Lda", field["value"])
        self.assertIn("no confirma que sea integrador", field["qualifier"])
        for item in field["items"]:
            ev = item["evidence"][0]
            self.assertTrue(typed_evidence_sufficient(ev))
            self.assertEqual(ev["item_value"], item["value"])
            self.assertEqual(ev["method"], "ted-selected-winning-tender-v1")

    def test_rejects_winner_if_buyer_or_notice_mismatches_or_no_selected_tender(self):
        original = dict(notice(), **{"winner-name": ["Empresa Adjudicataria SL"]})
        for unsupported in (
            dict(original, **{"buyer-name": "Ayuntamiento de Murcia"}),
            dict(original, **{"publication-number": "654321-2026"}),
            dict(original, **{"winner-name": []}),
            dict(original, **{"winner-name": ["unknown"]}),
        ):
            with self.subTest(unsupported=unsupported):
                source = row()
                self.assertEqual(reconcile_selected_winners(source, unsupported,
                    "123456-2026", "2026-11-27"), 0)
                self.assertNotIn("identified_integrators", source["fields"])

    def test_eu_funding_must_be_declared_in_exact_notice_not_inferred(self):
        buyer = row()
        published = dict(notice(), **{
            "eu-funds-programme-lot": ["ERDF", "EU4Health"],
            "eu-funds-name": None,
        })
        self.assertEqual(reconcile_eu_programmes(buyer, published, "123456-2026", "2026-11-27"), 2)
        self.assertEqual(reconcile_eu_programmes(buyer, published, "123456-2026", "2026-11-27"), 0)
        programme = buyer["fields"]["strategic_programs"]
        self.assertIn("Programa UE indicado en TED: ERDF", programme["value"])
        self.assertIn("no implica un programa estratégico propio", programme["qualifier"])
        for item in programme["items"]:
            proof = item["evidence"][0]
            self.assertEqual(proof["item_value"], item["value"])
            self.assertEqual(proof["field"], "strategic_programs")
            self.assertTrue(typed_evidence_sufficient(proof))
        for altered in (
            dict(published, **{"buyer-name": "Otro comprador"}),
            dict(published, **{"publication-number": "654321-2026"}),
            dict(published, **{"eu-funds-programme-lot": ["yes", "false", "unknown"], "eu-funds-name": []}),
        ):
            self.assertEqual(reconcile_eu_programmes(row(), altered, "123456-2026", "2026-11-27"), 0)

    def test_exact_description_only_promotes_explicit_technology_mentions(self):
        published = dict(notice(), **{
            "description-proc": {"spa": "Servicio de operación SOC y firewalls de nueva generación para la red municipal."},
            "description-lot": [{"spa": "Suministro de equipamiento de red LAN, infraestructura de red y backup."}],
            "title-lot": [],
        })
        buyer = row()
        first = reconcile_description_technologies(buyer, published, "123456-2026", "2026-11-27")
        self.assertGreaterEqual(first, 4)
        self.assertEqual(reconcile_description_technologies(buyer, published, "123456-2026", "2026-11-27"), 0)
        self.assertIn("SOC", buyer["fields"]["technology_signals"]["value"])
        self.assertIn("Data Center", buyer["fields"]["technology_domains"]["value"])
        self.assertNotIn("identified_vendors", buyer["fields"])
        for field_name in ("technology_signals", "technology_domains"):
            for item in buyer["fields"][field_name]["items"]:
                ev = item["evidence"][0]
                self.assertEqual(ev["field"], field_name)
                self.assertEqual(ev["item_value"], item["value"])
                self.assertEqual(ev["method"], "ted-literal-description-v1")
                self.assertTrue(typed_evidence_sufficient(ev))

    def test_description_cannot_substitute_for_wrong_buyer_or_irrelevant_text(self):
        original = dict(notice(), **{"description-lot": [
            "Servicio de gestión de redes sociales y seguridad de edificios municipales."
        ]})
        self.assertEqual(reconcile_description_technologies(row(), original,
            "123456-2026", "2026-11-27"), 0)
        original["description-lot"] = ["Servicio de plataforma de ciberseguridad municipal."]
        for unsupported in (
            dict(original, **{"buyer-name": "Otro comprador"}),
            dict(original, **{"publication-number": "654321-2026"}),
        ):
            self.assertEqual(reconcile_description_technologies(row(), unsupported,
                "123456-2026", "2026-11-27"), 0)

    def test_unavailable_batch_keeps_all_claims_unconfirmed(self):
        session = Mock()
        session.post.side_effect = RuntimeError("service down")
        # Unknown application errors should propagate rather than certifying
        # a source that was never fetched.
        with self.assertRaises(RuntimeError):
            retrieve_batch(session, ["123456-2026"])


if __name__ == "__main__":
    unittest.main()
