from __future__ import annotations

import unittest
from types import SimpleNamespace

from engine.research.web_intelligence import _subject_value_match


def doc(url: str, title: str, text: str):
    return SimpleNamespace(url=url, title=title, text=text)


class SemanticAttributionR8(unittest.TestCase):
    def test_integrity360_generic_audience_mention_is_rejected(self):
        d = doc(
            "https://www.integrity360.com/partners",
            "Partners | Integrity360",
            (
                "Do you know what your company's network vulnerabilities are? "
                "If your business handles credit card data, PCI DSS compliance "
                "is critical. From retailers and e-commerce platforms to service "
                "providers and financial institutions, securing credit card data "
                "is critical."
            ),
        )
        self.assertFalse(
            _subject_value_match(
                "Integrity360", "Service provider", d, field_id="capabilities"
            )
        )

    def test_inetum_enterprise_platforms_is_supported(self):
        d = doc(
            "https://www.inetum.com/es/es/services.html",
            "Servicios | Inetum",
            (
                "En Inetum, ofrecemos servicios que cubren todas tus necesidades: "
                "desde cloud y ciberseguridad hasta plataformas empresariales, "
                "puesto de trabajo digital e IA."
            ),
        )
        self.assertTrue(
            _subject_value_match(
                "Inetum Spain",
                "Plataformas empresariales",
                d,
                field_id="capabilities",
            )
        )

    def test_inetum_digital_workplace_service_list_is_supported(self):
        d = doc(
            "https://www.inetum.com/es/es/services.html",
            "Servicios | Inetum",
            (
                "Servicios Application Services Cloud Services Cybersecurity "
                "Data & AI Digital & Enterprise Transformation Digital Workplace "
                "Enterprise Platforms Infrastructure Services."
            ),
        )
        self.assertTrue(
            _subject_value_match(
                "Inetum Spain", "Digital Workplace", d, field_id="services"
            )
        )

    def test_inetum_sector_taxonomy_is_supported(self):
        d = doc(
            "https://www.inetum.com/es/es/services.html",
            "Servicios | Inetum",
            (
                "Sectores Aeroespacio y Defensa Energía y Utilities "
                "Servicios Financieros Salud Hospitality & Travel Seguros "
                "Manufacturing Sector Público Retail y CPG "
                "Transporte y Logística."
            ),
        )
        for value in (
            "Aeroespacio y defensa",
            "Servicios financieros",
            "Salud",
            "Sector público",
            "Transporte y logística",
        ):
            with self.subTest(value=value):
                self.assertTrue(
                    _subject_value_match(
                        "Inetum Spain", value, d, field_id="verticals"
                    )
                )

    def test_self_identification_can_support_service_provider(self):
        d = doc(
            "https://examplemssp.com/about",
            "About Example MSSP",
            (
                "Example MSSP is a managed security service provider delivering "
                "managed detection and response services."
            ),
        )
        self.assertTrue(
            _subject_value_match(
                "Example MSSP", "Service provider", d, field_id="capabilities"
            )
        )

    def test_third_party_explicit_partner_attribution_still_works(self):
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
                "Seyrcom", "SmartZone", d, field_id="capabilities"
            )
        )


if __name__ == "__main__":
    unittest.main()
