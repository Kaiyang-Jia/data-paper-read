#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据处理流水线

整合数据爬取、处理和服务的完整流程，提供一体化的数据更新与维护功能。
主要功能：
1. 从多个期刊RSS源爬取最新科研数据论文
2. 使用NLP处理翻译标题、生成解读及标签
3. 准备并导出处理好的数据到主应用
4. 维护数据库中的论文数据

使用方法:
python data_pipeline.py [--full-update]
"""

import os
import sys
import argparse
import logging
from datetime import datetime
import shutil
import csv
import json

# 配置日志
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 定义文件路径相对于脚本位置
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_PAPERS_CSV = os.path.join(SCRIPT_DIR, "raw_papers.csv")
PROCESSED_PAPERS_CSV = os.path.join(SCRIPT_DIR, "processed_papers.csv")
OUTPUT_JSON = os.path.join(SCRIPT_DIR, "nature_data_articles.json")
BACKUP_FOLDER = os.path.join(SCRIPT_DIR, "backups")

# 导入数据库工具类
try:
    from .db_helper import DBHelper  # 当作为包导入时
except ImportError:
    try:
        from db_helper import DBHelper  # 当在同一目录下直接运行时
    except ImportError:
        print("错误：无法导入数据库工具类，请确保 db_helper.py 文件存在")
        DBHelper = None

# 尝试导入本地模块 (使用相对导入)
try:
    from .crawler import RSSCrawler
    from .process import NLPProcessor
except ImportError as e:
    logger.error(f"导入本地模块失败: {e}")
    try:
        from crawler import RSSCrawler
        from process import NLPProcessor
    except ImportError as e2:
        logger.error(f"尝试导入本地模块失败 (绝对路径): {e2}")
        sys.exit(1)


def backup_files():
    """备份现有数据文件"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_folder = BACKUP_FOLDER

    # 确保备份文件夹存在
    if not os.path.exists(backup_folder):
        os.makedirs(backup_folder)

    # 备份文件列表
    files_to_backup = [
        {"source": RAW_PAPERS_CSV, "target": os.path.join(backup_folder, f"raw_papers_{timestamp}.csv")},
        {"source": PROCESSED_PAPERS_CSV, "target": os.path.join(backup_folder, f"processed_papers_{timestamp}.csv")},
        {"source": OUTPUT_JSON, "target": os.path.join(backup_folder, f"nature_data_articles_{timestamp}.json")}
    ]

    # 执行备份
    for file_info in files_to_backup:
        source = file_info["source"]
        target = file_info["target"]
        if os.path.exists(source):
            shutil.copy2(source, target)
            logger.info(f"数据文件已备份: {target}")
    
    return True


def convert_to_json():
    """将处理后的数据库数据转换为JSON格式"""
    json_file = OUTPUT_JSON
    logger.info(f"步骤4: 转换数据库数据到JSON格式: -> {json_file}")
    
    try:
        # 从数据库获取处理后的论文数据
        if not DBHelper:
            logger.error("数据库工具类未正确初始化，无法获取数据")
            return 0
            
        articles = DBHelper.get_all_processed_papers()
        if not articles:
            logger.error("数据库中没有找到处理后的论文数据")
            return 0
        
        # 处理数据，确保格式兼容
        for paper in articles:
            # tags字段已经在DBHelper.get_all_processed_papers()中处理过了
            pass
                
        # 写入JSON
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)
            
        logger.info(f"成功转换 {len(articles)} 条记录到 {json_file}")
        return len(articles)
    except Exception as e:
        logger.error(f"转换数据库数据到JSON失败: {e}")
        return 0


def run_pipeline(full_update=False):
    """运行数据处理流水线"""
    logger.info("开始执行数据处理流水线...")
    
    # 检查数据库是否正常初始化
    if not DBHelper:
        logger.error("数据库工具类未正确初始化，流水线执行失败")
        return False
    
    # 确保数据库表已初始化
    DBHelper.initialize_tables()
    
    # 步骤1: 备份现有数据文件（作为额外备份）
    logger.info("步骤1: 备份现有数据文件")
    backup_files()
    
    # 步骤2: 爬取最新数据并保存到数据库
    logger.info("步骤2: 爬取最新数据并保存到数据库")
    try:
        crawler = RSSCrawler()
        articles = crawler.crawl()
        
        # 检查是否有新数据，如果没有且不是全量更新，则跳过后续步骤
        if crawler.last_added_count == 0 and not full_update:
            logger.info("没有发现新数据，跳过后续处理步骤")
            # 但仍需要生成JSON文件供前端使用
            convert_to_json()
            return True
    except Exception as e:
        logger.error(f"爬取数据失败: {e}")
        return False
        
    # 步骤3: NLP处理数据并保存到数据库
    logger.info("步骤3: 处理数据 (NLP处理)")
    try:
        # 创建处理器，指定备份文件路径
        processor = NLPProcessor(
            input_csv=RAW_PAPERS_CSV, 
            output_csv=PROCESSED_PAPERS_CSV,
            backup_folder=BACKUP_FOLDER
        )
        # 处理数据
        processor.process_papers()
    except Exception as e:
        logger.error(f"处理数据失败: {e}")
        return False
        
    # 步骤4: 从数据库导出数据到JSON
    count = convert_to_json()
    if count == 0:
        logger.error("数据库到JSON转换失败或无数据")
        return False
        
    logger.info(f"数据处理流水线执行完成! 共处理 {count} 条记录")
    return True


if __name__ == "__main__":
    # 命令行参数
    parser = argparse.ArgumentParser(description="数据论文处理流水线")
    parser.add_argument("--full-update", action="store_true", help="执行全量更新而非增量更新")
    args = parser.parse_args()
    
    # 运行流水线
    success = run_pipeline(full_update=args.full_update)
    
    if not success:
        logger.error("流水线执行失败")
        sys.exit(1)
    else:
        logger.info("数据流水线处理成功完成！")