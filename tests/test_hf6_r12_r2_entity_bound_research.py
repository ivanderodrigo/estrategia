
from __future__ import annotations

import unittest
from types import SimpleNamespace

from engine.research.extractors import Candidate
from engine.research.web_intelligence import _focus_candidates, _seed_binding


def doc(url: str, title: str, text: str):
    return SimpleNamespace(
        url=url,
        title=title,
        text=text,
        links=(),
        content_digest="hf6-r12-r2",
    )


class HF6R12R2EntityBoundResearch(unittest.TestCase):
    def test_broad_distributor_official_does_not_bind_foreign_entity(self):
        self.assertEqual(
            _seed_binding(
                "https://www.also.com/ec/cms5/2610/es_es/cloud_marketplace/index.jsp",
                "Desyman",
                source_type="distributor-official",
                source_name="ALSO Spain Technology S.L.U.",
            ),
            "discovery-only",
        )

    def test_explicit_partner_path_remains_relationship_source(self):
        self.assertEqual(
            _seed_binding(
                "https://www.zscaler.com/partners/system-integrators",
                "SIA",
                source_type="vendor-official",
                source_name="Zscaler",
            ),
            "relationship-source",
        )

    def test_unrelated_also_services_cannot_enrich_desyman(self):
        d = doc(
            "https://www.also.com/ec/cms5/2610/es_es/cloud_marketplace/index.jsp",
            "Cloud Marketplace - ALSO Spain Technology S.L.U.",
            "ALSO ofrece servicios de soporte técnico y formación para sus partners.",
        )
        candidates = {
            "services": Candidate(
                ("Soporte", "Formación"),
                "fact",
                0.84,
                "soporte técnico y formación",
                ("soporte", "formación"),
            ),
            "differential_capabilities": Candidate(
                ("Soporte",),
                "fact",
                0.84,
                "soporte técnico",
                ("soporte",),
            ),
        }
        focused = _focus_candidates(
            candidates,
            {
                "entity": "Desyman",
                "section": "distributors",
                "fields": ["services", "differential_capabilities"],
                "target_values": {},
                "gap_kinds": [],
            },
            d,
            True,
        )
        self.assertNotIn("services", focused)
        self.assertNotIn("differential_capabilities", focused)

    def test_unrelated_arrow_capability_cannot_enrich_desyman(self):
        d = doc(
            "https://www.arrow.com/globalecs/es/",
            "Arrow Enterprise Computing Solutions",
            "Arrow provides cloud, cybersecurity, networking and support services.",
        )
        candidates = {
            "capabilities": Candidate(
                ("Cloud", "Cybersecurity"),
                "fact",
                0.84,
                "cloud cybersecurity",
                ("cloud", "cybersecurity"),
            )
        }
        focused = _focus_candidates(
            candidates,
            {
                "entity": "Desyman",
                "section": "distributors",
                "fields": ["capabilities"],
                "target_values": {},
                "gap_kinds": [],
            },
            d,
            True,
        )
        self.assertNotIn("capabilities", focused)

    def test_entity_owned_vvalley_service_survives_normalized_label(self):
        d = doc(
            "https://www.v-valley.pt/servicos/",
            "Serviços | V-Valley",
            "V-Valley Advanced Solutions Portugal oferece serviços de suporte técnico especializado.",
        )
        candidates = {
            "services": Candidate(
                ("Soporte",),
                "fact",
                0.84,
                "serviços de suporte técnico",
                ("suporte",),
            ),
            "differential_capabilities": Candidate(
                ("Soporte",),
                "fact",
                0.84,
                "serviços de suporte técnico",
                ("suporte",),
            ),
        }
        focused = _focus_candidates(
            candidates,
            {
                "entity": "V-Valley Advanced Solutions Portugal",
                "section": "distributors",
                "fields": ["services", "differential_capabilities"],
                "target_values": {},
                "gap_kinds": [],
            },
            d,
            True,
        )
        self.assertEqual(focused["services"].values, ("Soporte",))
        self.assertEqual(focused["differential_capabilities"].values, ("Soporte",))

    def test_foreign_partner_page_requires_subject_and_vendor_context(self):
        candidate = {
            "vendor_relations": Candidate(
                ("Zscaler",),
                "fact",
                0.84,
                "Zscaler",
                ("Zscaler",),
            )
        }

        unrelated = doc(
            "https://www.zscaler.com/partners/system-integrators",
            "Partner ecosystem | Zscaler",
            "Zscaler provides Zero Trust security for enterprise customers.",
        )
        focused = _focus_candidates(
            candidate,
            {
                "entity": "SIA",
                "section": "integrators",
                "fields": ["vendor_relations"],
                "target_values": {},
                "gap_kinds": [],
            },
            unrelated,
            True,
        )
        self.assertNotIn("vendor_relations", focused)

        explicit = doc(
            "https://www.zscaler.com/partners/sia",
            "SIA partner profile | Zscaler",
            "SIA is an authorized partner delivering Zscaler solutions to customers.",
        )
        focused = _focus_candidates(
            candidate,
            {
                "entity": "SIA",
                "section": "integrators",
                "fields": ["vendor_relations"],
                "target_values": {},
                "gap_kinds": [],
            },
            explicit,
            True,
        )
        self.assertEqual(focused["vendor_relations"].values, ("Zscaler",))

    def test_entity_owned_vendor_observation_remains_supported(self):
        d = doc(
            "https://www.sia.es/partners",
            "Partners | SIA",
            "Technology ecosystem: Zscaler, Palo Alto Networks and Fortinet.",
        )
        candidate = {
            "vendor_relations": Candidate(
                ("Zscaler",),
                "fact",
                0.84,
                "Zscaler",
                ("Zscaler",),
            )
        }
        focused = _focus_candidates(
            candidate,
            {
                "entity": "SIA",
                "section": "integrators",
                "fields": ["vendor_relations"],
                "target_values": {},
                "gap_kinds": [],
            },
            d,
            True,
        )
        self.assertEqual(focused["vendor_relations"].values, ("Zscaler",))

    def test_unrelated_zscaler_ai_does_not_become_sia_capability(self):
        d = doc(
            "https://www.zscaler.com/partners/technology",
            "Join the Partner Ecosystem | Zscaler",
            "Secure B2B Zero Trust. Security for AI. Adopt AI at full speed with Zscaler.",
        )
        candidates = {
            "capabilities": Candidate(
                ("AI / Data",),
                "fact",
                0.84,
                "Security for AI",
                ("AI",),
            )
        }
        focused = _focus_candidates(
            candidates,
            {
                "entity": "SIA",
                "section": "integrators",
                "fields": ["capabilities"],
                "target_values": {},
                "gap_kinds": [],
            },
            d,
            True,
        )
        self.assertNotIn("capabilities", focused)


if __name__ == "__main__":
    unittest.main()
