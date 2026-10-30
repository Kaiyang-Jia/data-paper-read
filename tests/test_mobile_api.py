"""Mobile discovery must stay read-only and work without session or models."""
import unittest
from unittest.mock import patch
from flask import Flask
from research.catalog import catalog
from research.mobile import register_mobile_api


class MobileAPITest(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        papers = [dict(title=f'Urban observations {i}', doi=f'10.1234/test/{i}',
                       titleCn=f'城市观测{i}', publishDate=f'2026-09-{i % 28 + 1:02d}',
                       abstract='Satellite measurements.', chineseProcessing={'basis': 'abstract'})
                  for i in range(35)]
        self.catalog = catalog(papers + [papers[0]])
        register_mobile_api(app, lambda: self.catalog)
        self.client = app.test_client()

    def test_daily_is_small_stable_and_uses_shared_chinese_cards(self):
        with patch('research.mobile.mobile_date', return_value='2026-10-03'):
            first = self.client.get('/api/miniprogram/feed').get_json()
            second = self.client.get('/api/miniprogram/feed').get_json()
        self.assertEqual(first, second)
        self.assertEqual(len(first['articles']), 6)
        self.assertEqual(first['summary']['totalCount'], 35)
        self.assertTrue(first['articles'][0]['titleCn'])
        with patch('research.mobile.mobile_date', return_value='2026-10-04'):
            other = self.client.get('/api/miniprogram/feed').get_json()
        self.assertNotEqual(first['articles'], other['articles'])

    def test_search_paginates_and_does_not_duplicate_records(self):
        first = self.client.get('/api/miniprogram/feed?mode=search&q=城市&page=1').get_json()
        second = self.client.get('/api/miniprogram/feed?mode=search&q=城市&page=2').get_json()
        self.assertEqual(first['total'], 35)
        self.assertEqual(len(first['articles']), 12)
        self.assertTrue(first['hasMore'])
        self.assertFalse({a['id'] for a in first['articles']} & {a['id'] for a in second['articles']})
        empty = self.client.get('/api/miniprogram/feed?mode=search&q=zzxy').get_json()
        self.assertEqual(empty['articles'], [])

    def test_cold_share_detail_and_validation(self):
        result = self.client.get('/api/miniprogram/article', query_string={'id': '10.1234/test/0'})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.get_json()['article']['titleCn'], '城市观测0')
        self.assertEqual(self.client.get('/api/miniprogram/article?id=missing').status_code, 404)
        for path in ('/api/miniprogram/article', '/api/miniprogram/feed?page=x', '/api/miniprogram/feed?mode=invalid'):
            self.assertEqual(self.client.get(path).status_code, 400)
        self.assertEqual(self.client.get('/api/miniprogram/updates').status_code, 200)


if __name__ == '__main__':
    unittest.main()
