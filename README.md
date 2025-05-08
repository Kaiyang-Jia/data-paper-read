# 科研数据论文阅读器

一个帮助您**用中文追踪科学数据前沿**的Web应用程序。自动获取、处理和展示来自知名期刊（主要是Nature Scientific Data）最新发表的科研数据论文，通过AI生成中文翻译和解读，让您轻松了解国际前沿科研数据成果。

![科研数据论文阅读器](https://img.shields.io/badge/%E7%A7%91%E7%A0%94%E6%95%B0%E6%8D%AE-%E8%AE%BA%E6%96%87%E9%98%85%E8%AF%BB%E5%99%A8-brightgreen)

## 🌟 功能特点

- 🔄 **自动更新数据**：从Nature Scientific Data和ESSD的RSS源爬取最新数据论文
- 🤖 **AI翻译与解读**：使用DeepSeek AI自动翻译标题、生成中文解读摘要和标签
- 📊 **智能学科分类**：自动为论文分配学科类别，便于筛选查找
- 📱 **友好用户界面**：移动端友好的响应式界面设计
- 🔍 **按学科浏览**：点击顶部学科分类按钮，快速筛选感兴趣的研究领域
- 🔗 **原文链接**：提供直达原始论文页面的链接
- 🗃️ **数据持久化**：支持MySQL数据库存储，方便数据管理和检索

## 📋 系统架构

### 技术栈

- **后端**：Python + Flask
- **数据处理**：
  - 爬虫：`feedparser`, `beautifulsoup4`
  - NLP处理：`openai`（用于DeepSeek API）
  - 数据存储：MySQL/CSV/JSON
- **前端**：HTML5 + CSS3 + 原生JavaScript

### 主要组件

```
data-paper-read/
├── app.py                      # Flask应用主文件
├── get_data/                   # 数据获取与处理模块
│   ├── crawler.py              # 期刊RSS爬虫
│   ├── abstract_fetcher.py     # 摘要获取工具
│   ├── process.py              # NLP处理（AI翻译与解读）
│   ├── data_pipeline.py        # 数据处理流水线
│   ├── db_helper.py            # 数据库操作封装
│   └── db_config.py            # 数据库配置
├── src/templates/              # Flask页面模板
│   ├── index.html              # 主页模板
│   └── feedback.html           # 反馈页面模板
└── static/                     # 静态资源
    ├── css/style.css           # 样式表
    ├── js/script.js            # 前端交互脚本
    └── icons/                  # 网站图标
```

## 🚀 如何使用

### 安装配置

1. **安装依赖**：
   ```bash
   pip install -r requirements.txt
   ```

2. **配置环境变量**：
   在使用前，请设置环境变量`DEEPSEEK_API_KEY`为您的DeepSeek API密钥。

   ```bash
   # Windows
   set DEEPSEEK_API_KEY=your_api_key_here
   
   # Linux/macOS
   export DEEPSEEK_API_KEY=your_api_key_here
   ```

### 启动应用

1. **更新数据**（首次运行或需要刷新数据时）：
   ```bash
   python get_data/data_pipeline.py
   ```

2. **启动Web服务**：
   ```bash
   python app.py
   ```

3. **访问应用**：
   在浏览器中访问 `http://127.0.0.1:5000`

   > **注意**：必须通过Flask服务器提供的地址访问，不要直接打开HTML文件。

## 💡 使用指南

- **浏览论文**：打开应用主页即可查看最新的论文列表，按发布日期倒序排列
- **按学科筛选**：点击页面上方的学科分类按钮，快速定位感兴趣的研究领域
- **查看详情**：点击论文卡片可查看更多信息（注：此功能正在开发中）
- **阅读原文**：点击"查看原文"链接跳转到期刊官网阅读完整论文

## 📚 预设学科分类

系统支持以下学科分类，自动对论文进行归类：

- **生物技术** (Biotechnology)
- **气候科学** (Climate Science)
- **计算生物学与生物信息学** (Computational Biology and Bioinformatics)
- **疾病** (Diseases)
- **生态学** (Ecology)
- **工程学** (Engineering)
- **环境科学** (Environmental Science)
- **环境社会科学** (Environmental Social Sciences)
- **遗传学** (Genetics)
- **医疗保健** (Health Care)
- **水文学** (Hydrology)
- **数学与计算** (Mathematics and Computing)
- **医学研究** (Medical Research)
- **微生物学** (Microbiology)
- **神经科学** (Neuroscience)
- **海洋科学** (Ocean Science)
- **植物科学** (Plant Science)
- **科学界** (Scientific Community)
- **社会科学** (Social Sciences)
- **动物学** (Zoology)
- **其他** (Other)

## ⚠️ 注意事项

- AI处理依赖于DeepSeek API，请确保API密钥有效且网络连接正常
- 爬虫和API调用应遵守相关服务的使用条款，避免过于频繁的请求
- 数据会自动备份到`get_data/backups/`目录，文件名包含时间戳

## 🔜 开发计划

- [ ] 完善前端：添加搜索框功能
- [ ] 实现点击卡片查看论文详情功能
- [ ] 添加数据刷新按钮
- [ ] 增加更多期刊来源支持
- [ ] 添加数据可视化功能（研究主题统计图表等）
- [ ] 优化多维度的筛选组合（如按学科+期刊筛选）

## 📄 许可证

MIT 许可证 - 详见 [LICENSE](LICENSE) 文件