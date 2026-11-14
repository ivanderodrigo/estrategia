"""Research publication tolerates UI-only changes but protects current data."""
import unittest
from scripts.publish_research_update import safe_remote_only

class SafeResearchPublicationTests(unittest.TestCase):
    def test_visual_changes_do_not_waste_validated_daily_research(self):
        self.assertTrue(safe_remote_only(["assets/app/intelligence.css","index.html"]))
        self.assertTrue(safe_remote_only(["data/current/daily_workflow_health.json"]))

    def test_canonical_or_evidence_changes_always_refuse_stale_publish(self):
        for path in ("engine/pipeline.py","scripts/validate.py",
                     "data/public/manifest.json","data/current/intelligence.json",
                     "config/current/historical_semantic_verified.json",
                     ".github/workflows/research-run.yml","tests/test_workflows.py"):
            self.assertFalse(safe_remote_only(["assets/app/intelligence.js",path]),
                             path)

    def test_no_change_is_not_a_rebase(self):
        self.assertFalse(safe_remote_only([]))

if __name__=="__main__":
    unittest.main()
