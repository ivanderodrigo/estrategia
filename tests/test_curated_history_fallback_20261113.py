import unittest
from scripts.accredit_structured_historical import apply_curated_reviews

URL = "https://www.gartner.com/reviews/product/attackiq-platform/alternatives"

class CuratedFallbackTests(unittest.TestCase):
    def test_exact_historical_claim_is_accredited_when_fetch_is_blocked(self):
        records=[{"section":"manufacturers","entity":"attackiq","field":"competitors",
                  "value":"Cymulate","source_url":URL,"status":"UNREACHABLE_OR_UNREADABLE"},
                 {"section":"manufacturers","entity":"attackiq","field":"competitors",
                  "value":"Unknown","source_url":URL,"status":"UNREACHABLE_OR_UNREADABLE"},
                 {"section":"manufacturers","entity":"efficientip","field":"competitors",
                  "value":"Cymulate","source_url":URL,"status":"UNREACHABLE_OR_UNREADABLE"}]
        curated={"existing_claim_sources":[{"section":"manufacturers","entity":"AttackIQ",
                  "field":"competitors","value":"Cymulate",
                  "source":{"url":URL,"source_type":"analyst-peer-review"}}]}
        result=apply_curated_reviews(records,curated)
        self.assertEqual(result[0]["status"],"VERIFIED_CURATED_DIRECT_SOURCE")
        self.assertEqual(result[1]["status"],"UNREACHABLE_OR_UNREADABLE")
        self.assertEqual(result[2]["status"],"UNREACHABLE_OR_UNREADABLE")

    def test_wrong_url_or_source_type_cannot_accredit(self):
        rows=[{"section":"manufacturers","entity":"attackiq","field":"competitors",
               "value":"Cymulate","source_url":URL,"status":"UNREACHABLE_OR_UNREADABLE"}]
        registry={"existing_claim_sources":[{"section":"manufacturers","entity":"AttackIQ",
                  "field":"competitors","value":"Cymulate",
                  "source":{"url":"https://unrelated.example/","source_type":"analyst-peer-review"}}]}
        self.assertEqual(apply_curated_reviews(rows,registry)[0]["status"],"UNREACHABLE_OR_UNREADABLE")

if __name__=="__main__":
    unittest.main()
