import unittest
from engine.research.web_intelligence import _unsourced_value_queries


def public_proof():
    return {
        "source": "Official", "title": "Partner listing", "date": "2026-10-31",
        "description": "Exact partner verified", "url": "https://example.org/partners",
        "provenance_origin": "PUBLIC_PRIMARY", "field": "vendor_relations",
        "item_value": "Verified Vendor",
    }


class UnsourcedClaimSearchTests(unittest.TestCase):
    def test_unsourced_exact_values_become_queries(self):
        row = {"name": "Integrator A", "fields": {"vendor_relations": {
            "items": [
                {"value": "Verified Vendor", "evidence": [public_proof()]},
                {"value": "Old Vendor", "evidence": []},
                {"value": "Legacy Platform", "evidence": []},
            ]
        }}}
        queries = _unsourced_value_queries(row, ["vendor_relations"])
        self.assertEqual(queries, [
            '"Integrator A" "Old Vendor"',
            '"Integrator A" "Legacy Platform"',
        ])

    def test_rotation_reaches_other_values_and_balances_fields(self):
        row = {"name": "Integrator A", "fields": {
            "vendor_relations": {"items": [
                {"value": "Vendor A", "evidence": []},
                {"value": "Vendor B", "evidence": []},
                {"value": "Vendor C", "evidence": []},
                {"value": "Vendor D", "evidence": []},
            ]},
            "capabilities": {"items": [
                {"value": "Network security", "evidence": []},
                {"value": "Cloud migration", "evidence": []},
            ]},
        }}
        result = _unsourced_value_queries(row, ["vendor_relations", "capabilities"], limit=3, rotation=1)
        self.assertEqual(result, [
            '"Integrator A" "Vendor B"',
            '"Integrator A" "Cloud migration"',
            '"Integrator A" "Vendor C"',
        ])
        rotated = _unsourced_value_queries(row, ["vendor_relations"], limit=1, rotation=3)
        self.assertEqual(rotated, ['"Integrator A" "Vendor D"'])

    def test_reject_unhelpful_values_and_bound_results(self):
        row = {"name": "Integrator A", "fields": {"capabilities": {
            "items": [
                {"value": "Integrator A", "evidence": []},
                {"value": "X", "evidence": []},
                {"value": "A" * 110, "evidence": []},
                {"value": "SASE", "evidence": []},
                {"value": "SD WAN", "evidence": []},
            ],
        }}}
        self.assertEqual(_unsourced_value_queries(row, ["capabilities"], limit=1), ['"Integrator A" "SASE"'])


if __name__ == "__main__":
    unittest.main()
