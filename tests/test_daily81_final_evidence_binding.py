"""Daily #81 regression: final restoration may not bypass atomic evidence validation."""
import unittest

from engine.enrichment import normalize_fields
from engine.preservation import restore_accredited_support
from engine.quality import audit


def _row():
    return {
        "name": "V-Valley Advanced Solutions Portugal",
        "fields": {
            "services": {
                "value": ["Soporte"],
                "items": [{"value": "Soporte", "evidence": []}],
                "evidence": [],
            },
            "differential_capabilities": {
                "value": ["Soporte"],
                "items": [{"value": "Soporte", "evidence": []}],
                "evidence": [],
            },
        },
    }


class Daily81EvidenceBinding(unittest.TestCase):
    def test_invalid_recovered_web_evidence_is_removed_by_final_normalization(self):
        bad = {
            "url": "https://example.org/soporte",
            "source": "Example",
            "title": "Soporte",
            "description": "Soporte",
            "method": "web-evidence:extracted",
            "source_binding": "claim-specific",
            "atomic": True,
            "researched_entity": "V-Valley Advanced Solutions Portugal",
            "field": "services",
            "item_value": "Other value",
        }
        before = {"distributors": [_row()]}
        before["distributors"][0]["fields"]["services"]["items"][0]["evidence"] = [bad]
        before["distributors"][0]["fields"]["services"]["evidence"] = [bad]
        current = {"distributors": [_row()]}
        restore_accredited_support(current, before)
        normalize_fields(current)
        item = current["distributors"][0]["fields"]["services"]["items"][0]
        self.assertEqual(item["evidence"], [])

    def test_final_normalization_follows_final_restoration_in_pipeline(self):
        from pathlib import Path
        code = (Path(__file__).resolve().parents[1] / "engine/pipeline.py").read_text(encoding="utf-8")
        anchor = code.index("final_support_reconciliation = restore_accredited_support(data, preservation_source)")
        final_normalize = code.index("normalize_fields(data)", anchor)
        quality = code.index("quality = audit(data, graph, legacy_quality_gaps)")
        self.assertLess(anchor, final_normalize)
        self.assertLess(final_normalize, quality)


if __name__ == "__main__":
    unittest.main()
