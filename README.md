# 快速了解最新公布的科研数据

这是一个用于获取、处理和展示科研数据期刊（主要是 Scientific Data）最新发表的科研数据论文的Web应用程序。通过这个应用，您可以快速获取、阅读和搜索最新公布的科研数据论文，并通过AI进行中文翻译和解读，了解前沿研究成果。

## 功能特点

-   自动从Nature Scientific Data RSS源爬取最新数据论文
-   使用AI（DeepSeek API）自动翻译论文标题、生成中文解读摘要和标签
-   自动对论文进行学科分类，便于筛选相关主题
-   Web界面展示论文标题（中英文）、中文解读、发布日期、DOI、期刊来源、学科分类、标签等信息
-   支持按学科分类筛选论文，实现快速定位感兴趣的研究领域
-   提供论文详情弹窗（前端可能需要完善触发逻辑）
-   支持手动触发数据更新流程（后端已实现，前端可能需要添加按钮）
-   后端支持按关键词搜索相关论文（涵盖标题、摘要、标签）
-   多期刊源支持（目前默认为 Scientific Data，架构支持未来扩展）

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
│   ├── process.py              # NLP处理脚本 (调用AI API进行翻译、解读、分类和标签生成)
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
    打开终端，进入项目根目录，运行数据处理流水线：
    ```bash
    python get_data/data_pipeline.py
    ```
    该命令会执行爬虫、NLP处理（包括翻译、解读、分类和生成标签），并更新相关数据文件。观察终端输出，确保没有错误，特别是关于API调用的错误。

2.  **启动Web应用**:
    在项目根目录运行以下命令启动Flask应用：
    ```bash
    python app.py
    ```

3.  **访问应用**:
    在浏览器中**必须通过 Flask 服务器提供的地址**访问: `http://127.0.0.1:5000`。
    **不要直接打开 `index.html` 文件**，否则页面无法正确加载数据和交互。

## 使用方法

-   **浏览论文**: 打开应用主页即可查看最新的论文列表，按发布日期倒序排列。
-   **筛选论文**: 点击页面上方的学科分类按钮进行筛选，快速找到相关领域的研究。
-   **查看详细信息**: 每篇论文卡片显示标题、中文翻译、发布日期、DOI、期刊、学科分类和标签信息。
-   **查看详情**: 论文详情的模态框和数据显示逻辑已在 `script.js` 中实现 (`showArticleDetails` 函数)，但前端页面当前未实现点击论文卡片触发详情显示的功能。
-   **阅读原文**: 点击"查看原文"链接跳转到期刊官网。
-   **搜索论文**: 后端 `/articles` API 支持 `keyword` 参数进行搜索，但前端页面当前未集成搜索框。
-   **刷新数据**: 后端 `/refresh` API 支持手动触发数据更新，但前端页面当前未集成"刷新数据"按钮。

## 预设学科分类

系统采用了以下预定义的学科分类体系，用于对论文进行自动分类：

- 生物技术
- 气候科学
- 计算生物学与生物信息学
- 疾病
- 生态学
- 工程学
- 环境科学
- 环境社会科学
- 遗传学
- 医疗保健
- 水文学
- 数学与计算
- 医学研究
- 微生物学
- 神经科学
- 海洋科学
- 植物科学
- 科学界
- 社会科学
- 动物学
- 其他

## 注意事项

-   数据更新依赖于DeepSeek API，请确保API密钥有效且网络连接正常。API调用可能需要时间并消耗配额。
-   爬虫和API调用应遵守相关服务的使用条款，避免过于频繁的请求。
-   数据处理流程会将原始数据和处理后数据分别保存在 `get_data/raw_papers.csv` 和 `get_data/processed_papers.csv` 中，并将最终结果导出到 `get_data/nature_data_articles.json` 供Web应用使用。
-   每次数据处理都会将原始数据和处理后数据备份到 `get_data/backups/` 目录，文件名包含时间戳。

## 后续改进计划

-   完善前端：添加搜索框、实现点击卡片查看详情、添加刷新数据按钮。
-   添加更多期刊来源，扩展科研数据的覆盖范围。
-   优化错误处理和日志记录。
-   增加数据可视化功能，如热门研究主题统计图表。
-   优化前端筛选和交互体验，提供多维度的筛选组合（如按学科+期刊筛选）。
-   根据用户反馈调整学科分类体系，提高分类准确性。

## 许可证

MIT