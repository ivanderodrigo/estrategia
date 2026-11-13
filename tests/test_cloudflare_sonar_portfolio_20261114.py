"""Portfolio inclusion and official product evidence for Sonar and Cloudflare."""
from __future__ import annotations

import unittest
from engine.storage import read_json
from engine.westcon_current_evidence import apply_westcon_current_evidence

CONFIG="config/current/westcon_fy27_document_facts.json"

class CloudflareSonarCompletePortfolio(unittest.TestCase):
    def test_first_party_membership_and_official_technology_taxonomy(self):
        config=read_json(CONFIG,{})
        data={"manufacturers":[],"meta":{}}
        apply_westcon_current_evidence(data,config)
        rows={r["name"]:r for r in data["manufacturers"]}
        for name,url in (
            ("Sonar","https://www.sonarsource.com/products/sonarqube/"),
            ("Cloudflare","https://www.cloudflare.com/application-services/"),
        ):
            with self.subTest(name=name):
                self.assertIn(name,rows)
                fields=rows[name]["fields"]
                for k in ("westcon_spain","westcon_portugal"):
                    self.assertIs(fields[k]["value"],True)
                    ev=fields[k]["evidence"]
                    self.assertEqual(ev[0]["provenance_origin"],"WESTCON_FIRST_PARTY_CURRENT")
                    self.assertTrue(ev[0]["accrediting"])
                domain=fields["domain"]
                self.assertTrue(domain["value"])
                self.assertTrue(any(e["url"]==url and e["provenance_origin"]=="PUBLIC_PRIMARY"
                                    for e in domain["evidence"]))
                caps=fields["capabilities"]
                self.assertGreaterEqual(len(caps["value"]),7)
                self.assertEqual(len(caps["value"]),len(caps["items"]))
                for item in caps["items"]:
                    self.assertEqual(item["evidence"][0]["item_value"],item["value"])
                    self.assertEqual(item["evidence"][0]["field"],"capabilities")
                    self.assertEqual(item["evidence"][0]["url"],url)
                    self.assertEqual(item["evidence"][0]["source_binding"],"claim-specific")

    def test_superseded_portfolio_still_excludes_departed_fabricants(self):
        config=read_json(CONFIG,{})
        data={"manufacturers":[],"meta":{}}
        apply_westcon_current_evidence(data,config)
        by_name={r["name"]:r for r in data["manufacturers"]}
        for name in ("Juniper Networks","Ruckus Networks"):
            self.assertIs(by_name[name]["fields"]["westcon_spain"]["value"],False)
            self.assertIs(by_name[name]["fields"]["westcon_portugal"]["value"],False)

if __name__ == "__main__":
    unittest.main()
