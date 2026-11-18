import unittest
from unittest.mock import Mock, patch

from scripts.backfill_news_publication_dates import retrieve, visible_publication_date


class NewsDateBackfillReviewTests(unittest.TestCase):
    def test_published_byline_in_spanish(self):
        self.assertEqual(visible_publication_date('', 'Publicado el 12 de noviembre de 2026 · Noticias'), '2026-11-12')

    def test_english_press_dateline(self):
        self.assertEqual(visible_publication_date('', 'LONDON, UK – 21 May, 2026 – Westcon announced the launch.'), '2026-05-21')

    def test_rejects_unlabelled_event_date(self):
        self.assertEqual(visible_publication_date('', 'Our annual conference was held on 21 May, 2026.'), '')

    def test_rejects_conflicting_publication_dates(self):
        raw = '<time class="published" datetime="2026-05-21"></time><time class="published" datetime="2026-05-22"></time>'
        self.assertEqual(visible_publication_date(raw, ''), '')

    @patch('engine.research.security.validate_public_url', side_effect=lambda url: url)
    @patch('scripts.backfill_news_publication_dates.requests.get')
    def test_one_safe_redirect_and_explain_result(self, get, _validate):
        redirect = Mock(status_code=301, headers={'location': '/news/story'})
        published = Mock(status_code=200, url='https://example.com/news/story', headers={'content-type': 'text/html'}, text='<meta property="article:published_time" content="2026-11-09">', content=b'<meta property="article:published_time" content="2026-11-09">')
        published.raise_for_status.return_value = None
        get.side_effect = [redirect, published]
        url, evidence, status = retrieve('https://example.com/news/old-story')
        self.assertEqual(status, 'VERIFIED')
        self.assertEqual(evidence['published_at'], '2026-11-09')
        self.assertEqual(get.call_count, 2)


if __name__ == '__main__':
    unittest.main()
