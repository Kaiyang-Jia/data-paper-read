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

class NLPProcessor:
    """科研论文NLP处理类"""
    
    def __init__(self):
        """初始化NLP处理器"""
        self.input_csv = "raw_papers.csv"
        self.output_csv = "processed_papers.csv"
        self.api_client = self._init_deepseek_client()

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
        if task == "translate":
            prompt = f"将以下英文论文标题翻译成简洁的学术中文，保持专业术语准确性，仅返回翻译结果，不要添加任何说明或注释：\n{text}"
        elif task == "interpret":
            prompt = f"基于以下论文描述，提供一段70-90字的简洁学术性中文总结，聚焦数据集的制作过程和潜在应用价值，采用适合研究人员的正式语气，仅返回总结内容，不要添加任何说明或注释：\n{text}"
        elif task == "generate_tags":
            prompt = f"基于以下论文描述，为这篇科研数据论文生成3-5个简洁的中文标签，使用逗号分隔，适合学术分类，仅返回标签内容，不要添加任何说明或注释：\n{text}"
        
        for attempt in range(retries):
            try:
                response = self.api_client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": "你是一位专业的科研文献翻译与解读助手"},
                        {"role": "user", "content": prompt}
                    ],
                    stream=False
                )
                return response.choices[0].message.content.strip()
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
        """处理论文数据"""
        # 检查文件是否存在
        if not os.path.exists(self.input_csv):
            logger.error(f"输入文件不存在: {self.input_csv}")
            return False
            
        # 读取输入CSV
        input_datasets = []
        try:
            with open(self.input_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                input_datasets = list(reader)
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
        existing_doi = set()
        if os.path.exists(self.output_csv):
            try:
                with open(self.output_csv, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        existing_data.append(row)
                        if "doi" in row and row["doi"]:
                            existing_doi.add(row["doi"])
                logger.info(f"已有 {len(existing_data)} 条处理过的数据")
            except Exception as e:
                logger.error(f"读取现有输出文件失败: {e}")
        
        # 处理新数据
        new_data = []
        headers = ["title", "titleCn", "interpretationCn", "publishDate", "doi",
                  "url", "authors", "tags", "abstract"]
        
        logger.info("开始处理新数据...")
        for data in tqdm(input_datasets, desc="处理论文"):
            if "doi" not in data or not data["doi"] or data["doi"] in existing_doi:
                continue
                
            # 获取基本信息
            title = data.get("title", "")
            abstract = data.get("abstract", "")
            
            # 准备处理对象
            processed_item = {
                "title": title,
                "publishDate": data.get("publishDate", ""),
                "doi": data.get("doi", ""),
                "url": data.get("url", ""),
                "authors": data.get("authors", ""),
                "abstract": abstract
            }
            
            # 如果有内容，进行NLP处理
            if title:
                # 翻译标题
                logger.info(f"翻译标题: {title[:30]}...")
                title_cn = self.call_ai_api(title, "translate")
                processed_item["titleCn"] = title_cn
                
                # 为确保有内容可解读，使用摘要优先，无摘要则使用标题
                text_for_interpretation = abstract if abstract else title
                
                # 生成解读
                logger.info(f"生成解读: {text_for_interpretation[:30]}...")
                interpretation_cn = self.call_ai_api(text_for_interpretation, "interpret")
                processed_item["interpretationCn"] = interpretation_cn
                
                # 生成标签（如果原始数据没有标签）
                if not data.get("tags"):
                    logger.info("生成标签...")
                    tags = self.call_ai_api(text_for_interpretation, "generate_tags")
                    processed_item["tags"] = tags
                else:
                    processed_item["tags"] = data.get("tags", "")
                    
                # 添加到新数据列表
                new_data.append(processed_item)
                
                # 每处理5篇文章等待一下，避免API限流
                if len(new_data) % 5 == 0:
                    time.sleep(2)
        
        # 检查是否有新处理的数据
        if not new_data:
            logger.info("没有新数据需要处理")
            return True
            
        # 写入输出CSV
        try:
            with open(self.output_csv, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                # 先写入已有数据，后写入新数据
                for row in existing_data:
                    # 确保所有字段都有值，避免CSV格式错误
                    for field in headers:
                        if field not in row:
                            row[field] = ""
                    writer.writerow(row)
                    
                for row in new_data:
                    # 确保所有字段都有值
                    for field in headers:
                        if field not in row:
                            row[field] = ""
                    writer.writerow(row)
                    
            logger.info(f"数据保存到 {self.output_csv}，{len(new_data)} 条新处理记录，共 {len(existing_data) + len(new_data)} 条记录")
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