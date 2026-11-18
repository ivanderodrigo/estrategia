import unittest

from engine.research.documents import parse_document
from engine.research.web_intelligence import _document_from_cache


class NewsPublicationDateTests(unittest.TestCase):
    def test_open_graph_article_date(self):
        doc = parse_document('<html><head><meta property="article:published_time" content="2026-11-12T10:30:00+01:00"></head></html>', 'https://example.org/news/article', 'a')
        self.assertEqual(doc.published_at, '2026-11-12')

    def test_jsonld_date(self):
        doc = parse_document('<script type="application/ld+json">{"@type":"NewsArticle","datePublished":"2025-05-09T08:00:00Z"}</script>', 'https://example.org/news/article', 'b')
        self.assertEqual(doc.published_at, '2025-05-09')

    def test_modified_and_retrieved_are_not_publication(self):
        doc = parse_document('<meta property="article:modified_time" content="2026-11-14"><meta name="date" content="2026-11-15">', 'https://example.org/news/article', 'c')
        self.assertEqual(doc.published_at, '')

    def test_invalid_date_is_not_invented(self):
        doc = parse_document('<meta property="article:published_time" content="2026-02-31">', 'https://example.org/news/article', 'd')
        self.assertEqual(doc.published_at, '')

    def test_cached_publication_date_survives(self):
        doc = _document_from_cache({'url':'https://example.org/article', 'published_at':'2025-01-20'})
        self.assertEqual(doc.published_at, '2025-01-20')


if __name__ == '__main__':
    unittest.main()
