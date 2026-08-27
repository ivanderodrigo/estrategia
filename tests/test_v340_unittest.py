from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class V340ProductionCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recommendations = load("data/v34/recommendations.json")
        cls.entities = load("data/v34/entities.json")
        cls.relationships = load("data/v34/relationships.json")
        cls.architectures = load("data/v34/architectures.json")
        cls.quality = load("data/v34/quality_report.json")
        cls.audit = load("data/v34/recommendation_audit.json")
        cls.sources = load("data/v34/source_coverage.json")
        cls.catalog = load("data/v34/source_catalog.json")
        cls.motion = load("data/v34/ecosystem_motion_intelligence.json")
        cls.history = load("data/v34/historical_intelligence.json")
        cls.queue = load("data/v34/research_queue.json")
        cls.tables = load("config/v34/table_config.json")

    def test_version_and_required_outputs(self):
        self.assertEqual((ROOT / "VERSION").read_text(encoding="utf-8").strip(), "3.4.0")
        required = {
            "recommendation_audit.json", "quality_report.json", "source_coverage.json",
            "source_catalog.json", "business_intelligence_report.json", "ecosystem_motion_intelligence.json",
        }
        self.assertTrue(required <= {path.name for path in (ROOT / "data/v34").glob("*.json")})

    def test_recommendation_audit_passes_without_optimising_away_warnings(self):
        self.assertEqual(self.audit["status"], "PASS")
        self.assertEqual(self.audit["summary"]["invented_recommendations"], 0)
        self.assertEqual(self.audit["summary"]["without_evidence"], 0)
        self.assertEqual(self.audit["summary"]["generic_recommendations"], 0)
        self.assertGreater(self.audit["summary"]["discarded_or_not_shown"], 0)

    def test_every_recommendation_has_executive_contract(self):
        required = {
            "action", "why", "why_now", "evidence", "fact_confidence", "interpretation_confidence",
            "action_risk", "confidence", "action_type", "impact_potential", "urgency", "effort", "horizon",
            "proposed_owner", "vendors_involved", "integrators_involved", "distributors_involved",
            "potential_services", "recurring_revenue_potential", "relative_margin_potential", "risks",
            "missing_information", "evidence_that_would_change_recommendation", "sources", "source_dates",
        }
        for row in self.recommendations["recommendations"]:
            self.assertTrue(required <= set(row), row.get("recommendation_id"))
            self.assertTrue(row["evidence"])
            self.assertTrue(all(item.get("url") and item.get("source") and item.get("date") for item in row["evidence"]))

    def test_action_types_are_proportional_not_absolute_gate(self):
        allowed = {"ACTUAR", "PREPARAR / VALIDAR", "INVESTIGAR", "VIGILAR"}
        rows = self.recommendations["recommendations"]
        self.assertTrue(rows)
        self.assertTrue({row["action_type"] for row in rows} <= allowed)
        self.assertIn("PREPARAR / VALIDAR", {row["action_type"] for row in rows})
        self.assertIn("INVESTIGAR", {row["action_type"] for row in rows})
        self.assertIn("VIGILAR", {row["action_type"] for row in rows})

    def test_actuar_requires_strong_evidence_if_present(self):
        for row in self.recommendations["recommendations"]:
            if row["action_type"] != "ACTUAR":
                continue
            self.assertGreaterEqual(row["fact_confidence"]["score"], 0.82)
            self.assertGreaterEqual(row["interpretation_confidence"]["score"], 0.68)
            self.assertLessEqual(row["action_risk"]["score"], 0.35)
            self.assertTrue(any(item["source_type"] == "primary" for item in row["evidence"]))

    def test_quality_passes_and_keeps_stale_evidence_warning(self):
        self.assertEqual(self.quality["status"], "PASS")
        self.assertEqual(self.quality["summary"]["errors"], 0)
        self.assertEqual(self.quality["checks"]["stale_evidence"]["status"], "WARN")

    def test_identity_role_conflicts_are_excluded(self):
        names = {row["name"] for row in self.entities["integrators"]}
        self.assertFalse({"Cisco", "Fortinet", "Infoblox", "Arista Networks"} & names)
        audit = load("data/v34/identity_audit.json")
        self.assertGreaterEqual(audit["excluded_count"], 4)

    def test_relationship_state_intensity_confidence_and_evidence_roles_are_separate(self):
        allowed = {"CONFIRMED", "PROBABLE", "RESEARCH PRIORITY", "INSUFFICIENT EVIDENCE"}
        for row in self.relationships["integrator_vendor"] + self.relationships["distributor_vendor"]:
            self.assertIn(row["status"], allowed)
            self.assertTrue(0 <= row["relationship_intensity"] <= 100)
            self.assertIn("score", row["fact_confidence"])
            self.assertIn("relationship_evidence", row)
            self.assertIn("partnership_level_evidence", row)
            self.assertIn("customer_case_evidence", row)

    def test_relationship_evidence_is_deduplicated(self):
        for row in self.relationships["integrator_vendor"] + self.relationships["distributor_vendor"]:
            urls = [item.get("url") for item in row.get("evidence", []) if item.get("url")]
            self.assertEqual(len(urls), len(set(urls)), row.get("relationship_id"))

    def test_source_learning_rates_stay_in_range(self):
        for row in self.sources["coverage"]:
            self.assertTrue(0 <= row["success_rate"] <= 1)
            self.assertTrue(0 <= row["next_use_priority"] <= 1)
            self.assertTrue(0 <= row["duplication_rate"] <= 1)

    def test_operational_source_catalog_is_complete_and_publicly_governed(self):
        rows = self.catalog["sources"]
        self.assertTrue(100 <= len(rows) <= 150)
        required = {"source_id", "name", "url", "free_or_paid", "scope", "source_class", "dimensions", "query_method", "recommended_frequency", "priority", "access_policy", "feeds"}
        self.assertTrue(all(required <= set(row) for row in rows))
        ids = {row["source_id"] for row in rows}
        self.assertTrue({"bdns", "cnmc_data", "anacom_stats", "vendor_partner_locators", "official_careers", "employer_ats"} <= ids)

    def test_ecosystem_motion_crosses_manufacturers_and_profiles(self):
        self.assertGreaterEqual(len(self.motion["entities"]), 30)
        for row in self.motion["entities"]:
            self.assertIn("manufacturers_confirmed", row)
            self.assertIn("manufacturers_probable", row)
            self.assertIn("manufacturers_to_research", row)
            self.assertIn("manufacturers_in_job_profiles", row)
            self.assertIn("profiles_sought", row)
            self.assertTrue(row["query_templates"])
        self.assertGreaterEqual(self.motion["meta"]["rejected_hiring_false_positives"], 1)

    def test_employment_signal_does_not_claim_partnership(self):
        for row in self.motion["entities"]:
            for signal in row["manufacturers_in_job_profiles"]:
                self.assertEqual(signal["status"], "EMPLOYMENT INDICATOR — NOT PARTNERSHIP")
        self.assertIn("ausencia de vacantes", self.motion["source_policy"]["negative_evidence"].lower())

    def test_vendor_relationship_playbook_prioritises_official_surfaces(self):
        playbook = self.motion["relationship_source_playbook"]
        self.assertEqual(playbook["evidence_order"][0]["type"], "partner_locator")
        self.assertEqual(playbook["evidence_order"][1]["type"], "partnership_level")
        self.assertGreaterEqual(len(playbook["vendor_families"]), 15)

    def test_adaptive_queue_routes_gaps_to_sources(self):
        self.assertTrue(self.queue["queue"])
        self.assertTrue(all(row.get("query_plan") and row.get("recommended_sources") for row in self.queue["queue"][:30]))
        self.assertTrue(all(row.get("negative_result_policy") for row in self.queue["queue"][:30]))

    def test_tables_hide_internal_and_sparse_columns(self):
        self.assertGreaterEqual(self.tables["behavior"]["minimum_population_ratio"], 0.15)
        self.assertTrue(self.tables["behavior"]["hide_internal_fields"])
        for kind in ("integrators", "distributors"):
            tier = next(column for column in self.tables["entities"][kind]["columns"] if column["field"] == "entity_tier")
            self.assertFalse(tier["user_visible"])

    def test_architectures_are_original_complete_and_cautious(self):
        rows = self.architectures["architectures"]
        self.assertGreaterEqual(len(rows), 12)
        required = {"problem", "opportunity", "layers", "vendors", "integrations", "integrators", "gaps", "westcon_services", "monetization", "recurrence", "kpis", "risks", "readiness", "evidence"}
        for row in rows:
            self.assertTrue(required <= set(row))
            self.assertTrue(all(layer["integration_status"] == "A VALIDAR" for layer in row["layers"]))

    def test_history_has_30_90_365_windows(self):
        self.assertEqual(set(self.history["windows"]), {"30", "90", "365"})
        self.assertTrue(all("by_type" in row and "technologies" in row and "changes" in row for row in self.history["windows"].values()))

    def test_daily_weekly_monthly_workflows_use_v34(self):
        workflow = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / ".github/workflows").glob("*.yml"))
        self.assertIn("research_supervisor_v34.py", workflow)
        self.assertIn("data/v34/", workflow)
        self.assertIn("--profile deep", workflow)
        self.assertIn("--profile exhaustive", workflow)

    def test_installer_is_portable_and_has_rollback(self):
        installer = (ROOT / "tools/aplicar_v340.py").read_text(encoding="utf-8")
        self.assertIn("pathlib", installer)
        self.assertIn("--migrate-from", installer)
        self.assertIn("--rollback-migration", installer)
        subprocess.run([sys.executable, "-m", "py_compile", str(ROOT / "tools/aplicar_v340.py")], check=True)

    def test_javascript_syntax_and_v34_smoke(self):
        for path in (ROOT / "assets").rglob("*.js"):
            subprocess.run(["node", "--check", str(path)], check=True, capture_output=True, text=True)
        subprocess.run(["node", str(ROOT / "tests/ui_smoke_v340.js")], check=True, capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
