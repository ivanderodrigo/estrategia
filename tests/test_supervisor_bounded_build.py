"""A slow canonical rebuild must never hang a scheduled research runner."""

import subprocess
import unittest
from unittest.mock import MagicMock, patch

from scripts.research_supervisor import _run_bounded_build


class SupervisorBuildDeadline(unittest.TestCase):
    @patch("scripts.research_supervisor.subprocess.Popen")
    def test_reads_child_metrics_after_success(self, popen):
        child = MagicMock()
        child.communicate.return_value = (
            'pipeline prepared\nSUPERVISOR_METRICS_JSON={"before":{"gaps_total":22},"after":{"gaps_total":19}}\n',
            None,
        )
        child.returncode = 0
        popen.return_value = child
        result = _run_bounded_build(300)
        self.assertEqual(result["after"]["gaps_total"], 19)
        child.communicate.assert_called_once_with(timeout=300)

    @patch("scripts.research_supervisor._terminate")
    @patch("scripts.research_supervisor.subprocess.Popen")
    def test_kills_hung_rebuild_and_fails_loudly(self, popen, terminate):
        child = MagicMock()
        child.communicate.side_effect = subprocess.TimeoutExpired("pipeline", 240)
        popen.return_value = child
        with self.assertRaisesRegex(TimeoutError, "exceeded 240s"):
            _run_bounded_build(240)
        terminate.assert_called_once_with(child)

    @patch("scripts.research_supervisor.subprocess.Popen")
    def test_refuses_missing_metrics_even_if_exit_zero(self, popen):
        child = MagicMock()
        child.communicate.return_value = ("some other output\n", None)
        child.returncode = 0
        popen.return_value = child
        with self.assertRaisesRegex(RuntimeError, "no machine-readable metrics"):
            _run_bounded_build(240)


if __name__ == "__main__":
    unittest.main()
