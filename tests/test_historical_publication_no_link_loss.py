"""Regression: historical trail publication must not silently cap links or facts."""
from __future__ import annotations
import json
import unittest
from unittest.mock import patch
from engine.historical_publication import publish_historical_trails


class HistoricalLinkRetention(unittest.TestCase):
    def test_every_claim_and_its_original_source_urls_survive_projection(self):
        values=[f"Vendor {i}" for i in range(32)]
        urls=[f"https://example.org/partners/{i}" for i in range(9)]
        history={"historical_samples":[
            {"value":json.dumps(v,ensure_ascii=False,sort_keys=True),
             "source_urls":urls,"first_revision":"old123"} for v in values
        ]}
        gaps={"gaps":[{"section":"integrators","entity":"Example Partner",
                        "field":"vendor_relations","target_values":values}]}
        with patch("engine.historical_publication.history_by_gap",return_value={}), \
             patch("engine.historical_publication.history_by_identity",return_value={}), \
             patch("engine.historical_publication.historical_record_for_gap",return_value=history):
            output,summary=publish_historical_trails(gaps,"2026-11-17T00:00:00Z")
        published=json.loads(output["data/public/historical/current/integrators.json"])
        claims=published["entities"]["example partner"]["vendor_relations"]
        self.assertEqual(len(claims),32)
        self.assertEqual(len(claims[0]["urls"]),9)
        self.assertEqual(set(claims[-1]["urls"]),set(urls))
        self.assertEqual(summary["claims"],32)
        self.assertEqual(summary["unique_urls"],9)

    def test_rebuild_keeps_previous_exact_claim_original_links(self):
        v="Cisco"
        history={"historical_samples":[{"value":json.dumps(v),
            "source_urls":["https://example.org/partners/current"]}]}
        earlier={"entities":{"example partner":{"vendor_relations":[{
            "value":"Cisco","urls":["https://example.org/partners/archived",
                                    "https://example.org/partners/current"]}]}}}
        gaps={"gaps":[{"section":"integrators","entity":"Example Partner",
                        "field":"vendor_relations","target_values":[v]}]}
        def previous(file, default=None):
            return earlier if file.endswith("/integrators.json") else (default or {})
        with patch("engine.historical_publication.history_by_gap",return_value={}), \
             patch("engine.historical_publication.history_by_identity",return_value={}), \
             patch("engine.historical_publication.historical_record_for_gap",return_value=history), \
             patch("engine.historical_publication.read_json",side_effect=previous):
            output,_=publish_historical_trails(gaps,"2026-11-17T00:00:00Z")
        current=json.loads(output["data/public/historical/current/integrators.json"])
        links=current["entities"]["example partner"]["vendor_relations"][0]["urls"]
        self.assertEqual(links,["https://example.org/partners/current",
                                "https://example.org/partners/archived"])

    def test_archive_index_disappearing_does_not_remove_still_pending_link(self):
        old={"entities":{"example partner":{"vendor_relations":[{
            "value":"Cisco","urls":["https://example.org/partners/cisco"]}]}}}
        gaps={"gaps":[{"section":"integrators","entity":"Example Partner",
                        "field":"vendor_relations","target_values":["Cisco"]}]}
        def prior(file,default=None):
            return old if file.endswith("/integrators.json") else {}
        with patch("engine.historical_publication.history_by_gap",return_value={}), \
             patch("engine.historical_publication.history_by_identity",return_value={}), \
             patch("engine.historical_publication.historical_record_for_gap",return_value=None), \
             patch("engine.historical_publication.read_json",side_effect=prior):
            files,summary=publish_historical_trails(gaps,"2026-11-17T00:00:00Z")
        current=json.loads(files["data/public/historical/current/integrators.json"])
        self.assertEqual(current["entities"]["example partner"]["vendor_relations"][0]["urls"],
                         ["https://example.org/partners/cisco"])
        self.assertEqual(summary["claims"],1)

    def test_other_vendor_source_is_quarantined_not_misattributed(self):
        vals=["Cloud security"]
        history={"historical_samples":[{"value":json.dumps(vals[0]),
            "source_urls":["https://www.cloudflare.com/products/",
                           "https://www.fortinet.com/products/"]}]}
        gaps={"gaps":[{"section":"manufacturers","entity":"Cloudflare",
                        "field":"capabilities","target_values":vals}]}
        with patch("engine.historical_publication.history_by_gap",return_value={}), \
             patch("engine.historical_publication.history_by_identity",return_value={}), \
             patch("engine.historical_publication.historical_record_for_gap",return_value=history):
            output,summary=publish_historical_trails(gaps,"2026-11-17T00:00:00Z")
        data=json.loads(output["data/public/historical/current/manufacturers.json"])
        self.assertEqual(data["entities"]["cloudflare"]["capabilities"][0]["urls"],
                         ["https://www.cloudflare.com/products/"])
        self.assertEqual(summary["quarantined_source_links"],1)


if __name__=="__main__":
    unittest.main()
