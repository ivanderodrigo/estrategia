from __future__ import annotations

import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from engine.model import canonical
from engine.graph import build_graph

from engine.relationship_revalidation import (
    _parse_ted_xml,
    _target_match,
    ted_publication_number,
    ted_xml_url,
)

ROOT = Path(__file__).resolve().parents[1]


def independently_supported_relation(relation):
    """A pending historical lead may coexist with independent *current* proof.

    A newly discovered official TED notice can create a valid technology edge
    without changing the status of an old, unrelated historical lead. The old
    assertion that the edge must NEVER appear caused successful research runs
    to fail when they found such independent evidence.
    """
    for ev in relation.get("evidence") or []:
        if not isinstance(ev, dict):
            continue
        # A recovered historical record is still a lead, including when its
        # original publisher is an official procurement portal.
        if str(ev.get("provenance_origin") or "").upper() in {
            "HISTORICAL_RECOVERED", "LEGACY_UNRESOLVED"
        }:
            continue
        url = str(ev.get("url") or "")
        source_type = str(ev.get("source_type") or "").casefold()
        if not (ev.get("official") and url.startswith("https://")):
            continue
        if source_type in {"official-procurement-notice", "official-procurement-notice-revalidated"}:
            if urlsplit(url).hostname == "ted.europa.eu" and str(ev.get("title") or "").strip():
                return True
        if (source_type == "official-procurement-api"
                and ev.get("method") == "ted-literal-title-v1"
                and ev.get("atomic") is True
                and ev.get("source_binding") == "claim-specific"
                and ev.get("field") == "technology_signals"
                and urlsplit(url).hostname == "ted.europa.eu"
                and canonical(ev.get("researched_entity")) == canonical(relation.get("entity_a"))
                and canonical(ev.get("item_value")) == canonical(relation.get("entity_b"))
                and ev.get("matched_terms")
                and str(ev.get("title") or "").strip()):
            return True
        if (str(ev.get("source_binding") or "") == "claim-specific"
                and str(ev.get("provenance_origin") or "") == "PUBLIC_PRIMARY"
                and not source_type.startswith(("historical", "legacy", "public-web"))):
            return True
    return False


class RelationshipRevalidationV405(unittest.TestCase):
    def test_historical_only_technology_signal_is_not_a_current_graph_edge(self) -> None:
        item = {
            "value": "Colaboración", "evidence": [{
                "source": "Archivo", "title": "Pista histórica", "date": "2024-02-01",
                "description": "Mención previa por comprobar",
                "url": "https://example.org/historical-source",
                "provenance_origin": "HISTORICAL_RECOVERED",
            }],
        }
        row = {"name": "Entidad de prueba", "fields": {
            "technology_signals": {"value": ["Colaboración"], "items": [item]},
        }}
        data = {"clients_public": [row]}
        self.assertFalse(any(r.get("relation") == "technology_signal"
                             and r.get("entity_a") == "Entidad de prueba"
                             and r.get("entity_b") == "Colaboración"
                             for r in build_graph(data)["relationships"]))

        item["evidence"].append({
            "source": "Entidad de prueba", "title": "Plan de colaboración tecnológica",
            "date": "2026-11-27", "description": "La entidad menciona colaboración.",
            "url": "https://example.org/official-plan", "official": True,
            "source_type": "official",
        })
        self.assertTrue(any(r.get("relation") == "technology_signal"
                            and r.get("entity_a") == "Entidad de prueba"
                            and r.get("entity_b") == "Colaboración"
                            for r in build_graph(data)["relationships"]))

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

    def test_pending_historical_relation_needs_independent_graph_proof(self) -> None:
        registry = self._registry()
        graph = json.loads(
            (ROOT / "data/current/relationship_graph.json").read_text(encoding="utf-8")
        )
        visible = {
            (
                str(r.get("entity_a") or "").casefold(),
                str(r.get("relation") or "").casefold(),
                str(r.get("entity_b") or "").casefold(),
            ): r
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
            if key in visible:
                relation = visible[key]
                if independently_supported_relation(relation):
                    continue
                # A new public observation is permitted as a *provisional*
                # signal. It must not be confused with the independent proof
                # required to confirm an old historical relationship. This
                # distinction avoids aborting otherwise successful research.
                self.assertEqual(relation.get("relation"), "technology_signal", key)
                self.assertEqual(relation.get("status"), "SEÑAL", key)
                self.assertEqual(relation.get("validity"), "needs-corroboration", key)
                self.assertTrue(relation.get("derived"), key)
                self.assertLessEqual(float(relation.get("confidence") or 0), 0.48, key)

    def test_old_historical_mention_alone_never_unlocks_graph_proof(self) -> None:
        historical = {"evidence": [{
            "url": "https://legacy.example/mention", "official": True,
            "source_type": "historical-unresolved", "provenance_origin": "HISTORICAL_RECOVERED",
            "title": "Mención sin revalidar",
        }]}
        self.assertFalse(independently_supported_relation(historical))
        modern = {"evidence": [{
            "url": "https://ted.europa.eu/en/notice/-/detail/583069-2026",
            "official": True, "source_type": "official-procurement-notice",
            "title": "583069-2026 · Ordenadores personales y portátiles",
        }]}
        self.assertTrue(independently_supported_relation(modern))
        modern["evidence"][0]["provenance_origin"] = "HISTORICAL_RECOVERED"
        self.assertFalse(independently_supported_relation(modern))
        bound = {"entity_a": "Diputación de Barcelona", "entity_b": "Cloud", "evidence": [{
            "url": "https://ted.europa.eu/en/notice/-/detail/123456-2026",
            "official": True, "source_type": "official-procurement-api",
            "method": "ted-literal-title-v1", "source_binding": "claim-specific",
            "atomic": True, "field": "technology_signals", "item_value": "Cloud",
            "researched_entity": "Diputación de Barcelona",
            "matched_terms": ["nube"], "title": "Servicios en la nube",
        }]}
        self.assertTrue(independently_supported_relation(bound))
        bound["evidence"][0]["researched_entity"] = "Otra institución"
        self.assertFalse(independently_supported_relation(bound))

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
