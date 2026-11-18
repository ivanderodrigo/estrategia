import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.audit_scheduled_workflows import SCHEDULES, classify, evaluate


NOW = datetime(2026, 11, 18, 18, tzinfo=timezone.utc)


def run(event="schedule", conclusion="success", created="2026-11-18T12:00:00Z"):
    return {
        "id": 123, "event": event, "status": "completed",
        "conclusion": conclusion, "created_at": created,
        "html_url": "https://github.com/ivanderodrigo/estrategia/actions/runs/123",
    }


class ScheduledHealthTests(unittest.TestCase):
    def test_successful_manual_retry_does_not_hide_scheduled_failure(self):
        result = classify([run(event="workflow_dispatch"), run(conclusion="failure")], NOW, 48)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["latest_run"]["conclusion"], "success")
        self.assertEqual(result["scheduled_run"]["conclusion"], "failure")

    def test_success_without_recent_schedule_is_not_green(self):
        self.assertEqual(classify([run(event="push")], NOW, 72)["status"], "UNKNOWN")
        stale = classify([run(created="2026-10-01T12:00:00Z")], NOW, 72)
        self.assertEqual(stale["status"], "STALE")

    def test_good_recent_schedule_is_green(self):
        self.assertEqual(classify([run()], NOW, 48)["status"], "PASS")

    def test_query_failure_never_claims_full_success(self):
        def offline(workflow, token):
            raise OSError("offline")
        result = evaluate(fetcher=offline, now=NOW, token="test")
        self.assertEqual(set(result["workflows"]), set(SCHEDULES))
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertTrue(all(x["status"] == "UNKNOWN" for x in result["workflows"].values()))

    def test_failed_schedule_changes_overall_status(self):
        def returns_failures(workflow, token):
            return [run(conclusion="failure" if workflow == "research-weekly.yml" else "success")]
        result = evaluate(fetcher=returns_failures, now=NOW, token="test")
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["workflows"]["research-weekly.yml"]["status"], "FAIL")

    def test_monitor_and_pages_publish_operational_health(self):
        root = Path(__file__).resolve().parents[1]
        monitor = (root / ".github/workflows/audit-live-integrity.yml").read_text(encoding="utf-8")
        pages = (root / ".github/workflows/pages-deploy.yml").read_text(encoding="utf-8")
        ui = (root / "assets/app/intelligence.js").read_text(encoding="utf-8")
        self.assertIn("python scripts/audit_scheduled_workflows.py", monitor)
        self.assertIn("data/public/scheduled_workflow_health.json", monitor)
        self.assertIn("data/public/scheduled_workflow_health.json", pages)
        self.assertIn("scheduled_workflow_health.json", ui)


if __name__ == "__main__":
    unittest.main()
