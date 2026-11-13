import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine.research import historical_leads


class StableHistoricalSourceRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{
            "gap_id": "old-gap-id",
            "section": "architectures",
            "entity": "Zero Trust",
            "field": "vendors",
            "match_level": "exact-value-history",
            "identity_scope": "canonical-name",
            "source_urls": ["https://www.nist.gov/publications/example"],
            "historical_samples": [{
                "value": json.dumps("Okta"),
                "source_urls": ["https://www.nist.gov/publications/example"],
            }],
            "status": "HISTORICAL_RESEARCH_LEAD_NOT_VERIFIED",
        }]

    def test_exact_historical_url_survives_new_gap_id_in_architectures(self):
        mapping = historical_leads.build_identity_index(self.rows)
        gap = {
            "id": "new-gap-id",
            "section": "architectures",
            "entity": "Zero Trust",
            "field": "vendors",
            "target_values": ["Okta"],
            "gap_kind": "evidence-support",
        }
        with patch.object(historical_leads, "history_by_identity", return_value=mapping):
            leads = historical_leads.historical_revalidation_seeds(gap, index={})
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0]["url"], "https://www.nist.gov/publications/example")
        self.assertTrue(leads[0]["historical_lead"])
        self.assertFalse(leads[0]["official"])

    def test_different_claim_does_not_inherit_old_source(self):
        mapping = historical_leads.build_identity_index(self.rows)
        for entity, value, field in [
            ("Zero Trust", "Microsoft", "vendors"),
            ("Secure LAN", "Okta", "vendors"),
            ("Zero Trust", "Okta", "layers"),
        ]:
            gap = {
                "id": "old-gap-id", "section": "architectures",
                "entity": entity, "field": field,
                "target_values": [value], "gap_kind": "evidence-support",
            }
            with patch.object(historical_leads, "history_by_identity", return_value=mapping):
                self.assertEqual(historical_leads.historical_revalidation_seeds(gap, index={
                    "old-gap-id": self.rows[0]
                }), [])

    def test_truncated_or_field_only_history_never_claims_exact_match(self):
        rows = self.rows + [{
            **self.rows[0],
            "gap_id": "field-only", "match_level": "field-only-history",
            "historical_samples": [{"value": '"partial invalid'}],
        }]
        mapping = historical_leads.build_identity_index(rows)
        self.assertEqual(len(mapping), 1)

    def test_derived_field_rejected(self):
        mapping = historical_leads.build_identity_index(self.rows)
        gap = {
            "id": "fresh", "section": "architectures", "entity": "Zero Trust",
            "field": "vendors", "target_values": ["Okta"],
            "gap_kind": "derivation-support",
        }
        with patch.object(historical_leads, "history_by_identity", return_value=mapping):
            self.assertEqual(historical_leads.historical_revalidation_seeds(gap, index={}), [])


if __name__ == "__main__":
    unittest.main()
