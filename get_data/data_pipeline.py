#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据处理流水线

整合数据爬取、处理和服务的完整流程，提供一体化的数据更新与维护功能。
主要功能：
1. 从多个期刊RSS源爬取最新科研数据论文
2. 使用NLP处理翻译标题、生成解读及标签
3. 准备并导出处理好的数据到主应用

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

# --- 修改开始: 定义文件路径相对于脚本位置 ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_PAPERS_CSV = os.path.join(SCRIPT_DIR, "raw_papers.csv")
PROCESSED_PAPERS_CSV = os.path.join(SCRIPT_DIR, "processed_papers.csv")
OUTPUT_JSON = os.path.join(SCRIPT_DIR, "nature_data_articles.json")
BACKUP_FOLDER = os.path.join(SCRIPT_DIR, "backups")
# --- 修改结束 ---

# 尝试导入本地模块 (使用相对导入)
try:
    from .crawler import RSSCrawler
    from .process import NLPProcessor
except ImportError as e:
    logger.error(f"导入本地模块失败: {e}")


def backup_files():
    """备份现有数据文件"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # --- 修改开始: 使用定义的备份文件夹路径 ---
    backup_folder = BACKUP_FOLDER
    # --- 修改结束 ---

    # 确保备份文件夹存在
    if not os.path.exists(backup_folder):
        os.makedirs(backup_folder)

    # 备份文件列表
    # --- 修改开始: 使用定义的文件路径常量 ---
    files_to_backup = [
        {"source": RAW_PAPERS_CSV, "target": os.path.join(backup_folder, f"raw_papers_{timestamp}.csv")},
        {"source": PROCESSED_PAPERS_CSV, "target": os.path.join(backup_folder, f"processed_papers_{timestamp}.csv")},
        {"source": OUTPUT_JSON, "target": os.path.join(backup_folder, f"nature_data_articles_{timestamp}.json")}
    ]
    # --- 修改结束 ---

    # 执行备份
    for file_info in files_to_backup:
        source = file_info["source"]
        target = file_info["target"]
        if os.path.exists(source):
            shutil.copy2(source, target)
            logger.info(f"数据文件已备份: {target}")
    
    return True


def convert_csv_to_json():
    """将处理后的CSV数据转换为JSON格式"""
    # --- 修改开始: 使用定义的文件路径常量 ---
    csv_file = PROCESSED_PAPERS_CSV
    json_file = OUTPUT_JSON
    # --- 修改结束 ---

    logger.info(f"步骤4: 转换CSV到JSON格式: {csv_file} -> {json_file}")
    
    try:
        # 读取CSV
        articles = []
        # --- 修改开始: 使用定义的文件路径常量 ---
        with open(csv_file, 'r', encoding='utf-8') as f:
        # --- 修改结束 ---
            reader = csv.DictReader(f)
            for row in reader:
                # 处理标签字段
                if row.get('tags'):
                    row['tags'] = [tag.strip() for tag in row['tags'].split(',') if tag.strip()]
                else:
                    row['tags'] = []
                    
                # 确保日期字段格式统一
                if 'publishDate' in row:
                    row['date'] = row['publishDate']
                    
                # 添加到结果列表
                articles.append(row)
                
        # 写入JSON
        # --- 修改开始: 使用定义的文件路径常量 ---
        with open(json_file, 'w', encoding='utf-8') as f:
        # --- 修改结束 ---
            json.dump(articles, f, ensure_ascii=False, indent=2)
            
        logger.info(f"成功转换 {len(articles)} 条记录到 {json_file}")
        return len(articles)
    except Exception as e:
        logger.error(f"转换CSV到JSON失败: {e}")
        return 0


def run_pipeline(full_update=False):
    """运行数据处理流水线"""
    logger.info("开始执行数据处理流水线...")
    
    # 步骤1: 备份现有数据
    logger.info("步骤1: 备份现有数据")
    backup_files()
    
    # 步骤2: 爬取最新数据
    logger.info("步骤2: 爬取最新数据")
    try:
        crawler = RSSCrawler()
        crawler.crawl()
        
        # 检查是否有新数据，如果没有且不是全量更新，则跳过后续步骤
        if crawler.last_added_count == 0 and not full_update:
            logger.info("没有发现新数据，跳过后续处理步骤")
            return True
    except Exception as e:
        logger.error(f"爬取数据失败: {e}")
        return False
        
    # 步骤3: NLP处理数据
    logger.info("步骤3: 处理数据 (NLP处理)")
    try:
        # --- 修改开始: 传递正确的输入输出路径给 NLPProcessor ---
        # 注意: NLPProcessor 内部也需要修改以接受这些路径参数
        # 这里暂时假设 NLPProcessor 构造函数或 process_papers 方法可以接受路径
        # 如果 NLPProcessor 内部写死了文件名，则需要修改 NLPProcessor
        processor = NLPProcessor()
        # 假设 process_papers 接受 input_csv 和 output_csv 参数
        # processor.process_papers(input_csv=RAW_PAPERS_CSV, output_csv=PROCESSED_PAPERS_CSV)
        # 或者修改 NLPProcessor 的 __init__
        processor.input_csv = RAW_PAPERS_CSV
        processor.output_csv = PROCESSED_PAPERS_CSV
        processor.backup_folder = BACKUP_FOLDER # 确保备份也使用正确的路径
        # --- 修改结束 ---
        processor.process_papers()
    except Exception as e:
        logger.error(f"处理数据失败: {e}")
        return False
        
    # 步骤4: 转换CSV到JSON
    count = convert_csv_to_json()
    if count == 0:
        logger.error("CSV到JSON转换失败或无数据")
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