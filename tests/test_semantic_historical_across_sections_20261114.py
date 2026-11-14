"""Regression: no historical URL can credit a different entity or unrelated claim."""
import json
import unittest
from pathlib import Path
from scripts.accredit_semantic_historical_sources import classify, owner_site, retained_comparison_is_still_explicit
from scripts.revalidate_historical_sources import historical_visible_text
from engine.model import canonical

ROOT=Path(__file__).resolve().parents[1]

def claim(section,field,entity,value,excerpt):
    return {"section":section,"field":field,"entity":entity,
            "value":value,"source_context":canonical(excerpt)}

class SemanticHistoricalTests(unittest.TestCase):
    def test_generic_atos_homepage_does_not_prove_logistics_service(self):
        ev=claim("integrators","services","Atos Spain","Logística",
                 "Atos Spain servicios de tecnologia logistica sector industrial")
        self.assertEqual(classify(
            ev, "https://www.atos.ai/es-es?utm_medium=301&utm_source=atos.net"),
            "GENERIC_HOMEPAGE_NOT_SERVICE_PROOF")

    def test_first_party_integrator_partner(self):
        ev=claim("integrators","vendor_relations","Nunsys","Avaya",
                 "Nunsys partners tecnologicos comunicaciones Avaya call center")
        self.assertEqual(classify(ev,"https://www.nunsys.com/personas/nosotros/partners/"),
                         "VERIFIED_EXPLICIT_PARTNER_CONTEXT")

    def test_cross_distributor_url_does_not_certify_distributor_services(self):
        ev=claim("distributors","services","Visiotech Security","Cloud Marketplace",
                 "ALSO Cloud Marketplace cloud subscription service")
        self.assertEqual(classify(ev,"https://www.also.com/ec/services/cloud-marketplace/"),
                         "NOT_FIRST_PARTY")

    def test_owner_client_specific_security_fact(self):
        ev=claim("clients_private","technology_signals","Aena",
                 "SGSI certificado ISO IEC 27001",
                 "Aena cuenta con un SGSI certificado ISO IEC 27001 y seguridad de la informacion")
        self.assertEqual(classify(ev,"https://www.aena.es/es/corporativa/seguridad-de-la-informacion.html"),
                         "VERIFIED_FIRST_PARTY_TECH_STATEMENT")

    def test_weak_client_domain_does_not_auto_promote(self):
        ev=claim("clients_private","technology_domains","Aena","Identity & Access",
                 "Aena participa en Identity & Access")
        self.assertEqual(classify(ev,"https://www.aena.es/es/pasajeros/pasajeros.html"),
                         "GENERIC_DOMAIN_OR_HIRING_NOT_SPECIFIC")

    def test_manufacturer_unsupported_generic_hypothesis(self):
        ev=claim("manufacturers","capabilities","AttackIQ","Señal derivada · posible BAS",
                 "AttackIQ possible BAS")
        self.assertEqual(classify(ev,"https://www.attackiq.com/"),"HYPOTHESIS_NOT_FACT")

    def test_report_titles_are_not_tech_relationships(self):
        ev=claim("architectures","vendors","Zero Trust","Okta",
                 "NIST Zero Trust Okta")
        self.assertEqual(classify(ev,"https://csrc.nist.gov/publications/detail/sp/800-207/final"),
                         "AMBIGUOUS_SHORT_VALUE")

    def test_official_vendor_comparison_is_explicit_competitive_proof(self):
        ev=claim("manufacturers","competitors","Ciena","Huawei",
                 "Ciena vs Huawei: compare optical network solutions")
        self.assertEqual(classify(ev,"https://www.ciena.com/compare/huawei"),
                         "VERIFIED_EXPLICIT_COMPETITOR_CONTEXT")

    def test_stale_comparison_accreditation_cannot_survive_reuse(self):
        source={"source_type":"historical-verified-excerpt",
                "verification_method":"VERIFIED_EXPLICIT_COMPETITOR_CONTEXT",
                "url":"https://1password.com/compare/1password-vs-lastpass",
                "description":"Extracto de evidencia: 1Password vs LastPass. Related vendors include Bitwarden."}
        invalid={"section":"manufacturers","field":"competitors",
                 "entity":"1Password","value":"Bitwarden","source":source}
        valid={**invalid,"value":"LastPass"}
        self.assertFalse(retained_comparison_is_still_explicit(invalid))
        self.assertTrue(retained_comparison_is_still_explicit(valid))

    def test_comparison_page_only_proves_the_named_pair(self):
        url="https://1password.com/compare/1password-vs-lastpass"
        excerpt="1Password vs LastPass password manager comparison. Related comparisons: Bitwarden, Keeper."
        yes=claim("manufacturers","competitors","1Password","LastPass",excerpt)
        no=claim("manufacturers","competitors","1Password","Bitwarden",excerpt)
        self.assertEqual(classify(yes,url),"VERIFIED_EXPLICIT_COMPETITOR_CONTEXT")
        self.assertEqual(classify(no,url),"COMPARISON_PAGE_DOES_NOT_NAME_PAIR")

    def test_vendor_mention_without_comparison_remains_uncredited(self):
        ev=claim("manufacturers","competitors","Ciena","Huawei",
                 "Ciena and Huawei participate at an industry event")
        self.assertEqual(classify(ev,"https://www.ciena.com/news/events"),
                         "COMPETITION_NOT_SHOWN")

    def test_third_party_comparison_without_first_party_support_not_auto_accredited(self):
        ev=claim("manufacturers","competitors","Ciena","Huawei",
                 "Ciena vs Huawei: compare optical solutions")
        self.assertEqual(classify(ev,"https://example.org/compare/vendors"),
                         "COMPETITION_NOT_SHOWN")

    def test_official_open_graph_description_is_available_for_verification(self):
        html = ('<html><head><meta property="og:title" '
                'content="Nunsys: partners tecnológicos">'
                '<meta property="og:description" '
                'content="Nunsys y Avaya, alianza de comunicaciones">'
                '<meta property="og:image" content="irrelevant-cover">'
                '</head><body></body></html>')
        excerpt = historical_visible_text(html)
        self.assertIn("nunsys y avaya alianza de comunicaciones", excerpt)
        self.assertNotIn("irrelevant cover", excerpt)
        ev=claim("integrators", "vendor_relations", "Nunsys", "Avaya",excerpt)
        self.assertEqual(classify(ev,"https://www.nunsys.com/partners/"),
                         "VERIFIED_EXPLICIT_PARTNER_CONTEXT")

    def test_partner_logo_alt_is_visible_for_original_source_audit(self):
        html=('''<html><body><h1>Partners tecnológicos</h1><section>'''
              '''<img src="/logos/avaya.svg" alt="Avaya">'''
              '''<img src="/logos/extreme.svg" aria-label="Extreme Networks">'''
              '''<script>ignore bogus fake competitor</script></section></body></html>''')
        txt=historical_visible_text(html)
        self.assertIn("avaya",txt)
        self.assertIn("extreme networks",txt)
        self.assertNotIn("bogus fake competitor",txt)

    def test_topic_roster_items_have_exact_market_document(self):
        reg=json.loads((ROOT/"config/current/verified_historical_topic_markets_20261114.json").read_text(encoding="utf-8"))
        market=json.loads((ROOT/"config/current/verified_historical_market_20261114.json").read_text(encoding="utf-8"))
        rosters=market["market_rosters"]
        self.assertEqual(len(reg["existing_claim_sources"]),48)
        allowed=reg["eligible_market_ids"]
        for entry in reg["existing_claim_sources"]:
            with self.subTest(section=entry["section"],entity=entry["entity"],value=entry["value"]):
                doc=entry["source"]["url"].split("/")[-1]
                self.assertIn(doc,allowed[entry["section"]][entry["entity"]])
                self.assertIn(doc,rosters)
                self.assertTrue(entry["source"]["topic_market_match"])
                self.assertEqual(entry["source"]["verification_method"],"same-market-explicit-vendor-list")

if __name__=="__main__":
    unittest.main()
