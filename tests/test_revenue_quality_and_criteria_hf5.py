from __future__ import annotations

import unittest
from pathlib import Path

from engine.research.documents import Document
from engine.research.extractors import (
    Candidate,
    manufacturer_revenue_value_is_strict,
    revenue_observations,
    revenue_value_is_strict,
)
from engine.research.web_intelligence import _focus_candidates

ROOT = Path(__file__).resolve().parents[1]


class RevenueQualityAndCriteriaHF5(unittest.TestCase):
    def test_distributor_style_revenue_is_valid(self) -> None:
        self.assertTrue(revenue_value_is_strict("300 M€ · ventas 2025 · España"))
        self.assertTrue(revenue_value_is_strict("1.750 M€ · ventas 2025 · España"))

    def test_manufacturer_global_revenue_accepts_total_company_scale(self) -> None:
        value = "In fiscal year 2025, Example Corp reported total revenue of US$ 12.4 billion"
        self.assertTrue(manufacturer_revenue_value_is_strict(value))
        values, _ = revenue_observations(value, global_only=True)
        self.assertTrue(values)
        self.assertIn("US$ 12.4 billion", values[0])
        self.assertIn("2025", values[0])

    def test_manufacturer_rejects_channel_region_and_segment_revenue(self) -> None:
        bad = [
            "2025 channel revenue was EUR 500 million",
            "España registró ingresos de 500 M€ en 2025",
            "EMEA revenue reached $900 million in 2025",
            "Segment revenue was US$ 700 million in 2025",
            "El volumen de ingresos de canal alcanzó 500 M€ en 2025",
        ]
        for value in bad:
            with self.subTest(value=value):
                self.assertFalse(manufacturer_revenue_value_is_strict(value))

    def test_unrelated_article_text_is_not_revenue(self) -> None:
        bad = (
            'Compartir ENTREVISTAS "España ya está al mismo nivel que Italia en volumen '
            'de ingresos de canal": directivos de un mayorista. Publicado en 2025.'
        )
        self.assertFalse(revenue_value_is_strict(bad))
        values, _ = revenue_observations(bad, global_only=True)
        self.assertEqual(values, [])

    def test_focus_filter_runs_even_without_target_values(self) -> None:
        bad = Candidate(
            ('Compartir ENTREVISTAS "ingresos de canal" publicado en 2025',),
            "fact",
            0.66,
            "snippet",
            ("ingresos",),
        )
        document = Document(
            url="https://example.com/news",
            title="Example",
            text='Example · Compartir ENTREVISTAS "ingresos de canal" publicado en 2025',
            links=(),
            content_digest="hf5",
        )
        result = _focus_candidates(
            {"revenue": bad},
            {"section": "manufacturers", "entity": "Example", "fields": ["revenue"]},
            document,
            False,
        )
        self.assertNotIn("revenue", result)

    def test_schema_distinguishes_global_manufacturer_revenue(self) -> None:
        import json
        schema = json.loads((ROOT / "config/current/business_intelligence_schema.json").read_text(encoding="utf-8"))
        m = next(c for c in schema["sections"]["manufacturers"] if c["id"] == "revenue")
        d = next(c for c in schema["sections"]["distributors"] if c["id"] == "revenue")
        self.assertEqual(m.get("revenue_scope"), "global")
        self.assertEqual(d.get("revenue_scope"), "entity")
        self.assertIn("canal", m.get("help", "").casefold())

    def test_research_criteria_button_is_below_sources(self) -> None:
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="criteriaModal"', html)
        source = html.index('id="btnSources"')
        criteria = html.index('id="btnResearchCriteria"')
        export = html.index('id="btnExport"')
        self.assertLess(source, criteria)
        self.assertLess(criteria, export)

    def test_research_criteria_cover_current_backend_playbooks(self) -> None:
        from engine.gap_intelligence import PLAYBOOKS
        js = (ROOT / "assets/app/intelligence.js").read_text(encoding="utf-8")
        self.assertIn("RESEARCH_CRITERIA_PLAYBOOKS", js)
        self.assertIn("renderResearchCriteria", js)
        for family in PLAYBOOKS:
            self.assertIn(f"{family}:", js)

    def test_frontend_suppresses_malformed_revenue_everywhere(self) -> None:
        js = (ROOT / "assets/app/intelligence.js").read_text(encoding="utf-8")
        self.assertIn("function plausibleRevenueValue(", js)
        self.assertIn("function strictRevenueField(", js)
        self.assertIn("col?.id==='revenue'?strictRevenueField(base,col):base", js)
        self.assertNotIn("cardField(c,row.fields?.[c.id],context)", js)

    def test_static_asset_is_cache_busted(self) -> None:
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("assets/app/intelligence.js?v=4.3.1-hf5", html)


if __name__ == "__main__":
    unittest.main()
