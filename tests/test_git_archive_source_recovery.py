"""Regression tests for recovering sources hidden in old Git revisions."""
import unittest
from unittest.mock import patch
from scripts.recover_historical_source_archive import (
    atom_values, choose_path_revisions, source_urls,
)


class LegacyArchiveRecoveryTests(unittest.TestCase):
    def test_inline_and_registry_references_are_recovered(self):
        field = {
            "evidence_ids": ["e1"],
            "evidence": [{"url": "https://vendor.example/partner"}],
        }
        registry = {"e1": {"url": "https://vendor.example/report"}}
        self.assertEqual(set(source_urls(field, registry)), {
            "https://vendor.example/report", "https://vendor.example/partner"
        })

    def test_non_web_and_untrusted_scheme_excluded(self):
        field = {"evidence": [
            {"url": "javascript:alert(1)"},
            {"url": "file:///secrets"},
            {"url": "http://example.com"},
            {"url": "https://example.com/verified"}
        ]}
        self.assertEqual(list(source_urls(field, {})),
                         ["https://example.com/verified"])

    def test_multivalue_fields_remain_atomic(self):
        self.assertEqual(atom_values({"value": ["Cisco", "Huawei", None]}),
                         ["Cisco", "Huawei"])

    def test_revision_sampling_covers_first_and_last(self):
        class Completed:
            returncode = 0
            stdout = b"one\ntwo\nthree\nfour\nfive\n"
        with patch("scripts.recover_historical_source_archive.git", return_value=Completed()):
            self.assertEqual(choose_path_revisions("data/current/intelligence.json", 3),
                             ["one", "three", "five"])


if __name__ == "__main__":
    unittest.main()
