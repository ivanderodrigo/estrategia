from __future__ import annotations

import unittest

from engine.gaps import build_gaps
from engine.knowledge_provenance import typed_evidence_sufficient
from engine.source_rationalization import rationalize_sources


def h_evidence(url: str = "https://old.example.com/cap") -> dict:
    return {
        "source": "Histórico",
        "title": "Fuente recuperada",
        "url": url,
        "date": "2025-01-01",
        "description": "Evidencia de una versión histórica.",
        "scope": "ES",
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
        "description": "Página actual que confirma el dato.",
        "scope": "ES",
        "source_grade": "A",
        "source_type": "official-domain-revalidated",
        "official": True,
    }


class SourceRationalizationV405(unittest.TestCase):
    def test_historical_never_closes_gap_by_itself(self) -> None:
        self.assertFalse(typed_evidence_sufficient(h_evidence()))

    def test_rationalizer_marks_h_search_required_without_current_open_source(self) -> None:
        data = {
            "manufacturers": [{
                "name": "Vendor",
                "fields": {
                    "capabilities": {
                        "value": ["SASE"],
                        "items": [{"value": "SASE", "evidence": [h_evidence()]}],
                        "evidence": [],
                    }
                },
            }]
        }
        report = rationalize_sources(data)
        self.assertEqual(report["historical_search_required"], 1)

    def test_current_open_source_sustains_historical_lineage(self) -> None:
        item = {"value": "SASE", "evidence": [h_evidence(), public_evidence()]}
        data = {
            "manufacturers": [{
                "name": "Vendor",
                "fields": {"capabilities": {"value": ["SASE"], "items": [item], "evidence": []}},
            }]
        }
        report = rationalize_sources(data)
        self.assertEqual(report["historical_supported_current_open"], 1)

    def test_build_gaps_creates_atomic_h_revalidation_even_with_westcon_document(self) -> None:
        westcon = {
            "source": "Westcon Comstor España",
            "title": "FY27",
            "url": "",
            "date": "FY2027",
            "description": "Documento Westcon",
            "document": "Westcon_Comstor_Espana_FY27_completa.pptx",
            "source_type": "westcon-document",
            "provenance_origin": "WESTCON_DOCUMENT",
            "official": True,
            "source_grade": "A-WESTCON",
        }
        data = {
            "schemas": {
                "manufacturers": [{
                    "id": "capabilities",
                    "label": "Capacidades",
                    "decision_required": True,
                }]
            },
            "manufacturers": [{
                "id": "vendor",
                "name": "Vendor",
                "fields": {
                    "capabilities": {
                        "value": ["SASE"],
                        "evidence": [westcon],
                        "items": [{
                            "value": "SASE",
                            "evidence": [westcon, h_evidence()],
                        }],
                    }
                },
            }],
        }
        gaps = build_gaps(data, "4.0.5", {})
        h_gaps = [g for g in gaps["gaps"] if g.get("gap_kind") == "historical-revalidation"]
        self.assertEqual(len(h_gaps), 1)
        self.assertEqual(h_gaps[0]["target_values"], ["SASE"])
        self.assertTrue(h_gaps[0]["revalidation_seeds"])


if __name__ == "__main__":
    unittest.main()
