"""Evidence queue must preserve backlog and never accredit unverified claims."""
import unittest
from scripts.audit_gap_debt import analyze

class GapDebtAuditTests(unittest.TestCase):
    def test_uses_claim_priority_without_reclassifying_blanks(self):
        report = {"total_gaps": 3, "gaps": [
            {"id": "i:x:services", "section": "integrators", "entity": "X",
             "field": "services", "gap_kind": "public-validation",
             "priority_tier": "P1", "priority_score": 10,
             "target_values": ["SOC"], "revalidation_seeds": [{"url": "https://example.org/"}]},
            {"id": "i:y:services", "section": "integrators", "entity": "Y",
             "field": "services", "gap_kind": "public-validation",
             "priority_tier": "P0", "priority_score": 7,
             "target_values": ["MSSP"]},
            {"id": "i:y:employees", "section": "integrators", "entity": "Y",
             "field": "employees", "gap_kind": "standard", "target_values": []},
        ]}
        result = analyze(report)
        self.assertEqual(result["total_open_gaps"], 3)
        self.assertEqual(result["debt_breakdown"]["claims_awaiting_evidence"], 2)
        self.assertEqual(result["debt_breakdown"]["empty_schema_fields"], 1)
        self.assertEqual(result["priority_evidence_queue"][0]["gap_id"], "i:y:services")
        self.assertEqual(len(result["priority_evidence_queue"]), 2)

if __name__ == "__main__":
    unittest.main()
