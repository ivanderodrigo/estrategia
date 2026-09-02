from __future__ import annotations

import unittest
from types import SimpleNamespace

from engine.research.web_intelligence import _subject_value_match


def doc(url: str, title: str, text: str):
    # _subject_value_match only requires url/title/text.
    # Avoid coupling this regression test to the concrete fetcher module.
    return SimpleNamespace(
        url=url,
        title=title,
        text=text,
    )


class ClaimValidationR6(unittest.TestCase):
    def test_infosys_cannot_be_supported_by_plain_nokia_page(self):
        d = doc(
            "https://www.nokia.com/",
            "Nokia Corporation | Nokia",
            "Nokia networking data center solutions for enterprises.",
        )
        self.assertFalse(_subject_value_match("Infosys", "Networking", d))
        self.assertFalse(_subject_value_match("Infosys", "Data Center", d))

    def test_seyrcom_cannot_be_supported_by_plain_ruckus_page(self):
        d = doc(
            "https://www.ruckusnetworks.com/",
            "RUCKUS Networks -- Purpose-driven enterprise networks",
            "SmartZone AIOps manufacturing networking solutions.",
        )
        self.assertFalse(_subject_value_match("Seyrcom", "SmartZone", d))
        self.assertFalse(_subject_value_match("Seyrcom", "AIOps", d))

    def test_sia_cannot_be_supported_by_plain_vectra_page(self):
        d = doc(
            "https://www.vectra.ai/",
            "AI-Native Security & Observability Platform | Vectra AI",
            "AI cybersecurity identity security and observability.",
        )
        self.assertFalse(_subject_value_match("SIA", "Cybersecurity", d))
        self.assertFalse(_subject_value_match("SIA", "AI", d))

    def test_owned_entity_page_can_support_exact_target(self):
        d = doc(
            "https://www.mapfre.com/talento/unete-a-nuestro-equipo/",
            "Únete a nuestro equipo - MAPFRE",
            "Buscamos Especialista de ciberseguridad para nuestro equipo.",
        )
        self.assertTrue(
            _subject_value_match(
                "Mapfre",
                "Especialista de ciberseguridad",
                d,
            )
        )

    def test_third_party_page_needs_subject_and_target_context(self):
        d = doc(
            "https://example.com/partners/seyrcom",
            "Partner ecosystem",
            "Seyrcom integra SmartZone en proyectos de redes empresariales.",
        )
        self.assertTrue(_subject_value_match("Seyrcom", "SmartZone", d))


if __name__ == "__main__":
    unittest.main()
