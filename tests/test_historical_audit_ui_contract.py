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
                "derivation_support", "other_open_debt"
            )),
        )

    def test_frontend_reads_canonical_derivation_support(self):
        script = (ROOT / "assets/app/audit-intelligence.js").read_text(encoding="utf-8")
        self.assertIn("summary.derivation_support||0", script)
        self.assertNotIn("summary.derived_support||0", script)

    def test_historical_audit_cover_full_inventory(self):
        workflow = (ROOT / ".github/workflows/historical-source-diligence.yml").read_text(encoding="utf-8")
        self.assertIn("--limit 2500", workflow)
        self.assertIn("accredit_semantic_historical_sources.py", workflow)

if __name__ == "__main__":
    unittest.main()
