#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据处理流水线管理模块

整合数据爬取、处理和服务的完整流程，提供一体化的数据更新与维护功能。
主要功能：
1. 从Nature RSS源爬取最新科研数据论文
2. 使用NLP处理翻译标题、生成解读及标签
3. 准备并导出处理好的数据到主应用

使用方法:
python data_pipeline.py [--full-update] [--serve]
"""

import os
import argparse
import logging
import shutil
import time
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 导入本地模块
try:
    # 尝试使用当前实际的文件名导入
    from crawler import NatureRSSCrawler
    from process import NLPProcessor
    logger.info("成功导入 crawler 和 process 模块")
except ImportError as e:
    logger.error(f"导入本地模块失败: {e}")
    # 如果需要，可以在这里添加备用导入逻辑或退出
    # 例如，尝试导入重命名后的文件
    # try:
    #     from nature_rss_crawler import NatureRSSCrawler
    #     from nlp_processor import NLPProcessor
    #     logger.info("成功导入 nature_rss_crawler 和 nlp_processor 模块")
    # except ImportError:
    #     logger.critical("无法找到必要的爬虫或处理模块，请检查文件是否存在且名称正确！")
    #     # 可以选择退出程序
    #     # import sys
    #     # sys.exit(1)
    # 设置为 None 或引发异常，以便后续代码知道导入失败
    NatureRSSCrawler = None
    NLPProcessor = None

def backup_data_files():
    """备份现有数据文件"""
    try:
        backup_dir = "backups"
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 备份原始数据文件
        if os.path.exists("raw_papers.csv"):
            backup_file = f"{backup_dir}/raw_papers_{timestamp}.csv"
            shutil.copy2("raw_papers.csv", backup_file)
            logger.info(f"原始数据文件已备份: {backup_file}")
            
        # 备份处理后的数据文件
        if os.path.exists("processed_papers.csv"):
            backup_file = f"{backup_dir}/processed_papers_{timestamp}.csv"
            shutil.copy2("processed_papers.csv", backup_file)
            logger.info(f"处理后数据文件已备份: {backup_file}")
            
        return True
    except Exception as e:
        logger.error(f"备份数据文件失败: {e}")
        return False

def export_to_main_app():
    """将处理好的数据导出为JSON文件到get_data目录"""
    try:
        src_file = "processed_papers.csv"
        if not os.path.exists(src_file):
            logger.error(f"源文件不存在: {src_file}")
            return False
            
        # 目标文件路径 (当前目录下)
        target_file = "nature_data_articles.json"
        
        # 转换CSV到JSON并导出
        import csv
        import json
        
        articles = []
        with open(src_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # 转换标签字符串为列表
                if "tags" in row and row["tags"]:
                    row["tags"] = [tag.strip() for tag in row["tags"].split(",")]
                articles.append(row)
                
        # 写入JSON文件
        with open(target_file, "w", encoding="utf-8") as f:
            json.dump(articles, f, ensure_ascii=False, indent=4)
            
        logger.info(f"数据已成功导出到: {target_file}")
        logger.info(f"共导出 {len(articles)} 篇论文数据")
        return True
    except Exception as e:
        logger.error(f"导出数据失败: {e}")
        return False

def run_full_pipeline(): # Removed serve=False parameter
    """执行完整数据处理流水线"""
    logger.info("开始执行数据处理流水线...")
    
    # 步骤1: 备份现有数据文件
    logger.info("步骤1: 备份现有数据")
    backup_data_files()
    
    # 步骤2: 爬取最新数据
    logger.info("步骤2: 爬取最新数据")
    try:
        crawler = NatureRSSCrawler()
        articles = crawler.crawl()
        logger.info(f"成功爬取 {len(articles)} 篇论文")
    except Exception as e:
        logger.error(f"爬取数据失败: {e}")
        return False
    
    # 步骤3: NLP处理数据
    logger.info("步骤3: NLP处理数据")
    try:
        processor = NLPProcessor()
        success = processor.process_papers()
        if not success:
            logger.error("NLP处理数据失败")
            return False
    except Exception as e:
        logger.error(f"NLP处理数据异常: {e}")
        return False

    # 步骤4: 导出到JSON文件
    logger.info("步骤4: 导出数据到JSON文件")
    export_success = export_to_main_app()
    if not export_success:
        logger.warning("导出数据到JSON文件失败")
    
    logger.info("数据处理流水线执行完毕")
    return True

def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="Nature科研数据论文处理流水线")
    parser.add_argument("--full-update", action="store_true", help="执行完整的数据更新流程")
    args = parser.parse_args()
    
    if args.full_update:  # 修正 full-update 为 full_update（下划线而非连字符）
        run_full_pipeline()
    else:
        logger.info("使用 --full-update 参数执行完整数据处理流程")

if __name__ == "__main__":
    main()