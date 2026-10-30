"""Mock provider calls; test evidence boundaries, interrupted writes and safe publication."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from research import enrich_catalog as pipeline

PAPER = {'doi': '10.1234/test', 'title': 'Patient observations', 'abstract': 'Observations from 20 patients.'}
CARD = {'titleCn': '患者观测数据', 'interpretationCn': '该研究提供患者观测数据，具体采集方法仍需核对原文说明。', 'tags': ['患者数据'], 'Subject': '医学与健康'}


def response(paper):
    return {**pipeline.validate_card(CARD, paper), 'chineseProcessing': {'inputHash': pipeline.fingerprint(paper), 'model': 'test-model', 'revision': pipeline.REVISION, 'generatedAt': '2026-10-03', 'status': 'generated-unreviewed', 'basis': 'abstract' if paper.get('abstract') else 'title'}}


class ChinesePipelineTest(unittest.TestCase):
    def test_title_only_card_never_uses_speculative_summary(self):
        result = pipeline.validate_card({**CARD, 'interpretationCn': '包含一万名患者，拥有开放许可，可以用于因果推断。'}, {**PAPER, 'abstract': ''})
        self.assertNotIn('一万', result['interpretationCn'])
        self.assertNotIn('开放许可', result['interpretationCn'])
        self.assertIn('仅依据标题', result['interpretationCn'])

    def test_invalid_output_cannot_be_published_as_chinese(self):
        for card in ({**CARD, 'titleCn': 'English title'}, {**CARD, 'tags': '标签'}, {**CARD, 'Subject': 'made-up'}):
            with self.assertRaises(ValueError): pipeline.validate_card(card, PAPER)

    def test_checkpoint_survives_failure_and_resumes_only_remaining_papers(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            snapshot = root / 'catalog.json'
            checkpoint = root / 'cards.jsonl'
            papers = [PAPER, {**PAPER, 'doi': '10.1234/second'}]
            original = json.dumps({'articles': papers})
            snapshot.write_text(original, encoding='utf-8')
            def first_run(paper, model):
                if paper['doi'].endswith('second'): raise RuntimeError('temporary provider failure')
                return response(paper)
            with patch.object(pipeline, 'ROOT', root), patch.dict('os.environ', {'DEEPSEEK_API_KEY': 'fixture', 'DEEPSEEK_MODEL': 'test-model'}), patch.object(pipeline, 'generate_card', side_effect=first_run), patch('builtins.print'):
                result = pipeline.enrich(snapshot, checkpoint, workers=1)
                self.assertEqual(len(result['failed']), 1)
                self.assertEqual(snapshot.read_text(encoding='utf-8'), original)
                # A partial final JSONL record must not destroy earlier successful work.
                with checkpoint.open('a', encoding='utf-8') as out: out.write('{interrupted}\n')
                with patch.object(pipeline, 'generate_card', side_effect=lambda p, m: response(p)) as generate:
                    result = pipeline.enrich(snapshot, checkpoint, workers=1)
                self.assertEqual(generate.call_count, 1)
            data = json.loads(snapshot.read_text(encoding='utf-8'))
            self.assertEqual(result['translationCount'], 2)
            self.assertEqual(data['articles'][0]['abstract'], PAPER['abstract'])
            self.assertNotIn('dataProfile', data['articles'][0])
            self.assertTrue(list((root / 'backups').glob('before_chinese_*.json')))

    def test_concurrent_catalog_change_does_not_get_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            snapshot = root / 'catalog.json'
            snapshot.write_text(json.dumps({'articles': [PAPER]}), encoding='utf-8')
            def generate(paper, model):
                snapshot.write_text('{"articles": [], "changed": true}', encoding='utf-8')
                return response(paper)
            with patch.object(pipeline, 'ROOT', root), patch.dict('os.environ', {'DEEPSEEK_API_KEY': 'fixture', 'DEEPSEEK_MODEL': 'test-model'}), patch.object(pipeline, 'generate_card', side_effect=generate), patch('builtins.print'):
                with self.assertRaises(RuntimeError): pipeline.enrich(snapshot, root / 'cards.jsonl')
            self.assertTrue(json.loads(snapshot.read_text(encoding='utf-8'))['changed'])

    def test_changed_abstract_invalidates_cached_card(self):
        self.assertNotEqual(pipeline.fingerprint(PAPER), pipeline.fingerprint({**PAPER, 'abstract': 'Updated source.'}))
