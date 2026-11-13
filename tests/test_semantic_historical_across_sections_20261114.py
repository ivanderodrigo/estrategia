"""Regression: no historical URL can credit a different entity or unrelated claim."""
import json
import unittest
from pathlib import Path
from scripts.accredit_semantic_historical_sources import classify, owner_site
from scripts.revalidate_historical_sources import historical_visible_text
from engine.model import canonical

ROOT=Path(__file__).resolve().parents[1]

def claim(section,field,entity,value,excerpt):
    return {"section":section,"field":field,"entity":entity,
            "value":value,"source_context":canonical(excerpt)}

class SemanticHistoricalTests(unittest.TestCase):
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
                         "UNSUPPORTED_FIELD_OR_CONTEXT")

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
        reg=json.loads((ROOT/"config/current/verified_historical_topic_markets_20261114.json").read_text())
        market=json.loads((ROOT/"config/current/verified_historical_market_20261114.json").read_text())
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
