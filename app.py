#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Flask, render_template, request, jsonify
import json
import os
import subprocess
import sys
import logging

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

def update_data():
    """
    使用新的数据管道更新数据
    """
    try:
        # 获取数据管道脚本的路径
        pipeline_script = os.path.join("get_data", "data_pipeline.py")
        
        if not os.path.exists(pipeline_script):
            logger.error(f"数据管道脚本不存在: {pipeline_script}")
            return False
            
        # 执行数据更新流程 (Run in the get_data directory)
        logger.info("启动数据更新流程...")
        script_dir = os.path.dirname(pipeline_script)
        script_name = os.path.basename(pipeline_script)
        result = subprocess.run([sys.executable, script_name, "--full-update"], 
                               cwd=script_dir, # Set working directory to 'get_data'
                               capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"数据更新失败: {result.stderr}")
            return False
            
        # 重新加载更新后的数据
        return load_cached_data()
    except Exception as e:
        logger.error(f"更新数据时出错: {e}")
        return False

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
    success = update_data()
    
    if success:
        return jsonify({
            'status': 'success',
            'message': f'成功更新 {len(articles_data)} 篇论文',
            'count': len(articles_data)
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

if __name__ == '__main__':
    # 确保启动时有数据
    if not load_cached_data():
        logger.info("没有找到缓存数据，正在更新数据...")
        update_data()
    
    logger.info(f"服务器启动在 http://127.0.0.1:5000")
    app.run(debug=True, port=5000)