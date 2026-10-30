#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""通过 Crossref REST API 获取期刊论文元数据。"""

import argparse
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from .db_helper import DBHelper
    from .abstract_fetcher import AbstractFetcher
except ImportError:
    from db_helper import DBHelper
    from abstract_fetcher import AbstractFetcher


logger = logging.getLogger(__name__)


class CrossrefCrawler:
    """按 ISSN 从 Crossref 增量拉取论文，作为 RSS 的补充数据源。"""

    API_BASE = "https://api.crossref.org"
    DEFAULT_JOURNALS = (
        {
            "name": "Scientific Data",
            "issn": "2052-4463",
        },
        {
            "name": "Earth System Science Data",
            "issn": "1866-3516",
        },
    )

    def __init__(self):
        self.journals = self.DEFAULT_JOURNALS
        self.rows = max(20, min(int(os.environ.get("CROSSREF_ROWS", "100")), 1000))
        self.max_pages = max(1, int(os.environ.get("CROSSREF_MAX_PAGES", "10")))
        self.lookback_days = max(1, int(os.environ.get("CROSSREF_LOOKBACK_DAYS", "120")))
        self.full_lookback_days = max(
            self.lookback_days,
            int(os.environ.get("CROSSREF_FULL_LOOKBACK_DAYS", "3650")),
        )
        self.last_added_count = 0
        self.session = self._build_session()
        self.abstract_fetcher = AbstractFetcher()

    @staticmethod
    def _build_session():
        session = requests.Session()
        retry = Retry(
            total=4,
            connect=4,
            read=4,
            backoff_factor=1,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(("GET",)),
            respect_retry_after_header=True,
        )
        session.mount("https://", HTTPAdapter(max_retries=retry))

        contact = os.environ.get("CROSSREF_MAILTO", "").strip()
        user_agent = "DataPaper/1.0"
        if contact:
            user_agent += f" (mailto:{contact})"
        session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept": "application/json",
            }
        )
        return session

    @staticmethod
    def normalize_doi(value):
        doi = str(value or "").strip()
        doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", doi, flags=re.I)
        return doi.lower().strip()

    @staticmethod
    def _first(value, default=""):
        if isinstance(value, list):
            return str(value[0]).strip() if value else default
        return str(value or default).strip()

    @staticmethod
    def _extract_date(item):
        for field in ("published-online", "published-print", "published", "issued"):
            date_parts = item.get(field, {}).get("date-parts", [])
            if not date_parts or not date_parts[0]:
                continue
            parts = list(date_parts[0]) + [1, 1]
            try:
                return datetime(int(parts[0]), int(parts[1]), int(parts[2])).strftime(
                    "%Y-%m-%d"
                )
            except (TypeError, ValueError):
                continue
        return ""

    @staticmethod
    def _extract_authors(item):
        authors = []
        for author in item.get("author", []):
            name = " ".join(
                part
                for part in (
                    str(author.get("given", "")).strip(),
                    str(author.get("family", "")).strip(),
                )
                if part
            )
            if name:
                authors.append(name)
        return ", ".join(authors)

    def _to_paper(self, item, journal_name):
        abstract_html = self._first(item.get("abstract"))
        abstract = (
            BeautifulSoup(abstract_html, "html.parser").get_text(" ", strip=True)
            if abstract_html
            else ""
        )
        doi = self.normalize_doi(item.get("DOI"))
        url = self._first(item.get("URL"))
        if not url and doi:
            url = f"https://doi.org/{doi}"

        return {
            "journal": self._first(item.get("container-title"), journal_name),
            "title": self._first(item.get("title"), "Unknown"),
            "abstract": abstract,
            "publishDate": self._extract_date(item),
            "doi": doi,
            "url": url,
            "authors": self._extract_authors(item),
            "tags": ",".join(str(tag).strip() for tag in item.get("subject", []) if tag),
        }

    @staticmethod
    def _is_supported_article(paper):
        """排除没有独立摘要、也不属于数据论文的更正公告。"""
        title = str(paper.get("title", "")).strip().lower()
        return not (
            title.startswith("correction:")
            or title.startswith("correction :")
            or title.startswith("publisher correction:")
        )

    @staticmethod
    def _get_existing_dois():
        connection = DBHelper.get_connection()
        if not connection:
            return set()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT doi FROM raw_papers WHERE doi IS NOT NULL AND doi != ''"
                )
                return {
                    CrossrefCrawler.normalize_doi(row[0])
                    for row in cursor.fetchall()
                    if row[0]
                }
        finally:
            connection.close()

    def _crawl_journal(
        self,
        journal,
        from_date,
        existing_dois,
        to_date=None,
        save_paper=None,
        enrich_abstracts=False,
    ):
        saved = 0
        cursor = "*"
        endpoint = f"{self.API_BASE}/journals/{journal['issn']}/works"
        save_paper = save_paper or DBHelper.insert_raw_paper

        for page in range(1, self.max_pages + 1):
            filters = [f"from-pub-date:{from_date}"]
            if to_date:
                filters.append(f"until-pub-date:{to_date}")
            params = {
                "filter": ",".join(filters),
                "rows": self.rows,
                "cursor": cursor,
                # Crossref no longer permits publication-date sorting with cursors.
                # Date filters define coverage; order records locally after fetching.
                "sort": "indexed",
                "order": "desc",
            }
            contact = os.environ.get("CROSSREF_MAILTO", "").strip()
            if contact:
                params["mailto"] = contact

            response = self.session.get(endpoint, params=params, timeout=(10, 45))
            response.raise_for_status()
            message = response.json().get("message", {})
            items = message.get("items", [])
            logger.info(
                "%s Crossref 第 %s 页返回 %s 条记录",
                journal["name"],
                page,
                len(items),
            )

            for item in items:
                paper = self._to_paper(item, journal["name"])
                doi = paper["doi"]
                if (
                    not doi
                    or doi in existing_dois
                    or not self._is_supported_article(paper)
                ):
                    continue
                if enrich_abstracts and not paper["abstract"]:
                    result = self.abstract_fetcher.fetch_abstract(
                        doi,
                        journal_name=paper["journal"],
                    )
                    paper["abstract"] = result.get("abstract", "")
                if save_paper(paper):
                    existing_dois.add(doi)
                    saved += 1

            if len(items) < self.rows:
                break
            next_cursor = message.get("next-cursor")
            if not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor

        return saved

    def crawl(self, full_update=False):
        """抓取配置期刊，并返回新插入的论文数量。"""
        DBHelper.initialize_tables()
        existing_dois = self._get_existing_dois()
        days = self.full_lookback_days if full_update else self.lookback_days
        from_date = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
        total_saved = 0

        for journal in self.journals:
            try:
                logger.info(
                    "开始从 Crossref 获取 %s（ISSN %s，起始日期 %s）",
                    journal["name"],
                    journal["issn"],
                    from_date,
                )
                total_saved += self._crawl_journal(
                    journal,
                    from_date,
                    existing_dois,
                    enrich_abstracts=True,
                )
            except (requests.RequestException, ValueError) as exc:
                logger.error("Crossref 获取 %s 失败: %s", journal["name"], exc)

        self.last_added_count = total_saved
        logger.info("Crossref 获取完成，新增 %s 篇论文", total_saved)
        return total_saved

    def export_jsonl(self, output_path, from_date, to_date=None):
        """不依赖数据库，将指定日期范围内的论文导出为 JSONL。"""
        output_path = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        existing_dois = set()
        total_saved = 0

        with open(output_path, "w", encoding="utf-8") as output:
            def write_paper(paper):
                output.write(json.dumps(paper, ensure_ascii=False) + "\n")
                return True

            for journal in self.journals:
                logger.info(
                    "开始导出 %s（%s 至 %s）",
                    journal["name"],
                    from_date,
                    to_date or "今天",
                )
                total_saved += self._crawl_journal(
                    journal,
                    from_date,
                    existing_dois,
                    to_date=to_date,
                    save_paper=write_paper,
                )

        self.last_added_count = total_saved
        logger.info("离线导出完成，共 %s 篇: %s", total_saved, output_path)
        return total_saved


def main():
    parser = argparse.ArgumentParser(description="Crossref 论文元数据采集器")
    parser.add_argument("--from-date", help="起始发布日期，格式 YYYY-MM-DD")
    parser.add_argument("--to-date", help="结束发布日期，格式 YYYY-MM-DD")
    parser.add_argument("--output", help="不写数据库，导出到指定 JSONL 文件")
    args = parser.parse_args()

    crawler = CrossrefCrawler()
    if args.output:
        if not args.from_date:
            parser.error("使用 --output 时必须提供 --from-date")
        count = crawler.export_jsonl(args.output, args.from_date, args.to_date)
        print(f"Crossref 数据导出完成，共 {count} 篇论文: {args.output}")
    else:
        count = crawler.crawl()
        print(f"Crossref 数据获取完成，新增 {count} 篇论文")


if __name__ == "__main__":
    main()
