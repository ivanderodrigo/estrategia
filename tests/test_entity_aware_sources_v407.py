from __future__ import annotations

import unittest
from types import SimpleNamespace

from engine.research.web_intelligence import (
    _decode_http_body,
    _seed_binding,
    _subject_value_match,
)


def doc(url: str, title: str, text: str):
    return SimpleNamespace(url=url, title=title, text=text)


class EntityAwareSourcesV407(unittest.TestCase):
    def test_utf8_beats_requests_latin1_default(self):
        body = "Únete · España · López · integração · cibersegurança".encode("utf-8")
        response = SimpleNamespace(
            headers={"Content-Type": "text/html"},
            encoding="ISO-8859-1",
        )
        decoded = _decode_http_body(body, response)
        self.assertEqual(
            decoded,
            "Únete · España · López · integração · cibersegurança",
        )

    def test_explicit_cp1252_still_works(self):
        text = "España – información"
        body = text.encode("cp1252")
        response = SimpleNamespace(
            headers={"Content-Type": "text/html; charset=windows-1252"},
            encoding="windows-1252",
        )
        self.assertEqual(_decode_http_body(body, response), text)

    def test_foreign_homepages_are_discovery_only(self):
        self.assertEqual(
            _seed_binding(
                "https://www.nokia.com/",
                "Infosys",
                source_type="official-domain",
                source_name="Infosys",
            ),
            "discovery-only",
        )
        self.assertEqual(
            _seed_binding(
                "https://www.vectra.ai/",
                "SIA",
                source_type="official-domain",
                source_name="SIA",
            ),
            "discovery-only",
        )

    def test_partner_directory_is_relationship_source(self):
        self.assertEqual(
            _seed_binding(
                "https://www.zscaler.com/partners/system-integrators",
                "SIA",
                source_type="vendor-partner-directory",
                source_name="Zscaler",
            ),
            "relationship-source",
        )

    def test_mapfre_is_entity_owned(self):
        self.assertEqual(
            _seed_binding(
                "https://www.mapfre.com/talento/unete-a-nuestro-equipo/",
                "Mapfre",
                source_type="customer-careers",
                source_name="MAPFRE",
            ),
            "entity-owned",
        )

    def test_integrity360_generic_service_provider_is_not_capability(self):
        d = doc(
            "https://www.integrity360.com/partners",
            "Partners | Integrity360",
            (
                "If your business handles credit card data, PCI DSS compliance "
                "is critical. From retailers and e-commerce platforms to service "
                "providers and financial institutions, securing card data matters."
            ),
        )
        self.assertFalse(
            _subject_value_match(
                "Integrity360",
                "Service provider",
                d,
                field_id="capabilities",
            )
        )

    def test_mapfre_job_is_valid_hiring_signal(self):
        d = doc(
            "https://www.mapfre.com/talento/unete-a-nuestro-equipo/",
            "Únete a nuestro equipo - Mapfre",
            "Últimos puestos publicados. Especialista de ciberseguridad.",
        )
        self.assertTrue(
            _subject_value_match(
                "Mapfre",
                "Especialista de ciberseguridad",
                d,
                field_id="hiring_signals",
            )
        )

    def test_zscaler_ai_does_not_prove_sia_ai(self):
        d = doc(
            "https://www.zscaler.com/partners/technology",
            "Join the Partner Ecosystem | Zscaler Partners",
            (
                "Secure B2B Zero Trust SASE Everywhere. Security for AI. "
                "Adopt AI at full speed with Zscaler."
            ),
        )
        self.assertFalse(
            _subject_value_match(
                "SIA",
                "AI",
                d,
                field_id="specializations",
            )
        )

    def test_explicit_partner_context_can_support_claim(self):
        d = doc(
            "https://vendor.example/partners/seyrcom",
            "Partner profile",
            (
                "Seyrcom is an authorized technology partner delivering "
                "SmartZone solutions to enterprise customers."
            ),
        )
        self.assertTrue(
            _subject_value_match(
                "Seyrcom",
                "SmartZone",
                d,
                field_id="capabilities",
            )
        )


if __name__ == "__main__":
    unittest.main()
