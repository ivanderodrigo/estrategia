"""The FY27 portfolio must never replace an accredited atomic domain list."""
import unittest
from copy import deepcopy

from engine.westcon_current_evidence import apply_westcon_current_evidence
from engine.preservation import snapshot, audit


class EfficientIPPortfolioDomain(unittest.TestCase):
    def test_portfolio_preserves_existing_atomic_domain_support(self):
        web = {
            "source": "efficientip.com",
            "title": "Core Networking Services | EfficientIP",
            "description": "EfficientIP core networking services",
            "url": "https://efficientip.com/products/",
            "source_type": "primary-or-company",
            "source_binding": "atomic-item",
            "researched_entity": "EfficientIP",
            "field": "domain",
            "item_value": "Networking",
            "atomic": True,
            "method": "web-evidence:services",
        }
        data = {"manufacturers": [{
            "id": "mfr-efficientip",
            "name": "EfficientIP",
            "fields": {"domain": {
                "value": ["Networking"],
                "items": [{"value": "Networking", "evidence": [web]}],
                "evidence": [web],
            }},
        }]}
        before = snapshot(deepcopy(data))
        config = {
            "document": {
                "document_id": "test-current-westcon",
                "title": "Current Westcon FY27",
                "source": "Westcon",
                "source_type": "westcon-document-current",
                "provenance_origin": "WESTCON_DOCUMENT_CURRENT",
                "source_binding": "claim-specific",
                "accrediting": True,
            },
            "portfolio_spain": {"EfficientIP": {
                "domain": "Networking",
                "slides": [42],
                "capabilities": [],
            }},
            "portugal_rule": {"source": "Westcon", "scope": "PT"},
        }
        apply_westcon_current_evidence(data, config)
        domain = data["manufacturers"][0]["fields"]["domain"]
        self.assertEqual(domain["value"], ["Networking"])
        self.assertEqual(len(domain["items"]), 1)
        self.assertTrue(any(ev.get("method") == "web-evidence:services"
                            for ev in domain["items"][0]["evidence"]))
        self.assertTrue(any(ev.get("provenance_origin") == "WESTCON_DOCUMENT_CURRENT"
                            for ev in domain["items"][0]["evidence"]))
        after = snapshot(data)
        self.assertEqual(set(before["evidences"]) - set(after["evidences"]), set())


if __name__ == "__main__":
    unittest.main()
