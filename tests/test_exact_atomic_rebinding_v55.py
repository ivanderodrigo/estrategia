import unittest

from engine.publication import _rebind_exact_item_evidence, _compact_object


def evidence(value, *, origin="PUBLIC_PRIMARY", field="vendor_relations"):
    return {
        "source": "Official partner directory", "title": "Partner directory",
        "description": "Exact listed partner", "date": "2026-10-31",
        "url": "https://example.org/partners", "source_grade": "A",
        "provenance_origin": origin, "field": field, "item_value": value,
    }


class AtomicRebindingTests(unittest.TestCase):
    def test_only_explicit_matching_item_gets_accredited(self):
        rows = [{"name": "Partner A", "fields": {"vendor_relations": {
            "value": ["Vendor X", "Vendor Y"],
            "items": [{"value": "Vendor X", "evidence": []}, {"value": "Vendor Y", "evidence": []}],
            "evidence": [evidence("Vendor X")],
        }}}]
        fixed, count = _rebind_exact_item_evidence(rows)
        self.assertEqual(count, 1)
        self.assertEqual(rows[0]["fields"]["vendor_relations"]["items"][0]["evidence"], [])
        items = fixed[0]["fields"]["vendor_relations"]["items"]
        self.assertEqual(len(items[0]["evidence"]), 1)
        self.assertEqual(items[1]["evidence"], [])
        registry = {}
        projected = _compact_object(items, registry)
        self.assertEqual(len(projected[0]["evidence_ids"]), 1)
        self.assertEqual(projected[1]["evidence_ids"], [])

    def test_wrong_field_or_historical_seed_does_not_rebind(self):
        rows = [{"fields": {"vendor_relations": {
            "items": [{"value": "Vendor X", "evidence": []}],
            "evidence": [evidence("Vendor X", field="services"),
                         evidence("Vendor X", origin="RESEARCH_SEED")],
        }}}]
        fixed, count = _rebind_exact_item_evidence(rows)
        self.assertEqual(count, 0)
        self.assertEqual(fixed[0]["fields"]["vendor_relations"]["items"][0]["evidence"], [])


if __name__ == "__main__":
    unittest.main()
