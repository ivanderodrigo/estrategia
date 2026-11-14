from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github/workflows"


class WorkflowIntegrity(unittest.TestCase):
    def test_all_workflows_parse_and_script_references_exist(self) -> None:
        for path in WORKFLOWS.glob("*.yml"):
            text = path.read_text(encoding="utf-8")
            self.assertIsInstance(yaml.safe_load(text), dict)
            self.assertNotRegex(text, r"(data|assets|scripts|config)/v\d+")
            self.assertNotIn("actions/checkout@v4", text)
            for relative in re.findall(r"python (?:-m )?([A-Za-z0-9_./-]+\.py)", text):
                self.assertTrue((ROOT / relative).exists(), f"{path.name}: {relative}")

    def test_daily_weekly_and_monthly_call_one_hardened_runner(self) -> None:
        expected = {
            "daily": ("daily", "17 5 * * 1-5"),
            "weekly": ("deep", "29 22 * * 0,1,3,5"),
            "monthly": ("exhaustive", "41 3 1 * *"),
        }
        for name, (profile, cron) in expected.items():
            text = (WORKFLOWS / f"research-{name}.yml").read_text(encoding="utf-8")
            self.assertIn("uses: ./.github/workflows/research-run.yml", text)
            self.assertIn(f"profile: {profile}", text)
            self.assertIn(f'cron: "{cron}"', text)
            self.assertIn("contents: write", text)

    def test_runtime_has_room_for_validation_and_publication(self) -> None:
        for name, minimum in (("weekly", 65), ("monthly", 90)):
            source = (WORKFLOWS / f"research-{name}.yml").read_text(encoding="utf-8")
            self.assertIn(f"timeout_minutes: {minimum}", source)
        daily = (WORKFLOWS / "research-daily.yml").read_text(encoding="utf-8")
        self.assertNotIn("      - 'tests/**'", daily)
        self.assertIn("workflow_dispatch:", daily)

    def test_every_scheduled_profile_publishes_source_bindings_and_same_snapshot_audit(self) -> None:
        runner = (WORKFLOWS / "research-run.yml").read_text(encoding="utf-8")
        publisher = (ROOT / "scripts/publish_research_update.py").read_text(encoding="utf-8")
        pages = (WORKFLOWS / "pages-deploy.yml").read_text(encoding="utf-8")
        # Research owns generation and source binding. Deployment only verifies
        # the already-committed immutable snapshot.
        for script in ("scripts/attach_sase_layer_vendor_sources.py",
                       "scripts/audit_public_consistency.py"):
            self.assertIn(script, runner)
            self.assertTrue((ROOT / script).exists())
        self.assertNotIn("python scripts/attach_sase_layer_vendor_sources.py", pages)
        self.assertNotIn("python -m engine.pipeline", pages)
        self.assertNotIn("git push", pages)
        self.assertIn("contents: read", pages)
        self.assertIn('"data/public/audit_integrity.json"', publisher)
        self.assertLess(runner.index("attach_sase_layer_vendor_sources.py"),
                        runner.index("Validate generated snapshot"))
        self.assertLess(runner.index("audit_public_consistency.py"),
                        runner.index("Publish validated intelligence"))
        for name in ("daily", "weekly", "monthly"):
            workflow = (WORKFLOWS / f"research-{name}.yml").read_text(encoding="utf-8")
            self.assertIn("uses: ./.github/workflows/research-run.yml", workflow)
        self.assertIn("scripts/audit_public_consistency.py", pages)

    def test_historical_evidence_reaches_public_snapshot(self) -> None:
        runner = (WORKFLOWS / "research-run.yml").read_text(encoding="utf-8")
        integration = (WORKFLOWS / "historical-evidence-integration.yml").read_text(encoding="utf-8")
        self.assertLess(runner.index("revalidate_historical_sources.py"),
                        runner.index("Accredit newly verified historical claim excerpts"))
        self.assertLess(runner.index("Accredit newly verified historical claim excerpts"),
                        runner.index("Integrate accredited historical claims into the public snapshot"))
        self.assertLess(runner.index("Integrate accredited historical claims into the public snapshot"),
                        runner.index("Publish validated intelligence"))
        self.assertIn("Historical Source Diligence", integration)
        self.assertIn("python -m engine.pipeline", integration)
        self.assertIn("scripts/audit_public_consistency.py", integration)
        self.assertIn("scripts/publish_research_update.py", integration)
        publisher = (ROOT / "scripts/publish_research_update.py").read_text(encoding="utf-8")
        self.assertIn('"config/current/historical_semantic_verified.json"', publisher)
        self.assertIn('"data/public/historical/current/semantic_claim_audit.json"', publisher)
        self.assertLess(integration.index("python -m engine.pipeline"),
                        integration.index("scripts/publish_research_update.py"))
        self.assertIn("group: westcon-intelligence-research", integration)

    def test_structured_competitor_proof_runs_on_historical_schedule(self) -> None:
        diligence = (WORKFLOWS / "historical-source-diligence.yml").read_text(encoding="utf-8")
        publisher = (ROOT / "scripts/publish_research_update.py").read_text(encoding="utf-8")
        self.assertIn("scripts/accredit_structured_historical.py --limit 60", diligence)
        for artifact in ("config/current/historical_structured_verified.json",
                         "data/public/historical/current/structured_verification.json"):
            self.assertIn(artifact, diligence)
            self.assertIn(f'"{artifact}"', publisher)

    def test_source_verification_uses_python_modules(self) -> None:
        source = (WORKFLOWS / "source-verification.yml").read_text(encoding="utf-8")
        self.assertIn("python -m scripts.audit_claim_sources", source)
        self.assertIn("python -m scripts.review_sources_live", source)
        self.assertIn("workflow_dispatch:", source)

    def test_scheduled_failures_have_one_nonrecursive_fresh_main_recovery(self) -> None:
        recovery = (WORKFLOWS / "research-scheduled-recovery.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_run:", recovery)
        self.assertIn("run_attempt == 1", recovery)
        self.assertIn("workflow_run.event == 'schedule'", recovery)
        self.assertIn("workflow_run.conclusion == 'failure'", recovery)
        self.assertIn("actions: write", recovery)
        self.assertIn("gh workflow run", recovery)
        self.assertIn("--ref main", recovery)
        for name in ("research-daily.yml", "research-weekly.yml", "research-monthly.yml"):
            self.assertIn(name, recovery)
        # Retries use dispatch rather than rerunning a stale SHA.
        self.assertNotIn("gh run rerun", recovery)

    def test_source_verification_publishes_snapshot_bound_review_status(self) -> None:
        source = (WORKFLOWS / "source-verification.yml").read_text(encoding="utf-8")
        self.assertIn("scripts/publish_source_verification_status.py", source)
        self.assertIn("data/public/source_verification_status.json", source)
        self.assertIn("contents: write", source)
        self.assertIn("git fetch origin main", source)
        self.assertIn("git reset --hard origin/main", source)
        self.assertIn("source-live-review.json", source)
        frontend = (ROOT / "assets/app/command-center.js").read_text(encoding="utf-8")
        self.assertIn("source_verification_status.json", frontend)
        self.assertIn("REVIEW_QUEUE_NOT_FACT_ACCREDITATION", frontend)
        self.assertIn("snapshot_generated_at===m.generated_at", frontend)

    def test_published_scheduling_copy_matches_actual_utc_cron(self) -> None:
        frontend = (ROOT / "assets/app/intelligence.js").read_text(encoding="utf-8")
        schedules = {
            "daily": ("17 5 * * 1-5", "05:17 UTC"),
            "weekly": ("29 22 * * 0,1,3,5", "22:29 UTC"),
            "monthly": ("41 3 1 * *", "03:41 UTC"),
        }
        for profile, (cron, label) in schedules.items():
            workflow = (WORKFLOWS / f"research-{profile}.yml").read_text(encoding="utf-8")
            self.assertIn(cron, workflow)
            self.assertIn(label, frontend)
        self.assertIn("horarios indicados son UTC", frontend)

    def test_reusable_runner_serializes_validates_and_preserves_diagnostics(self) -> None:
        text = (WORKFLOWS / "research-run.yml").read_text(encoding="utf-8")
        for token in (
            "group: westcon-intelligence-research", "cancel-in-progress: false",
            "timeout-minutes:", "research_supervisor.py", "security_audit.py",
            "if: always()", "upload-artifact@v4", "publish_research_update.py",
            "python -m unittest discover", "node tests/ui_smoke.js",
        ):
            self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()
