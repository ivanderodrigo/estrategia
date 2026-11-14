"""Telemetry distinguishes evidence binding from independently verified truth."""
import unittest
from scripts.publish_source_verification_status import build


class SourceVerificationTelemetryTests(unittest.TestCase):
    def test_timestamp_and_scope_tied_to_original_public_snapshot(self):
        result=build(
            {"sections":{"manufacturers":{"counts":{"claims":12,"without_source":3}}}},
            {"total_references":1900,"sampled":2,"items":[
                {"review_status":"page_mentions_value_only"},
                {"review_status":"http_403"},
            ]},
            {"generated_at":"2026-11-14T12:00:00+00:00"},
            checked_at="2026-11-14T18:00:00+00:00",
            run_url="https://github.com/ivanderodrigo/estrategia/actions/runs/123",
        )
        self.assertEqual(result["snapshot_generated_at"],"2026-11-14T12:00:00+00:00")
        self.assertEqual(result["live_sample_reviewed"],2)
        self.assertEqual(result["total_live_review_candidates"],1900)
        self.assertFalse(result["source_content_semantically_verified"])
        self.assertEqual(result["status"],"REVIEW_QUEUE_NOT_FACT_ACCREDITATION")
        self.assertEqual(result["live_review_statuses"]["http_403"],1)
        self.assertEqual(result["by_section"]["manufacturers"]["without_source"],3)


if __name__=="__main__":
    unittest.main()
