#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Build the local FAISS paper index from the MariaDB source of truth."""

import argparse
import logging
import json
from pathlib import Path

from get_data.db_helper import DBHelper
from get_data.faiss_store import LocalFaissStore


def main():
    parser = argparse.ArgumentParser(description="从 MariaDB 构建本地 FAISS 索引")
    parser.add_argument("--index-dir", help="索引目录，默认读取 FAISS_INDEX_DIR")
    parser.add_argument("--catalog", type=Path, help="数据库不可用时使用真实论文快照 JSON")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    papers = (json.loads(args.catalog.read_text(encoding="utf-8"))["articles"]
              if args.catalog else DBHelper.get_all_processed_papers())
    if not papers:
        raise SystemExit("MariaDB 中没有可索引的 processed_papers 数据")

    store = LocalFaissStore(args.index_dir)
    count = store.build(papers)
    print(f"FAISS 索引构建完成：{count} 篇论文，目录 {store.index_dir}")


if __name__ == "__main__":
    main()
