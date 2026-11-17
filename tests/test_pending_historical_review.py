import unittest

from scripts.publish_pending_historical_review import pending_index


class IndividualHistoricalReview(unittest.TestCase):
    def test_verified_one_source_does_not_accredit_a_second_link(self):
        history={"manufacturers":{"entities":{"ciena":{"competitors":[{
            "value":"Huawei",
            "urls":["https://ciena.com/compare-huawei","https://unrelated.example/a"]
        }]}}}}
        registry={"existing_claim_sources":[
            {"section":"manufacturers","entity":"Ciena","field":"competitors",
             "value":"Huawei","source":{"url":"https://ciena.com/compare-huawei"}}]}
        checks={"results":{
            "https://ciena.com/compare-huawei":{"status":"REACHABLE_TEXT_MATCH"},
            "https://unrelated.example/a":{"status":"REACHABLE_NO_EXACT_TEXT",
                "claim_checks":[{"section":"manufacturers","entity":"ciena","field":"competitors",
                                 "value":"Huawei","status":"NO_SPECIFIC_VALUE_CONFIRMED"}]}
        }}
        pending,counts=pending_index(history,registry,checks)
        self.assertEqual(counts["already_accredited_exact_url"],1)
        self.assertEqual(len(pending),1)
        self.assertEqual(pending[0]["url"],"https://unrelated.example/a")
        self.assertEqual(pending[0]["claim_status"],"NO_SPECIFIC_VALUE_CONFIRMED")

    def test_each_unaccredited_link_has_individual_status_and_order(self):
        history={"integrators":{"entities":{"partner":{"vendor_relations":[{
            "value":"Cisco","urls":["https://partner.example/","https://partner.example/vendors"]}]}}}}
        checks={"results":{
            "https://partner.example/":{"status":"INSUFFICIENT_SOURCE_CONTENT"},
            "https://partner.example/vendors":{"status":"REACHABLE_TEXT_MATCH",
                "claim_checks":[{"section":"integrators","entity":"partner",
                                 "field":"vendor_relations","value":"Cisco",
                                 "status":"VALUE_PRESENT_REQUIRES_CONTEXT"}]}}}
        pending,counts=pending_index(history,{},checks)
        self.assertEqual(len(pending),2)
        self.assertEqual(pending[0]["priority"],1)
        self.assertEqual(pending[0]["url"],"https://partner.example/vendors")
        self.assertEqual(pending[1]["priority"],4)
        self.assertEqual(counts["integrators"],2)


if __name__=="__main__":
    unittest.main()
