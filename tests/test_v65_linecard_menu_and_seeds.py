from __future__ import annotations

import unittest
from pathlib import Path

from engine.research.documents import parse_document
from engine.research.extractors import distributor_linecard_vendors, extract_candidates
from engine.research.sources import seeds_for
from engine.research.web_intelligence import _prioritize_research_queries


ROOT = Path(__file__).resolve().parents[1]


class LinecardCoverageV65(unittest.TestCase):
    def test_ajoomal_style_first_party_navigation_is_a_distributor_catalogue(self):
        html = """<html><head><title>Ajoomal Asociados</title></head><body>
        <nav><span>Fabricantes</span>
        <a href="/bluecat/">Bluecat</a><a href="/check-point/">Check Point</a>
        <a href="/kaseya/">Kaseya</a><a href="/portnox/">Portnox</a>
        <a href="/netwrix/">Netwrix</a>
        <a href="/opswat/">Opswat</a>
        <span>Soluciones &amp; Servicios</span>
        <a href="/backup/">Back Up</a><a href="/noticias/">Noticias</a></nav>
        <p>Somos un mayorista especializado.</p></body></html>"""
        doc = parse_document(html, "https://www.ajoomal.com/", "v65-test")
        known, terms = distributor_linecard_vendors(doc, [])
        self.assertEqual(
            set(known),
            {"Bluecat", "Check Point", "Kaseya", "Portnox", "Netwrix", "Opswat"},
        )
        self.assertNotIn("Back Up", known)
        self.assertNotIn("Noticias", known)
        candidates = extract_candidates(
            "distributors", "official", doc, [], official=True,
            researched_entity="Ajoomal",
        )
        self.assertEqual(set(candidates["vendor_relations"].values), set(known))

    def test_generic_news_or_unrelated_navigation_does_not_create_linecard(self):
        doc = parse_document(
            """<html><title>Noticias</title><body>Fabricantes de referencia.
               <a href="/articulo/">Cisco</a><a href="/blog/">Check Point</a>
               <a href="/contacto/">Contacto</a></body></html>""",
            "https://www.example.com/noticias", "v65-test",
        )
        self.assertEqual(distributor_linecard_vendors(doc, []), ([], []))

    def test_locale_vendor_catalogue_extracts_new_logo_brands(self):
        doc = parse_document(
            """<html><title>Fabricantes en España</title><body>
            <img alt="NicheFab Technologies logo"><img alt="Cloud">
            </body></html>""",
            "https://www.infinigate.com/es/vendors/", "v65-test",
        )
        names, _ = distributor_linecard_vendors(doc, [])
        self.assertIn("NicheFab Technologies", names)
        self.assertNotIn("Cloud", names)

    def test_cold_start_distributor_sources_are_leads_not_facts(self):
        ajoomal = seeds_for(
            {"name": "Ajoomal", "fields": {}}, ["vendor_relations"],
            target={"section": "distributors"},
        )
        self.assertTrue(any(s.url == "https://www.ajoomal.com/" and s.official for s in ajoomal))
        self.assertTrue(all(s.family in {"partners", "official"} for s in ajoomal))
        infin = seeds_for(
            {"name": "Infinigate", "fields": {}}, ["vendor_relations"],
            target={"section": "distributors"},
        )
        self.assertTrue(any(s.url == "https://www.infinigate.com/es/vendors/" for s in infin))
        self.assertEqual(seeds_for(
            {"name": "Unknown Distributor", "fields": {}}, ["vendor_relations"],
            target={"section": "distributors"},
        ), [])

    def test_daily_budget_prioritizes_explicit_site_and_linecard(self):
        planned = [
            'site:ajoomal.com fabricantes marcas vendors linecard',
            '"Ajoomal" "line card" "vendors" partner',
            '"Ajoomal" generic article',
        ]
        chosen = _prioritize_research_queries(
            ['"Ajoomal" "legacy unverified"'], planned, 2,
            section="distributors",
        )
        self.assertEqual(len(chosen), 2)
        self.assertIn("site:ajoomal.com", chosen[0])
        self.assertTrue(any("line card" in q or "linecard" in q for q in chosen))

    def test_audit_table_has_accessible_contrast(self):
        css = (ROOT / "assets/app/command-center.css").read_text(encoding="utf-8")
        self.assertIn("#commandCenter .cc-audit-table tbody th{background:#f3f8fa!important;color:#123e51!important", css)
        self.assertIn("position:static!important", css)


if __name__ == "__main__":
    unittest.main()
