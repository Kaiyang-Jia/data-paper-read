#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Restore paper metadata from a JSONL backup into MariaDB."""

import argparse
import json
from pathlib import Path

from get_data.db_helper import DBHelper


def load_papers(path):
    papers = {}
    with path.open(encoding="utf-8") as source:
        for line in source:
            paper = json.loads(line)
            key = str(
                paper.get("doi") or paper.get("url") or paper.get("title") or ""
            ).strip().lower()
            if key:
                papers[key] = paper
    return list(papers.values())


def restore(path):
    papers = load_papers(path)
    connection = DBHelper.get_connection()
    if not connection:
        raise RuntimeError("无法连接 MariaDB")

    raw_rows = []
    processed_rows = []
    for paper in papers:
        tags = paper.get("tags") or ""
        if isinstance(tags, list):
            tags = ",".join(str(tag).strip() for tag in tags if str(tag).strip())
        common = (
            str(paper.get("title") or "")[:500],
            str(paper.get("abstract") or ""),
            str(paper.get("publishDate") or "")[:20],
            str(paper.get("doi") or "")[:255],
            str(paper.get("url") or "")[:500],
            str(paper.get("authors") or ""),
            str(tags),
            str(paper.get("journal") or "")[:255],
        )
        raw_rows.append(common)
        processed_rows.append((
            common[0],
            str(paper.get("titleCn") or "")[:500],
            str(paper.get("interpretationCn") or ""),
            common[1],
            common[2],
            common[3],
            common[4],
            common[5],
            common[6],
            str(paper.get("Subject") or "")[:50],
            common[7],
        ))

    try:
        with connection.cursor() as cursor:
            cursor.executemany("""
                INSERT INTO raw_papers
                    (title, abstract, publishDate, doi, url, authors, tags, journal)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    title=VALUES(title), abstract=VALUES(abstract),
                    publishDate=VALUES(publishDate), url=VALUES(url),
                    authors=VALUES(authors), tags=VALUES(tags), journal=VALUES(journal)
            """, raw_rows)
            cursor.executemany("""
                INSERT INTO processed_papers
                    (title, titleCn, interpretationCn, abstract, publishDate, doi,
                     url, authors, tags, Subject, journal)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    title=VALUES(title), abstract=VALUES(abstract),
                    publishDate=VALUES(publishDate), url=VALUES(url),
                    authors=VALUES(authors), tags=VALUES(tags), journal=VALUES(journal)
            """, processed_rows)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return len(papers)


def main():
    parser = argparse.ArgumentParser(description="从 JSONL 恢复论文到 MariaDB")
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=Path("backups/crossref_2026_complete.jsonl"),
    )
    args = parser.parse_args()
    if not DBHelper.initialize_tables():
        raise SystemExit("MariaDB 表初始化失败")
    count = restore(args.path)
    print(f"已恢复 {count} 篇论文到 MariaDB")


if __name__ == "__main__":
    main()
