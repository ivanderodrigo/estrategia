"""End-to-end offline proof that source-first routing preserves evidence gates."""
from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from engine.research.documents import parse_document
from engine.research.extractors import Candidate
from engine.research.extractors import extract_candidates, specialization_observations
from engine.research.sources import SourceSeed
from engine.research import web_intelligence as research


class _OfflineFetcher:
    visited: list[str] = []

    def __init__(self, *, state, **_kwargs):
        self.state = state
        self.session = object()

    def fetch(self, seed):
        self.visited.append(seed.url)
        doc = parse_document(
            "<title>Acme Integraciones · Servicios</title>"
            "<body>Acme Integraciones ofrece cloud managed services.</body>",
            seed.url, "offline-proof",
        )
        return doc, False, 200, ""


class SourceFirstResearch(unittest.TestCase):
    def _run_offline(self, *, primary_has_evidence: bool):
        primary = SourceSeed(
            "https://acme.example/services", "services", True,
            "A", "official", "Acme Integraciones",
        )
        fallback = SourceSeed(
            "https://acme.example/other-services", "services", True,
            "A", "official", "Acme Integraciones",
        )
        target = {
            "section": "integrators", "entity": "Acme Integraciones",
            "gap_ids": ["gap-services"], "fields": ["services"],
            "families": ["services"], "source_families": ["services"],
            "gap_kinds": ["evidence-support"], "priority_tiers": ["P1"],
            "target_values": {}, "target_values_by_field": {},
            "revalidation_seeds": [], "query_hints": ["Acme servicios cloud"],
        }
        initial_data = {
            "integrators": [{"name": "Acme Integraciones", "fields": {}}],
            "manufacturers": [],
        }
        gaps = {"gaps": [{
            "id": "gap-services", "section": "integrators",
            "entity": "Acme Integraciones", "field": "services",
        }]}
        saved = []

        def fake_read(path, default=None):
            if path == "data/current/intelligence.json":
                return copy.deepcopy(initial_data)
            if path == "data/current/research_gaps.json":
                return copy.deepcopy(gaps)
            return copy.deepcopy(default if default is not None else {})

        def extract(_section, _family, document, _vendors, **_kw):
            if primary_has_evidence or document.url == fallback.url:
                return {"services": Candidate(("Cloud",), "fact", 0.90, "cloud", ("cloud",))}
            return {}

        _OfflineFetcher.visited = []
        with (
            patch.object(research, "read_json", side_effect=fake_read),
            patch.object(research, "plan", return_value=[target]),
            patch.object(research, "Fetcher", _OfflineFetcher),
            patch.object(research, "seeds_for", return_value=[primary]),
            patch.object(research, "_catalog_source_seeds", return_value=[]),
            patch.object(research, "_filter_entity_seeds", side_effect=lambda seeds, *_: seeds),
            patch.object(research, "intelligent_discovery_queries", return_value=[]),
            patch.object(research, "precise_claim_queries", return_value=[]),
            patch.object(research, "extract_candidates", side_effect=extract),
            patch.object(research, "_checkpoint", side_effect=lambda *args: saved.append(args[0])),
            patch.object(research, "atomic_write_json"),
            patch("engine.public_recovery.recover_newer_public"),
            patch.object(research, "discover_search_sources", return_value=(
                [fallback], {"queries_attempted": 1, "queries_succeeded": 1,
                             "urls_discovered": 1},
            )) as discovery,
        ):
            report = research.run(
                "deep", max_runtime=60,
                include_gap_kinds={"evidence-support"},
            )
        self.assertTrue(saved)
        return report, discovery.call_count, _OfflineFetcher.visited

    def test_primary_evidence_avoids_search(self):
        report, calls, visited = self._run_offline(primary_has_evidence=True)
        self.assertEqual(calls, 0)
        self.assertEqual(len(visited), 1)
        self.assertEqual(report["target_fields_resolved_early"], 1)
        self.assertEqual(report["accepted_evidences"], 1)

    def test_one_technology_page_can_yield_multiple_distinct_supported_fields(self):
        document = parse_document(
            "<title>Acme Integraciones | Soluciones tecnológicas</title>"
            "<body><h1>Nuestras soluciones y servicios</h1>"
            "Acme Integraciones somos especialistas en ciberseguridad. "
            "Ofrecemos servicios gestionados y consultoría de seguridad." 
            "</body>",
            "https://acme.example/technology", "multi-field-proof",
        )
        candidates = extract_candidates(
            "integrators", "technology", document, [], official=True,
            researched_entity="Acme Integraciones",
        )
        self.assertIn("Cybersecurity", candidates["capabilities"].values)
        self.assertIn("Servicios gestionados", candidates["services"].values)
        self.assertIn("Cybersecurity", candidates["specializations"].values)
        self.assertIn("Cybersecurity", candidates["technology_domains"].values)

    def test_specialization_requires_explicit_expertise_phrase(self):
        self.assertEqual(specialization_observations(
            "Acme ofrece servicios de cloud y networking"), ([], []))
        self.assertNotIn("Cloud", specialization_observations(
            "Somos especialistas en contabilidad. También distribuimos cloud.")[0])
        self.assertIn("Cybersecurity", specialization_observations(
            "Somos especialistas en ciberseguridad y gestión de incidentes")[0])

    def test_search_occurs_only_after_failed_primary_probe(self):
        report, calls, visited = self._run_offline(primary_has_evidence=False)
        self.assertEqual(calls, 1)
        self.assertEqual(visited, ["https://acme.example/services",
                                   "https://acme.example/other-services"])
        self.assertEqual(report["primary_source_probes_before_search"], 1)
        self.assertEqual(report["accepted_evidences"], 1)


if __name__ == "__main__":
    unittest.main()
