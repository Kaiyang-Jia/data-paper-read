#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库辅助工具类

为数据科研论文索引系统提供数据库操作封装，包括：
1. 数据库连接与初始化
2. 原始论文数据的存储与检索
3. 处理后论文数据的存储与检索
4. 按条件查询和过滤数据
"""

import os
import logging
import pymysql
from datetime import datetime
import json

# 导入数据库配置
try:
    from .db_config import DB_CONFIG, print_db_info
except ImportError:
    try:
        from db_config import DB_CONFIG, print_db_info
    except ImportError:
        print("错误：无法导入数据库配置，请确保 db_config.py 文件存在")
        DB_CONFIG = {
            'host': 'localhost',
            'user': 'root',
            'password': '',
            'database': 'data_paper',
            'charset': 'utf8mb4',
            'port': 3306
        }
        
        def print_db_info():
            print(f"使用默认数据库配置: {DB_CONFIG}")

# 配置日志
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class DBHelper:
    """数据库辅助工具类，提供数据库操作封装"""
    
    @staticmethod
    def get_connection():
        """获取数据库连接"""
        try:
            connection = pymysql.connect(**DB_CONFIG)
            return connection
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            return None
    
    @staticmethod
    def initialize_tables():
        """初始化数据库表"""
        connection = DBHelper.get_connection()
        if not connection:
            logger.error("无法连接到数据库，表初始化失败")
            return False
            
        try:
            with connection.cursor() as cursor:
                # 创建原始论文数据表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS raw_papers (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        title VARCHAR(500) NOT NULL,
                        abstract TEXT,
                        publishDate VARCHAR(20),
                        doi VARCHAR(255) UNIQUE,
                        url VARCHAR(500),
                        authors VARCHAR(500),
                        tags TEXT,
                        journal VARCHAR(255),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        INDEX idx_doi (doi),
                        INDEX idx_journal (journal),
                        INDEX idx_date (publishDate)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)
                
                # 创建处理后论文数据表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS processed_papers (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        title VARCHAR(500) NOT NULL,
                        titleCn VARCHAR(500),
                        interpretationCn TEXT,
                        abstract TEXT,
                        publishDate VARCHAR(20),
                        doi VARCHAR(255) UNIQUE,
                        url VARCHAR(500),
                        authors VARCHAR(500),
                        tags TEXT,
                        Subject VARCHAR(50),
                        journal VARCHAR(255),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        INDEX idx_doi (doi),
                        INDEX idx_subject (Subject),
                        INDEX idx_journal (journal),
                        INDEX idx_date (publishDate)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)
                
                connection.commit()
                logger.info("数据库表初始化完成")
                return True
        except Exception as e:
            logger.error(f"数据库表初始化失败: {e}")
            return False
        finally:
            connection.close()
    
    @staticmethod
    def insert_raw_paper(paper_data):
        """
        将原始论文数据插入数据库
        
        参数:
            paper_data (dict): 包含论文数据的字典
            
        返回:
            bool: 是否成功
        """
        connection = DBHelper.get_connection()
        if not connection:
            logger.error("无法连接到数据库，原始论文数据插入失败")
            return False
            
        try:
            with connection.cursor() as cursor:
                # 检查是否已存在相同DOI的记录
                cursor.execute(
                    "SELECT COUNT(*) FROM raw_papers WHERE doi = %s",
                    (paper_data.get('doi', ''),)
                )
                count = cursor.fetchone()[0]
                
                if count > 0:
                    # 更新现有记录
                    cursor.execute("""
                        UPDATE raw_papers SET
                        title = %s,
                        abstract = %s,
                        publishDate = %s,
                        url = %s,
                        authors = %s,
                        tags = %s,
                        journal = %s,
                        updated_at = NOW()
                        WHERE doi = %s
                    """, (
                        paper_data.get('title', ''),
                        paper_data.get('abstract', ''),
                        paper_data.get('publishDate', ''),
                        paper_data.get('url', ''),
                        paper_data.get('authors', ''),
                        paper_data.get('tags', ''),
                        paper_data.get('journal', ''),
                        paper_data.get('doi', '')
                    ))
                    logger.info(f"更新原始论文数据，DOI: {paper_data.get('doi', '')}")
                else:
                    # 插入新记录
                    cursor.execute("""
                        INSERT INTO raw_papers (
                            title, abstract, publishDate, doi, url, authors, tags, journal
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        paper_data.get('title', ''),
                        paper_data.get('abstract', ''),
                        paper_data.get('publishDate', ''),
                        paper_data.get('doi', ''),
                        paper_data.get('url', ''),
                        paper_data.get('authors', ''),
                        paper_data.get('tags', ''),
                        paper_data.get('journal', '')
                    ))
                    logger.info(f"插入新的原始论文数据，DOI: {paper_data.get('doi', '')}")
                
                connection.commit()
                return True
        except Exception as e:
            logger.error(f"原始论文数据操作失败: {e}")
            connection.rollback()
            return False
        finally:
            connection.close()
    
    @staticmethod
    def insert_processed_paper(paper_data):
        """
        将处理后的论文数据插入数据库
        
        参数:
            paper_data (dict): 包含处理后论文数据的字典
            
        返回:
            bool: 是否成功
        """
        connection = DBHelper.get_connection()
        if not connection:
            logger.error("无法连接到数据库，处理后论文数据插入失败")
            return False
            
        try:
            # 如果tags是列表，将其转换为字符串
            tags = paper_data.get('tags', '')
            if isinstance(tags, list):
                tags = ','.join(tags)
            
            with connection.cursor() as cursor:
                # 检查是否已存在相同DOI的记录
                cursor.execute(
                    "SELECT COUNT(*) FROM processed_papers WHERE doi = %s",
                    (paper_data.get('doi', ''),)
                )
                count = cursor.fetchone()[0]
                
                if count > 0:
                    # 更新现有记录
                    cursor.execute("""
                        UPDATE processed_papers SET
                        title = %s,
                        titleCn = %s,
                        interpretationCn = %s,
                        abstract = %s,
                        publishDate = %s,
                        url = %s,
                        authors = %s,
                        tags = %s,
                        Subject = %s,
                        journal = %s,
                        updated_at = NOW()
                        WHERE doi = %s
                    """, (
                        paper_data.get('title', ''),
                        paper_data.get('titleCn', ''),
                        paper_data.get('interpretationCn', ''),
                        paper_data.get('abstract', ''),
                        paper_data.get('publishDate', ''),
                        paper_data.get('url', ''),
                        paper_data.get('authors', ''),
                        tags,
                        paper_data.get('Subject', ''),
                        paper_data.get('journal', ''),
                        paper_data.get('doi', '')
                    ))
                    logger.info(f"更新处理后论文数据，DOI: {paper_data.get('doi', '')}")
                else:
                    # 插入新记录
                    cursor.execute("""
                        INSERT INTO processed_papers (
                            title, titleCn, interpretationCn, abstract, publishDate, doi,
                            url, authors, tags, Subject, journal
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        paper_data.get('title', ''),
                        paper_data.get('titleCn', ''),
                        paper_data.get('interpretationCn', ''),
                        paper_data.get('abstract', ''),
                        paper_data.get('publishDate', ''),
                        paper_data.get('doi', ''),
                        paper_data.get('url', ''),
                        paper_data.get('authors', ''),
                        tags,
                        paper_data.get('Subject', ''),
                        paper_data.get('journal', '')
                    ))
                    logger.info(f"插入新的处理后论文数据，DOI: {paper_data.get('doi', '')}")
                
                connection.commit()
                return True
        except Exception as e:
            logger.error(f"处理后论文数据操作失败: {e}")
            connection.rollback()
            return False
        finally:
            connection.close()
    
    @staticmethod
    def get_all_raw_papers():
        """获取所有原始论文数据"""
        connection = DBHelper.get_connection()
        if not connection:
            logger.error("无法连接到数据库，获取原始论文数据失败")
            return []
            
        try:
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute("SELECT * FROM raw_papers ORDER BY publishDate DESC")
                papers = cursor.fetchall()
                
                # 处理tags字段，将其转换为列表
                for paper in papers:
                    if 'tags' in paper and paper['tags']:
                        paper['tags'] = paper['tags'].split(',')
                    else:
                        paper['tags'] = []
                    
                    # 移除不需要的时间戳字段
                    if 'created_at' in paper:
                        del paper['created_at']
                    if 'updated_at' in paper:
                        del paper['updated_at']
                
                return papers
        except Exception as e:
            logger.error(f"获取原始论文数据失败: {e}")
            return []
        finally:
            connection.close()
    
    @staticmethod
    def get_all_processed_papers():
        """获取所有处理后的论文数据"""
        connection = DBHelper.get_connection()
        if not connection:
            logger.error("无法连接到数据库，获取处理后论文数据失败")
            return []
            
        try:
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute("SELECT * FROM processed_papers ORDER BY publishDate DESC")
                papers = cursor.fetchall()
                
                # 处理tags字段，将其转换为列表
                for paper in papers:
                    if 'tags' in paper and paper['tags']:
                        paper['tags'] = paper['tags'].split(',')
                    else:
                        paper['tags'] = []
                    
                    # 移除不需要的时间戳字段
                    if 'created_at' in paper:
                        del paper['created_at']
                    if 'updated_at' in paper:
                        del paper['updated_at']
                    if 'id' in paper:
                        del paper['id']
                
                return papers
        except Exception as e:
            logger.error(f"获取处理后论文数据失败: {e}")
            return []
        finally:
            connection.close()
    
    @staticmethod
    def get_unprocessed_raw_papers():
        """获取未处理的原始论文数据（存在于raw_papers但不在processed_papers中）"""
        connection = DBHelper.get_connection()
        if not connection:
            logger.error("无法连接到数据库，获取未处理论文数据失败")
            return []
            
        try:
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute("""
                    SELECT r.* 
                    FROM raw_papers r
                    LEFT JOIN processed_papers p ON r.doi = p.doi
                    WHERE p.doi IS NULL
                    ORDER BY r.publishDate DESC
                """)
                papers = cursor.fetchall()
                
                # 处理tags字段，将其转换为列表
                for paper in papers:
                    if 'tags' in paper and paper['tags']:
                        paper['tags'] = paper['tags'].split(',')
                    else:
                        paper['tags'] = []
                    
                    # 移除不需要的时间戳字段
                    if 'created_at' in paper:
                        del paper['created_at']
                    if 'updated_at' in paper:
                        del paper['updated_at']
                    if 'id' in paper:
                        del paper['id']
                
                return papers
        except Exception as e:
            logger.error(f"获取未处理论文数据失败: {e}")
            return []
        finally:
            connection.close()
    
    @staticmethod
    def get_processed_papers_by_subject(subject):
        """
        按学科分类获取处理后的论文数据
        
        参数:
            subject (str): 学科分类名称
            
        返回:
            list: 包含符合条件的论文数据字典的列表
        """
        connection = DBHelper.get_connection()
        if not connection:
            logger.error("无法连接到数据库，按学科获取论文数据失败")
            return []
            
        try:
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute("""
                    SELECT * FROM processed_papers
                    WHERE Subject = %s
                    ORDER BY publishDate DESC
                """, (subject,))
                papers = cursor.fetchall()
                
                # 处理tags字段，将其转换为列表
                for paper in papers:
                    if 'tags' in paper and paper['tags']:
                        paper['tags'] = paper['tags'].split(',')
                    else:
                        paper['tags'] = []
                    
                    # 移除不需要的时间戳字段
                    if 'created_at' in paper:
                        del paper['created_at']
                    if 'updated_at' in paper:
                        del paper['updated_at']
                    if 'id' in paper:
                        del paper['id']
                
                return papers
        except Exception as e:
            logger.error(f"按学科获取论文数据失败: {e}")
            return []
        finally:
            connection.close()
    
    @staticmethod
    def search_processed_papers(keyword):
        """
        搜索处理后的论文数据
        
        参数:
            keyword (str): 搜索关键词
            
        返回:
            list: 包含符合条件的论文数据字典的列表
        """
        connection = DBHelper.get_connection()
        if not connection:
            logger.error("无法连接到数据库，搜索论文数据失败")
            return []
            
        try:
            # 构建LIKE模式匹配字符串
            pattern = f"%{keyword}%"
            
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute("""
                    SELECT * FROM processed_papers
                    WHERE title LIKE %s OR
                          abstract LIKE %s OR
                          titleCn LIKE %s OR
                          interpretationCn LIKE %s OR
                          tags LIKE %s OR
                          Subject LIKE %s OR
                          journal LIKE %s OR
                          authors LIKE %s
                    ORDER BY publishDate DESC
                """, (pattern, pattern, pattern, pattern, pattern, pattern, pattern, pattern))
                papers = cursor.fetchall()
                
                # 处理tags字段，将其转换为列表
                for paper in papers:
                    if 'tags' in paper and paper['tags']:
                        paper['tags'] = paper['tags'].split(',')
                    else:
                        paper['tags'] = []
                    
                    # 移除不需要的时间戳字段
                    if 'created_at' in paper:
                        del paper['created_at']
                    if 'updated_at' in paper:
                        del paper['updated_at']
                    if 'id' in paper:
                        del paper['id']
                
                return papers
        except Exception as e:
            logger.error(f"搜索论文数据失败: {e}")
            return []
        finally:
            connection.close()
            
    @staticmethod
    def get_processed_paper_by_doi(doi):
        """
        通过DOI获取处理后的论文数据
        
        参数:
            doi (str): 论文DOI
            
        返回:
            dict: 包含论文数据的字典，如果未找到则返回None
        """
        connection = DBHelper.get_connection()
        if not connection:
            logger.error("无法连接到数据库，通过DOI获取论文数据失败")
            return None
            
        try:
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute("SELECT * FROM processed_papers WHERE doi = %s", (doi,))
                paper = cursor.fetchone()
                
                if paper:
                    # 处理tags字段，将其转换为列表
                    if 'tags' in paper and paper['tags']:
                        paper['tags'] = paper['tags'].split(',')
                    else:
                        paper['tags'] = []
                    
                    # 移除不需要的时间戳字段
                    if 'created_at' in paper:
                        del paper['created_at']
                    if 'updated_at' in paper:
                        del paper['updated_at']
                    if 'id' in paper:
                        del paper['id']
                
                return paper
        except Exception as e:
            logger.error(f"通过DOI获取论文数据失败: {e}")
            return None
        finally:
            connection.close()

    @staticmethod
    def get_all_subjects():
        """
        获取系统中所有使用的学科分类
        
        返回:
            list: 包含所有学科分类的列表
        """
        connection = DBHelper.get_connection()
        if not connection:
            logger.error("无法连接到数据库，获取学科分类失败")
            return []
            
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT DISTINCT Subject FROM processed_papers WHERE Subject IS NOT NULL AND Subject != ''")
                subjects = [row[0] for row in cursor.fetchall()]
                return subjects
        except Exception as e:
            logger.error(f"获取学科分类失败: {e}")
            return []
        finally:
            connection.close()

if __name__ == "__main__":
    # 测试数据库连接和表初始化
    print_db_info()
    success = DBHelper.initialize_tables()
    print(f"数据库表初始化: {'成功' if success else '失败'}")
    
    # 可以添加其他测试代码
    subjects = DBHelper.get_all_subjects()
    print(f"系统中的学科分类: {subjects}")