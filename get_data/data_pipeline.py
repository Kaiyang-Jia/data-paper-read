#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据处理流水线

整合数据爬取、处理和服务的完整流程，提供一体化的数据更新与维护功能。
主要功能：
1. 从多个期刊RSS源爬取最新科研数据论文
2. 使用NLP处理翻译标题、生成解读及标签
3. 直接将处理好的数据保存到数据库

使用方法:
python data_pipeline.py [--full-update]
"""

import os
import sys
import argparse
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 定义文件路径相对于脚本位置
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

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


def run_pipeline(full_update=False):
    """运行数据处理流水线"""
    logger.info("开始执行数据处理流水线...")
    
    # 检查数据库是否正常初始化
    if not DBHelper:
        logger.error("数据库工具类未正确初始化，流水线执行失败")
        return False, 0
    
    # 确保数据库表已初始化
    DBHelper.initialize_tables()
    
    # 步骤1: 爬取最新数据并保存到数据库
    logger.info("步骤1: 爬取最新数据并保存到数据库")
    try:
        crawler = RSSCrawler()
        articles = crawler.crawl()
        
        # 检查是否有新数据
        has_new_articles = crawler.last_added_count > 0
        
        # 检查是否有未处理的原始论文
        unprocessed_count = 0
        try:
            unprocessed_papers = DBHelper.get_unprocessed_raw_papers()
            unprocessed_count = len(unprocessed_papers) if unprocessed_papers else 0
            if unprocessed_count > 0:
                logger.info(f"发现 {unprocessed_count} 条未处理的原始论文数据")
        except Exception as e:
            logger.error(f"检查未处理论文时出错: {e}")
        
        # 如果没有新数据且没有未处理的论文，并且不是全量更新，则跳过后续步骤
        if not has_new_articles and unprocessed_count == 0 and not full_update:
            logger.info("没有发现新数据或未处理的论文，跳过后续处理步骤")
            return True, 0
    except Exception as e:
        logger.error(f"爬取数据失败: {e}")
        return False, 0
        
    # 步骤2: NLP处理数据并保存到数据库
    logger.info("步骤2: 处理数据 (NLP处理)")
    try:
        # 创建处理器，移除文件路径参数
        processor = NLPProcessor()
        # 处理数据
        processed_count = processor.process_papers()
    except Exception as e:
        logger.error(f"处理数据失败: {e}")
        return False, 0
    
    logger.info(f"数据处理流水线执行完成! 共处理 {processed_count} 条记录")
    return True, processed_count


def update_database(generate_json=False):
    """更新数据库中的论文数据，返回更新的记录数量"""
    try:
        success, count = run_pipeline(full_update=False)
        return count if success else 0
    except Exception as e:
        logger.error(f"数据库更新失败: {e}")
        return 0


if __name__ == "__main__":
    # 命令行参数
    parser = argparse.ArgumentParser(description="数据论文处理流水线")
    parser.add_argument("--full-update", action="store_true", help="执行全量更新而非增量更新")
    args = parser.parse_args()
    
    # 运行流水线
    success, count = run_pipeline(full_update=args.full_update)
    
    if not success:
        logger.error("流水线执行失败")
        sys.exit(1)
    else:
        logger.info(f"数据流水线处理成功完成！更新了 {count} 条记录")