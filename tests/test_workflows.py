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

    def test_source_verification_uses_python_modules(self) -> None:
        source = (WORKFLOWS / "source-verification.yml").read_text(encoding="utf-8")
        self.assertIn("python -m scripts.audit_claim_sources", source)
        self.assertIn("python -m scripts.review_sources_live", source)
        self.assertIn("workflow_dispatch:", source)

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
