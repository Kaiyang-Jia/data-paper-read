# 快速了解最新公布的科研数据

这是一个用于获取、处理和展示Nature数据期刊（Scientific Data）最新发表的科研数据论文的Web应用程序。通过这个应用，您可以快速获取、阅读和搜索最新公布的科研数据论文，并通过AI进行中文翻译和解读，了解前沿研究成果。

## 功能特点

-   自动从Nature Scientific Data RSS源爬取最新数据论文
-   使用AI（DeepSeek API）自动翻译论文标题、生成中文解读摘要和标签
-   Web界面展示论文标题（中英文）、中文解读、发布日期、DOI、标签等信息
-   支持按关键词搜索相关论文（涵盖标题、摘要、标签）
-   支持按标签筛选论文
-   提供论文详情弹窗
-   支持手动触发数据更新流程

## 技术栈

-   **后端**: Python + Flask
    -   Flask 是一个 Python 微框架，用于构建 Web 应用。在这个项目中，它负责处理浏览器请求、路由 URL 到相应的处理函数、渲染 HTML 模板以及提供 API 端点供前端 JavaScript 调用。
-   **数据处理**:
    -   爬虫: `feedparser`, `beautifulsoup4`
    -   NLP处理: `openai` (用于 DeepSeek API)
    -   数据存储: CSV, JSON
-   **前端**: HTML + CSS + JavaScript

## 项目结构

```
data_paper/
├── app.py                      # Flask应用主文件 (处理Web请求、路由、渲染模板)
├── nature_data_articles.json   # 最终用于Web应用的数据缓存文件 (JSON)
├── README.md                   # 项目说明文件
├── get_data/                   # 数据获取与处理模块目录
│   ├── api.py / data_service.py # (可选) 提供数据的API服务脚本
│   ├── crawler.py / nature_rss_crawler.py # Nature RSS爬虫脚本
│   ├── data_pipeline.py        # 数据处理流水线管理脚本
│   ├── process.py / nlp_processor.py # NLP处理脚本 (调用AI API)
│   ├── processed_papers.csv    # 经过NLP处理后的数据文件 (CSV)
│   ├── raw_papers.csv          # 爬虫获取的原始数据文件 (CSV)
│   └── backups/                # 数据备份目录
├── src/
│   └── templates/              # Flask网页模板目录
│       └── index.html          # 主页模板
└── static/
    ├── css/                    # CSS样式文件目录
    │   └── style.css
    └── js/                     # JavaScript脚本文件目录
        └── script.js
```

## 安装依赖

在运行项目之前，请确保安装以下依赖项：

```bash
pip install Flask feedparser beautifulsoup4 openai tqdm
```

## 如何运行

**重要提示**: 在首次运行或更新数据前，请确保 `get_data/process.py` 文件中的 DeepSeek API 密钥是有效的。

1.  **更新数据 (首次运行或需要更新时)**:
    打开终端，进入项目根目录 (`d:\01个人文件\data_paper`)，运行数据处理流水线：
    ```bash
    python get_data/data_pipeline.py --full-update
    ```
    观察终端输出，确保没有错误，特别是关于API调用的错误。成功运行后，`nature_data_articles.json` 文件会被更新。

2.  **启动Web应用**:
    在项目根目录运行以下命令启动Flask应用：
    ```bash
    python app.py
    ```

3.  **访问应用**:
    在浏览器中**必须通过 Flask 服务器提供的地址**访问: `http://127.0.0.1:5000`。
    **不要直接打开 `index.html` 文件**，否则页面无法正确加载。

## 使用方法

-   **浏览论文**: 打开应用主页即可查看最新的论文列表。
-   **筛选论文**: 点击页面上方的标签进行筛选。
-   **搜索论文**: (如果前端实现了搜索功能) 使用搜索框输入关键词进行搜索。
-   **查看详情**: 点击论文卡片上的"详细信息"按钮查看弹窗。
-   **阅读原文**: 点击"查看原文"链接跳转到Nature官网。
-   **刷新数据**: 点击页面底部的"刷新数据"按钮，会触发后台执行步骤1的数据更新流程，完成后页面会自动刷新。

## 注意事项

-   数据更新依赖于DeepSeek API，请确保API密钥有效且网络连接正常。API调用可能需要时间并消耗配额。
-   爬虫和API调用应遵守相关服务的使用条款，避免过于频繁的请求。
-   数据处理流程会将原始数据和处理后数据分别保存在 `raw_papers.csv` 和 `processed_papers.csv` 中，并将最终结果导出到 `nature_data_articles.json` 供Web应用使用。

## 后续改进计划

-   添加更多期刊来源。
-   优化错误处理和日志记录。
-   增加数据可视化功能。
-   优化前端搜索和筛选体验。

## 许可证

MIT