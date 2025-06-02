#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库配置模块

为数据科研论文索引系统提供数据库连接配置信息。
使用环境变量或默认配置进行数据库连接。
"""

import os
import logging
from dotenv import load_dotenv
load_dotenv()
# 配置日志
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 从环境变量获取数据库配置
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_USER = os.environ.get('DB_USER', 'root')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
DB_NAME = os.environ.get('DB_NAME', 'paper_data')
DB_PORT = int(os.environ.get('DB_PORT', 3306))

# 数据库配置字典
DB_CONFIG = {
    'host': DB_HOST,
    'user': DB_USER,
    'password': DB_PASSWORD,
    'database': DB_NAME,
    'charset': 'utf8mb4',
    'port': DB_PORT
}

def get_db_url():
    """获取SQLAlchemy格式的数据库URL"""
    return f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

def print_db_info():
    """打印数据库连接信息（不显示密码）"""
    safe_config = DB_CONFIG.copy()
    safe_config['password'] = '******' if DB_CONFIG['password'] else '[empty]'
    
    logger.info(f"数据库配置: {safe_config}")

# 在导入模块时打印数据库信息（调试用）
if __name__ == "__main__":
    print_db_info()