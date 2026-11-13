"""Regression for published historical badges and feed-only topic fields."""
import unittest
from pathlib import Path
from engine.verified_research import apply_verified_research

ROOT=Path(__file__).resolve().parents[1]

class HistoryTrendArchitectureRegression(unittest.TestCase):
    def test_frontend_attaches_exact_source_to_badge(self):
        js=(ROOT/"assets/app/intelligence.js").read_text(encoding="utf-8")
        self.assertIn("state.historicalVerifiedRecords=new Map",js)
        self.assertIn("item.evidence.push(ev)",js)
        self.assertIn("historicalKey(e.item_value)===historicalKey(h.value)",js)
        self.assertIn("if(section==='manufacturers'&&fieldId==='competitors')",js)

    def test_feed_only_news_not_duplicated_as_empty_claim(self):
        js=(ROOT/"assets/app/intelligence.js").read_text(encoding="utf-8")
        self.assertIn("!c.feed_only&&c.id!=='recent_signals'",js)
        self.assertIn("if((context==='trend'||row._section==='architectures')&&!rendered&&!historical)return ''",js)

    def test_architecture_existing_context_receives_exact_primary_citation(self):
        val="Convergencia de conectividad WAN, acceso Zero Trust y controles de seguridad cloud-delivered."
        data={"architectures":[{"name":"SASE / SSE","fields":{"context":{"value":val,"evidence":[]}}}]}
        apply_verified_research(data)
        field=data["architectures"][0]["fields"]["context"]
        self.assertTrue(field["evidence"] or any(it.get("evidence") for it in field.get("items") or []))
        self.assertEqual(field["value"],val)

if __name__=="__main__":
    unittest.main()
