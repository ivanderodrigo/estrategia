from __future__ import annotations

import json
import unittest
from pathlib import Path

from engine.relationship_revalidation import (
    _parse_ted_xml,
    _target_match,
    ted_publication_number,
    ted_xml_url,
)

ROOT = Path(__file__).resolve().parents[1]


class RelationshipRevalidationV405(unittest.TestCase):
    def _registry(self):
        return json.loads(
            (ROOT / "config/current/relationship_revalidation_registry.json").read_text(
                encoding="utf-8"
            )
        )

    def test_relationship_registry_exists_and_is_nonempty(self) -> None:
        data = self._registry()
        self.assertGreater(data.get("candidates_total", 0), 0)

    def test_registry_counters_are_explicit(self) -> None:
        data = self._registry()
        self.assertIn("supported_current_open", data)
        self.assertIn("search_required", data)
        self.assertEqual(
            data.get("candidates_total"),
            int(data.get("supported_current_open") or 0)
            + int(data.get("search_required") or 0),
        )

    def test_every_candidate_has_url_seed(self) -> None:
        data = self._registry()
        for row in data.get("candidates") or []:
            self.assertTrue(row.get("revalidation_seeds"))
            self.assertTrue(
                any(
                    str(seed.get("url") or "").startswith(("http://", "https://"))
                    for seed in row.get("revalidation_seeds") or []
                )
            )

    def test_relationship_debt_is_separate_from_main_gap_kpi(self) -> None:
        gaps = json.loads(
            (ROOT / "data/current/research_gaps.json").read_text(encoding="utf-8")
        )
        debt = gaps.get("relationship_revalidation_debt") or []
        self.assertEqual(
            len(debt),
            gaps.get("relationship_revalidation_debt_total"),
        )

    def test_current_graph_does_not_count_pending_h_relationships(self) -> None:
        registry = self._registry()
        graph = json.loads(
            (ROOT / "data/current/relationship_graph.json").read_text(encoding="utf-8")
        )
        visible = {
            (
                str(r.get("entity_a") or "").casefold(),
                str(r.get("relation") or "").casefold(),
                str(r.get("entity_b") or "").casefold(),
            )
            for r in graph.get("relationships") or []
        }
        for row in registry.get("candidates") or []:
            if row.get("revalidation_status") == "supported-by-current-open-source":
                continue
            key = (
                str(row.get("entity") or "").casefold(),
                str(row.get("relation") or "").casefold(),
                str(row.get("entity_b") or "").casefold(),
            )
            self.assertNotIn(key, visible)

    def test_ted_detail_url_is_converted_to_official_xml(self) -> None:
        url = "https://ted.europa.eu/en/notice/-/detail/595840-2026"
        self.assertEqual(ted_publication_number(url), "595840-2026")
        self.assertEqual(
            ted_xml_url(url),
            "https://ted.europa.eu/en/notice/595840-2026/xml",
        )

    def test_ted_xml_parser_extracts_procurement_content_and_cpv(self) -> None:
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <ContractNotice xmlns:cbc="urn:test">
          <cbc:Title>Servicios Cloud para plataforma corporativa</cbc:Title>
          <cbc:Description>Servicio gestionado de nube híbrida.</cbc:Description>
          <cbc:ItemClassificationCode>72222300</cbc:ItemClassificationCode>
        </ContractNotice>"""
        parsed = _parse_ted_xml(xml)
        self.assertIn("Cloud", parsed["searchable_text"])
        self.assertIn("72222300", parsed["cpv_codes"])

    def test_no_semantic_invention_when_target_is_not_explicit(self) -> None:
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <ContractNotice xmlns:cbc="urn:test">
          <cbc:Title>Suministro de equipamiento informático</cbc:Title>
          <cbc:Description>Ordenadores y periféricos para puestos de trabajo.</cbc:Description>
        </ContractNotice>"""
        parsed = _parse_ted_xml(xml)
        self.assertFalse(_target_match("networking", parsed["searchable_text"]))
        self.assertFalse(_target_match("Cloud", parsed["searchable_text"]))


if __name__ == "__main__":
    unittest.main()
