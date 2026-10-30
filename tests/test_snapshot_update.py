import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as server
from research import refresh_snapshot


class SnapshotUpdateTest(unittest.TestCase):
    def test_merge_preserves_curated_content_and_adds_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = root / 'site/public/data/articles.json'
            snapshot.parent.mkdir(parents=True)
            snapshot.write_text(json.dumps({'articles':[{'doi':'10.1/test','title':'Original','titleCn':'人工校对标题','Subject':'水文学','abstract':''}]}),encoding='utf-8')
            incoming = root / 'incoming.jsonl'
            incoming.write_text(json.dumps({'doi':'10.1/test','title':'Changed','abstract':'Source abstract'})+'\n'+json.dumps({'doi':'10.1/new','title':'New paper','publishDate':'2026-10-02'}),encoding='utf-8')
            with patch.object(refresh_snapshot, 'ROOT', root), patch('builtins.print'):
                refresh_snapshot.refresh(incoming)
            result = json.loads(snapshot.read_text(encoding='utf-8'))
            old = next(p for p in result['articles'] if p['doi']=='10.1/test')
            self.assertEqual(old['titleCn'], '人工校对标题')
            self.assertEqual(old['title'], 'Original')
            self.assertEqual(old['abstract'], 'Source abstract')
            self.assertEqual(result['summary']['newCount'],1)
            self.assertEqual(result['summary']['totalCount'],2)

    def test_explicit_snapshot_source_never_loads_stale_database(self):
        with patch.dict('os.environ',{'DATAPAPER_CATALOG_SOURCE':'snapshot'}), patch.object(server.DBHelper,'get_all_processed_papers') as read:
            self.assertFalse(server.load_from_database())
        read.assert_not_called()


if __name__ == '__main__':
    unittest.main()
