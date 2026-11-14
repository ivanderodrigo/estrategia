"""Telemetry distinguishes evidence binding from independently verified truth."""
import unittest
from scripts.publish_source_verification_status import build, scheduled_health


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


    def test_actual_scheduled_failures_are_counted_not_hidden(self):
        history={"workflow_runs":[
            {"name":"Westcon Intelligence Daily","event":"schedule",
             "id":1001,"created_at":"2026-11-13T05:17:00Z",
             "status":"completed","conclusion":"failure"},
            {"name":"Westcon Intelligence Daily","event":"schedule",
             "id":1000,"created_at":"2026-11-12T05:17:00Z",
             "status":"completed","conclusion":"success"},
            {"name":"Westcon Intelligence Daily","event":"push",
             "id":9999,"created_at":"2026-11-14T17:00:00Z",
             "status":"completed","conclusion":"success"},
        ]}
        metrics=scheduled_health(history)
        daily=metrics["Westcon Intelligence Daily"]
        self.assertEqual(daily["last_run_id"],1001)
        self.assertEqual(daily["last_conclusion"],"failure")
        self.assertEqual(daily["recent_failures_in_sample"],1)
        self.assertEqual(daily["runs_in_api_sample"],2)
        self.assertEqual(metrics["Westcon Intelligence Monthly"]["last_conclusion"],"NOT_OBSERVED")

    def test_unreadable_http_202_pages_are_not_reported_as_source_validation(self):
        result=build({"sections":{}},
                     {"total_references":200,"sampled":2,
                      "items":[{"review_status":"http_202"},{"review_status":"http_202"}]},
                     {"generated_at":"2026-11-14T10:00:00Z"},
                     checked_at="2026-11-14T11:00:00Z",run_url="")
        self.assertEqual(result["live_collection_health"],"NO_CONTENT_EXTRACTED")
        self.assertEqual(result["live_content_accessible"],0)
        self.assertFalse(result["source_content_semantically_verified"])

if __name__=="__main__":
    unittest.main()
