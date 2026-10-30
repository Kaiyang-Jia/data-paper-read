"""Check source identity, bounded retries, durable recovery and pipeline ordering."""
from datetime import date
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import requests
from research import abstract_backfill as module
from research import update_catalog

DOI = '10.1038/s41597-026-08429-z'
ABSTRACT = 'Measurements from a documented collection of observations support analysis across multiple scientific disciplines.'
PAPER = {'doi': DOI, 'title': 'An observational dataset', 'abstract': ''}


class AbstractBackfillTest(unittest.TestCase):
    def test_publisher_requires_matching_doi_and_explicit_abstract(self):
        head = f'<meta name="citation_doi" content="https://doi.org/{DOI}">'
        html = head + f'<div id="Abs1-content"><p>{ABSTRACT}</p><p>Second paragraph.</p></div>'
        value, _ = module.publisher_abstract(html, DOI)
        self.assertEqual(value, ABSTRACT + ' Second paragraph.')
        self.assertEqual(module.publisher_abstract(html, '10.1038/wrong')[0], '')
        seo = head + f'<meta name="description" content="{ABSTRACT}">'
        self.assertEqual(module.publisher_abstract(seo, DOI)[0], '')

    def test_europepmc_requires_exact_doi(self):
        payload = {'resultList': {'result': [
            {'doi': '10.1038/wrong', 'abstractText': ABSTRACT},
            {'doi': DOI.upper(), 'abstractText': '<p>' + ABSTRACT + '</p>', 'id': '123', 'source': 'MED'},
        ]}}
        self.assertEqual(module.europepmc_abstract(payload, DOI), (ABSTRACT, '123', 'MED'))

    def test_notices_do_not_trigger_external_requests(self):
        source = module.Sources()
        with patch.object(source, 'get') as get:
            result = source.fetch({**PAPER, 'title': 'Publisher Correction: An observational dataset'})
        self.assertEqual(result['status'], 'not-applicable')
        get.assert_not_called()

    def test_connection_retry_is_bounded_and_blocks_are_not_retried(self):
        source = module.Sources()
        response = SimpleNamespace(status_code=200)
        with patch.object(module.requests, 'get', side_effect=[requests.ConnectionError('temporary'), response]) as get, patch.object(module.time, 'sleep'):
            self.assertIs(source.get(module.publisher_url(DOI)), response)
            self.assertEqual(get.call_count, 2)
        source = module.Sources()
        with patch.object(module.requests, 'get', return_value=SimpleNamespace(status_code=429)) as get:
            self.assertEqual(source.get(module.publisher_url(DOI)).status_code, 429)
            with self.assertRaises(RuntimeError): source.get(module.publisher_url(DOI))
            self.assertEqual(get.call_count, 1)

    def test_publisher_failure_falls_back_to_exact_europepmc_record(self):
        source = module.Sources()
        payload = {'resultList': {'result': [{'doi': DOI, 'abstractText': ABSTRACT, 'id': '123', 'source': 'MED'}]}}
        response = SimpleNamespace(status_code=200, url=module.EPMC, json=lambda: payload)
        with patch.object(source, 'get', side_effect=[requests.ConnectionError('temporary'), response]):
            result = source.fetch(PAPER)
        self.assertEqual(result['abstract'], ABSTRACT)
        self.assertEqual(result['abstractSource']['provider'], 'europe-pmc')

    def test_checkpoint_reuse_preserves_existing_abstract_and_bibliography(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            snapshot, checkpoint = root / 'catalog.json', root / 'abstracts.jsonl'
            original = {'articles': [PAPER, {**PAPER, 'doi': '10.1234/existing', 'abstract': 'Original abstract'}]}
            snapshot.write_text(json.dumps(original), encoding='utf-8')
            result = module.Sources.result(DOI, ABSTRACT, 'publisher', module.publisher_url(DOI), 'fixture', '2026-10-03')
            with patch.object(module, 'ROOT', root), patch.object(module.Sources, 'fetch', return_value=result) as fetch, patch('builtins.print'):
                module.backfill(snapshot, checkpoint, publish=False)
                self.assertEqual(json.loads(snapshot.read_text()), original)
                fetch.reset_mock()
                report = module.backfill(snapshot, checkpoint)
                fetch.assert_not_called()
            papers = {p['doi']: p for p in json.loads(snapshot.read_text(encoding='utf-8'))['articles']}
            self.assertEqual(report['recovered'], 1)
            self.assertEqual(papers[DOI]['title'], PAPER['title'])
            self.assertEqual(papers[DOI]['abstract'], ABSTRACT)
            self.assertEqual(papers['10.1234/existing']['abstract'], 'Original abstract')
            self.assertTrue(list((root / 'backups').glob('before_abstracts_*.json')))

    def test_concurrent_update_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            snapshot = root / 'catalog.json'
            snapshot.write_text(json.dumps({'articles': [PAPER]}), encoding='utf-8')
            def fetch(paper):
                snapshot.write_text('{"articles":[],"changed":true}', encoding='utf-8')
                return module.Sources.result(DOI, ABSTRACT, 'publisher', module.publisher_url(DOI), 'fixture', '2026-10-03')
            with patch.object(module, 'ROOT', root), patch.object(module.Sources, 'fetch', side_effect=fetch), patch('builtins.print'):
                with self.assertRaises(RuntimeError): module.backfill(snapshot, root / 'abstracts.jsonl')
            self.assertTrue(json.loads(snapshot.read_text())['changed'])

    def test_update_backfills_before_chinese_processing_and_index_build(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            snapshot = root / 'site/public/data/articles.json'
            snapshot.parent.mkdir(parents=True)
            snapshot.write_text(json.dumps({'articles': [PAPER]}), encoding='utf-8')
            order = []
            def step(name, result=None):
                def invoke(*args, **kwargs):
                    order.append(name)
                    return result
                return invoke
            with patch.object(update_catalog, 'ROOT', root), patch.object(update_catalog, 'load_dotenv'), patch.object(update_catalog, 'set_key'), patch('builtins.print'), patch.object(update_catalog, 'CrossrefCrawler') as crawler, patch.object(update_catalog, 'refresh', side_effect=step('merge')), patch.object(update_catalog, 'backfill', side_effect=step('abstracts')), patch.object(update_catalog, 'enrich', side_effect=step('chinese', {'failed': [], 'translationCount': 1})), patch.object(update_catalog, 'LocalFaissStore') as store:
                crawler.return_value.export_jsonl.side_effect = step('acquire')
                store.return_value.build.side_effect = step('index', 1)
                update_catalog.run(date(2026, 10, 1), date(2026, 10, 3))
            self.assertEqual(order, ['acquire', 'merge', 'abstracts', 'chinese', 'index'])


if __name__ == '__main__':
    unittest.main()
