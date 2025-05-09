#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Flask, render_template, request, jsonify
import json
import os
import subprocess
import sys
import logging
import datetime
import csv

# 导入数据库工具类
try:
    from get_data.db_helper import DBHelper
except ImportError as e:
    DBHelper = None
    print(f"警告：无法导入数据库工具类，将回退到使用JSON文件: {e}")

# 配置日志
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='src/templates')

# 全局变量存储数据
CACHE_FILE = os.path.join('get_data', 'nature_data_articles.json') # 作为备份和回退方案
articles_data = []

# 反馈存储文件
FEEDBACK_FILE = 'user_feedback.csv'

def load_from_database():
    """从数据库加载数据"""
    global articles_data
    try:
        if DBHelper:
            logger.info("正在从数据库加载数据...")
            db_articles = DBHelper.get_all_processed_papers()
            if db_articles and len(db_articles) > 0:
                articles_data = db_articles
                logger.info(f"成功从数据库加载了 {len(articles_data)} 篇论文数据")
                return True
            else:
                logger.warning("数据库中没有找到论文数据")
                return False
        else:
            logger.warning("数据库工具类未初始化，无法从数据库加载数据")
            return False
    except Exception as e:
        logger.error(f"从数据库加载数据时出错: {e}")
        return False

def load_cached_data():
    """
    从缓存文件中加载数据（作为备份或回退方案）
    """
    global articles_data
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                articles_data = json.load(f)
            logger.info(f"成功从缓存文件加载了 {len(articles_data)} 篇论文数据")
            return len(articles_data) > 0
        logger.warning(f"缓存文件不存在: {CACHE_FILE}")
        return False
    except Exception as e:
        logger.error(f"加载缓存数据时出错: {e}")
        return False

def update_data(full_update=False):
    """
    使用数据管道更新数据
    Args:
        full_update (bool): 是否执行全量更新，默认为False(增量更新)
    Returns:
        tuple: (成功与否, 新增文章数)
    """
    try:
        # 获取更新前的文章数量
        old_count = len(articles_data)
        
        # 获取当前时间，用于计算更新耗时
        start_time = datetime.datetime.now()
        
        # 获取项目根目录路径
        project_root = os.path.dirname(os.path.abspath(__file__))
        
        # 使用 python -m 方式调用模块以解决相对导入问题
        update_type = "全量更新" if full_update else "增量更新"
        logger.info(f"启动数据更新流程... 更新类型: {update_type}, 更新时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        cmd = [sys.executable, "-m", "get_data.data_pipeline"]
        if full_update:
            cmd.append("--full-update")
            
        result = subprocess.run(
            cmd,
            cwd=project_root, # 确保在项目根目录执行
            capture_output=True,
            text=True,
            encoding="utf-8",  # 强制用utf-8解码
            errors="replace"   # 非法字符用?替换，防止崩溃
        )
        
        if result.returncode != 0:
            logger.error(f"数据更新失败: {result.stderr}")
            return False, 0
            
        # 提取来自命令行输出的信息
        output_lines = result.stdout.split('\n') if result.stdout else []
        for line in output_lines:
            if "成功" in line and "条记录" in line:
                logger.info(f"数据管道输出: {line.strip()}")
        
        # 优先从数据库重新加载数据，如果失败则尝试从缓存文件加载
        success = load_from_database() or load_cached_data()
        
        # 计算新增文章数
        new_count = len(articles_data) - old_count if success and old_count > 0 else len(articles_data)
        
        # 计算更新耗时
        end_time = datetime.datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info(f"数据更新完成! 更新类型: {update_type}, 新增文章数: {new_count}, 总文章数: {len(articles_data)}, 耗时: {duration:.2f}秒")
        return success, new_count
    except Exception as e:
        logger.error(f"更新数据时出错: {e}")
        return False, 0

@app.route('/')
def index():
    """
    主页视图
    """
    # 尝试优先从数据库加载数据，如果失败则尝试从缓存文件加载，如果还是没有数据则更新数据
    if not (load_from_database() or load_cached_data()):
        update_data()
    
    return render_template('index.html', articles=articles_data)

@app.route('/refresh', methods=['POST'])
def refresh_data():
    """
    刷新数据的API端点
    """
    request_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"收到数据刷新请求 - 时间: {request_time}")
    
    # 确定是否为全量更新
    full_update = request.args.get('full', 'false').lower() == 'true'
    update_type = "全量更新" if full_update else "增量更新"
    logger.info(f"即将执行{update_type}...")
    
    success, new_count = update_data(full_update)
    
    if success:
        result_message = f'成功更新 {new_count} 篇论文'
        logger.info(f"数据刷新成功: {result_message}")
        return jsonify({
            'status': 'success',
            'message': result_message,
            'count': new_count
        })
    else:
        error_message = '数据更新失败，请查看服务器日志'
        logger.error(f"数据刷新失败: {error_message}")
        return jsonify({
            'status': 'error',
            'message': error_message
        }), 500

@app.route('/articles')
def get_articles():
    """
    获取文章数据的API端点
    支持关键词过滤和学科分类过滤
    """
    # 关键词过滤
    keyword = request.args.get('keyword', '').lower()
    # 学科分类过滤
    subject = request.args.get('subject', '')
    
    # 如果DBHelper可用且有subject参数，直接从数据库按学科过滤
    if DBHelper and subject and subject != '全部':
        try:
            filtered_articles = DBHelper.get_processed_papers_by_subject(subject)
            # 如果还有关键词，再进行二次过滤
            if keyword:
                filtered_articles = [
                    article for article in filtered_articles 
                    if keyword in article.get('title', '').lower() or 
                       keyword in article.get('abstract', '').lower() or
                       keyword in article.get('titleCn', '').lower() or
                       keyword in article.get('interpretationCn', '').lower() or
                       any(keyword in tag.lower() for tag in article.get('tags', []) if isinstance(article.get('tags'), list)) or
                       (isinstance(article.get('tags'), str) and keyword in article.get('tags', '').lower())
                ]
            return jsonify(filtered_articles)
        except Exception as e:
            logger.error(f"按学科筛选数据失败: {e}")
            # 如果出错，继续使用内存中的数据作为回退
    
    # 如果DBHelper可用且只有keyword参数，直接从数据库搜索
    elif DBHelper and keyword and not subject:
        try:
            filtered_articles = DBHelper.search_processed_papers(keyword)
            return jsonify(filtered_articles)
        except Exception as e:
            logger.error(f"搜索数据失败: {e}")
            # 如果出错，继续使用内存中的数据作为回退
    
    # 否则在内存中进行过滤（回退方案）
    # 如果有学科过滤
    if subject and subject != '全部':
        filtered_articles = [article for article in articles_data if article.get('Subject') == subject]
    else:
        filtered_articles = articles_data
        
    # 如果有关键词过滤
    if keyword:
        filtered_articles = [
            article for article in filtered_articles 
            if keyword in article.get('title', '').lower() or 
               keyword in article.get('abstract', '').lower() or
               keyword in article.get('titleCn', '').lower() or
               keyword in article.get('interpretationCn', '').lower() or
               any(keyword in tag.lower() for tag in article.get('tags', []) if isinstance(article.get('tags'), list)) or
               (isinstance(article.get('tags'), str) and keyword in article.get('tags', '').lower())
        ]
    
    return jsonify(filtered_articles)

@app.route('/article/<int:index>')
def get_article(index):
    """
    获取特定文章数据的API端点
    """
    try:
        return jsonify(articles_data[index])
    except IndexError:
        return jsonify({'error': '文章不存在'}), 404

@app.route('/article/doi/<path:doi>')
def get_article_by_doi(doi):
    """
    通过DOI获取特定文章数据的API端点
    """
    try:
        if DBHelper:
            # 从数据库获取文章
            article = DBHelper.get_processed_paper_by_doi(doi)
            if article:
                return jsonify(article)
        
        # 如果数据库查询失败或没有结果，从内存中查找
        for article in articles_data:
            if article.get('doi') == doi:
                return jsonify(article)
                
        return jsonify({'error': '文章不存在'}), 404
    except Exception as e:
        logger.error(f"通过DOI获取文章时出错: {e}")
        return jsonify({'error': f'获取文章时出错: {str(e)}'}), 500

@app.route('/feedback')
def feedback():
    """
    反馈页面路由
    """
    return render_template('feedback.html')

@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    """
    处理反馈提交
    """
    try:
        # 获取表单数据
        title = request.form.get('title', '')
        content = request.form.get('content', '')
        name = request.form.get('name', '匿名用户')
        contact = request.form.get('contact', '')
        
        # 确认必填字段
        if not title or not content:
            return jsonify({'success': False, 'message': '标题和内容为必填项'})
        
        # 创建反馈记录
        feedback_data = {
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'title': title,
            'content': content,
            'name': name,
            'contact': contact
        }
        
        # 确保反馈文件目录存在
        os.makedirs(os.path.dirname(FEEDBACK_FILE) if os.path.dirname(FEEDBACK_FILE) else '.', exist_ok=True)
        
        # 检查文件是否存在，以决定是否需要写入标题行
        file_exists = os.path.isfile(FEEDBACK_FILE)
        
        # 写入CSV文件
        with open(FEEDBACK_FILE, 'a', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['timestamp', 'title', 'content', 'name', 'contact']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            if not file_exists:
                writer.writeheader()  # 如果是新文件，写入表头
            
            writer.writerow(feedback_data)
        
        logger.info(f"成功保存来自 {name} 的反馈: {title}")
        return jsonify({'success': True, 'message': '感谢您的反馈！'})
        
    except Exception as e:
        logger.error(f"保存反馈时出错: {str(e)}")
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'}), 500

if __name__ == '__main__':
    # 确保数据库表已初始化
    if DBHelper:
        DBHelper.initialize_tables()
    
    # 确保启动时有数据
    if not (load_from_database() or load_cached_data()):
        logger.info("没有找到数据，正在更新数据...")
        update_data()
    
    logger.info(f"服务器启动在 http://127.0.0.1:5000")
    app.run(debug=True, port=5000)