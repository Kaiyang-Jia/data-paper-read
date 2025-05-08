#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Nature和ESSD RSS爬虫模块

自动爬取Nature Scientific Data和ESSD期刊的RSS源，获取最新发布的数据论文信息。
输出原始数据到MySQL数据库，同时保留CSV导出功能作为备份。
"""

import feedparser
import csv
import os
from datetime import datetime
from bs4 import BeautifulSoup
import logging
import requests  # 保留，可能其他地方仍需使用
from urllib.parse import urlparse # 保留，可能其他地方仍需使用
import re        # 保留，可能其他地方仍需使用
import time      # 保留，可能其他地方仍需使用
import random    # 保留，可能其他地方仍需使用
from .abstract_fetcher import AbstractFetcher # 导入 AbstractFetcher

# 导入数据库工具类
try:
    from .db_helper import DBHelper  # 当作为包导入时
except ImportError:
    try:
        from db_helper import DBHelper  # 当在同一目录下直接运行时
    except ImportError:
        print("错误：无法导入数据库工具类，请确保 db_helper.py 文件存在")
        DBHelper = None

# 配置日志
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class RSSCrawler:
    """通用RSS爬虫类，支持多个期刊"""
    
    def __init__(self):
        # 定义多个期刊的RSS源和名称
        self.journals = [
            {
                "name": "Scientific Data",
                "rss_url": "https://www.nature.com/sdata.rss",
                "output_file": "raw_papers.csv"
            },
            {
                "name": "Earth System Science Data",
                "rss_url": "https://essd.copernicus.org/articles/xml/rss2_0.xml",
                "output_file": "raw_papers.csv"
            }
        ]
        self.last_added_count = 0  # 新增属性，用于跟踪新添加的记录数
        self.headers = {  # 添加请求头
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.abstract_fetcher = AbstractFetcher() # 初始化 AbstractFetcher
        
        # 初始化数据库表
        if DBHelper:
            DBHelper.initialize_tables()

    # --- 继续使用现有方法 --- 
    def clean_abstract(self, raw_abstract, title, journal_name):
        """清理HTML和冗余标题"""
        # 移除HTML标签
        soup = BeautifulSoup(raw_abstract, "html.parser")
        text = soup.get_text()
        # 移除标题（常重复）
        text = text.replace(title, "").strip()
        # 移除元数据（针对不同期刊的元数据格式）
        lines = text.split("\n")
        cleaned_lines = []
        if journal_name == "Nature Scientific Data":
            # Nature的RSS摘要通常很短或没有，主要依赖网页抓取
            cleaned_lines = [line for line in lines if not line.startswith("Scientific Data,")]
        elif journal_name == "Earth System Science Data":
            # ESSD的RSS摘要可能包含作者和期刊信息，需要清理
            cleaned_lines = [line for line in lines if not ("Earth Syst. Sci. Data" in line or "Preprint under review" in line or line.count(',') > 3)] # 尝试移除作者行
        else:
            cleaned_lines = lines
        
        # 进一步清理可能的作者信息（基于大写字母和逗号）
        final_lines = []
        for line in cleaned_lines:
            if not (len(line.split()) > 2 and line.count(',') > 1 and all(word[0].isupper() for word in line.replace(',', '').split() if word)): # 启发式移除作者行
                final_lines.append(line)
                
        return " ".join(final_lines).strip()
    
    def format_date(self, pub_date_str, journal_name):
        """根据期刊名称解析日期字符串并格式化为 YYYY-MM-DD"""
        if not pub_date_str:
            logger.warning(f"日期字符串为空，使用当前日期")
            return datetime.now().strftime("%Y-%m-%d")

        parsed_date = None
        try:
            if journal_name == "Scientific Data":
                # Scientific Data 通常使用 YYYY-MM-DD 格式
                try:
                    parsed_date = datetime.strptime(pub_date_str, "%Y-%m-%d")
                except ValueError:
                    # 作为后备，尝试从类似 'Scientific Data, Published online: 2025-04-23; | doi:...' 的字符串提取
                    match = re.search(r'(\d{4}-\d{2}-\d{2})', pub_date_str)
                    if match:
                        parsed_date = datetime.strptime(match.group(1), "%Y-%m-%d")
                    else:
                         logger.warning(f"无法从 Scientific Data 的日期字符串 '{pub_date_str}' 解析日期")

            elif journal_name == "Earth System Science Data":
                # ESSD 通常使用 RFC 822 格式，例如 'Wed, 23 Apr 2025 15:46:08 +0200'
                # Python's %z handles timezone offsets like +0200
                try:
                    # 尝试去除可能存在的时区名称 (如 GMT, CEST)，因为 %z 可能无法处理它们
                    parts = pub_date_str.split()
                    if len(parts) > 5 and not parts[-1].startswith(('+', '-')):
                         pub_date_str = " ".join(parts[:-1]) # 移除最后的时区名称

                    # 尝试解析带时区的格式
                    parsed_date = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %z")
                except ValueError:
                     # 如果带时区的解析失败，尝试不带时区的格式
                     try:
                         parsed_date = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S")
                         logger.warning(f"ESSD 日期 '{pub_date_str}' 缺少时区信息，已解析")
                     except ValueError:
                         logger.warning(f"无法从 ESSD 的日期字符串 '{pub_date_str}' 解析日期")

            else:
                # 其他期刊或未知期刊，尝试通用格式
                common_formats = [
                    "%Y-%m-%d",
                    "%Y-%m-%dT%H:%M:%S%z",
                    "%Y-%m-%dT%H:%M:%SZ",
                    "%a, %d %b %Y %H:%M:%S %z",
                    "%a, %d %b %Y %H:%M:%S",
                ]
                for fmt in common_formats:
                    try:
                        parsed_date = datetime.strptime(pub_date_str, fmt)
                        break # 解析成功即跳出循环
                    except ValueError:
                        continue
                if not parsed_date:
                    logger.warning(f"无法使用通用格式解析日期字符串 '{pub_date_str}'")

            if parsed_date:
                return parsed_date.strftime("%Y-%m-%d")
            else:
                # 如果所有尝试都失败，返回当前日期
                logger.warning(f"最终无法解析日期 '{pub_date_str}'，使用当前日期")
                return datetime.now().strftime("%Y-%m-%d")

        except Exception as e:
            logger.error(f"日期格式化时发生意外错误: {e}，日期字符串: '{pub_date_str}'，使用当前日期")
            return datetime.now().strftime("%Y-%m-%d")

    def crawl(self):
        """执行RSS爬取"""
        all_data = []
        db_saved_count = 0  # 数据库保存计数
        
        # 确保数据库表已初始化
        if DBHelper:
            DBHelper.initialize_tables()
        
        for journal_info in self.journals:
            journal_name = journal_info["name"]
            rss_url = journal_info["rss_url"]
            logger.info(f"开始爬取 {journal_name} RSS: {rss_url}")
            try:
                feed = feedparser.parse(rss_url)
                data_list = []
                
                logger.info(f"{journal_name} RSS包含 {len(feed.entries)} 条条目")
                for i, entry in enumerate(feed.entries):
                    title = entry.get("title", "Unknown")
                    
                    # 兼容不同RSS的描述字段
                    raw_abstract = ""
                    fields_to_try = ["description", "summary", "content", "content:encoded", "dc:description"]
                    for field in fields_to_try:
                        if field in entry:
                            raw_abstract = entry.get(field, "")
                            if raw_abstract: break
                    
                    # 直接使用RSS配置的期刊名
                    current_journal_name = journal_name
                    
                    abstract = self.clean_abstract(raw_abstract, title, current_journal_name)
                    
                    # --- 获取日期 ---
                    pub_date_str = ""
                    if journal_name == "Scientific Data":
                        # 优先 updated (可能对应 <dc:date> 或 <published>)
                        updated_date = entry.get("updated", entry.get("published", None))
                        if updated_date and re.match(r'\d{4}-\d{2}-\d{2}', updated_date.split('T')[0]): # 提取 YYYY-MM-DD 部分
                            pub_date_str = updated_date.split('T')[0]
                            logger.info(f"使用 'updated' 或 'published' 字段提取日期: {pub_date_str}")

                        # 其次尝试 dc:date (注意 feedparser 可能不带命名空间前缀)
                        if not pub_date_str:
                            dc_date = entry.get("dc_date", None)
                            if dc_date and re.match(r'\d{4}-\d{2}-\d{2}', dc_date):
                                pub_date_str = dc_date
                                logger.info(f"使用 'dc_date' 字段提取日期: {pub_date_str}")

                        # 最后从 dc_source 提取
                        if not pub_date_str:
                            dc_source = entry.get("dc_source", None)
                            if dc_source:
                                match = re.search(r'(\d{4}-\d{2}-\d{2})', dc_source)
                                if match:
                                    pub_date_str = match.group(1)
                                    logger.info(f"从 'dc_source' 字段提取日期: {pub_date_str}")

                    elif journal_name == "Earth System Science Data":
                        # ESSD 的逻辑保持不变
                        pub_date_str = entry.get("pubDate", entry.get("dc_date", entry.get("published", "")))
                    else:
                        # 其他期刊的默认顺序保持不变
                        pub_date_str = entry.get("published", entry.get("pubDate", entry.get("dc_date", "")))

                    # 调用 format_date 方法 (确保它能处理 YYYY-MM-DD)
                    formatted_date = self.format_date(pub_date_str, journal_name)

                    # 兼容DOI字段
                    doi = entry.get("dc_identifier", "").replace("doi:", "") if "dc_identifier" in entry else entry.get("guid", "")
                    # 尝试从URL提取DOI
                    url = entry.get("link", "")
                    if not doi and url and "doi.org" in url:
                        try:
                            doi = url.split("doi.org/")[1]
                        except IndexError:
                            pass
                    elif not doi and url and "nature.com/articles/" in url:
                        try:
                            doi = url.split("articles/")[1]
                        except IndexError:
                            pass
                            
                    authors = entry.get("author", "Unknown")
                    # 兼容标签字段
                    tags = entry.get("category", "").split(",") if "category" in entry else []
                    
                    # --- 摘要增强逻辑 ---
                    # 如果摘要为空或过短，尝试从网页获取
                    should_fetch_web = False
                    if not abstract:
                        # 如果RSS完全没有摘要，对所有期刊都尝试抓取
                        should_fetch_web = True
                        logger.info(f"RSS摘要缺失，准备从网页获取: {url}")
                    elif current_journal_name != "Earth System Science Data" and len(abstract) < 100:
                        # 对于非ESSD期刊，如果摘要过短，尝试抓取
                        should_fetch_web = True
                        logger.info(f"RSS摘要过短 (<100 chars)，准备从网页获取: {url}")
                    # 对于ESSD，只要RSS提供了摘要（即使很短），就不再从网页抓取

                    if should_fetch_web:
                        if url:
                            logger.info(f"开始从网页获取摘要: {url}")
                            # 使用 AbstractFetcher 获取摘要
                            web_abstract_data = self.abstract_fetcher.fetch_abstract(url, journal_name=current_journal_name)
                            if web_abstract_data and web_abstract_data.get('abstract'): # 检查字典和 'abstract' 键
                                fetched_web_abstract = web_abstract_data['abstract']
                                # 只有当网页抓取的摘要比RSS的长时才替换
                                if len(fetched_web_abstract) > len(abstract):
                                    logger.info(f"使用网页获取的更长摘要替换RSS摘要")
                                    abstract = fetched_web_abstract # 使用网页获取的摘要
                                else:
                                    logger.info(f"网页获取的摘要不比RSS摘要长，保留RSS摘要")
                            else:
                                logger.warning(f"无法从网页获取有效摘要")
                        else:
                            logger.warning(f"摘要缺失/过短且无URL，无法从网页获取")
                    elif abstract and current_journal_name == "Earth System Science Data":
                        logger.info(f"ESSD期刊已有RSS摘要，跳过网页抓取")

                    # 格式化日期
                    formatted_date = self.format_date(pub_date_str, journal_name)
                    
                    # 创建论文数据字典
                    paper_data = {
                        "journal": current_journal_name,
                        "title": title,
                        "abstract": abstract,
                        "publishDate": formatted_date,
                        "doi": doi,
                        "url": url,
                        "authors": authors,
                        "tags": ",".join(tags)
                    }
                    
                    # 保存到数据库
                    if DBHelper:
                        if doi:  # 确保有DOI
                            if DBHelper.insert_raw_paper(paper_data):
                                data_list.append([
                                    current_journal_name, title, abstract, formatted_date, doi, url, authors, ",".join(tags)
                                ])
                                db_saved_count += 1
                    else:
                        # 当数据库不可用时，直接添加到数据列表
                        data_list.append([
                            current_journal_name, title, abstract, formatted_date, doi, url, authors, ",".join(tags)
                        ])
                
                all_data.extend(data_list)
                logger.info(f"{journal_name} 爬取完成，共获取 {len(data_list)} 条数据")
            except Exception as e:
                logger.error(f"{journal_name} 爬取过程中发生错误: {e}")
        
        # 保存所有数据到CSV作为备份
        if all_data:
            self.save_to_csv(all_data)
        
        logger.info(f"所有期刊爬取完成，共获取 {len(all_data)} 条数据，其中 {db_saved_count} 条保存到数据库")
        return all_data
    
    def save_to_csv(self, data_list):
        """保存数据到CSV文件作为备份，避免重复条目"""
        headers = ["journal", "title", "abstract", "publishDate", "doi", "url", "authors", "tags"]
        # 获取当前脚本 (crawler.py) 所在的目录
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # 定义输出文件路径在当前脚本所在目录下 (即 get_data)
        output_file = os.path.join(script_dir, "raw_papers.csv")

        # 读取现有数据
        existing_data = []
        existing_doi = set()
        
        if os.path.exists(output_file):
            logger.info(f"发现现有数据文件: {output_file}")
            with open(output_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    existing_data.append(row)
                    if row["doi"]:  # 确保doi不为空
                        existing_doi.add(row["doi"])
        
        # 追加新数据（去重）
        new_rows = []
        for data in data_list:
            if data[4] and data[4] not in existing_doi:  # data[4]是doi
                new_rows.append(dict(zip(headers, data)))
        
        if len(existing_data) == 0:
            # 如果没有现有数据，创建新文件
            with open(output_file, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                writer.writerows(new_rows)
        else:
            # 如果文件已存在且有数据，只追加新数据，不覆盖原有文件
            with open(output_file, "a", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writerows(new_rows)
        
        logger.info(f"数据同时保存到CSV文件 {output_file}，{len(new_rows)} 条新记录, 共 {len(existing_data) + len(new_rows)} 条记录")
        self.last_added_count = len(new_rows)  # 更新新添加记录数
        return len(new_rows)

def main():
    """主函数"""
    # 初始化数据库表
    if DBHelper:
        DBHelper.initialize_tables()
    
    # 爬取数据
    crawler = RSSCrawler()
    articles = crawler.crawl()
    print(f"已爬取 {len(articles)} 篇数据期刊论文")
    return articles

if __name__ == "__main__":
    main()