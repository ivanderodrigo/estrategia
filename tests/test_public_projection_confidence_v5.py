import unittest
from engine.publication import _compact_object


class PublicConfidenceGuardTests(unittest.TestCase):
    def test_high_confidence_without_public_evidence_is_downgraded(self):
        registry = {}
        claim = {
            "value": "Vendor X", "confidence": 0.99,
            "confidence_band": "high", "fact_confidence": 0.99,
            "evidence": [{
                "source": "Historical lead", "provenance_origin": "RESEARCH_SEED",
                "url": "https://example.org/lead",
            }],
        }
        output = _compact_object(claim, registry)
        self.assertEqual(output["evidence_ids"], [])
        self.assertEqual(output["confidence_band"], "low")
        self.assertLessEqual(output["confidence"], 0.38)
        self.assertEqual(registry, {})

    def test_public_evidence_keeps_source_and_confidence(self):
        claim = {
            "value": "Vendor X", "confidence": 0.9, "confidence_band": "high",
            "evidence": [{
                "source": "Official", "provenance_origin": "PUBLIC_PRIMARY",
                "url": "https://example.org/confirmed",
                "source_grade": "A",
            }],
        }
        registry = {}
        output = _compact_object(claim, registry)
        self.assertEqual(len(output["evidence_ids"]), 1)
        self.assertEqual(output["confidence_band"], "high")
        self.assertEqual(len(registry), 1)


if __name__ == "__main__":
    unittest.main()
