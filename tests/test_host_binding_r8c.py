from __future__ import annotations

import unittest

from engine.research.web_intelligence import _host_entity_owned, _seed_binding


class HostBindingR8C(unittest.TestCase):
    def test_short_entity_does_not_match_tld_substring(self):
        self.assertFalse(_host_entity_owned("https://databreachtoday.asia/", "SIA"))
        self.assertEqual(
            _seed_binding(
                "https://databreachtoday.asia/",
                "SIA",
                source_type="official-domain",
                source_name="SIA",
            ),
            "discovery-only",
        )

    def test_short_entity_matches_exact_domain_label(self):
        self.assertTrue(_host_entity_owned("https://www.sia.es/", "SIA"))

    def test_ibm_exact_short_domain_still_matches(self):
        self.assertTrue(_host_entity_owned("https://www.ibm.com/es-es", "IBM"))

    def test_normal_entity_domains_still_match(self):
        self.assertTrue(_host_entity_owned("https://www.mapfre.com/talento/", "Mapfre"))
        self.assertTrue(_host_entity_owned("https://www.inetum.com/es/es/", "Inetum Spain"))
        self.assertTrue(_host_entity_owned("https://www.integrity360.com/", "Integrity360"))

    def test_compound_domain_matches_joined_entity_name(self):
        self.assertTrue(_host_entity_owned("https://www.grupoica.com/", "Grupo ICA"))
        self.assertTrue(
            _host_entity_owned(
                "https://telefonicatech.com/",
                "Telefónica Tech",
            )
        )

    def test_joined_name_rule_does_not_reintroduce_asia_collision(self):
        self.assertFalse(_host_entity_owned("https://example.asia/", "SIA"))


if __name__ == "__main__":
    unittest.main()
