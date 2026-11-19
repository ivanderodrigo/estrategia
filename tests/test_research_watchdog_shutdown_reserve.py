"""Research timeout budget must leave room to finalize useful crawl results."""
import unittest
from pathlib import Path

from scripts.research_supervisor import _allocate_budgets, _worker_runtime


class WatchdogShutdownReserve(unittest.TestCase):
    def test_deep_and_fallback_finish_before_supervisor_hard_deadline(self):
        _, deep, fallback, build = _allocate_budgets(1800, 240)
        self.assertGreaterEqual(build, 60)
        self.assertEqual(fallback, 240)
        for total in (deep, fallback):
            worker, reserve = _worker_runtime(total)
            self.assertEqual(worker + reserve, total)
            self.assertGreaterEqual(reserve, 30)
            self.assertLess(worker, total - 15)

    def test_daily_has_bounded_worker_and_checkpoint_window(self):
        _, daily, fallback, _ = _allocate_budgets(720, 0)
        self.assertEqual(fallback, 0)
        worker, reserve = _worker_runtime(daily)
        self.assertGreaterEqual(worker, 20)
        self.assertGreaterEqual(reserve, 30)
        self.assertLess(worker + 15, daily)

    def test_weekly_runs_corrected_watchdog_once_after_merge(self):
        root = Path(__file__).resolve().parents[1]
        weekly = (root / ".github/workflows/research-weekly.yml").read_text(encoding="utf-8")
        self.assertIn("'scripts/research_supervisor.py'", weekly)
        self.assertIn("branches: [main]", weekly)


if __name__ == "__main__":
    unittest.main()
