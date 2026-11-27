"""A URL for a product category must not resurrect it as a green vendor."""
import unittest

from scripts.audit_published_semantic_historical import historical_non_vendor_claim
from scripts.accredit_semantic_historical_sources import classify


class HistoricalVendorReclassification(unittest.TestCase):
    def test_verified_category_is_not_a_verified_manufacturer(self):
        sample = {"section": "distributors", "entity": "Globomatik",
                  "field": "vendor_relations", "value": "Placas Base Intel",
                  "source": {"url": "https://www.globomatik.com/componentes/placas-base"}}
        self.assertTrue(historical_non_vendor_claim(sample))
        self.assertTrue(historical_non_vendor_claim({**sample, "value": "Portátiles Acer"}))
        self.assertFalse(historical_non_vendor_claim({**sample, "value": "Acer"}))
        self.assertFalse(historical_non_vendor_claim({**sample, "field": "services"}))
        self.assertFalse(historical_non_vendor_claim({**sample, "section": "manufacturers"}))
        self.assertEqual(
            classify({**sample, "source_context": "Fabricantes, Placas Base Intel, accesorios"},
                     "https://www.globomatik.com/componentes/placas-base-intel"),
            "CATALOG_CATEGORY_NOT_VENDOR",
        )


if __name__ == "__main__":
    unittest.main()
