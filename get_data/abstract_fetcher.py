#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
摘要获取工具

通过DOI或URL直接从论文原始页面获取完整的摘要内容。
主要支持Nature Scientific Data和ESSD期刊，也可扩展到其他期刊。
"""

import requests
import argparse
import json
import logging
from bs4 import BeautifulSoup
import csv
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 配置日志
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class AbstractFetcher:
    """论文摘要获取类"""
    
    def __init__(self):
        """初始化摘要获取器"""
        self.headers = {
            'User-Agent': 'DataPaper/1.0 (academic metadata collection)'
        }
        self.session = requests.Session()
        retry = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=1,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(("GET", "HEAD")),
            respect_retry_after_header=True,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.headers.update(self.headers)
    
    def doi_to_url(self, doi):
        """将DOI转换为URL"""
        if not doi:
            return None
        
        # 移除可能的前缀
        doi = doi.replace("doi:", "").strip()
        
        # 先检查是否已经是URL
        if doi.startswith("http"):
            return doi
        
        # Nature Scientific Data 的 DOI 可直接映射到文章页，避免额外重定向。
        nature_match = re.match(r"10\.1038/(s41597-[^\s]+)$", doi, flags=re.I)
        if nature_match:
            return f"https://www.nature.com/articles/{nature_match.group(1)}"

        # 构造DOI解析URL
        return f"https://doi.org/{doi}"
    
    def get_journal_from_url(self, url):
        """从URL中识别期刊"""
        if not url:
            return "unknown"
            
        # 检查DOI格式的特殊处理
        if "doi.org/10.1038/s41597" in url:
            return "Nature Scientific Data"
            
        domain = urlparse(url).netloc
        path = urlparse(url).path
        
        # 首先检查重定向后的最终URL
        final_url = url
        try:
            # 发送HEAD请求，只获取头信息，不下载内容
            response = self.session.head(url, timeout=10, allow_redirects=True)
            final_url = response.url
            print(f"重定向后的URL: {final_url}")
        except Exception as e:
            print(f"获取最终URL失败: {e}")
            # 如果HEAD请求失败，使用原始URL
        
        final_domain = urlparse(final_url).netloc
        final_path = urlparse(final_url).path
        
        # 特别检查Nature Scientific Data (最优先)
        if ("nature.com" in final_domain and 
            ("/sdata/" in final_path or 
             "scientificdata" in final_domain or 
             "scientificdata" in final_path or
             "s41597" in final_path)):  # 通过DOI前缀识别
            return "Nature Scientific Data"
            
        # 检查最终URL
        if "nature.com" in final_domain:
            # 先尝试从URL提取期刊名
            journal_part = final_path.split('/')[1] if len(final_path.split('/')) > 1 else ""
            
            # 根据路径识别特定期刊
            if journal_part == "sdata" or "scientificdata" in journal_part:
                return "Nature Scientific Data"
            elif journal_part:
                if journal_part in ["nature", "news", "articles"]:
                    return "Nature"
                else:
                    return f"Nature {journal_part.capitalize()}"
            else:
                return "Nature"
        elif "copernicus.org" in final_domain:
            if "/essd/" in final_path:
                return "Earth System Science Data"
            else:
                journal_part = final_path.split('/')[1] if len(final_path.split('/')) > 1 else ""
                if journal_part:
                    return f"Copernicus {journal_part.upper()}"
                return "Copernicus Journal"
        elif "science.org" in final_domain:
            return "Science"
        elif "pnas.org" in final_domain:
            return "PNAS"
        elif "wiley.com" in final_domain:
            return "Wiley Journal"
        elif "springer.com" in final_domain or "springeropen.com" in final_domain:
            return "Springer Journal"
        elif "elsevier.com" in final_domain or "sciencedirect.com" in final_domain:
            return "Elsevier Journal"
        else:
            # 尝试从DOI中提取出版商信息
            if "/10." in url:
                doi_part = url.split("/10.")[1]
                if "1038/s41597" in doi_part:  # 专门检查Nature Scientific Data的DOI
                    return "Nature Scientific Data"
                publisher = doi_part.split("/")[0]
                if publisher:
                    return f"{publisher.upper()} Journal"
            
            return "unknown"
    
    def fetch_abstract(self, doi_or_url, journal_name=None): # 添加 journal_name 参数
        """获取论文摘要
        
        参数:
            doi_or_url: DOI或论文URL
            journal_name: (可选) 期刊名称，用于辅助识别
        
        返回:
            字典，包含摘要和期刊信息
        """
        # 转换DOI为URL
        url = doi_or_url if doi_or_url.startswith("http") else self.doi_to_url(doi_or_url)
        
        if not url:
            logger.error(f"无效的DOI或URL: {doi_or_url}")
            return {"abstract": "", "journal": "unknown", "url": url}
        
        try:
            # 发送请求
            logger.info(f"正在获取页面内容: {url}")
            # 增加超时设置，并允许重定向
            response = self.session.get(
                url,
                timeout=(10, 30),
                allow_redirects=True
            )
            
            # 处理状态码
            if response.status_code != 200:
                logger.error(f"获取页面失败，状态码: {response.status_code}")
                return {"abstract": "", "journal": "unknown", "url": url}
                
            # 识别期刊
            journal = journal_name or self.get_journal_from_url(response.url)
            logger.info(f"识别出期刊: {journal}")
            
            # 解析HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 根据不同期刊使用不同的选择器
            abstract = ""
            
            if journal in ("Scientific Data", "Nature Scientific Data"):
                # 尝试多种选择器
                abstract_elements = soup.select(
                    'div#Abs1-content p, section[data-title="Abstract"] p'
                )
                if abstract_elements:
                    abstract = "\n".join(
                        elem.get_text(" ", strip=True) for elem in abstract_elements
                    )
                else:
                    for selector in (
                        'meta[name="dc.description"]',
                        'meta[name="description"]',
                    ):
                        element = soup.select_one(selector)
                        if element and element.get("content"):
                            abstract = element["content"]
                            break
            
            elif journal == "Earth System Science Data":
                # ESSD期刊摘要选择器
                abstract_elements = soup.select('div.abstract p, div.abstract-content p')
                if abstract_elements:
                    abstract = "\n".join([elem.get_text().strip() for elem in abstract_elements])
            
            else:
                # 通用选择器
                # 尝试常见的摘要标签类名
                abstract_selectors = [
                    'div.abstract p', 
                    'div#abstract', 
                    'section.abstract',
                    'div[class*="abstract"]',
                    'meta[name="description"]'
                ]
                
                for selector in abstract_selectors:
                    elements = soup.select(selector)
                    if elements:
                        if selector == 'meta[name="description"]':
                            abstract = elements[0].get('content', '')
                        else:
                            abstract = "\n".join([elem.get_text().strip() for elem in elements])
                        break
            
            # 清理摘要内容
            if abstract:
                # 移除多余空白
                abstract = re.sub(r'\s+', ' ', abstract)
                # 移除特殊标记
                abstract = abstract.replace("Abstract", "").strip()
                abstract = abstract.replace("\n", " ").strip()
                logger.info(f"成功获取摘要: {abstract[:100]}...")
            else:
                logger.warning(f"未能找到摘要内容")
                
            return {
                "abstract": abstract,
                "journal": journal,
                "url": url
            }
            
        except Exception as e:
            logger.error(f"获取摘要过程中发生错误: {e}")
            return {"abstract": "", "journal": "unknown", "url": url}

    def process_jsonl(self, input_file, output_file=None, workers=4):
        """并发补全 JSONL 中缺失的摘要，并保留原有记录顺序。"""
        if not os.path.exists(input_file):
            logger.error(f"输入文件不存在: {input_file}")
            return 0, 0

        if not output_file:
            name, ext = os.path.splitext(input_file)
            output_file = f"{name}_with_abstracts{ext or '.jsonl'}"

        with open(input_file, "r", encoding="utf-8") as source:
            rows = [json.loads(line) for line in source if line.strip()]

        missing_indexes = [
            index
            for index, row in enumerate(rows)
            if not str(row.get("abstract", "")).strip() and row.get("doi")
        ]
        logger.info("共 %s 条记录，其中 %s 条需要补摘要", len(rows), len(missing_indexes))

        def fetch(index):
            row = rows[index]
            result = self.fetch_abstract(
                row["doi"],
                journal_name=row.get("journal"),
            )
            return index, result.get("abstract", "")

        def save_rows():
            temporary_file = f"{output_file}.tmp"
            with open(temporary_file, "w", encoding="utf-8") as target:
                for row in rows:
                    target.write(json.dumps(row, ensure_ascii=False) + "\n")
            os.replace(temporary_file, output_file)

        completed = 0
        processed = 0
        with ThreadPoolExecutor(max_workers=max(1, min(workers, 8))) as executor:
            futures = {executor.submit(fetch, index): index for index in missing_indexes}
            for future in as_completed(futures):
                index = futures[future]
                processed += 1
                try:
                    _, abstract = future.result()
                    if abstract:
                        rows[index]["abstract"] = abstract
                        completed += 1
                except Exception as exc:
                    logger.error("补摘要失败，DOI %s: %s", rows[index].get("doi"), exc)

                if processed % 50 == 0 or processed == len(futures):
                    save_rows()
                    logger.info(
                        "补摘要进度 %s/%s，成功 %s",
                        processed,
                        len(futures),
                        completed,
                    )

        save_rows()

        logger.info("摘要补全完成，成功 %s/%s: %s", completed, len(missing_indexes), output_file)
        return completed, len(missing_indexes)
    
    def process_csv(self, input_file, output_file=None):
        """处理CSV文件中的DOI，获取摘要
        
        参数:
            input_file: 输入CSV文件路径，需要包含doi列
            output_file: 输出CSV文件路径，默认为input_file加上_with_abstracts后缀
        """
        if not os.path.exists(input_file):
            logger.error(f"输入文件不存在: {input_file}")
            return False
            
        if not output_file:
            name, ext = os.path.splitext(input_file)
            output_file = f"{name}_with_abstracts{ext}"
        
        try:
            # 读取输入CSV
            data = []
            with open(input_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames
                
                # 检查是否有doi列
                if 'doi' not in headers:
                    logger.error(f"输入文件 {input_file} 中没有doi列")
                    return False
                    
                # 检查是否已有abstract列
                if 'abstract' not in headers:
                    headers.append('abstract')
                    
                data = list(reader)
                
            logger.info(f"读取了 {len(data)} 条记录，开始获取摘要...")
            
            # 获取摘要
            for i, row in enumerate(data):
                doi = row.get('doi', '')
                existing_abstract = row.get('abstract', '')
                
                # 检查现有摘要是否足够长
                if existing_abstract and len(existing_abstract) > 50:
                    logger.info(f"使用CSV中已有的摘要 (DOI: {doi})")
                    continue
                    
                if not doi:
                    logger.warning(f"记录 {i+1}/{len(data)} 没有DOI，跳过")
                    continue
                
                logger.info(f"处理记录 {i+1}/{len(data)} DOI: {doi}")
                result = self.fetch_abstract(doi)
                
                if result['abstract']:
                    row['abstract'] = result['abstract']
                    
                    # 如果没有journal信息，添加
                    if 'journal' not in row or not row['journal']:
                        row['journal'] = result['journal']
                
                # 每10条记录休息一下，避免被服务器封锁
                if (i + 1) % 10 == 0:
                    logger.info("暂停2秒...")
                    time.sleep(2)
                    
            # 写入输出CSV
            with open(output_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                writer.writerows(data)
                
            logger.info(f"处理完成，结果保存到 {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"处理CSV文件时发生错误: {e}")
            return False

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='论文摘要获取工具')
    parser.add_argument('--doi', help='要获取摘要的DOI或URL')
    parser.add_argument('--input', help='输入CSV文件路径')
    parser.add_argument('--output', help='输出CSV文件路径')
    parser.add_argument('--jsonl', help='输入JSONL文件并补全缺失摘要')
    parser.add_argument('--workers', type=int, default=4, help='JSONL补摘要并发数，默认4')
    
    args = parser.parse_args()
    
    fetcher = AbstractFetcher()
    
    if args.doi:
        # 单个DOI模式
        result = fetcher.fetch_abstract(args.doi)
        print(f"期刊: {result['journal']}")
        print(f"摘要: {result['abstract']}")
        
    elif args.jsonl:
        completed, total = fetcher.process_jsonl(args.jsonl, args.output, args.workers)
        print(f"摘要补全完成，成功 {completed}/{total}")

    elif args.input:
        # CSV模式
        success = fetcher.process_csv(args.input, args.output)
        if not success:
            sys.exit(1)
    
    else:
        # 交互模式
        print("请输入DOI或URL (输入q退出):")
        while True:
            doi = input("> ")
            if doi.lower() == 'q':
                break
                
            if doi:
                result = fetcher.fetch_abstract(doi)
                print(f"期刊: {result['journal']}")
                print(f"摘要: {result['abstract']}")
                print("\n请输入下一个DOI或URL (输入q退出):")

if __name__ == "__main__":
    main()
