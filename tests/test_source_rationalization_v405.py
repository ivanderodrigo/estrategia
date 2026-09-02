from __future__ import annotations

import unittest

from engine.gaps import build_gaps
from engine.source_rationalization import (
    claim_policy,
    rationalize_sources,
    support_basis,
)


def h_evidence() -> dict:
    return {
        "source": "Histórico",
        "title": "Fuente recuperada",
        "url": "https://old.example.com/cap",
        "date": "2025-01-01",
        "description": "Evidencia histórica.",
        "source_grade": "A",
        "source_type": "official-domain",
        "official": True,
        "provenance_origin": "HISTORICAL_RECOVERED",
    }


def public_evidence() -> dict:
    return {
        "source": "Fabricante",
        "title": "Página oficial actual",
        "url": "https://vendor.example.com/capability",
        "date": "2026-09-01",
        "description": "Página actual.",
        "source_grade": "A",
        "source_type": "official-domain-revalidated",
        "official": True,
        "provenance_origin": "PUBLIC_PRIMARY",
    }


def westcon_evidence() -> dict:
    return {
        "source": "Westcon Comstor España",
        "title": "FY27",
        "url": "",
        "date": "FY2027",
        "description": "Documento Westcon",
        "document": "Westcon_Comstor_Espana_FY27_completa.pptx",
        "slide": 29,
        "source_type": "westcon-document",
        "provenance_origin": "WESTCON_DOCUMENT",
        "official": True,
        "source_grade": "A-WESTCON",
    }


class SupportModelR3(unittest.TestCase):
    def test_a1_or_public_are_direct_support(self) -> None:
        self.assertEqual(
            support_basis([h_evidence(), westcon_evidence()]),
            "WESTCON_DOCUMENT",
        )
        self.assertEqual(
            support_basis([h_evidence(), public_evidence()]),
            "CURRENT_PUBLIC",
        )

    def test_westcon_fit_is_derived_not_literal_web_claim(self) -> None:
        policy = claim_policy("clients_public", "westcon_fit")
        self.assertEqual(policy["claim_class"], "DERIVED_FACT")
        self.assertEqual(policy["research_mode"], "derive-from-supported-inputs")

    def test_external_fact_without_support_creates_public_gap(self) -> None:
        data = {
            "schemas": {"manufacturers": [{
                "id": "competitors", "label": "Competidores", "decision_required": True
            }]},
            "manufacturers": [{
                "id": "v", "name": "Vendor",
                "fields": {
                    "competitors": {
                        "value": ["Peer"],
                        "items": [{"value": "Peer", "evidence": [h_evidence()]}],
                    }
                },
            }],
        }
        gaps = build_gaps(data, "4.0.6", {})
        found = [g for g in gaps["gaps"] if g.get("gap_kind") == "evidence-support"]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["claim_class"], "EXTERNAL_FACT")
        self.assertTrue(found[0]["preserve_value"])

    def test_derived_fact_creates_derivation_gap_not_public_search(self) -> None:
        data = {
            "schemas": {"clients_public": [{
                "id": "westcon_fit", "label": "Fit", "decision_required": True
            }]},
            "clients_public": [{
                "id": "c", "name": "Cliente",
                "fields": {
                    "westcon_fit": {
                        "value": ["Networking"],
                        "items": [{
                            "value": "Networking",
                            "evidence": [h_evidence()],
                        }],
                    }
                },
            }],
        }
        gaps = build_gaps(data, "4.0.6", {})
        derived = [g for g in gaps["gaps"] if g.get("gap_kind") == "derivation-support"]
        external = [g for g in gaps["gaps"] if g.get("gap_kind") == "evidence-support"]
        self.assertEqual(len(derived), 1)
        self.assertEqual(external, [])
        self.assertEqual(derived[0]["dependency_fields"], ["technology_signals"])

    def test_populated_field_absent_from_schema_still_gets_gap(self) -> None:
        # Exact regression for the two orphan TD SYNNEX vertical claims.
        data = {
            "schemas": {"distributors": []},
            "distributors": [{
                "id": "td-synnex", "name": "TD SYNNEX",
                "fields": {
                    "verticals": {
                        "value": ["Telecomunicaciones", "Transporte"],
                        "items": [
                            {"value": "Telecomunicaciones", "evidence": [h_evidence()]},
                            {"value": "Transporte", "evidence": [h_evidence()]},
                        ],
                    }
                },
            }],
        }
        gaps = build_gaps(data, "4.0.6", {})
        found = [
            g for g in gaps["gaps"]
            if g.get("gap_kind") == "evidence-support"
            and g.get("field") == "verticals"
        ]
        self.assertEqual(len(found), 2)

    def test_rationalizer_reports_occurrences_vs_unique_claims(self) -> None:
        data = {
            "clients_public": [
                {
                    "name": "Cliente",
                    "fields": {
                        "westcon_fit": {
                            "value": ["Networking", "Networking"],
                            "items": [
                                {"value": "Networking", "evidence": [h_evidence()]},
                                {"value": "Networking", "evidence": [h_evidence()]},
                            ],
                        }
                    },
                }
            ]
        }
        report = rationalize_sources(data)
        self.assertEqual(report["support_pending_occurrences"], 2)
        self.assertEqual(report["support_pending_unique_claims"], 1)
        self.assertEqual(report["duplicate_pending_occurrences"], 1)
        self.assertEqual(report["derived_support_required_unique"], 1)


if __name__ == "__main__":
    unittest.main()
