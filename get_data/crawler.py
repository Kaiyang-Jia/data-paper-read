#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Nature RSS爬虫模块

自动爬取Nature Scientific Data期刊的RSS源，获取最新发布的数据论文信息。
输出原始数据到raw_papers.csv中，供后续处理。
"""

import feedparser
import csv
import os
from datetime import datetime
from bs4 import BeautifulSoup
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class NatureRSSCrawler:
    """Nature RSS爬虫类"""
    
    def __init__(self):
        self.rss_url = "https://www.nature.com/sdata.rss"
        self.output_file = "raw_papers.csv"
    
    def clean_abstract(self, raw_abstract, title):
        """清理HTML和冗余标题"""
        # 移除HTML标签
        soup = BeautifulSoup(raw_abstract, "html.parser")
        text = soup.get_text()
        # 移除标题（常重复）
        text = text.replace(title, "").strip()
        # 移除元数据（如"Scientific Data, Published online..."）
        lines = [line for line in text.split("\n") if not line.startswith("Scientific Data,")]
        return " ".join(lines).strip()
    
    def format_date(self, pub_date):
        """格式化日期字符串"""
        try:
            # 尝试常见的RSS日期格式
            date_formats = [
                "%a, %d %b %Y %H:%M:%S %Z",
                "%Y-%m-%dT%H:%M:%SZ"
            ]
            
            for fmt in date_formats:
                try:
                    return datetime.strptime(pub_date, fmt).strftime("%Y-%m-%d")
                except ValueError:
                    continue
                    
            # 如果所有格式都失败，返回当前日期
            logger.warning(f"无法解析日期格式: {pub_date}，使用当前日期")
            return datetime.now().strftime("%Y-%m-%d")
        except Exception as e:
            logger.error(f"日期格式化错误: {e}")
            return datetime.now().strftime("%Y-%m-%d")
    
    def crawl(self):
        """执行RSS爬取"""
        logger.info(f"开始爬取Nature Scientific Data RSS: {self.rss_url}")
        try:
            feed = feedparser.parse(self.rss_url)
            data_list = []
            
            logger.info(f"RSS包含 {len(feed.entries)} 条条目")
            for entry in feed.entries:
                title = entry.get("title", "Unknown")
                raw_abstract = entry.get("description", "")
                abstract = self.clean_abstract(raw_abstract, title)
                pub_date = entry.get("published", "")
                doi = entry.get("dc_identifier", "").replace("doi:", "") if "dc_identifier" in entry else ""
                url = entry.get("link", "")
                authors = entry.get("author", "Unknown")
                tags = entry.get("category", "").split(",") if "category" in entry else []
                
                # 格式化日期
                formatted_date = self.format_date(pub_date)
                
                data_list.append([
                    title, abstract, formatted_date, doi, url, authors, ",".join(tags)
                ])
            
            # 保存数据
            self.save_to_csv(data_list)
            logger.info(f"爬取完成，共获取 {len(data_list)} 条数据")
            return data_list
        except Exception as e:
            logger.error(f"爬取过程中发生错误: {e}")
            return []
    
    def save_to_csv(self, data_list):
        """保存数据到CSV文件，避免重复条目"""
        headers = ["title", "abstract", "publishDate", "doi", "url", "authors", "tags"]
        # 读取现有数据
        existing_data = []
        existing_doi = set()
        
        if os.path.exists(self.output_file):
            logger.info(f"发现现有数据文件: {self.output_file}")
            with open(self.output_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    existing_data.append(row)
                    if row["doi"]:  # 确保doi不为空
                        existing_doi.add(row["doi"])
            
        # 追加新数据（去重）
        new_rows = []
        for data in data_list:
            if data[3] and data[3] not in existing_doi:  # data[3]是doi
                new_rows.append(dict(zip(headers, data)))
        
        # 写入CSV
        with open(self.output_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(existing_data + new_rows)
        
        logger.info(f"数据保存到 {self.output_file}，{len(new_rows)} 条新记录, 共 {len(existing_data) + len(new_rows)} 条记录")
        return len(new_rows)

def main():
    """主函数"""
    crawler = NatureRSSCrawler()
    articles = crawler.crawl()
    print(f"已爬取 {len(articles)} 篇Nature数据期刊论文")
    return articles

if __name__ == "__main__":
    main()