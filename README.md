# 快速了解最新公布的科研数据

这是一个用于获取、处理和展示Nature数据期刊（Scientific Data）最新发表的科研数据论文的Web应用程序。通过这个应用，您可以快速获取、阅读和搜索最新公布的科研数据论文，并通过AI进行中文翻译和解读，了解前沿研究成果。

## 功能特点

-   自动从Nature Scientific Data RSS源爬取最新数据论文
-   使用AI（DeepSeek API）自动翻译论文标题、生成中文解读摘要和标签
-   Web界面展示论文标题（中英文）、中文解读、发布日期、DOI、标签等信息
-   支持按标签筛选论文
-   提供论文详情弹窗（前端可能需要完善触发逻辑）
-   支持手动触发数据更新流程（后端已实现，前端可能需要添加按钮）
-   后端支持按关键词搜索相关论文（涵盖标题、摘要、标签）

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
data-paper-read/
├── app.py                      # Flask应用主文件 (处理Web请求、路由、渲染模板)
├── README.md                   # 项目说明文件
├── requirements.txt            # Python依赖列表
├── LICENSE                     # 项目许可证
├── .gitattributes              # Git属性文件
├── get_data/                   # 数据获取与处理模块目录
│   ├── crawler.py              # Nature RSS爬虫脚本
│   ├── process.py              # NLP处理脚本 (调用AI API)
│   ├── data_pipeline.py        # 数据处理流水线管理脚本
│   ├── nature_data_articles.json # 最终用于Web应用的数据缓存文件 (JSON)
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

在运行项目之前，请确保安装 Python 依赖项：

```bash
pip install -r requirements.txt
```
*注意：`requirements.txt` 文件可能包含非标准字符，如果安装失败，请根据文件内容手动安装 `Flask`, `feedparser`, `beautifulsoup4`, `openai`, `tqdm` 等核心库。*

## 如何运行

**重要提示**: 在首次运行或更新数据前，请确保设置了环境变量 `DEEPSEEK_API_KEY`，并且其值是有效的 DeepSeek API 密钥。`get_data/process.py` 文件会读取此环境变量。

1.  **更新数据 (首次运行或需要更新时)**:
    打开终端，进入项目根目录 (`/Users/jiakaiyang/Documents/GitHub/data-paper-read`)，运行数据处理流水线：
    ```bash
    python get_data/data_pipeline.py --full-update
    ```
    该命令会执行爬虫、NLP处理，并更新 `get_data/nature_data_articles.json` 文件。观察终端输出，确保没有错误，特别是关于API调用的错误。

2.  **启动Web应用**:
    在项目根目录运行以下命令启动Flask应用：
    ```bash
    python app.py
    ```

3.  **访问应用**:
    在浏览器中**必须通过 Flask 服务器提供的地址**访问: `http://127.0.0.1:5000`。
    **不要直接打开 `index.html` 文件**，否则页面无法正确加载数据和交互。

## 使用方法

-   **浏览论文**: 打开应用主页即可查看最新的论文列表。
-   **筛选论文**: 点击页面上方的标签进行筛选。
-   **搜索论文**: 后端 `/articles` API 支持 `keyword` 参数进行搜索，但前端页面当前未集成搜索框。
-   **查看详情**: 论文详情的模态框和数据显示逻辑已在 `script.js` 中实现 (`showArticleDetails` 函数)，但前端页面当前未实现点击论文卡片触发详情显示的功能。
-   **阅读原文**: 点击"查看原文"链接跳转到Nature官网。
-   **刷新数据**: 后端 `/refresh` API 支持手动触发数据更新，但前端页面当前未集成“刷新数据”按钮。

## 注意事项

-   数据更新依赖于DeepSeek API，请确保API密钥有效且网络连接正常。API调用可能需要时间并消耗配额。
-   爬虫和API调用应遵守相关服务的使用条款，避免过于频繁的请求。
-   数据处理流程会将原始数据和处理后数据分别保存在 `get_data/raw_papers.csv` 和 `get_data/processed_papers.csv` 中，并将最终结果导出到 `get_data/nature_data_articles.json` 供Web应用使用。
-   `get_data` 目录下的脚本（如 `crawler.py`, `process.py`, `data_pipeline.py`）设计为在 `get_data` 目录内或通过设置正确工作目录（如 `app.py` 中调用 `data_pipeline.py` 时所做）来运行，以确保文件路径正确。

## 后续改进计划

-   完善前端：添加搜索框、实现点击卡片查看详情、添加刷新数据按钮。
-   添加更多期刊来源。
-   优化错误处理和日志记录。
-   增加数据可视化功能。
-   优化前端筛选和交互体验。

## 许可证

MIT