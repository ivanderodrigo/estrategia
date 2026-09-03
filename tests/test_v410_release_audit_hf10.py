from __future__ import annotations

import unittest

from scripts.audit_release_v410 import evaluate_release_contract


def _manifest(source_class="Fuente pública primaria", origin="PUBLIC_PRIMARY"):
    return {
        "sections": {"manufacturers": {"file": "section.json"}},
        "source_catalog": [
            {"name": "Official", "class": source_class, "url": "https://example.com/source"}
        ],
        "_section": {
            "evidence": {
                "ev1": {
                    "source_role": source_class,
                    "provenance_origin": origin,
                    "url": "https://example.com/evidence",
                }
            }
        },
    }


def _preservation():
    return {
        "status": "PASS",
        "errors": [],
        "before": {
            "entities": {"manufacturers": 36, "integrators": 130},
            "values": 100,
            "evidences": 80,
            "relations": 50,
            "research_seed_claims": 40,
        },
        "after": {
            "entities": {"manufacturers": 36, "integrators": 130},
            "values": 120,
            "evidences": 90,
            "relations": 75,
            "research_seed_claims": 40,
        },
        "missing": {
            "entities": [], "values": [], "evidences": [], "relations": [],
            "research_seed_claims": [], "floor_failures": [],
        },
    }


def _ledger(accepted=3138):
    return {"accepted_evidences": accepted, "results": [{"accepted": accepted}]}


class ReleaseAuditHF10(unittest.TestCase):
    def _run(self, manifest=None, preservation=None, ledger=None):
        manifest = manifest or _manifest()
        preservation = preservation or _preservation()
        ledger = ledger or _ledger()
        return evaluate_release_contract(
            manifest,
            preservation,
            ledger,
            lambda _path: manifest["_section"],
        )[0]

    def test_additive_research_no_longer_requires_counter_equality(self):
        self.assertEqual(self._run(), [])

    def test_any_preservation_missing_class_still_blocks_release(self):
        preservation = _preservation()
        preservation["missing"]["evidences"] = ["claim:lost"]
        errors = self._run(preservation=preservation)
        self.assertTrue(any("missing evidences" in error for error in errors))

    def test_public_acceptance_ledger_is_floor_not_magic_exact_count(self):
        self.assertEqual(self._run(ledger=_ledger(3138)), [])
        errors = self._run(ledger=_ledger(7))
        self.assertTrue(any("below v4.1.0 floor" in error for error in errors))

    def test_internal_document_cannot_leak_into_public_sources(self):
        errors = self._run(manifest=_manifest("Fuente documental Westcon", "WESTCON_DOCUMENT"))
        self.assertTrue(any("internal/historical evidence" in error for error in errors))
        self.assertTrue(any("non-public accrediting catalog class" in error for error in errors))

    def test_protected_counter_regression_still_blocks(self):
        preservation = _preservation()
        preservation["after"]["relations"] = 49
        errors = self._run(preservation=preservation)
        self.assertTrue(any("relations count regressed" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
