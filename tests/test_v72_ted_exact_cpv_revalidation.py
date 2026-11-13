"""v7.2: CPV accreditation requires fresh official TED notice evidence."""
import unittest
from unittest.mock import Mock

from engine.provenance import evidence_for_item
from engine.knowledge_provenance import typed_evidence_sufficient
from scripts.revalidate_ted_cpv import (
    eligible_notices, reconcile_notice, retrieve_batch, _api_payload,
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

    def test_api_scope_is_all_notices_including_closed(self):
        payload = _api_payload(["123456-2026", "234567-2025"])
        self.assertEqual(payload["scope"], "ALL")
        self.assertEqual(payload["query"],
                         "publication-number IN (123456-2026 234567-2025)")
        self.assertIn("classification-cpv", payload["fields"])

    def test_unavailable_batch_keeps_all_claims_unconfirmed(self):
        session = Mock()
        session.post.side_effect = RuntimeError("service down")
        # Unknown application errors should propagate rather than certifying
        # a source that was never fetched.
        with self.assertRaises(RuntimeError):
            retrieve_batch(session, ["123456-2026"])


if __name__ == "__main__":
    unittest.main()
