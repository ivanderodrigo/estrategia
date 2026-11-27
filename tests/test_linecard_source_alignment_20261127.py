"""An official source lead must actually attach to a researched entity."""
import unittest

from engine.model import canonical
from engine.research.sources import seeds_for
from engine.storage import read_json


class LinecardSourceAlignment(unittest.TestCase):
    def test_every_official_linecard_url_reaches_an_actual_distributor(self):
        data = read_json("data/current/intelligence.json", {})
        names = {canonical(row["name"]) for row in data.get("distributors") or []}
        reg = read_json("config/current/linecard_source_leads.json", {})
        entries = reg.get("entries") or []
        self.assertGreaterEqual(len(entries), 20)
        unmatched = [(x.get("name"), x.get("url")) for x in entries
                     if canonical(x.get("name")) not in names]
        self.assertEqual(unmatched, [])
        self.assertTrue(all(str(x.get("url") or "").startswith("https://") for x in entries))

    def test_esprinet_and_arrow_direct_sources_are_routed(self):
        cases = {
            "Esprinet / V-Valley": "https://www.v-valley.com/es/vendor/ruckus/",
            "Arrow ECS": "https://www.arrow.com/globalecs/es/productos/f5-networks/",
        }
        for name, url in cases.items():
            with self.subTest(entity=name):
                seeds = seeds_for({"name": name, "fields": {}}, ["vendor_relations"],
                                  target={"section": "distributors"})
                self.assertIn(url, [seed.url for seed in seeds])


if __name__ == "__main__":
    unittest.main()
