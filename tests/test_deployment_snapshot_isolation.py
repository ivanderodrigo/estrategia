"""Deployment may not reject a valid snapshot for registry changes not yet integrated."""
import unittest
from pathlib import Path


class DeploymentSnapshotIsolation(unittest.TestCase):
    def test_deployment_uses_immutable_snapshot_checks(self):
        root = Path(__file__).resolve().parents[1]
        pages = (root / ".github/workflows/pages-deploy.yml").read_text(encoding="utf-8")
        integration = (root / ".github/workflows/historical-evidence-integration.yml").read_text(
            encoding="utf-8"
        )
        runner = (root / ".github/workflows/research-run.yml").read_text(encoding="utf-8")
        self.assertIn("scripts/audit_public_consistency.py", pages)
        self.assertIn("scripts/validate_mass_historical_publication.py", pages)
        for script in (
            "audit_published_historical_market.py",
            "audit_published_topic_markets.py",
            "audit_published_peer_competitors.py",
            "audit_published_semantic_historical.py",
            "audit_published_issuer_competitors.py",
        ):
            self.assertNotIn("python scripts/" + script, pages)
        self.assertIn("python scripts/audit_published_semantic_historical.py", integration)
        self.assertIn("python scripts/audit_published_semantic_historical.py", runner)


if __name__ == "__main__":
    unittest.main()
