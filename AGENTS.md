# AGENTS.md - AI 评测平台项目指南

## 项目概述

这是一个面向 RAG、AI Agent、多轮对话等场景的 AI 应用评测平台。评测内核由平台原生执行器负责，直接使用 OpenAI 兼容模型返回评分和评判理由。

**技术栈：**
- 后端：FastAPI + SQLAlchemy + SQLite + Python 3.9+
- 前端：React 18 + TypeScript + Ant Design 5 + Vite
- 评测 LLM：通义千问 Qwen Plus (DashScope，OpenAI 兼容)

## 项目结构


## 编码规范

### Python 后端
- 使用类型注解
- 遵循 PEP 8 规范
- 异步函数使用 `async/await`
- 错误处理使用 HTTPException
- 日志记录使用 logging 模块

### TypeScript 前端
- 严格类型检查
- 组件使用函数式 + Hooks
- 使用 Ant Design 组件库
- API 调用封装在 services 层
- 类型定义放在 types 目录

## 常见任务

### 添加新的评测指标
1. 在 `backend/app/models/metric_definition.py` 中定义指标
2. 在 `backend/app/core/evaluation_engine.py` 中实现评分逻辑
3. 在前端 `frontend/src/components/MetricConfigPanel.tsx` 中添加配置界面

### 添加新的 API 端点
1. 在 `backend/app/api/` 中创建或修改路由文件
2. 定义 Pydantic schemas 在 `backend/app/schemas/`
3. 在 `backend/app/main.py` 中注册路由

### 添加前端页面
1. 在 `frontend/src/pages/` 中创建页面组件
2. 在 `frontend/src/App.tsx` 中添加路由
3. 如需要，在 `frontend/src/services/api.ts` 中添加 API 调用

### 修改 RSI 自进化闭环
RSI 是独立于评测引擎的闭环模块，代码分布在：
- `backend/app/models/rsi.py`：`rsi_loops` / `rsi_iterations` / `rsi_proposals` / `rsi_config_versions` 四表
- `backend/app/core/rsi_policy.py`：验收策略、holdout 稳定哈希切分、冻结阈值、指标汇总与判定
- `backend/app/core/rsi_patch.py`：Patch 白名单、`before_value` 漂移校验、快照/写回/回滚
- `backend/app/core/rsi_diagnosis.py`、`rsi_proposer.py`：失败归因与提案生成（只读 train）
- `backend/app/core/rsi_regression.py`、`rsi_engine.py`：影子回归（复用 `EvalTask.scenario_snapshot` + `run_evaluation`）与循环编排
- `backend/app/api/rsi.py`：`/api/rsi/*` 路由，`RSI_ENABLED=false` 返回 403

约束：不要修改评测引擎评分逻辑与 Judge 契约；候选配置只通过影子任务的 `scenario_snapshot` 传入；验收必须使用创建循环时冻结的 `reference_thresholds`；写回必须先快照再落库，默认人工审批。

## 环境变量说明

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_API_KEY` | DashScope API Key | 必需 |
| `LLM_MODEL` | 使用的模型 | qwen-plus |
| `LLM_ENDPOINT` | API 端点 | DashScope 兼容模式 |
| `DATABASE_URL` | 数据库连接 | sqlite:///./eval_platform.db |
| `CORS_ORIGINS` | CORS 白名单 | ["http://localhost:5173"] |
| `SEED_ON_STARTUP` | 启动时填充种子数据 | true |
| `RSI_ENABLED` | RSI 模块总开关，关闭后 `/api/rsi/*` 返回 403 | true |
| `RSI_MAX_ITERATIONS` | 单循环最大迭代数 | 3 |
| `RSI_MAX_ROWS_PER_ITERATION` | 每轮最大评测行数（预算/归因裁剪口径） | 50 |
| `RSI_MAX_LLM_CALLS` | 每循环 LLM 调用预算上限 | 300 |
| `RSI_MAX_MINUTES` | 每循环耗时预算上限 | 45 |
| `RSI_MAX_PROPOSALS_PER_ITERATION` | 每轮最多提案数 | 3 |
| `RSI_HOLDOUT_RATIO` | holdout 抽样比例 | 0.3 |
| `RSI_MIN_OBJECTIVE_GAIN` | 验收最小目标增益 | 0.03 |
| `RSI_MAX_METRIC_DROP` | 受保护指标最大降幅 | 0.02 |
| `RSI_AUTO_APPLY_LOW_RISK` | 是否允许低风险补丁自动采纳 | false |
| `RSI_PROPOSER_TEMPERATURE` | 提案模型采样温度 | 0.2 |
| `LOG_LEVEL` | 应用日志级别 | INFO |
| `LOG_JSON` | 是否输出 JSON 结构化日志 | false |
| `RATE_LIMIT_ENABLED` | 是否启用重任务限流中间件 | true |
| `RATE_LIMIT_HEAVY_PER_MIN` | 重任务 POST 每分钟上限（按 IP） | 120 |
| `MAX_UPLOAD_MB` | 上传文件大小上限（MB） | 20 |
| `EVAL_METRIC_CONCURRENCY` | 单行内指标并发度 | 3 |
| `EVAL_CACHE_ENABLED` | 是否启用 LLM 指标结果缓存 | true |
| `JUDGE_MAX_CONCURRENCY` | Judge 模型调用并发上限 | 4 |
| `JUDGE_MAX_RETRIES` | Judge 调用重试次数（429/5xx/网络错误） | 2 |
| `JUDGE_SAMPLES` | 关键指标重复采样次数 | 1 |
| `LLM_FALLBACK_MODEL` | 主模型失败后的备用模型（留空不启用） | "" |
| `LLM_PRICE_INPUT_PER_1K` | 输入 token 每千个价格（用于成本估算） | 0.0 |
| `LLM_PRICE_OUTPUT_PER_1K` | 输出 token 每千个价格（用于成本估算） | 0.0 |
| `SUMMARY_BOOTSTRAP_ITERS` | 汇总统计 bootstrap 迭代次数（0 关闭置信区间） | 1000 |

## 文档与 Git 协作规则

### 文档存放位置
- 所有说明、方案、复盘类文档统一放在 `docs/` 目录（即需求中约定的 `doc` 文件夹，本项目沿用既有目录名 `docs/`）。
- 不要在项目根目录或代码目录下新建 Markdown 文档；例外：`AGENTS.md` 作为工作区规则文件保留在根目录。

### Git 提交节奏（每 2 次修改对话合并提交一次）
**默认不自动提交。** 只有在累计完成 **2 次包含代码 / 配置文件 / 文档修改的对话交互**后，或用户显式要求提交时，才统一执行一次 Git 变更管理。

1. 第 1 次包含文件修改的对话：正常新增 / 修改 / 删除文件，**不执行** `git commit`、`git push`。
2. 累计到第 2 次包含文件修改的对话（或用户主动要求提交）时，统一执行：
   - `git add .` 暂存全部变更；
   - `git commit -m "<中文详细提交描述>"`，提交信息必须简明、专业、清晰，概括本轮累计修改的核心内容与变更点；
   - `git push` 同步到远程仓库；
   - 若无远程分支或推送需确认，直接向用户汇报当前 Git 状态，不擅自创建远程。
3. 提交完成后，计数器归零，重新开始下一轮 2 次对话修改周期。
4. 若某次对话只做问答、阅读、验证而不修改文件，不计入周期。

## 注意事项

1. **API Key 安全**：永远不要将 `.env` 文件提交到版本控制
2. **数据库迁移**：当前使用 SQLite，SQLAlchemy 自动建表
3. **文件上传**：RAG 任务文件存储在 `uploads/rag_jobs/` 目录
4. **异步任务**：评测任务使用后台线程执行，进度通过轮询或 `GET /api/evaluations/{task_id}/stream`（SSE）获取
5. **种子数据**：首次启动会自动创建示例数据，方便快速体验

## 调试技巧

- 后端日志：查看控制台输出，包含 SQL 查询和 API 请求
- 前端调试：浏览器开发者工具 + React DevTools
- API 测试：使用 http://localhost:8000/docs 交互式文档
- 数据库查看：使用 DB Browser for SQLite 打开 `eval_platform.db`