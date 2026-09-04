import json
import unittest
from pathlib import Path

from engine.gap_intelligence import annotate_gap
from engine.research.planner import _learning_yield
from engine.preservation import audit as preservation_audit, snapshot as preservation_snapshot
from scripts.patch_runtime_v430 import _patch_web_text
from engine.westcon_current_evidence import _ensure_capabilities

ROOT = Path(__file__).resolve().parents[1]


class ResearchROIV430(unittest.TestCase):
    def test_growth_budget_is_bounded_by_profile(self):
        policy = json.loads((ROOT / "config/current/research_policy.json").read_text(encoding="utf-8"))
        self.assertEqual(policy.get("structured_growth_limits"), {"daily": 24, "deep": 100, "exhaustive": 220})

    def test_low_context_public_gap_cannot_reach_p0_p1(self):
        gap = {
            "section": "clients_public",
            "entity": "Synthetic Buyer",
            "field": "request_or_need",
            "priority": 1,
            "gap_kind": "standard",
            "research_state": "Por investigar",
        }
        public = {
            "schemas": {"clients_public": [{"id": "request_or_need", "decision_required": True}]},
            "clients_public": [],
        }
        annotate_gap(gap, public)
        self.assertEqual(gap["opportunity_context_multiplier"], 1.0)
        self.assertEqual(gap["priority_tier"], "P2")
        self.assertLess(gap["priority_score"], 58)

    def test_learning_penalises_no_yield_family(self):
        poor = {"families": {"manufacturers:news": {"attempts": 100, "fetch_successes": 10, "pages_relevant": 2, "accepted_evidence": 0}}}
        good = {"families": {"manufacturers:news": {"attempts": 100, "fetch_successes": 80, "pages_relevant": 45, "accepted_evidence": 30}}}
        self.assertLess(_learning_yield(poor, "manufacturers", "news"), _learning_yield(good, "manufacturers", "news"))

    def test_web_runner_uses_bounded_structured_growth_budget(self):
        text = (ROOT / "engine/research/web_intelligence.py").read_text(encoding="utf-8")
        self.assertIn('structured_growth_limits = RESEARCH_POLICY.get("structured_growth_limits")', text)
        self.assertIn('limit=structured_growth_budget,', text)
        self.assertIn('stats["structured_entities_added"] = structured_added', text)
        self.assertNotIn('limit={"daily": 80, "deep": 150, "exhaustive": 250}[profile],', text)

    def test_installer_patches_current_nested_ted_block_idempotently(self):
        fixture = """def run(profile, deadline, profile_config, fetcher, data, stats, started):
    # Structured public procurement is both higher precision and a genuine growth path.
    if deadline - time.monotonic() > profile_config.request_timeout_s + 3:
        try:
            notices = fetch_notices(
                fetcher.session,
                lookback_days=profile_config.ted_lookback_days,
                timeout_s=profile_config.request_timeout_s,
                limit={\"daily\": 80, \"deep\": 150, \"exhaustive\": 250}[profile],
            )
            stats[\"entities_added\"] += upsert_notices(data, notices)
            stats[\"structured_notices\"] = len(notices)
        except requests.RequestException:
            pass
    stats[\"elapsed_s\"] = round(time.monotonic() - started, 2)
"""
        patched = _patch_web_text(fixture)
        self.assertIn('structured_growth_limits = RESEARCH_POLICY.get("structured_growth_limits")', patched)
        self.assertIn('limit=structured_growth_budget,', patched)
        self.assertIn('stats["structured_entities_added"] = structured_added', patched)
        self.assertIn('stats["accepted_evidence_per_fetch_attempt"]', patched)
        self.assertNotIn('limit={"daily": 80, "deep": 150, "exhaustive": 250}[profile],', patched)
        self.assertEqual(_patch_web_text(patched), patched)

    def test_installer_patches_ted_block_without_deadline_wrapper(self):
        fixture = """def run(profile, profile_config, fetcher, data, stats, started):
    try:
        notices = fetch_notices(
            fetcher.session,
            lookback_days=profile_config.ted_lookback_days,
            timeout_s=profile_config.request_timeout_s,
            limit={\"daily\": 80, \"deep\": 150, \"exhaustive\": 250}[profile],
        )
        stats[\"entities_added\"] += upsert_notices(data, notices)
        stats[\"structured_notices\"] = len(notices)
    except requests.RequestException:
        pass
    stats[\"elapsed_s\"] = round(time.monotonic() - started, 2)
"""
        patched = _patch_web_text(fixture)
        self.assertIn('structured_growth_limits = RESEARCH_POLICY.get("structured_growth_limits")', patched)
        self.assertIn('limit=structured_growth_budget,', patched)
        self.assertIn('stats["structured_entities_added"] = structured_added', patched)
        self.assertIn('stats["accepted_evidence_per_fetch_attempt"]', patched)
        self.assertNotIn('limit={"daily": 80, "deep": 150, "exhaustive": 250}[profile],', patched)
        self.assertEqual(_patch_web_text(patched), patched)

    def _preservation_floor_data(self):
        return {
            "manufacturers": [{"id": f"m{i}", "name": f"M{i}", "fields": {}} for i in range(36)],
            "trends": [{"id": f"t{i}", "name": f"T{i}", "fields": {}} for i in range(15)],
            "architectures": [{"id": f"a{i}", "name": f"A{i}", "fields": {}} for i in range(12)],
        }

    def test_provisional_derived_relationship_can_be_recomputed_without_hard_loss(self):
        data = self._preservation_floor_data()
        provisional = {
            "entity_a_id": "client-semapa",
            "entity_a": "Semapa",
            "relation": "technology_signal",
            "entity_b_id": "tech-networking",
            "entity_b": "Networking",
            "countries": ["PT"],
            "country": "PT",
            "confidence": 0.48,
            "status": "SEÑAL",
            "validity": "needs-corroboration",
            "derived": True,
        }
        before = preservation_snapshot(data, {"relationships": [provisional]})
        after = preservation_snapshot(data, {"relationships": []})
        self.assertEqual(before.get("relations"), [])
        self.assertEqual(len(before.get("provisional_relations") or []), 1)
        report = preservation_audit(before, after)
        self.assertEqual(report["status"], "PASS")

    def test_confirmed_relationship_remains_hard_protected(self):
        data = self._preservation_floor_data()
        confirmed = {
            "entity_a_id": "partner-a",
            "entity_a": "Partner A",
            "relation": "uses",
            "entity_b_id": "vendor-a",
            "entity_b": "Vendor A",
            "confidence": 0.9,
            "status": "CONFIRMADA",
            "validity": "current",
            "derived": False,
        }
        before = preservation_snapshot(data, {"relationships": [confirmed]})
        after = preservation_snapshot(data, {"relationships": []})
        self.assertEqual(len(before.get("relations") or []), 1)
        report = preservation_audit(before, after)
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(any("Relaciones válidas" in row for row in report.get("errors") or []))


    def test_current_westcon_capability_evidence_cannot_bleed_into_adc(self):
        document = {
            "provenance_origin": "WESTCON_DOCUMENT_CURRENT",
            "document_id": "westcon-fy27",
            "title": "Westcon FY27",
        }
        documented = [
            "Application Security", "Application Delivery", "WAAP/WAF",
            "DDoS Protection", "Network Firewall", "Multicloud Connectivity",
            "API Security", "Bot Management",
        ]
        contaminated = [
            {
                "provenance_origin": "WESTCON_DOCUMENT_CURRENT",
                "document_id": "westcon-fy27",
                "field": "capabilities",
                "item_value": value,
                "atomic": True,
            }
            for value in documented
        ]
        public_adc = {
            "source": "f5.com",
            "classification": "public",
            "field": "capabilities",
            "item_value": "ADC",
        }
        row = {
            "name": "F5",
            "fields": {
                "capabilities": {
                    "value": ["ADC", "WAAP/WAF"],
                    "evidence": list(contaminated),
                    "items": [
                        {"value": "ADC", "evidence": list(contaminated) + [public_adc]},
                        {"value": "WAAP/WAF", "evidence": list(contaminated)},
                    ],
                }
            },
        }
        _ensure_capabilities(row, documented, document, [14, 7])
        items = {item["value"]: item for item in row["fields"]["capabilities"]["items"]}
        adc_current = [
            ev for ev in items["ADC"]["evidence"]
            if ev.get("provenance_origin") in {"WESTCON_DOCUMENT_CURRENT", "WESTCON_FIRST_PARTY_CURRENT"}
        ]
        self.assertEqual(adc_current, [])
        self.assertIn(public_adc, items["ADC"]["evidence"])
        waap_current = [
            ev for ev in items["WAAP/WAF"]["evidence"]
            if ev.get("provenance_origin") == "WESTCON_DOCUMENT_CURRENT"
        ]
        self.assertTrue(waap_current)
        self.assertTrue(all(ev.get("item_value") == "WAAP/WAF" for ev in waap_current))

    def test_release_integrity_contract_is_v430(self):
        text = (ROOT / "tests/test_release.py").read_text(encoding="utf-8")
        self.assertIn('self.assertEqual(VERSION, "4.3.0")', text)
        self.assertNotIn('self.assertEqual(VERSION, "4.2.2")', text)

    def test_workflow_runs_v430_audit_twice(self):
        text = (ROOT / ".github/workflows/research-run.yml").read_text(encoding="utf-8")
        self.assertEqual(text.count("python -m scripts.audit_v430"), 2)


if __name__ == "__main__":
    unittest.main()
