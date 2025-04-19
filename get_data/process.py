#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NLP处理模块

使用DeepSeek API对原始论文数据进行自然语言处理，包括：
1. 英文标题翻译成中文
2. 生成中文解读摘要
3. 基于内容生成相关标签

输入：raw_papers.csv（原始爬取数据）
输出：processed_papers.csv（处理后的完整数据）
"""

import csv
import os
import logging
from openai import OpenAI
from tqdm import tqdm
import time
import random

# 配置日志
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- 新增：定义预设分类 (Subject) ---
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
    "其他"  # 添加一个“其他”类别以防万一
]
class NLPProcessor:
    """科研论文NLP处理类"""
    
    def __init__(self):
        """初始化NLP处理器"""
        self.input_csv = "raw_papers.csv"
        self.output_csv = "processed_papers.csv"
        self.api_client = self._init_deepseek_client()
        # --- 新增：将分类列表存为实例属性 ---
        self.subjects = PREDEFINED_SUBJECTS
        # --- 新增：默认期刊来源 ---
        self.default_journal = "Scientific Data"

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
        # --- 新增：处理 classify 任务 ---
        elif task == "classify":
            subject_list_str = ", ".join(self.subjects)
            prompt = f"请根据以下论文信息（优先参考摘要，其次是标题），从下列预定义的分类 (Subject) 中选择一个最相关的类别：[{subject_list_str}]。请仅返回最合适的中文类别名称，不要添加任何说明、标点或注释。\n\n论文信息：\n{text}"
            system_content = "你是一位专业的科研文献分类助手。" # 针对分类任务调整 System Prompt

        # --- 新增：确保处理 classify 任务 ---
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
                
                # --- 新增：对分类结果进行校验 ---
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
                            result = "其他" # 默认归类为“其他”
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
    
    def process_papers(self):
        """处理论文数据，包括处理新论文和补全旧论文的缺失信息"""
        # 检查文件是否存在
        if not os.path.exists(self.input_csv):
            logger.error(f"输入文件不存在: {self.input_csv}")
            return False
            
        # 读取输入CSV
        input_datasets = []
        input_doi_map = {}
        try:
            with open(self.input_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    input_datasets.append(row)
                    if "doi" in row and row["doi"]:
                        input_doi_map[row["doi"]] = row # Store raw data by DOI
            logger.info(f"成功读取 {len(input_datasets)} 条输入数据")
        except Exception as e:
            logger.error(f"读取输入文件失败: {e}")
            return False
        
        # 如果输入为空，退出处理
        if not input_datasets:
            logger.warning("没有找到需要处理的数据")
            return False
        
        # 读取现有输出CSV（避免重复处理）
        existing_data = []
        processed_doi = set()
        if os.path.exists(self.output_csv):
            try:
                with open(self.output_csv, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        existing_data.append(row)
                        if "doi" in row and row["doi"]:
                            processed_doi.add(row["doi"])
                logger.info(f"已有 {len(existing_data)} 条处理过的数据")
            except Exception as e:
                logger.error(f"读取现有输出文件失败: {e}")
                # If reading fails, proceed as if no existing data
                existing_data = []
                processed_doi = set()
        
        # 准备最终输出的数据列表和头部
        final_output_data = []
        # --- 修改：在 headers 中添加 journal ---
        headers = ["title", "titleCn", "interpretationCn", "publishDate", "doi",
                   "url", "authors", "tags", "Subject", "journal", "abstract"] # 添加了 "journal"
        
        # 标记是否有数据被修改或添加
        data_changed = False

        # 1. 检查并更新现有数据
        logger.info("开始检查并更新现有数据...")
        for i, row in enumerate(tqdm(existing_data, desc="检查旧数据")):
            doi = row.get("doi", "")
            title = row.get("title", "")
            abstract = row.get("abstract", "") # Get abstract from processed if available
            # If abstract is missing in processed, try getting it from raw input map
            if not abstract and doi in input_doi_map:
                 abstract = input_doi_map[doi].get("abstract", "")
                 row["abstract"] = abstract # Update row if abstract was missing
                 if abstract:
                     data_changed = True
                     logger.info(f"为 DOI {doi} 从原始数据补充了摘要")

            needs_update = False
            
            # 检查中文标题
            if title and not row.get("titleCn"): 
                logger.info(f"为 DOI {doi} 补全中文标题...")
                title_cn = self.call_ai_api(title, "translate")
                if title_cn:
                    row["titleCn"] = title_cn
                    needs_update = True
                    time.sleep(1) # API call delay
            
            # 确定用于解读、分类和标签生成的文本 (优先摘要)
            text_for_nlp = abstract if abstract else title

            # 检查中文解读 (需要原文标题或摘要)
            if text_for_nlp and not row.get("interpretationCn"):
                logger.info(f"为 DOI {doi} 补全中文解读...")
                interpretation_cn = self.call_ai_api(text_for_nlp, "interpret")
                if interpretation_cn:
                    row["interpretationCn"] = interpretation_cn
                    needs_update = True
                    time.sleep(1) # API call delay

            # 检查标签 (需要原文标题或摘要)
            if text_for_nlp and not row.get("tags"):
                logger.info(f"为 DOI {doi} 补全标签...")
                tags = self.call_ai_api(text_for_nlp, "generate_tags")
                if tags:
                    row["tags"] = tags
                    needs_update = True
                    time.sleep(1) # API call delay

            # --- 新增：检查 Subject 分类 ---
            if text_for_nlp and not row.get("Subject"):
                logger.info(f"为 DOI {doi} 补全 Subject 分类...")
                subject = self.call_ai_api(text_for_nlp, "classify")
                if subject: # 确保API调用成功且返回了有效分类
                    row["Subject"] = subject
                    needs_update = True
                    time.sleep(1) # API call delay

            # --- 新增：检查 journal 字段 ---
            if not row.get("journal"):
                row["journal"] = self.default_journal
                data_changed = True
                logger.info(f"为 DOI {doi} 补充默认期刊信息")
            
            if needs_update:
                data_changed = True
                # 每处理5篇等待一下
                if i > 0 and i % 5 == 0:
                    logger.info("API调用间歇等待...")
                    time.sleep(2)

            final_output_data.append(row) # Add potentially updated row

        # 2. 处理新数据 (存在于 raw 但不在 processed 中的)
        logger.info("开始处理新数据...")
        new_papers_processed_count = 0
        for data in tqdm(input_datasets, desc="处理新论文"):
            doi = data.get("doi", "")
            if not doi or doi in processed_doi:
                continue # Skip if no DOI or already processed
                
            # 获取基本信息
            title = data.get("title", "")
            abstract = data.get("abstract", "")
            
            # --- 修改：初始化 processed_item，包含 journal ---
            processed_item = {
                "title": title,
                "publishDate": data.get("publishDate", ""),
                "doi": doi,
                "url": data.get("url", ""),
                "authors": data.get("authors", ""),
                "abstract": abstract,
                "titleCn": "",
                "interpretationCn": "",
                "tags": data.get("tags", ""), # 使用原始 tags (如果有)
                "Subject": "", # 初始化 Subject 字段
                "journal": data.get("journal", self.default_journal) # 添加 journal 字段，默认为 Scientific Data
            }
            
            # 如果有内容，进行NLP处理
            if title:
                logger.info(f"处理新论文 DOI {doi}: {title[:30]}...")
                # 翻译标题
                title_cn = self.call_ai_api(title, "translate")
                processed_item["titleCn"] = title_cn
                time.sleep(1)
                
                # 为确保有内容可处理，使用摘要优先，无摘要则使用标题
                text_for_nlp = abstract if abstract else title
                
                # 生成解读
                interpretation_cn = self.call_ai_api(text_for_nlp, "interpret")
                processed_item["interpretationCn"] = interpretation_cn
                time.sleep(1)
                
                # 生成标签（如果原始数据没有标签）
                if not processed_item["tags"]:
                    tags = self.call_ai_api(text_for_nlp, "generate_tags")
                    processed_item["tags"] = tags
                    time.sleep(1)

                # --- 新增：生成 Subject 分类 ---
                subject = self.call_ai_api(text_for_nlp, "classify")
                processed_item["Subject"] = subject # 存储分类结果
                time.sleep(1)
                    
            final_output_data.append(processed_item)
            data_changed = True
            new_papers_processed_count += 1
            processed_doi.add(doi) # Add to processed set immediately
                
            # 每处理5篇新文章等待一下
            if new_papers_processed_count > 0 and new_papers_processed_count % 5 == 0:
                logger.info("API调用间歇等待...")
                time.sleep(2)
        
        # 检查是否有数据更改或添加
        if not data_changed:
            logger.info("没有数据被修改或添加，文件保持不变")
            return True
            
        # 写入输出CSV (覆盖写入)
        try:
            with open(self.output_csv, "w", encoding="utf-8", newline="") as f:
                # --- 确保使用更新后的 headers ---
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                
                # 写入所有数据 (已更新的旧数据 + 新处理的数据)
                for row in final_output_data:
                    # 确保所有字段都有值，避免CSV格式错误
                    output_row = {field: row.get(field, "") for field in headers}
                    writer.writerow(output_row)
                    
            logger.info(f"数据已更新并保存到 {self.output_csv}，共 {len(final_output_data)} 条记录")
            return True
        except Exception as e:
            logger.error(f"保存输出文件失败: {e}")
            return False

def main():
    """主函数"""
    processor = NLPProcessor()
    success = processor.process_papers()
    
    if success:
        print("论文数据处理完成！")
    else:
        print("处理过程中出现错误，请查看日志")

if __name__ == "__main__":
    main()