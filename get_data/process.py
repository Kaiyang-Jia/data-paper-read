#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NLP处理模块

使用DeepSeek API对原始论文数据进行自然语言处理，包括：
1. 英文标题翻译成中文
2. 生成中文解读摘要
3. 基于内容生成相关标签
4. 按主题分类数据论文

输入：从数据库表 raw_papers 读取原始爬取数据（包含多个期刊）
输出：处理后的完整数据保存到数据库表 processed_papers
保留CSV导出功能作为备份
"""

import csv
import os
import logging
from openai import OpenAI
from tqdm import tqdm
import time
import random
import shutil
from datetime import datetime

# 导入数据库工具类
try:
    from .db_helper import DBHelper  # 当作为包导入时
except ImportError:
    try:
        from db_helper import DBHelper  # 当在同一目录下直接运行时
    except ImportError:
        print("错误：无法导入数据库工具类，请确保 db_helper.py 文件存在")
        DBHelper = None

# 配置日志
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- 预设分类 (Subject) ---
PREDEFINED_SUBJECTS = [
    "生物技术",
    "气候科学",
    "计算生物学与生物信息学",
    "疾病",
    "生态学",
    "工程学",
    "环境科学",
    "环境社会科学",
    "遗传学",
    "医疗保健",
    "水文学",
    "数学与计算",
    "医学研究",
    "微生物学",
    "神经科学",
    "海洋科学",
    "植物科学",
    "科学界",
    "社会科学",
    "动物学",
    "其他"  # 添加一个"其他"类别以防万一
]

class NLPProcessor:
    """科研论文NLP处理类"""
    
    def __init__(self, input_csv="raw_papers.csv", output_csv="processed_papers.csv", backup_folder="backups"):
        """初始化NLP处理器，允许指定文件路径"""
        # 保留 CSV 文件路径作为备份
        self.input_csv = input_csv
        self.output_csv = output_csv
        self.api_client = self._init_deepseek_client()
        self.subjects = PREDEFINED_SUBJECTS
        self.backup_folder = backup_folder # 备份文件夹
        
        # 确保数据库表已初始化
        if DBHelper:
            DBHelper.initialize_tables()

    def _init_deepseek_client(self):
        """初始化DeepSeek API客户端"""
        try:
            api_key = os.environ.get("DEEPSEEK_API_KEY")
            if not api_key:
                logger.error("未找到环境变量 DEEPSEEK_API_KEY")
                return None
            return OpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com"
            )
        except Exception as e:
            logger.error(f"初始化DeepSeek API客户端失败: {e}")
            return None
    
    def call_ai_api(self, text, task, retries=3):
        """调用DeepSeek API，支持重试机制"""
        if not self.api_client:
            logger.error("API客户端未初始化")
            return ""
            
        prompt = ""
        system_content = "你是一位专业的科研文献翻译与解读助手" # 默认 System Prompt
        if task == "translate":
            prompt = f"将以下英文论文标题翻译成简洁的学术中文，保持专业术语准确性，仅返回翻译结果，不要添加任何说明或注释：\n{text}"
        elif task == "interpret":
            prompt = f"基于以下论文描述，提供一段70-90字的简洁学术性中文总结，聚焦数据集的制作过程和潜在应用价值，采用适合研究人员的正式语气，仅返回总结内容，不要添加任何说明或注释：\n{text}"
        elif task == "generate_tags":
            prompt = f"基于以下论文描述，为这篇科研数据论文生成3-5个简洁的中文标签，使用逗号分隔，适合学术分类，仅返回标签内容，不要添加任何说明或注释：\n{text}"
        elif task == "classify":
            subject_list_str = ", ".join(self.subjects)
            prompt = f"请根据以下论文信息（优先参考摘要，其次是标题），从下列预定义的分类 (Subject) 中选择一个最相关的类别：[{subject_list_str}]。请仅返回最合适的中文类别名称，不要添加任何说明、标点或注释。\n\n论文信息：\n{text}"
            system_content = "你是一位专业的科研文献分类助手。" # 针对分类任务调整 System Prompt

        if not prompt:
             logger.error(f"未知的 AI 任务类型: {task}")
             return ""

        for attempt in range(retries):
            try:
                response = self.api_client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": prompt}
                    ],
                    stream=False
                )
                result = response.choices[0].message.content.strip()
                
                # 对分类结果进行校验
                if task == "classify":
                    # 移除可能的标点符号
                    result = result.replace("，", "").replace(",", "").replace("。", "").strip()
                    if result not in self.subjects:
                        logger.warning(f"LLM返回的分类 '{result}' 不在预定义列表中，将尝试查找最接近的或标记为'其他'")
                        # 尝试查找包含关系的匹配
                        found = False
                        for subj in self.subjects:
                            if subj in result or result in subj: # 简单包含关系检查
                                result = subj
                                found = True
                                logger.info(f"修正分类为: {result}")
                                break
                        if not found:
                            logger.warning(f"无法匹配分类 '{result}'，标记为 '其他'")
                            result = "其他" # 默认归类为"其他"
                return result
            except Exception as e:
                logger.error(f"API调用失败 (尝试 {attempt+1}/{retries}): {e}")
                if attempt < retries - 1:
                    # 等待时间递增，添加随机因素避免同时重试
                    sleep_time = (2 ** attempt) + random.uniform(0, 1)
                    logger.info(f"等待 {sleep_time:.1f} 秒后重试...")
                    time.sleep(sleep_time)
                else:
                    logger.error("达到最大重试次数，放弃处理")
                    return ""
    
    def backup_files(self):
        """创建输入和输出文件的备份"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 确保备份文件夹存在
        if not os.path.exists(self.backup_folder):
            os.makedirs(self.backup_folder)
            logger.info(f"已创建备份文件夹: {self.backup_folder}")
            
        # 备份输入文件（如果存在）
        if os.path.exists(self.input_csv):
            input_backup = os.path.join(self.backup_folder, f"raw_papers_{timestamp}.csv")
            shutil.copy2(self.input_csv, input_backup)
            logger.info(f"已创建输入文件备份: {input_backup}")
            
        # 备份输出文件（如果存在）
        if os.path.exists(self.output_csv):
            output_backup = os.path.join(self.backup_folder, f"processed_papers_{timestamp}.csv")
            shutil.copy2(self.output_csv, output_backup)
            logger.info(f"已创建输出文件备份: {output_backup}")
    
    def process_papers(self):
        """处理论文数据，包括处理新论文和补全旧论文的缺失信息，使用数据库作为数据源和目标"""
        # 创建备份 (用于保留 CSV 备份)
        self.backup_files()
        
        # 确保数据库连接正常
        if not DBHelper:
            logger.error("数据库工具类未正确初始化，无法处理数据")
            return False
        
        # 1. 从数据库获取已处理的论文数据
        processed_papers = DBHelper.get_all_processed_papers()
        processed_doi_set = set()
        for paper in processed_papers:
            if paper.get('doi'):
                processed_doi_set.add(paper.get('doi'))
        logger.info(f"从数据库中获取到 {len(processed_papers)} 条已处理的论文数据")
        
        # 2. 获取未处理的原始论文数据（在 raw_papers 中但不在 processed_papers 中）
        unprocessed_papers = DBHelper.get_unprocessed_raw_papers()
        logger.info(f"发现 {len(unprocessed_papers)} 条未处理的论文数据")
        
        # 3. 处理未处理的论文数据
        new_papers_processed_count = 0
        if unprocessed_papers:
            logger.info("开始处理新论文数据...")
            for paper in tqdm(unprocessed_papers, desc="处理新论文"):
                doi = paper.get('doi', '')
                title = paper.get('title', '')
                abstract = paper.get('abstract', '')
                
                # 创建处理后的论文数据对象
                processed_paper = {
                    'title': title,
                    'publishDate': paper.get('publishDate', ''),
                    'doi': doi,
                    'url': paper.get('url', ''),
                    'authors': paper.get('authors', ''),
                    'abstract': abstract,
                    'journal': paper.get('journal', ''),
                    'titleCn': '',
                    'interpretationCn': '',
                    'tags': paper.get('tags', ''),
                    'Subject': ''
                }
                
                # 如果有内容，进行NLP处理
                if title:
                    logger.info(f"处理新论文 DOI {doi}: {title[:30]}...")
                    # 翻译标题
                    title_cn = self.call_ai_api(title, "translate")
                    processed_paper['titleCn'] = title_cn
                    time.sleep(1)
                    
                    # 为确保有内容可处理，使用摘要优先，无摘要则使用标题
                    text_for_nlp = abstract if abstract else title
                    
                    # 生成解读
                    interpretation_cn = self.call_ai_api(text_for_nlp, "interpret")
                    processed_paper['interpretationCn'] = interpretation_cn
                    time.sleep(1)
                    
                    # 生成标签（如果原始数据没有标签）
                    if not processed_paper['tags']:
                        tags = self.call_ai_api(text_for_nlp, "generate_tags")
                        processed_paper['tags'] = tags
                        time.sleep(1)

                    # 生成 Subject 分类
                    subject = self.call_ai_api(text_for_nlp, "classify")
                    processed_paper['Subject'] = subject
                    time.sleep(1)
                    
                    # 保存到数据库
                    if DBHelper.insert_processed_paper(processed_paper):
                        new_papers_processed_count += 1
                    
                    # 每处理5篇新文章等待一下
                    if new_papers_processed_count > 0 and new_papers_processed_count % 5 == 0:
                        logger.info("API调用间歇等待...")
                        time.sleep(2)
        
        # 4. 检查并更新已处理数据中可能缺失的字段
        updated_papers_count = 0
        if processed_papers:
            logger.info("开始检查并补全已处理论文数据中缺失的字段...")
            for paper in tqdm(processed_papers, desc="检查已处理数据"):
                doi = paper.get('doi', '')
                title = paper.get('title', '')
                abstract = paper.get('abstract', '')
                
                needs_update = False
                
                # 检查中文标题
                if title and not paper.get('titleCn'): 
                    logger.info(f"为 DOI {doi} 补全中文标题...")
                    title_cn = self.call_ai_api(title, "translate")
                    if title_cn:
                        paper['titleCn'] = title_cn
                        needs_update = True
                        time.sleep(1)
                
                # 确定用于解读、分类和标签生成的文本 (优先摘要)
                text_for_nlp = abstract if abstract else title

                # 检查中文解读
                if text_for_nlp and not paper.get('interpretationCn'):
                    logger.info(f"为 DOI {doi} 补全中文解读...")
                    interpretation_cn = self.call_ai_api(text_for_nlp, "interpret")
                    if interpretation_cn:
                        paper['interpretationCn'] = interpretation_cn
                        needs_update = True
                        time.sleep(1)

                # 检查标签
                if text_for_nlp and not paper.get('tags'):
                    logger.info(f"为 DOI {doi} 补全标签...")
                    tags = self.call_ai_api(text_for_nlp, "generate_tags")
                    if tags:
                        paper['tags'] = tags
                        needs_update = True
                        time.sleep(1)

                # 检查 Subject 分类
                if text_for_nlp and not paper.get('Subject'):
                    logger.info(f"为 DOI {doi} 补全 Subject 分类...")
                    subject = self.call_ai_api(text_for_nlp, "classify")
                    if subject:
                        paper['Subject'] = subject
                        needs_update = True
                        time.sleep(1)

                # 如果需要更新，将更新后的数据保存回数据库
                if needs_update:
                    if DBHelper.insert_processed_paper(paper):  # 使用 insert_processed_paper 同时支持插入和更新
                        updated_papers_count += 1
                    
                    # 每更新5篇等待一下
                    if updated_papers_count > 0 and updated_papers_count % 5 == 0:
                        logger.info("API调用间歇等待...")
                        time.sleep(2)
        
        # 导出处理后的数据到 CSV 文件作为备份
        self.export_processed_data_to_csv()
        
        logger.info(f"论文处理完成，新处理 {new_papers_processed_count} 篇，更新 {updated_papers_count} 篇")
        return new_papers_processed_count > 0 or updated_papers_count > 0
    
    def export_processed_data_to_csv(self):
        """将处理后的数据从数据库导出到CSV文件作为备份"""
        if not DBHelper:
            logger.error("数据库工具类未正确初始化，无法导出数据")
            return False
        
        processed_papers = DBHelper.get_all_processed_papers()
        if not processed_papers:
            logger.warning("没有找到可导出的处理后论文数据")
            return False
        
        try:
            # 定义CSV文件的字段列表
            headers = ["title", "titleCn", "interpretationCn", "publishDate", "doi",
                       "url", "authors", "tags", "abstract", "Subject", "journal"]
            
            # 将数据写入CSV文件
            with open(self.output_csv, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                
                for paper in processed_papers:
                    # 从论文对象中提取相关字段
                    row = {field: paper.get(field, "") for field in headers}
                    
                    # 处理特殊字段
                    if "tags" in row and isinstance(row["tags"], list):
                        row["tags"] = ",".join(row["tags"])
                    
                    writer.writerow(row)
            
            logger.info(f"成功将 {len(processed_papers)} 条处理后的论文数据导出到 {self.output_csv}")
            return True
        except Exception as e:
            logger.error(f"导出数据到CSV时发生错误: {e}")
            return False

def main():
    """主函数"""
    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(script_dir, "raw_papers.csv")
    output_file = os.path.join(script_dir, "processed_papers.csv")
    backup_dir = os.path.join(script_dir, "backups")

    # 确保数据库表已初始化
    if DBHelper:
        DBHelper.initialize_tables()
    else:
        logger.error("无法初始化数据库，请确保数据库配置正确")
        return

    processor = NLPProcessor(input_csv=input_file, output_csv=output_file, backup_folder=backup_dir)
    success = processor.process_papers()
    
    if success:
        print("论文数据处理完成！")
    else:
        print("处理过程中出现错误，请查看日志")

if __name__ == "__main__":
    main()