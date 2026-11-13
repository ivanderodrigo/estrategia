"""Claim triage categorises, never converts an old assertion into evidence."""
import unittest

from scripts.triage_easy_claims import summarize


class ClaimTriageTests(unittest.TestCase):
    def test_categorizes_exact_claims_missing_fields_and_derived_debt(self):
        report = {"gaps": [
            {"section": "distributors", "entity": "Distributor A",
             "field": "vendor_relations", "gap_kind": "evidence-support",
             "target_values": ["Fortinet", "Juniper"],
             "revalidation_seeds": [{"url": "https://example.com/vendors", "official": True}]},
            {"section": "distributors", "entity": "Distributor A",
             "field": "vendor_relations", "gap_kind": "standard",
             "target_values": []},
            {"section": "clients_public", "entity": "Town", "field": "westcon_fit",
             "gap_kind": "derivation-support", "target_values": ["Networking"]},
            {"section": "integrators", "entity": "Partner B", "field": "services",
             "gap_kind": "evidence-support", "target_values": ["Managed Services"]},
        ]}
        result = summarize(report)
        self.assertEqual(result["total_claims"], 2)
        self.assertEqual(result["derived"], 1)
        self.assertEqual(result["unfilled_or_unspecified"], 1)
        self.assertEqual(result["high_yield_claims"], 2)
        first = [f for f in result["fields"] if f["field"] == "distributors.vendor_relations"][0]
        self.assertEqual(first["values"], 2)
        self.assertEqual(first["with_direct_leads"], 1)
        self.assertEqual(first["with_official_leads"], 1)
        self.assertEqual(result["top_companies"][0]["entity"], "Distributor A")

    def test_emits_no_claim_values_when_no_existing_candidates(self):
        self.assertEqual(summarize({"gaps": []})["total_claims"], 0)


if __name__ == "__main__":
    unittest.main()
