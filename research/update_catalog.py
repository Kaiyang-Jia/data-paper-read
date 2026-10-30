"""One run: acquire -> merge -> source abstracts -> Chinese cards -> semantic index."""
import argparse
from datetime import date, timedelta, datetime, timezone
import os
from pathlib import Path

from dotenv import load_dotenv, set_key
from get_data.crossref_crawler import CrossrefCrawler
from get_data.faiss_store import LocalFaissStore
from research.refresh_snapshot import refresh
from research.enrich_catalog import enrich
from research.abstract_backfill import backfill
import json

ROOT = Path(__file__).resolve().parent.parent


def run(from_date, to_date, workers=6, acquire=True, abstracts=True):
    if from_date > to_date:
        raise ValueError('开始日期不能晚于结束日期')
    load_dotenv(ROOT / '.env')
    snapshot = ROOT / 'site/public/data/articles.json'
    if acquire:
        export = ROOT / 'backups' / f'crossref_{from_date}_{to_date}.jsonl'
        CrossrefCrawler().export_jsonl(export, str(from_date), str(to_date))
        refresh(export)
    if abstracts:
        backfill(snapshot, ROOT / 'backups/abstract_backfill_v1.jsonl', workers=min(workers, 3))
    report = enrich(snapshot, ROOT / 'backups/chinese_cards_v1.jsonl', workers=workers)
    if report['failed']:
        raise RuntimeError('部分中文加工失败，结果已保存；修复后重新运行将续接')
    # Rebuild after Chinese content changes; select the completed index only on success.
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    index_relative = f'data/faiss_chinese_{stamp}'
    count = LocalFaissStore(ROOT / index_relative).build(json.loads(snapshot.read_text(encoding='utf-8'))['articles'])
    if count != report['translationCount']:
        raise RuntimeError('索引记录数与中文目录记录数不一致，不切换配置')
    set_key(str(ROOT / '.env'), 'FAISS_INDEX_DIR', index_relative)
    set_key(str(ROOT / '.env'), 'DATAPAPER_CATALOG_SOURCE', 'snapshot')
    print(f'更新完成：{count}篇中文卡片，索引{index_relative}。重启网页服务后生效。', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from-date', type=date.fromisoformat, default=date.today() - timedelta(days=14))
    parser.add_argument('--to-date', type=date.fromisoformat, default=date.today())
    parser.add_argument('--workers', type=int, choices=range(1, 13), default=6)
    parser.add_argument('--skip-acquire', action='store_true', help='跳过新论文采集，续接摘要补全、中文加工和索引')
    parser.add_argument('--skip-abstracts', action='store_true', help='跳过原文摘要补全，直接加工已有目录')
    args = parser.parse_args()
    run(args.from_date, args.to_date, args.workers, not args.skip_acquire, not args.skip_abstracts)
