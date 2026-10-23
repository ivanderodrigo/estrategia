"""Daily #81 regression: restoration cannot cross web evidence field binding."""
import unittest

from engine.enrichment import normalize_fields
from engine.preservation import restore_accredited_support


def _field():
    return {
        "value": ["Soporte"],
        "items": [{"value": "Soporte", "evidence": []}],
        "evidence": [],
    }


class Daily81EvidenceBinding(unittest.TestCase):
    def test_moved_support_with_old_field_metadata_is_filtered(self):
        # A legitimate source field can disappear during a migration while the
        # generic value survives in another field. Restoration's unique-value
        # fallback must not confer the old source on the new field.
        owner = "V-Valley Advanced Solutions Portugal"
        source = {
            "url": "https://example.org/soporte",
            "source": owner,
            "title": "Soporte",
            "description": "Soporte",
            "method": "web-evidence:extracted",
            "source_binding": "claim-specific",
            "accrediting": True,
            "atomic": True,
            "researched_entity": owner,
            "field": "services",
            "item_value": "Soporte",
        }
        old_field = _field()
        old_field["items"][0]["evidence"] = [source]
        old_field["evidence"] = [source]
        before = {"distributors": [{"name": owner, "fields": {"services": old_field}}]}
        new_field = _field()
        current = {"distributors": [{"name": owner, "fields": {
            "differential_capabilities": new_field,
        }}]}
        stats = restore_accredited_support(current, before)
        self.assertEqual(stats["moved_item_support_restored"], 1)
        item = current["distributors"][0]["fields"]["differential_capabilities"]["items"][0]
        self.assertEqual(len(item["evidence"]), 1)
        normalize_fields(current)
        item = current["distributors"][0]["fields"]["differential_capabilities"]["items"][0]
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
