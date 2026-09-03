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
        from engine.source_rationalization import support_basis

        westcon = {
            "source": "Westcon",
            "title": "Deck",
            "date": "FY2027",
            "description": "Pista interna",
            "document": "deck.pptx",
            "source_type": "westcon-document",
            "provenance_origin": "WESTCON_DOCUMENT",
        }
        public = {
            "source": "Vendor",
            "title": "Official",
            "date": "2026-09-02",
            "description": "Official public evidence",
            "url": "https://vendor.example/official",
            "official": True,
            "source_grade": "A2",
            "provenance_origin": "PUBLIC_PRIMARY",
        }
        self.assertEqual(support_basis([westcon]), "SEARCH_REQUIRED")
        self.assertEqual(support_basis([public]), "CURRENT_PUBLIC")
        self.assertEqual(support_basis([westcon, public]), "CURRENT_PUBLIC")

    def test_westcon_fit_is_derived_not_literal_web_claim(self) -> None:
        policy = claim_policy("clients_public", "westcon_fit")
        self.assertEqual(policy["claim_class"], "DERIVED_FACT")
        self.assertEqual(policy["research_mode"], "derive-from-supported-inputs")

    def test_external_fact_without_support_creates_public_gap(self) -> None:
        from engine.gaps import build_gaps

        public = {
            "schemas": {
                "manufacturers": [
                    {"id": "capabilities", "label": "Capacidades", "decision_required": True}
                ]
            },
            "manufacturers": [
                {
                    "id": "vendor-test",
                    "name": "Vendor Test",
                    "fields": {
                        "capabilities": {
                            "value": "SASE",
                            "evidence": [],
                        }
                    },
                }
            ],
        }
        report = build_gaps(public, research_state={})
        found = [
            gap for gap in report["gaps"]
            if gap.get("section") == "manufacturers"
            and gap.get("entity") == "Vendor Test"
            and gap.get("field") == "capabilities"
            and gap.get("target_values") == ["SASE"]
        ]
        self.assertEqual(len(found), 1)
        gap = found[0]
        self.assertEqual(gap.get("claim_class"), "EXTERNAL_FACT")
        self.assertEqual(gap.get("research_mode"), "public-source-verification")
        self.assertEqual(gap.get("support_requirement"), "CURRENT_PUBLIC_ONLY")
        self.assertEqual(gap.get("gap_kind"), "evidence-support")
        self.assertEqual(gap.get("research_state"), "Por investigar")
        self.assertTrue(gap.get("preserve_value"))

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
        from engine.gaps import build_gaps

        public = {
            "schemas": {"distributors": []},
            "distributors": [
                {
                    "id": "dist-test",
                    "name": "Distributor Test",
                    "fields": {
                        "orphan_one": {"value": "Value A", "evidence": []},
                        "orphan_two": {"value": "Value B", "evidence": []},
                    },
                }
            ],
        }
        report = build_gaps(public, research_state={})
        found = [
            gap for gap in report["gaps"]
            if gap.get("section") == "distributors"
            and gap.get("entity") == "Distributor Test"
            and gap.get("field") in {"orphan_one", "orphan_two"}
        ]
        self.assertEqual(len(found), 2)
        self.assertEqual({gap.get("field") for gap in found}, {"orphan_one", "orphan_two"})
        self.assertTrue(all(gap.get("claim_class") == "EXTERNAL_FACT" for gap in found))
        self.assertTrue(all(gap.get("research_mode") == "public-source-verification" for gap in found))
        self.assertTrue(all(gap.get("support_requirement") == "CURRENT_PUBLIC_ONLY" for gap in found))
        self.assertTrue(all(gap.get("gap_kind") == "evidence-support" for gap in found))
        self.assertTrue(all(gap.get("research_state") == "Por investigar" for gap in found))

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
