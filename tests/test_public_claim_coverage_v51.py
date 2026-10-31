import unittest
from engine.publication import _source_coverage


class PublicClaimCoverageTests(unittest.TestCase):
    def test_counts_only_real_value_claims_and_broken_references(self):
        rows = [{"fields": {
            "a": {"value": "Fact", "confidence": .9, "evidence_ids": ["e1"]},
            "b": {"value": "Lead", "confidence": .38, "evidence_ids": []},
            "c": {"value": "Missing registry", "confidence": .9, "evidence_ids": ["bad"]},
            "d": {"value": "", "confidence": .0, "evidence_ids": []},
        }}]
        result = _source_coverage(rows, {"e1": {"url": "https://example.org"}})
        self.assertEqual(result, {"claims": 3, "sourced": 1, "unsourced": 2, "broken_references": 1})


if __name__ == "__main__":
    unittest.main()
