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

# 配置日志
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='src/templates')

# 全局变量存储数据
CACHE_FILE = os.path.join('get_data', 'nature_data_articles.json') # Updated path
articles_data = []

# 反馈存储文件
FEEDBACK_FILE = 'user_feedback.csv'

def load_cached_data():
    """
    从缓存文件中加载数据
    """
    global articles_data
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                articles_data = json.load(f)
            logger.info(f"成功从缓存加载了 {len(articles_data)} 篇论文数据")
            return len(articles_data) > 0
        logger.warning(f"缓存文件不存在: {CACHE_FILE}")
        return False
    except Exception as e:
        logger.error(f"加载缓存数据时出错: {e}")
        return False

def update_data(full_update=False):
    """
    使用新的数据管道更新数据
    Args:
        full_update (bool): 是否执行全量更新，默认为False(增量更新)
    Returns:
        tuple: (成功与否, 新增文章数)
    """
    try:
        # 获取更新前的文章数量
        old_count = len(articles_data)
        
        # 获取项目根目录路径
        project_root = os.path.dirname(os.path.abspath(__file__))
        
        # 使用 python -m 方式调用模块以解决相对导入问题
        logger.info("启动数据更新流程...")
        cmd = [sys.executable, "-m", "get_data.data_pipeline"]
        if full_update:
            cmd.append("--full-update")
            
        result = subprocess.run(
            cmd,
            cwd=project_root, # 确保在项目根目录执行
            capture_output=True, 
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"数据更新失败: {result.stderr}")
            return False, 0
            
        # 重新加载更新后的数据
        success = load_cached_data()
        
        # 计算新增文章数
        new_count = len(articles_data) - old_count if success and old_count > 0 else len(articles_data)
        
        return success, new_count
    except Exception as e:
        logger.error(f"更新数据时出错: {e}")
        return False, 0

@app.route('/')
def index():
    """
    主页视图
    """
    # 尝试加载缓存数据，如果没有则更新数据
    if not load_cached_data():
        update_data()
    
    return render_template('index.html', articles=articles_data)

@app.route('/refresh', methods=['POST'])
def refresh_data():
    """
    刷新数据的API端点
    """
    success, new_count = update_data()
    
    if success:
        return jsonify({
            'status': 'success',
            'message': f'成功更新 {new_count} 篇论文',
            'count': new_count  # 这里改为new_count，不再使用总数
        })
    else:
        return jsonify({
            'status': 'error',
            'message': '数据更新失败，请查看服务器日志'
        }), 500

@app.route('/articles')
def get_articles():
    """
    获取文章数据的API端点
    """
    # 关键词过滤
    keyword = request.args.get('keyword', '').lower()
    
    if keyword:
        filtered_articles = [
            article for article in articles_data 
            if keyword in article.get('title', '').lower() or 
               keyword in article.get('abstract', '').lower() or
               keyword in article.get('titleCn', '').lower() or
               keyword in article.get('interpretationCn', '').lower() or
               any(keyword in tag.lower() for tag in article.get('tags', []) if isinstance(article.get('tags'), list)) or
               (isinstance(article.get('tags'), str) and keyword in article.get('tags', '').lower())
        ]
        return jsonify(filtered_articles)
    else:
        return jsonify(articles_data)

@app.route('/article/<int:index>')
def get_article(index):
    """
    获取特定文章数据的API端点
    """
    try:
        return jsonify(articles_data[index])
    except IndexError:
        return jsonify({'error': '文章不存在'}), 404

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
    # 确保启动时有数据
    if not load_cached_data():
        logger.info("没有找到缓存数据，正在更新数据...")
        update_data()
    
    logger.info(f"服务器启动在 http://127.0.0.1:5000")
    app.run(debug=True, port=5000)