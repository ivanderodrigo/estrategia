"""Learning should allocate work by accrediting evidence, not successful HTTP alone."""
import unittest
from engine.research.planner import _learning_yield

class AdaptiveYieldTests(unittest.TestCase):
    def test_high_evidence_yield_beats_large_failed_source(self):
        learning = {"families": {
            "integrators:services": {"attempts": 100, "fetch_successes": 60, "pages_relevant": 45, "accepted_evidence": 34},
            "integrators:financial": {"attempts": 1000, "fetch_successes": 800, "pages_relevant": 5, "accepted_evidence": 2},
        }}
        self.assertGreater(_learning_yield(learning, "integrators", "services"),
                           _learning_yield(learning, "integrators", "financial"))

    def test_new_family_not_starved(self):
        empty = {"families": {}}
        self.assertGreaterEqual(_learning_yield(empty, "integrators", "emerging"), 0.7)

    def test_no_evidence_worse_than_unknown_even_if_http_succeeds(self):
        learning = {"families": {
            "distributors:partners": {"attempts": 1000, "fetch_successes": 1000, "pages_relevant": 0, "accepted_evidence": 0}
        }}
        self.assertLess(_learning_yield(learning, "distributors", "partners"),
                        _learning_yield(learning, "distributors", "new-source"))

if __name__ == "__main__":
    unittest.main()
