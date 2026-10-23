"""Missing-support forensics must identify the claim, not just its hash."""
import unittest

from engine.preservation import _claim_support_key, _entity_key
from engine.preservation_forensics import trace_missing_evidences


class MissingSupportTraceTest(unittest.TestCase):
    def test_reports_before_and_after_support_for_same_claim(self):
        owner = "V-Valley Advanced Solutions Portugal"
        row = {"name": owner, "fields": {"services": {
            "value": ["Soporte"],
            "items": [{"value": "Soporte", "evidence": [{
                "url": "https://example.org/support",
                "source": owner,
                "title": "Soporte",
                "method": "web-evidence:test",
                "field": "services",
                "item_value": "Soporte",
                "researched_entity": owner,
                "atomic": True,
                "source_binding": "claim-specific",
            }]}],
            "evidence": [],
        }}}
        before = {"distributors": [row]}
        after = {"distributors": [{"name": owner, "fields": {
            "services": {"value": ["Soporte"], "items": [
                {"value": "Soporte", "evidence": []}
            ], "evidence": []}
        }}]}
        key = _claim_support_key(
            "distributors", _entity_key("distributors", row),
            "services", value="Soporte", scalar=False,
        )
        report = trace_missing_evidences(before, after, {
            "missing": {"evidences": [key]}
        })
        self.assertEqual(report["missing_fingerprints"], [key])
        self.assertEqual(report["before_claims"][0]["field"], "services")
        self.assertEqual(report["before_claims"][0]["accepted_evidence_count"], 1)
        self.assertEqual(report["after_claims"][0]["accepted_evidence_count"], 0)


if __name__ == "__main__":
    unittest.main()
