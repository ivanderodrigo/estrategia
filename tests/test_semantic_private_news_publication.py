import unittest
from unittest.mock import patch

from engine.verified_research import apply_verified_research


class HistoricalPrivateNewsPublication(unittest.TestCase):
    def test_exact_official_private_client_news_reaches_public_model(self):
        title = "Altri inaugura un centro"
        url = "https://altri.pt/es/noticias/centro"
        source = {
            "url": url,
            "source_type": "historical-verified-excerpt",
            "verification_method": "VERIFIED_FIRST_PARTY_NEWS_STATEMENT",
            "description": "Extracto de evidencia: Altri inaugura un centro",
            "provenance_origin": "PUBLIC_PRIMARY",
            "source_binding": "claim-specific",
        }
        registry = {
            "existing_claim_sources": [{
                "section": "clients_private", "entity": "Altri",
                "field": "recent_signals", "value": title, "source": source,
            }]
        }
        data = {"clients_private": [{
            "name": "Altri",
            "fields": {"recent_signals": {
                "value": [title], "items": [{"value": title, "evidence": []}],
                "evidence": [],
            }},
        }]}
        with patch("engine.verified_research.read_json",
                   side_effect=lambda path, default=None: registry if path.endswith(
                       "historical_semantic_verified.json") else {}):
            stats = apply_verified_research(data)
        self.assertEqual(stats["existing_claims_accredited"], 1)
        evidence = data["clients_private"][0]["fields"]["recent_signals"]["items"][0]["evidence"]
        self.assertTrue(any(e.get("url") == url and e.get("item_value") == title
                            and e.get("atomic") is True for e in evidence))


if __name__ == "__main__":
    unittest.main()
