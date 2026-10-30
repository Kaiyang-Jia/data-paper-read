import tempfile
import unittest
from unittest.mock import patch

from get_data.faiss_store import LocalFaissStore, article_embedding_text, article_key


PAPERS = [
    {
        "doi": "10.1234/ABC",
        "title": "Global climate observations",
        "titleCn": "全球气候观测",
        "abstract": "Temperature and precipitation measurements.",
        "Subject": "Climate Science",
        "tags": ["climate", "temperature"],
    },
    {
        "doi": "10.1234/xyz",
        "title": "Human genome dataset",
        "titleCn": "人类基因组数据集",
        "abstract": "A population genomics resource.",
        "Subject": "Genetics",
        "tags": ["genome"],
    },
]


class LocalFaissStoreTest(unittest.TestCase):
    def test_incremental_reuses_unchanged_and_reembeds_changed_records(self):
        with tempfile.TemporaryDirectory() as directory:
            old = LocalFaissStore(f'{directory}/old')
            with patch.object(old, 'embed', return_value=[[1., 0.], [0., 1.]]):
                old.build(PAPERS)
            new = LocalFaissStore(f'{directory}/new')
            updated = [PAPERS[0], {**PAPERS[1], 'abstract': 'Changed abstract'}]
            with patch.object(new, 'embed', return_value=[[0., 1.]]) as embed:
                self.assertEqual(new.build_incremental(updated, old), (2, 1))
                self.assertEqual(len(embed.call_args.args[0]), 1)
            with patch.object(new, 'embed', return_value=[[1., 0.]]):
                self.assertEqual(new.search('climate', updated, 1)[0]['article']['doi'], PAPERS[0]['doi'])

    def test_article_key_normalizes_doi(self):
        self.assertEqual(article_key(PAPERS[0]), "doi:10.1234/abc")

    def test_embedding_text_contains_searchable_fields(self):
        text = article_embedding_text(PAPERS[0])
        self.assertIn("全球气候观测", text)
        self.assertIn("Climate Science", text)
        self.assertIn("climate、temperature", text)

    def test_build_load_and_search(self):
        vectors = {
            "全球": [1.0, 0.0],
            "基因": [0.0, 1.0],
        }

        def fake_embed(texts):
            result = []
            for text in texts:
                result.append(
                    vectors["基因"] if "基因" in text else vectors["全球"]
                )
            return result

        with tempfile.TemporaryDirectory() as directory:
            index_directory = f"{directory}/中文索引"
            store = LocalFaissStore(index_directory)
            with patch.object(store, "embed", side_effect=fake_embed):
                self.assertEqual(store.build(PAPERS), 2)

            loaded_store = LocalFaissStore(index_directory)
            with patch.object(loaded_store, "embed", side_effect=fake_embed):
                results = loaded_store.search("基因研究", PAPERS, limit=1)

            self.assertEqual(results[0]["article"]["doi"], "10.1234/xyz")
            self.assertAlmostEqual(results[0]["semanticScore"], 1.0)


if __name__ == "__main__":
    unittest.main()
