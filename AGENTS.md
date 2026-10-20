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

## 注意事项

1. **API Key 安全**：永远不要将 `.env` 文件提交到版本控制
2. **数据库迁移**：当前使用 SQLite，SQLAlchemy 自动建表
3. **文件上传**：RAG 任务文件存储在 `uploads/rag_jobs/` 目录
4. **异步任务**：评测任务使用后台任务执行，通过 WebSocket 推送进度
5. **种子数据**：首次启动会自动创建示例数据，方便快速体验

## 调试技巧

- 后端日志：查看控制台输出，包含 SQL 查询和 API 请求
- 前端调试：浏览器开发者工具 + React DevTools
- API 测试：使用 http://localhost:8000/docs 交互式文档
- 数据库查看：使用 DB Browser for SQLite 打开 `eval_platform.db`