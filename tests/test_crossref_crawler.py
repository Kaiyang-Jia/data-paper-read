import unittest
from unittest.mock import Mock, patch

from get_data.crossref_crawler import CrossrefCrawler


class CrossrefCrawlerTest(unittest.TestCase):
    def test_normalize_doi(self):
        self.assertEqual(
            CrossrefCrawler.normalize_doi("https://doi.org/10.1234/ABC "),
            "10.1234/abc",
        )
        self.assertEqual(CrossrefCrawler.normalize_doi("doi: 10.1234/ABC"), "10.1234/abc")

    def test_maps_crossref_item(self):
        item = {
            "DOI": "10.1234/Test",
            "title": ["A test paper"],
            "container-title": ["Test Journal"],
            "abstract": "<jats:p>An <b>abstract</b>.</jats:p>",
            "published-online": {"date-parts": [[2026, 6, 12]]},
            "author": [{"given": "Ada", "family": "Lovelace"}],
            "subject": ["Data science"],
        }

        paper = CrossrefCrawler()._to_paper(item, "Fallback")

        self.assertEqual(paper["doi"], "10.1234/test")
        self.assertEqual(paper["publishDate"], "2026-06-12")
        self.assertEqual(paper["authors"], "Ada Lovelace")
        self.assertEqual(paper["journal"], "Test Journal")
        self.assertIn("abstract", paper["abstract"])

    def test_filters_correction_notices(self):
        self.assertFalse(
            CrossrefCrawler._is_supported_article(
                {"title": "Publisher Correction: A dataset"}
            )
        )
        self.assertTrue(
            CrossrefCrawler._is_supported_article(
                {"title": "A useful scientific dataset"}
            )
        )

    @patch("get_data.crossref_crawler.DBHelper.insert_raw_paper", return_value=True)
    def test_cursor_pagination_and_deduplication(self, insert_raw_paper):
        crawler = CrossrefCrawler()
        crawler.rows = 1
        crawler.max_pages = 3

        first_response = Mock()
        first_response.raise_for_status.return_value = None
        first_response.json.return_value = {
            "message": {
                "items": [{"DOI": "10.1234/new", "title": ["New paper"]}],
                "next-cursor": "second",
            }
        }
        second_response = Mock()
        second_response.raise_for_status.return_value = None
        second_response.json.return_value = {
            "message": {
                "items": [{"DOI": "10.1234/NEW", "title": ["Duplicate paper"]}],
                "next-cursor": "done",
            }
        }
        third_response = Mock()
        third_response.raise_for_status.return_value = None
        third_response.json.return_value = {"message": {"items": []}}
        crawler.session.get = Mock(
            side_effect=[first_response, second_response, third_response]
        )

        saved = crawler._crawl_journal(
            {"name": "Test Journal", "issn": "1234-5678"},
            "2026-01-01",
            set(),
            save_paper=insert_raw_paper,
        )

        self.assertEqual(saved, 1)
        self.assertEqual(insert_raw_paper.call_count, 1)
        self.assertEqual(crawler.session.get.call_count, 3)
        # Current Crossref rejects publication-date sorting with cursor pagination.
        self.assertEqual(crawler.session.get.call_args_list[0].kwargs['params']['sort'], 'indexed')


if __name__ == "__main__":
    unittest.main()
