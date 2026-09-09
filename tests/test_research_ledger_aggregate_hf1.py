from __future__ import annotations

import unittest
from pathlib import Path

from scripts.audit_release_v410 import evaluate_release_contract


ROOT = Path(__file__).resolve().parents[1]


def preservation_pass():
    counts = {
        "values": 100,
        "evidences": 100,
        "relations": 100,
        "research_seed_claims": 100,
        "entities": {"manufacturers": 36},
    }
    return {
        "status": "PASS",
        "errors": [],
        "missing": {
            "entities": [],
            "values": [],
            "evidences": [],
            "relations": [],
            "research_seed_claims": [],
            "floor_failures": [],
        },
        "before": counts,
        "after": counts,
    }


def evaluate(ledger):
    return evaluate_release_contract(
        {"sections": {}, "source_catalog": []},
        preservation_pass(),
        ledger,
        lambda _relative: {},
    )


class ResearchLedgerAggregateHF1(unittest.TestCase):
    def test_writer_persists_full_run_aggregate_before_truncation(self):
        source = (ROOT / "engine/research/web_intelligence.py").read_text(encoding="utf-8")
        self.assertIn('ledger["accepted_result_rows_total"]', source)
        self.assertIn('ledger["result_rows_total"]', source)
        self.assertIn('ledger["results_truncated"]', source)
        self.assertIn('ledger["results"] = result_rows[-300:]', source)

    def test_94_accepted_not_invalidated_by_zero_yield_tail(self):
        ledger = {
            "accepted_evidences": 94,
            "accepted_result_rows_total": 94,
            "result_rows_total": 650,
            "results_truncated": True,
            "results": [{"accepted": 0} for _ in range(300)],
        }
        errors, stats = evaluate(ledger)
        self.assertFalse(any("accepted public evidence" in error for error in errors), errors)
        self.assertEqual(stats["accepted_result_rows"], 94)
        self.assertEqual(stats["accepted_result_rows_source"], "full-run aggregate")

    def test_full_run_aggregate_mismatch_is_rejected(self):
        ledger = {
            "accepted_evidences": 94,
            "accepted_result_rows_total": 0,
            "result_rows_total": 650,
            "results_truncated": True,
            "results": [{"accepted": 0} for _ in range(300)],
        }
        errors, _stats = evaluate(ledger)
        self.assertTrue(any("aggregate mismatch" in error for error in errors), errors)
        self.assertTrue(any("result rows regressed" in error for error in errors), errors)

    def test_legacy_300_row_ledger_uses_complete_counter(self):
        ledger = {
            "accepted_evidences": 94,
            "results": [{"accepted": 0} for _ in range(300)],
        }
        errors, stats = evaluate(ledger)
        self.assertFalse(any("accepted public evidence" in error for error in errors), errors)
        self.assertEqual(stats["accepted_result_rows"], 94)
        self.assertIn("legacy ledger fallback", stats["accepted_result_rows_source"])


if __name__ == "__main__":
    unittest.main()
