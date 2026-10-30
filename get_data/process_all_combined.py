#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Process all unprocessed papers with one structured LLM call per paper."""

import argparse
import json
import logging
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
from openai import OpenAI

from .db_helper import DBHelper
from .process import PREDEFINED_SUBJECTS


load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def normalize_result(payload):
    title_cn = str(payload.get("titleCn", "")).strip()
    interpretation_cn = str(payload.get("interpretationCn", "")).strip()
    tags = payload.get("tags", [])
    if isinstance(tags, str):
        tags = [tag.strip() for tag in tags.replace("，", ",").split(",") if tag.strip()]
    else:
        tags = [str(tag).strip() for tag in tags if str(tag).strip()]
    subject = str(payload.get("Subject", "")).strip().strip("，,。")
    if subject not in PREDEFINED_SUBJECTS:
        subject = next(
            (candidate for candidate in PREDEFINED_SUBJECTS if candidate in subject),
            "其他",
        )
    if not title_cn or not interpretation_cn or not tags:
        raise ValueError("LLM response has missing required fields")
    return {
        "titleCn": title_cn,
        "interpretationCn": interpretation_cn,
        "tags": tags[:5],
        "Subject": subject,
    }


def process_one(client, model, paper, retries=3):
    title = paper.get("title", "")
    abstract = paper.get("abstract", "")
    prompt = {
        "title": title,
        "abstract": abstract,
        "allowedSubjects": PREDEFINED_SUBJECTS,
    }
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=model,
                extra_body={"thinking": {"type": "disabled"}},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是科研数据论文处理助手。根据标题和摘要返回严格 JSON："
                            '{"titleCn":"准确简洁的中文标题",'
                            '"interpretationCn":"约100-180字中文解读，说明数据制作、'
                            '关键变量、时空范围或分辨率、用途与明显限制",'
                            '"tags":["3至5个中文标签"],'
                            '"Subject":"只能从 allowedSubjects 中选择一个"}。'
                            "不得添加 Markdown 或 JSON 之外的内容，不得虚构摘要未提供的信息。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(prompt, ensure_ascii=False),
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                stream=False,
            )
            result = normalize_result(json.loads(response.choices[0].message.content))
            processed = {
                "title": title,
                "titleCn": result["titleCn"],
                "interpretationCn": result["interpretationCn"],
                "abstract": abstract,
                "publishDate": paper.get("publishDate", ""),
                "doi": paper.get("doi", ""),
                "url": paper.get("url", ""),
                "authors": paper.get("authors", ""),
                "tags": result["tags"],
                "Subject": result["Subject"],
                "journal": paper.get("journal", ""),
            }
            if not DBHelper.insert_processed_paper(processed):
                raise RuntimeError("database insert failed")
            return paper.get("doi", "")
        except Exception as error:
            if attempt == retries - 1:
                raise
            delay = (2 ** attempt) + random.uniform(0, 1)
            logger.warning(
                "Retrying DOI %s after error: %s",
                paper.get("doi", ""),
                error,
            )
            time.sleep(delay)


def main():
    parser = argparse.ArgumentParser(description="Process all papers with combined calls")
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is missing")

    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")
    papers = DBHelper.get_unprocessed_raw_papers()
    if args.limit > 0:
        papers = papers[:args.limit]
    total = len(papers)
    logger.info("Starting combined processing: total=%s workers=%s model=%s", total, args.workers, model)
    if not papers:
        return

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com", timeout=45, max_retries=0)
    completed = 0
    failed = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(process_one, client, model, paper): paper
            for paper in papers
        }
        for future in as_completed(futures):
            paper = futures[future]
            try:
                future.result()
                completed += 1
                if completed % 10 == 0 or completed == total:
                    logger.info("Progress: %s/%s", completed, total)
            except Exception as error:
                failed.append(paper.get("doi", ""))
                logger.error("Failed DOI %s: %s", paper.get("doi", ""), error)

    logger.info("Finished: completed=%s failed=%s", completed, len(failed))
    if failed:
        logger.info("Failed DOIs: %s", ",".join(failed))


if __name__ == "__main__":
    main()
