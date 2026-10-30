"""Offline contract tests: real model calls are intentionally mocked."""
import unittest
from unittest.mock import patch

import app as server
from research.catalog import catalog, evidence, expand_terms, normalize

PAPER = {'doi': '10.1234/test', 'title': 'Urban temperature observations in China',
         'abstract': 'We provide satellite temperature observations in China.',
         'journal': 'Scientific Data', 'publishDate': '2026-01-01', 'tags': None}


class ResearchWorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.original = server.articles_data
        server.articles_data = [dict(PAPER)]
        self.client = server.app.test_client()

    def tearDown(self):
        server.articles_data = self.original

    def test_catalog_deduplicates_and_counts_actual_coverage(self):
        result = catalog([PAPER, PAPER, {**PAPER, 'doi': '10.1234/other', 'abstract': None}])
        self.assertEqual(result['summary']['totalCount'], 2)
        self.assertEqual(result['summary']['abstractCount'], 1)
        self.assertEqual(result['summary']['translationCount'], 0)

    def test_links_are_safe_and_missing_values_are_explicit(self):
        item = normalize({**PAPER, 'url': 'javascript:alert(1)', 'abstract': None})
        self.assertEqual(item['url'], '')
        self.assertEqual(item['evidenceStatus'], 'metadata-only')
        self.assertEqual(len(item['missingChecks']), 4)

    def test_chinese_query_expands_to_english(self):
        self.assertIn('urban', expand_terms('中国城市热岛', []))
        with patch.object(server.FAISS_STORE, 'search', return_value=[]):
            found = server.retrieve_research_candidates('中国城市热岛')
        self.assertEqual(found[0]['article']['doi'], PAPER['doi'])

    def test_evidence_is_verbatim(self):
        item = evidence(PAPER, ['satellite'])
        self.assertIn(item['text'], PAPER[item['field']])

    def test_invalid_payloads_return_400(self):
        for payload in ([], 'wrong', {'message': []}, {'message': '短'}, {'message': 'a'*1001}):
            with self.subTest(payload=str(payload)[:30]):
                self.assertEqual(self.client.post('/api/research-assistant', json=payload).status_code, 400)

    def test_unavailable_models_fall_back_without_fake_ai(self):
        with patch.object(server.FAISS_STORE, 'search', side_effect=RuntimeError('unavailable')), patch.object(server, 'generate_ai_recommendation', return_value=None):
            result = self.client.post('/api/research-assistant', json={'message': '中国城市热岛'}).get_json()
        self.assertEqual(result['mode'], 'local')
        self.assertEqual(result['recommendations'][0]['doi'], PAPER['doi'])
        self.assertIn('evidence', result['recommendations'][0])

    def test_ai_cannot_insert_unknown_or_duplicate_papers(self):
        output = {'answer': 'test', 'recommendations': [None, {'id': 'fabricated'}, {'id': PAPER['doi']}, {'id': PAPER['doi']}]}
        with patch.object(server.FAISS_STORE, 'search', return_value=[]), patch.object(server, 'generate_ai_recommendation', return_value=output):
            result = self.client.post('/api/research-assistant', json={'message': 'urban temperature'}).get_json()
        self.assertEqual(result['mode'], 'ai')
        self.assertEqual(len(result['recommendations']), 1)
        self.assertEqual(result['recommendations'][0]['doi'], PAPER['doi'])

    def test_no_match_does_not_invent_recommendations(self):
        with patch.object(server.FAISS_STORE, 'search', return_value=[]):
            result = self.client.post('/api/research-assistant', json={'message': 'zzzzxyxyxy'}).get_json()
        self.assertEqual(result['recommendations'], [])

    def test_browsing_never_starts_crawler(self):
        with patch.object(server, 'update_data') as update, patch.object(server, 'get_data_status', return_value={}):
            self.assertEqual(self.client.get('/').status_code, 200)
        update.assert_not_called()

    def test_refresh_requires_operator_token(self):
        with patch.object(server, 'update_data') as update:
            self.assertEqual(self.client.post('/refresh').status_code, 403)
        update.assert_not_called()

    def test_catalog_api_works_without_homepage(self):
        result = self.client.get('/api/catalog')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.get_json()['summary']['totalCount'], 1)

    def test_catalog_page_filters_and_paginates_full_catalog(self):
        server.articles_data = [dict(PAPER, doi=f'10.1234/{i}', title=f'urban record {i}', publishDate=f'2026-01-{i:02d}') for i in range(1, 16)] + [dict(PAPER, doi='10.1234/other', title='genome', abstract='genome', publishDate='2025-01-01')]
        result = self.client.get('/api/catalog/page?q=urban&page=2&size=10').get_json()
        self.assertEqual(result['summary']['totalCount'], 16)
        self.assertEqual(result['pagination']['total'], 15)
        self.assertEqual(len(result['articles']), 5)
        self.assertEqual(result['pagination']['page'], 2)
        self.assertEqual(self.client.get('/api/catalog/page?year=2025').get_json()['pagination']['total'], 1)

    def test_catalog_lookup_returns_only_requested_articles(self):
        server.articles_data = [dict(PAPER), dict(PAPER, doi='10.1234/other')]
        result = self.client.post('/api/catalog/lookup', json={'keys': ['10.1234/other']}).get_json()
        self.assertEqual([a['doi'] for a in result['articles']], ['10.1234/other'])
        self.assertEqual(self.client.post('/api/catalog/lookup', json={'keys': ['x'] * 501}).status_code, 400)


if __name__ == '__main__':
    unittest.main()
