"""Official historical link discovery favours the claim, not generic menus."""
import unittest
from scripts.revalidate_historical_sources import deep_source_links, historical_visible_text

class TargetedHistoricalLinkDiscovery(unittest.TestCase):
    def test_specific_partner_link_beats_generic_product_menu(self):
        page = """<html><body><a href="/solutions/security">Security solutions</a>
        <a href="/products">Products</a>
        <a href="/partners/cisco">Cisco partner portfolio</a></body></html>"""
        links=deep_source_links(page, "https://example.com/", limit=2,
                                claims=[{"value":"Cisco","field":"vendor_relations"}])
        self.assertEqual(links[0], "https://example.com/partners/cisco")
        self.assertEqual(len(links),2)

    def test_excludes_external_followup_pages(self):
        page = """<a href="https://other.example.com/partners/cisco">Cisco</a>
        <a href="/fabricantes/cisco">Cisco</a>"""
        links=deep_source_links(page, "https://example.com/", claims=[{"value":"Cisco"}])
        self.assertEqual(links, ["https://example.com/fabricantes/cisco"])

    def test_alt_text_keeps_official_partner_logo_label(self):
        text=historical_visible_text('<a href="/partners"><img alt="Cisco" src="/logos/cisco.svg"></a>')
        self.assertIn("cisco",text)

if __name__=="__main__":
    unittest.main()
