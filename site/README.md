# DataPaper Web Workspace

网页前端使用 React + vinext，保留现有 Sites 部署结构。

## 本地完整运行

优先在项目根目录运行 `python run_workspace.py`，同时启动网页和 Python API。
单独开发：`npm run dev`。`site/.dev.vars` 配置 `DATAPAPER_API_URL=http://127.0.0.1:5000`。
该文件被忽略，不上传至网站。缺少后端时显示真实论文快照与词表匹配。

## 检查

- `npm test`：检索、来源、导出和快照契约。
- `npm run typecheck`：类型检查。
- `npm run lint`：代码检查。
- `npm run build`：构建 Worker 和浏览器资源。

`runtime.d.ts` 是 Wrangler 从现有构建配置生成的运行时类型。`optional-bindings.d.ts` 声明保留的可选数据库类型。工作台不要求 D1。

## 部署边界

`.openai/hosting.json` 指向原有私有网站。云端不能访问本机 localhost、MariaDB 或 FAISS。
部署未配置可达的 Python 后端时，提供明确标注的快照体验。连接公网后端前需配置鉴权、限流和运行监控；不要公开现有本地开发服务器。

游客清单和笔记保存在浏览器；登录后经 `/api/account/*` 同源代理保存到 Flask 用户库。右上角进入注册、登录、个人资料、密码修改和本地清单导入；侧栏提供最近阅读。账户数据不能回退成匿名的云端记录。详情展示的是论文证据，不是数据文件验证结论。

用户模块的使用方法、同步冲突规则和上线限制见 `../docs/用户模块首版_2026-10-03.md`。

## 跨学科需求与属性

研究问题助手支持通用属性、六类可组合学科模板和自定义文字属性。所有模板默认不选。
共享字段定义位于 `public/data/requirements-framework.json`；Python和网页读取同一份定义。
必须条件与偏好分开，只有带原文来源、核验状态和核验日期的属性才参与比较。
当前论文快照尚未登记核验属性，所以条件判断显示未知。完整说明见项目根目录 `docs/跨学科需求与属性框架_v1.md`。
