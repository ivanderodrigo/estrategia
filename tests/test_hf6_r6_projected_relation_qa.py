from __future__ import annotations

import unittest

from engine.quality import audit


def inverse_web_evidence():
    return {
        "source": "3Hold",
        "title": "3Hold partners with 1Password",
        "date": "2026-10-10",
        "description": "3Hold Technologies is a partner of 1Password in Spain.",
        "url": "https://example.com/3hold-1password",
        "scope": "ES",
        "scope_provenance": "explicit-text",
        "method": "web-evidence:partner-page",
        "source_binding": "claim-specific",
        "accrediting": True,
        "atomic": True,
        # Original extraction orientation:
        "researched_entity": "3Hold Technologies",
        "field": "vendor_relations",
        "item_value": "1Password",
        "item_key": "1password",
    }


def wrong_neighbour_evidence():
    return {
        "source": "Ignition Technology",
        "title": "Ignition Technology Our Vendors",
        "date": "2026-10-10",
        "description": "CrowdStrike is available through Ignition Technology in Spain and Portugal.",
        "url": "https://example.com/ignition-vendors",
        "scope": "IBERIA",
        "scope_provenance": "explicit-text",
        "method": "web-evidence:vendor-page",
        "source_binding": "claim-specific",
        "accrediting": True,
        "atomic": True,
        "researched_entity": "Ignition Technology",
        "field": "vendor_relations",
        "item_value": "CrowdStrike",
        "item_key": "crowdstrike",
    }


def dataset(evidence, *, vendor="1Password", integrator="3Hold Technologies"):
    return {
        "schemas": {"manufacturers": [{"id": "integrators"}]},
        "manufacturers": [{
            "name": vendor,
            "fields": {
                "integrators": {
                    "value": [integrator],
                    "items": [{"value": integrator, "evidence": [evidence]}],
                    "evidence": [evidence],
                    "claim_type": "fact",
                }
            },
        }],
        "distributors": [],
        "integrators": [],
        "clients_public": [],
        "clients_private": [],
        "trends": [],
        "architectures": [],
    }


def graph(evidence, *, vendor="1Password", integrator="3Hold Technologies"):
    return {
        "relationships": [{
            "id": "rel_test",
            "entity_a_id": "integrator_test",
            "entity_a": integrator,
            "relation": "partners_with",
            "entity_b_id": "manufacturer_test",
            "entity_b": vendor,
            "countries": ["ES"],
            "evidence": [evidence],
            "status": "CONFIRMADO",
        }]
    }


class HF6R6ProjectedRelationshipQA(unittest.TestCase):
    def test_inverse_projected_relationship_evidence_is_valid(self):
        ev = inverse_web_evidence()
        result = audit(dataset(ev), graph(ev), {"gaps": []})
        self.assertFalse(
            [e for e in result["errors"] if "mal asociada" in e or "Metadata atómica cruzada" in e],
            result["errors"],
        )

    def test_wrong_neighbour_still_fails(self):
        ev = wrong_neighbour_evidence()
        result = audit(
            dataset(ev, vendor="Claroty", integrator="Ignition Technology"),
            graph(ev, vendor="Claroty", integrator="Ignition Technology"),
            {"gaps": []},
        )
        errors = "\n".join(result["errors"])
        self.assertIn("Evidencia atómica mal asociada", errors)
        self.assertIn("Evidencia web mal asociada", errors)
        self.assertIn("Relación con evidencia mal asociada", errors)

    def test_non_relationship_field_still_requires_exact_field_binding(self):
        ev = inverse_web_evidence()
        data = {
            "schemas": {"manufacturers": [{"id": "capabilities"}]},
            "manufacturers": [{
                "name": "3Hold Technologies",
                "fields": {
                    "capabilities": {
                        "value": ["1Password"],
                        "items": [{"value": "1Password", "evidence": [ev]}],
                        "evidence": [ev],
                    }
                },
            }],
            "distributors": [],
            "integrators": [],
            "clients_public": [],
            "clients_private": [],
            "trends": [],
            "architectures": [],
        }
        result = audit(data, {"relationships": []}, {"gaps": []})
        self.assertTrue(
            any("Evidencia web mal asociada" in e for e in result["errors"]),
            result["errors"],
        )


if __name__ == "__main__":
    unittest.main()
