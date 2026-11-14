"""Regressions for canonical publication/audit field names."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class HistoricalAuditUiContracts(unittest.TestCase):
    def test_debt_breakdown_reconciles(self):
        report = json.loads((ROOT / "data/public/debt_overview.json").read_text(encoding="utf-8"))
        breakdown = report["debt_breakdown"]
        self.assertEqual(
            report["total_open_gaps"],
            sum(int(breakdown.get(k, 0)) for k in (
                "empty_schema_fields", "claims_awaiting_evidence",
                "derived_support", "other_open_debt"
            )),
        )

    def test_frontend_reads_canonical_derivation_support(self):
        script = (ROOT / "assets/app/audit-intelligence.js").read_text(encoding="utf-8")
        self.assertIn("summary.derived_support||0", script)
        self.assertIn("section.derivation_support", script)

    def test_explicit_official_distribution_is_accredited(self):
        from scripts.accredit_semantic_historical_sources import classify
        claim = {
            "section": "manufacturers", "entity": "1Password",
            "field": "distributors", "value": "Ingram Micro",
            "source_context": "1Password announces a distribution agreement with Ingram Micro for channel resellers",
        }
        source = "https://1password.com/blog/1password-ingram-micro-partnership-resellers"
        self.assertEqual("VERIFIED_EXPLICIT_DISTRIBUTION_AGREEMENT", classify(claim, source))
        claim["source_context"] = "1Password and Ingram Micro are mentioned in a partner directory"
        self.assertEqual("DISTRIBUTION_RELATIONSHIP_NOT_SHOWN", classify(claim, source))
        self.assertEqual("DISTRIBUTION_RELATIONSHIP_NOT_SHOWN",
                         classify(claim, "https://unrelated.example.org/research"))

    def test_historical_audit_cover_full_inventory(self):
        workflow = (ROOT / ".github/workflows/historical-source-diligence.yml").read_text(encoding="utf-8")
        self.assertIn("--limit 100000", workflow)
        self.assertIn("report['urls_checked_this_run'] == report['urls_in_inventory']", workflow)
        self.assertIn("accredit_semantic_historical_sources.py", workflow)

if __name__ == "__main__":
    unittest.main()
