import unittest
from engine.verified_research import apply_verified_research
from engine.model import canonical

class HistoricalCompetitorRecovery(unittest.TestCase):
    def test_only_curated_gartner_competitor_can_be_recovered(self):
        data={"manufacturers":[{"name":"AttackIQ","fields":{"competitors":{
            "value":["Unrelated Vendor"],
            "items":[{"value":"Unrelated Vendor","evidence":[]}]}}}]}
        apply_verified_research(data)
        field=data["manufacturers"][0]["fields"]["competitors"]
        values={canonical(v) for v in field["value"]}
        self.assertIn("cymulate",values)
        indexed={canonical(item.get("value")):item for item in field.get("items") or []}
        self.assertTrue(indexed["cymulate"].get("evidence"))
        self.assertFalse(indexed["unrelated vendor"].get("evidence"))
if __name__=="__main__":
    unittest.main()
