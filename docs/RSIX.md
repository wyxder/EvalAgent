# RSIX 自进化能力设计与实施计划（最终合并版）

> 文档定位：可直接执行的工程设计与实施计划，合并 `docs/RSI.md` 与 `RSI1.md` 的优点，并修正两份原稿中的关键问题。
> 适用基线：`backend/app`（FastAPI + SQLAlchemy + SQLite/PG + 原生 Judge 引擎）、`frontend/src`（React + Ant Design）、`backend/tests`（pytest）。
> 目标读者：后端、前端、评测算法、测试与运维同学。
> 版本：v1.0（最终合并版）。

---

## 0. 摘要（TL;DR）

- **RSI 定义**：本项目中的 RSI 指 **评测驱动的配置自进化**。平台用自身评测结果驱动平台内可配置资产（场景指标 Prompt、阈值、非内置指标 config、数据集 hard-case、P2 的接口请求模板）的自动诊断、结构化提案、影子回归、人工审批、版本写回与回滚，形成“评估 → 归因 → 提案 → 回归 → 采纳/回滚 → 再评估”的递归闭环；**不训练模型权重，不做无约束代码自改写**。
- **核心复用**：`EvalTask.scenario_snapshot` 冻结机制 + `run_evaluation()` 原生执行器 + `EvalRowResult.metric_scores` 逐条证据 + `scenario_snapshot` 反序列化。RSI 只构造“候选快照”，不改评分逻辑。
- **核心安全线**：白名单结构化 Patch、`before_value` 漂移校验、长度/敏感串校验、先快照后写回、默认人工审批、一场景单 running loop、超预算停止、一键回滚、响应脱敏。
- **关键修正**（相对两份原稿）：
  1. 版本模型采用“按实体保存 before 快照 + 写回实体 + 回滚恢复字段”，不采用“只切 `is_active` 指针”的方案，确保普通评测真正读得到新配置/回滚结果。
  2. 验收口径改为 **阈值无关**：优先使用指标均值或冻结参考阈值下的 `reference_pass_rate`，避免“降低 `pass_threshold` 刷通过率”。
  3. Holdout 采用同数据集稳定哈希划分，并明确 **归因/提案只读 train，验收只读 holdout**，防止 holdout 通过归因输入泄漏。
  4. MVP 不开放 `weight` Patch（当前 `weight` 未参与汇总与通过判定），P1 完成加权汇总后再开放。
  5. 小样本降级：holdout 行数不足时禁用 holdout 并强制人工审批；`N_min=30` 只作为“允许自动采纳”的门槛，不作为“能否跑 MVP”的门槛。
  6. SQLite 下候选评估串行执行；两阶段评估、缓存、并发信号量放到 P1/P2，且并发需先解决 SQLite 写锁。
- **实施节奏**：M0 设计冻结 0.5–1 人日；MVP 约 21 人日（含 15% 缓冲约 24 人日）；P1 约 11 人日；P2 约 8–10 人日（含可选 Alembic 约 9.7 人日）。
- **兼容性承诺**：新增表、可空列、路由、页面；现有 9 个后端路由模块、5 个测试模块、12 条前端路由行为不变。

---

## 1. 背景与目标

### 1.1 背景与痛点

| 现状 | 痛点 |
|------|------|
| 平台已具备“数据集 → 场景指标 → Judge 执行 → 报告 → 人工复核/盲测”的完整链路 | 评测只产出分数，不产出可执行的改进动作，改进仍靠人读报告、手工改 Prompt、再手动重跑 |
| `ScenarioMetric.prompt_override` 支持场景级判据覆盖 | 判据好坏全凭经验，缺少数据驱动的回归验证 |
| `EvalRowResult.metric_scores` 保存 `{score, reason}`，reason 截断 800 字 | 失败归因没有被结构化沉淀，无法聚类复用 |
| 场景指标修改后，历史任务因 `scenario_snapshot` 冻结而可复现 | 修改本身没有版本、没有回归证据、没有回滚机制 |
| RAG 数据集可由文档生成、也可人工导入 | 困难样本不随评测结果演进，失败簇无法自动补强 |
| 现有 `/reports/{id}/compare` 只能比较同数据集、同场景、同指标名集合的任务 | 无法直接支撑“改判据/改阈值”的候选与基线对比 |

### 1.2 RSI 定义

> **评测驱动的配置自进化（Evaluation-Driven Recursive Self-Improvement）**：以一次已完成的评测为基线，自动完成失败归因、候选配置提案、白名单校验、影子回归评估与验收判定，并在人工审批（或满足严格条件的低风险自动采纳）后写回平台配置；写回前保存版本快照，支持一键回滚；下一轮以上一轮被采纳的候选为基线继续迭代，直到达到目标、收敛或预算耗尽。

“递归”体现在：

1. **评估对象递归**：第 N+1 轮的基线是第 N 轮被采纳的评估结果，而不是最初基线。
2. **改进对象递归（P2+）**：RSI 自己的验收阈值、预算、提案策略也纳入版本管理，可依据历史提案成功率反向调整，即“改进改进器”。

### 1.3 目标（可度量）

| 目标 | 度量方式 | MVP 目标 | P1/P2 目标 |
|------|----------|----------|------------|
| 缩短改进闭环 | 从“报告失败”到“产出可回归候选配置”的人工步骤数 | 从 ≥6 步降到 ≤2 步（发起 + 审批） | 同等 |
| 改进可验证 | 每轮迭代必须有 baseline/candidate 双评估与 delta | 100% 迭代有 `metrics` 证据 | 增加 holdout 置信区间 |
| 改进可回滚 | 任意采纳动作都能恢复采纳前配置 | 100% 采纳有 `rsi_config_versions` 快照 | 增加启动时一致性校验 |
| 成本可控 | 单 loop LLM 调用次数 | 默认上限 300 次，超限即停 | 两阶段评估 + 缓存，降低 30%+ |
| 不引入回归 | 既有测试 + 前端构建 | 全绿 | 全绿 |
| 人机协同 | 中高风险提案必须人工审批 | 强制 | 低风险可按策略自动 |
| 真实增益（P1） | holdout 上目标指标提升且无受保护指标回归 | 记录但不强制统计显著 | 提升 ≥3%，95% 置信区间下界 >0 |

> 说明：MVP 的目标是“闭环正确、可审计、可回滚”，不承诺统计显著；P1 才引入严格统计门槛。这样既能在 5 行种子数据上演示，也避免小样本导致功能完全不可用。

### 1.4 能力边界（做什么、不做什么）

**做：**

- 优化平台内评测资产：`ScenarioMetric.prompt_override`、`pass_threshold`（MVP）；非内置 `MetricDefinition.config`、数据集 hard-case（P1）；`EndpointTarget.request_body_template`（P2，人工审批 + 盲测门禁）。
- 以影子评测任务验证候选配置，不污染原场景、不改历史任务。
- 产出结构化失败归因、证据行、提案 diff、成本与耗时统计。
- 版本化、审计、回滚。
- 在归因/提案阶段使用独立 `proposer_llm_config_id`，避免提案模型与评判模型完全同源。

**不做（重要）：**

- 不训练/微调模型权重，不做强化学习训练。
- 不修改外部被测系统的代码或其内部 Prompt；只能修改平台保存的请求模板。若被测系统的系统提示词不通过请求传入，平台无法自动优化它。
- 不修改 `metric_type`、`name`、`is_builtin`、`JUDGE_SYSTEM_PROMPT`、评分 JSON 契约。
- 不做无约束代码生成/自我改写，不允许 LLM 直接执行 SQL 或任意 HTTP。
- 不自动删除数据集行，不自动覆盖人工标注的 `reference`。
- MVP 不自动采纳；P2 的低风险自动采纳必须显式开启且仅限非评判类变更。

### 1.5 核心闭环

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          RSI Loop（一个自进化任务）                        │
│                                                                          │
│  ①基线评估 ──► ②失败归因 ──► ③优化提案 ──► ④白名单/静态校验               │
│      ▲              │              │                    │                │
│      │              │              │                    ▼                │
│      │              │              │            ⑤沙盒试跑(P1)             │
│      │              │              │                    │                │
│      │              │              │                    ▼                │
│      │              │              └────────► ⑥影子回归评估（全量+holdout）│
│      │              │                                       │            │
│      │              │                                       ▼            │
│      │              │                          ⑦验收判定（accepted/       │
│      │              │                             rejected/inconclusive） │
│      │              │                                       │            │
│      │              │                          ┌────────────┴─────────┐  │
│      │              │                          ▼                      ▼  │
│      │              │                    人工审批/自动采纳         拒绝/无改善│
│      │              │                          │                      │  │
│      │              │                          ▼                      │  │
│      │              └────────────────── ⑧版本快照+写回+回滚入口        │  │
│      │                                         │                      │  │
│      └────────────── 下一轮以 candidate 为基线 ◄─────────────────────┘  │
│                                                                          │
│   终止条件：达到目标 / 连续 N 轮增益 < ε / 预算耗尽 / 无合法提案 / 人工取消  │
└──────────────────────────────────────────────────────────────────────────┘
```

| 步骤 | 输入 | 处理 | 输出 |
|------|------|------|------|
| ① 基线评估 | 已完成的 `EvalTask` | 校验状态、指标集、数据行数；冻结参考阈值 | `baseline_eval_id` + `summary_scores` + `reference_thresholds` |
| ② 失败归因 | `EvalRowResult`（train 切片） | 规则聚合 + LLM 聚类 + 失败降级 | `diagnosis.clusters[]` |
| ③ 优化提案 | 归因 + 当前配置快照 | LLM 生成结构化 Patch | `rsi_proposals[]` |
| ④ 静态校验 | Patch | 白名单、漂移、类型/范围、长度/敏感串、风险分级 | 合法 Patch / 拒绝原因 |
| ⑤ 沙盒试跑(P1) | 合法 Patch + 代表行 | 复用单行调试链路 | 预筛结果，降低全量回归成本 |
| ⑥ 影子回归 | 候选 `scenario_snapshot` | 创建 `EvalTask` + `run_evaluation()` | `candidate_eval_id` |
| ⑦ 验收判定 | 双评估逐行结果 | 阈值无关目标 + 约束 + holdout + 人工门禁 | `accepted/rejected/inconclusive` |
| ⑧ 采纳与版本 | accepted + 审批 | 先快照、再写回实体、再记录 | `rsi_config_versions` + 回滚入口 |

### 1.6 需求清单（R1–R10）

| 编号 | 需求 | 优先级 | 对应任务 |
|------|------|--------|----------|
| R1 | 从历史评测结果自动抽取失败信号（低分/错误/人工复核/盲测） | 必须 | B5 |
| R2 | 对失败做归因聚类（判据歧义/字段缺失/检索缺陷/接口失败/数据标注噪声） | 必须 | B5 |
| R3 | 自动生成候选变异（判据改写/阈值调整；P1 指标 config/数据集） | 必须 | B6 |
| R4 | 在固定 train/holdout 划分上自动重评测候选，计算 delta | 必须 | B8 |
| R5 | 门禁校验（防回归、错误率、样本量、人工审批） | 必须 | B9 |
| R6 | 版本化、血缘、一键采纳与回滚、审计留痕 | 必须 | B4/B12 |
| R7 | Web 可视化：运行列表/详情/时间线/提案 diff/审批/回滚 | 必须 | F2/F3 |
| R8 | 成本与预算管控、收敛停止、P1 两阶段评估剪枝 | 重要 | B9/B22 |
| R9 | 被测接口请求模板的自进化 + 盲测人工验证 | 增强（P2） | B16/B17 |
| R10 | 反奖励黑客：阈值无关验收、判据交叉校验、对抗集/跨场景校验 | 重要（P1/P2） | B21/B24 |

---

## 2. 现状分析

### 2.1 现有架构事实（以代码为准）

| 维度 | 现状 | 对 RSI 的含义 |
|------|------|---------------|
| 后端分层 | `api/` 路由 → `core/` 引擎 → `models/` ORM → `schemas/` Pydantic | RSI 按同一分层新增 `api/rsi.py`、`core/rsi_*.py`、`models/rsi.py`、`schemas/rsi.py` |
| 任务执行 | `threading.Thread` + `asyncio.run(run_xxx(task_id, SessionLocal))`，进度/日志写库 | RSI 复用同一模式，不引入 Celery/Redis |
| 前端进度 | 评测任务/日志 1s（`EvaluationPage`、`ExperimentWorkbenchPage`），盲测/RAG 任务页 1–2s；无 WebSocket 实现 | RSI 沿用轮询，不新增长连接设施 |
| 配置冻结 | `build_scenario_snapshot()` 在任务创建时冻结指标 Prompt/阈值/权重/指标 config；`run_evaluation()` 优先用快照 | 可用“候选快照”跑回归，不改原场景即可验证 |
| Judge 引擎 | `OpenAIJudgeClient` + 原生指标类；逐条持久化 `{score, reason}`；`diagnose_metric_prompt()` 可检测 Prompt 与字段冲突 | 直接复用；`diagnose_metric_prompt` 可作为提案静态校验器 |
| 汇总口径 | `_determine_pass()` 只看 `pass_threshold`；`_compute_summary_scores()` 输出 mean/min/max/pass_rate/error_count；`weight` 当前未参与汇总与通过判定 | 验收必须使用阈值无关指标或冻结参考阈值；MVP 不开放 `weight` |
| 报告对比 | `GET /reports/{id}/compare` 要求同数据集、同场景、指标名集合一致，否则 422 | RSI 自算 delta，不复用 compare；MVP 禁止增删指标 |
| 数据库 | SQLite 默认 + `create_all` + `ensure_runtime_schema()` 手工补列；无 Alembic | 新表由 `create_all` 自动创建；`eval_tasks` 新列必须写补丁；模型必须在 `models/__init__.py` 注册 |
| 敏感数据 | `schemas/sensitive.py` 提供 `mask_secret` / `redact_sensitive_mapping`；LLM Key、Endpoint Authorization 不回显 | RSI 的 loop 响应与提案 diff 必须复用脱敏；禁止把 Authorization 发送给提案 LLM |
| 内置指标保护 | `api/metric.py` 禁止更新/删除 `is_builtin=True` 的指标 | 优化内置指标只能写 `ScenarioMetric.prompt_override`，不能改 `MetricDefinition` |
| 长任务恢复 | `recover_stale_rag_dataset_job()` 按超时将 `running` 回收为 failed | RSI 需实现同类 `recover_stale_rsi_loop()` |
| 单行调试 | `/api/evaluations/debug` 的核心逻辑写在路由函数内，包含字段/Prompt 冲突告警与 Judge trace | P1 抽取到 `core/evaluation_debug.py` 后供沙盒试跑复用 |
| RAG 生成 | 文档解析 + 分块 + 质量打分 + LLM 出题/校验 + 15 分钟超时 | P2 可复用为“失败簇相似样本合成” |
| 鉴权 | 当前无登录/RBAC | RSI 默认人工审批，生产需前置网关鉴权；审批记录先记录“系统/人工” |

### 2.2 现有模块与 RSI 的关联点

| 模块 | 现状能力 | RSI 关联点 | 复用 / 改造 |
|------|----------|------------|-------------|
| `dataset` / `DatasetRow` | 统一样本契约、`field_schema`、导入导出、回写 | 回归数据源；失败簇定位；hard-case 追加 | 复用读取；P1 新增“派生数据集 + 行来源标记”（建议 `DatasetRow.data._rsi_origin` 或新增可空列） |
| `evaluation`（EvalTask/EvalRowResult） | 任务、进度、日志、逐行得分、接口 trace | 基线与回归载体 | 新增可空列 `rsi_loop_id`、`rsi_iteration_id`，不影响现有查询 |
| `core/evaluation_engine.py` | 指标构建、Judge 调用、通过判定、汇总 | 回归执行与指标口径 | 直接复用 `run_evaluation`；`_determine_pass`/`_compute_summary_scores` 保持不动 |
| `/api/evaluations/debug` | 单行试跑、Judge Prompt/trace、字段与 Prompt 冲突告警 | P1 沙盒试跑 | 抽取 `core/evaluation_debug.py`，路由改为调用，行为不变 |
| `metric` | 内置 + 自定义指标；`config.prompt/definition/allowed_values` | 提案对象（仅非内置） | 复用；新增 Patch 白名单约束 |
| `scenario` / `ScenarioMetric` | 指标挂载、权重、阈值、`prompt_override` | 主要写回落点 | 复用 ORM；写回前先做版本快照 |
| `llm_config` | Judge/生成模型配置，API Key 脱敏 | 需要区分 Judge 与提案模型 | 新增 `proposer_llm_config_id`（可空，默认取 Judge） |
| `endpoint_target` | 接口 URL/传输/鉴权/请求模板/响应映射 | 回归时复用同一被测接口；P2 提案模板 | 复用 `invoke_endpoint`；loop 内保存 `target_config` 快照并脱敏返回 |
| `blind_test` | A/B 人工偏好 | P2 采纳后的主观验证门禁 | 复用创建/汇总逻辑，不改造 |
| `rag_dataset_job` | 文档 → 样本 | P2 针对失败簇合成相似样本 | 复用分块/生成/校验函数 |
| `report` | 摘要、逐条、复核、版本对比 | RSI 详情页展示口径 | 复用 delta 思路；不能直接调用 compare |
| `prompt_manager` | 平台级 System Prompt 与渲染器 | 新增 RSI 诊断/提案 Prompt | 扩展常量，不混入业务 Prompt |
| `scenario_snapshot` | 快照构建与反序列化 | 候选快照构建 | 扩展“按提案覆盖指标”的构建函数，保持旧签名兼容 |
| `database.ensure_runtime_schema` | 轻量补列 | 新列补丁 | 追加 `eval_tasks.rsi_*` |
| `sensitive` | 脱敏工具 | 提案/循环响应 | 复用 |

### 2.3 可复用能力清单

1. `run_evaluation(task_id, SessionLocal)`：构造 `EvalTask` 即可获得与人工评测一致的执行、进度、日志、逐行结果。
2. `build_scenario_snapshot` / `snapshot_to_scenario_metrics`：配置冻结与反序列化，是“影子配置”的基础。
3. `diagnose_metric_prompt`：检查指标类型与 Prompt 冲突、变量缺失、离线模式 `endpoint.*` 不可用等问题，直接用于提案静态校验。
4. `EvalRowResult.metric_scores` 的 `{score, reason}` 结构：失败归因的原始证据。
5. `/api/evaluations/debug` 的 trace 结构：沙盒试跑的可解释输出。
6. 线程 + `asyncio.run` + 状态/日志落库 + 轮询：最小可用的长任务编排。
7. `recover_stale_rag_dataset_job`：任务恢复范式。
8. `redact_sensitive_mapping`：敏感字段响应保护。
9. `build_metric` 与 `MetricDefinition.config`：无需改动即可评估新 Prompt。

### 2.4 需要改造或补齐的部分

| 缺口 | 说明 | 方案 |
|------|------|------|
| 无配置版本表 | 场景/指标修改无 before 快照，无法回滚 | 新增 `rsi_config_versions`，按 `(scope, scope_id)` 唯一版本 |
| `metric_overrides` 能力有限 | 只支持 `prompt_override/pass_threshold/weight`，且按 `metric_definition_id` 覆盖，无法改指标 `config` | RSI 直接构造候选 `scenario_snapshot`，不依赖创建接口 |
| 单行调试逻辑在路由内 | 无法被引擎复用 | 抽取 `core/evaluation_debug.py` |
| 任务归属不可追溯 | `EvalTask` 无法看出属于哪个 RSI 迭代 | 新增可空列 + 索引 |
| 无失败聚类 | 只有逐行 reason | 新增 `rsi_diagnosis.py`（规则 + LLM + 降级） |
| 无预算/验收策略 | 无统一停止与判定 | 新增 `rsi_policy.py` |
| `weight` 未参与汇总 | 改权重无实际效果 | MVP 禁止 `weight` Patch；P1 先补加权汇总再开放 |
| 阈值可变导致 pass_rate 可被“刷” | 降阈值即可提高通过率 | 验收使用指标均值或冻结参考阈值下的 `reference_pass_rate` |
| 判据变更导致 baseline/candidate 不可比 | Judge Prompt 变了，分数不是同一把尺子 | P1 判据交叉校验；MVP 强制人工审批 + 固定 Judge |
| Holdout 可能泄漏到归因 | 归因读取全量失败行会把 holdout 失败样本带入提案 | 显式 train/holdout 划分，归因只读 train |
| 缺少任务恢复 | 进程重启后 loop 可能卡在 running | `recover_stale_rsi_loop()` |
| 文档缺 RSI 章节 | 用户不知道如何用 | 本文 + `usage-guide.md` 增补 |

### 2.5 对现有系统的影响分析

**架构影响**

- 新增独立业务域 `rsi`，不侵入评测引擎内部；RSI 与评测之间只通过 `EvalTask` / `EvalRowResult` / 配置快照交互。
- 新增后台线程与现有评测/盲测/RAG 任务一致，不引入消息队列；SQLite 下 loop 串行、候选评估串行。
- 新增一个可选的“单行调试”抽取层（P1），路由行为不变。

**数据库影响**

- 新增 4 张核心表：`rsi_loops`、`rsi_iterations`、`rsi_proposals`、`rsi_config_versions`。
- `eval_tasks` 新增 2 个可空列：`rsi_loop_id`、`rsi_iteration_id` + 索引；由 `ensure_runtime_schema()` 兼容旧库。
- P1 可选新增 `rsi_signals`、`rsi_clusters` 两张分析表；MVP 用 `rsi_iterations.diagnosis` JSON，避免过早复杂化。
- 不修改任何现有列类型/约束；历史数据无需迁移。

**API 影响**

- 新增 `/api/rsi/*`，全部为新增端点；现有 9 个路由模块行为不变。
- 现有 `/reports/{id}/compare` 约束不变；RSI 自算 delta。
- 响应统一脱敏 `target_config`；提案上下文不包含 Authorization/API Key。

**前端影响**

- 新增 2 个页面与 1 个菜单分组；`App.tsx` 增加 2 条路由，不改既有 12 条路由。
- `ReportDetailPage` 增加“发起自进化”入口（P1），不改变现有 Tabs。
- 类型与 API 封装按现有 `types/index.ts`、`services/api.ts` 约定扩展。

**测试影响**

- 现有 5 个测试模块不受影响（新表由 `create_all` 建；新列可空）。
- 新增 7 个测试文件（MVP 4 个、P1 2 个、P2 1 个）；需 mock LLM 与评测执行，保证离线可跑。

**性能与成本影响**

- 每轮回归成本 ≈ `采样行数 × LLM 指标数` 次 Judge 调用；默认 `max_rows_per_iteration=50`、`max_iterations=3`、`max_llm_calls=300`。
- 归因/提案为低频调用（每轮 1–2 次）；P1 两阶段评估可显著降低候选筛选成本。
- SQLite 下串行执行，单 loop 预计 10–45 分钟；P2 可切 PostgreSQL 提升并发。

**安全影响**

- 新增“LLM 生成配置变更”攻击面：必须白名单 + 结构化校验 + 不执行任意代码/SQL/HTTP。
- 数据集内容进入提案 Prompt，存在提示注入风险，需分隔、截断、条数上限。
- 配置写回需审计与回滚，避免业务口径被静默篡改。
- 当前无鉴权，RSI 默认人工审批；生产需前置鉴权与审批人记录。

---

## 3. 总体设计

### 3.1 设计原则

1. **评估引擎零侵入**：不修改 `evaluation_engine.py` 的评分逻辑与 Judge 契约。
2. **影子优先**：任何候选配置先以快照形式跑影子评测，通过后才写回实体。
3. **白名单 + 结构化**：LLM 只能产出受限 JSON Patch，平台负责校验与执行。
4. **先快照后写回**：写回前必须生成版本快照，失败可回滚。
5. **人机协同**：默认人工审批；低风险自动采纳必须显式开启，且不适用于判据/阈值类变更。
6. **证据可追溯**：每个提案关联失败行 id、指标名、Judge reason 摘要与前后 diff。
7. **失败可降级**：LLM 归因/提案失败时降级为规则归因或直接终止，不产生“半改”状态。
8. **阈值无关验收**：验收目标不使用候选自己的 `pass_threshold` 计算通过率；使用指标均值或冻结参考阈值。
9. **Holdout 隔离**：归因/提案只读 train，验收只读 holdout；holdout 不进入提案上下文。
10. **一场景一循环**：同一 `scenario_id` 同时只允许一个 `running` loop，避免配置互相覆盖。

### 3.2 分层架构

```
┌───────────────────────────────────────────────────────────────┐
│ 前端：RsiLoopListPage / RsiLoopDetailPage / 报告页入口          │
└───────────────────────────┬───────────────────────────────────┘
                            │ REST（轮询）
┌───────────────────────────▼───────────────────────────────────┐
│ API 层：backend/app/api/rsi.py                                │
│  - 创建/启动/取消/详情/日志/迭代/审批/回滚/版本                  │
└───────────────────────────┬───────────────────────────────────┘
                            │
┌───────────────────────────▼───────────────────────────────────┐
│ 编排层：core/rsi_engine.py（状态机 + 线程入口 + 日志 + 恢复）    │
│         core/rsi_policy.py（预算 + 验收 + 收敛 + 统计）          │
└───────┬───────────────┬───────────────┬───────────────────────┘
        │               │               │
┌───────▼──────┐ ┌──────▼───────┐ ┌─────▼────────────┐
│ rsi_diagnosis│ │ rsi_proposer │ │ rsi_regression   │
│ 规则+LLM归因 │ │ LLM 提案     │ │ 影子快照+执行+delta│
└───────┬──────┘ └──────┬───────┘ └─────┬────────────┘
        │               │               │
┌───────▼───────────────▼───────────────▼───────────────────────┐
│ 复用层：evaluation_engine / evaluation_debug / endpoint_eval    │
│         scenario_snapshot / prompt_manager / sensitive          │
└───────────────────────────┬───────────────────────────────────┘
                            │
┌───────────────────────────▼───────────────────────────────────┐
│ 存储：rsi_* 新表 + eval_tasks / eval_row_results / 现有资源表    │
└───────────────────────────────────────────────────────────────┘
```

### 3.3 数据流（一次迭代）

1. 读取 `loop.baseline_eval_id` 对应 `EvalTask`，校验 `status=completed`、`summary_scores` 非空。
2. 按指标聚合 `EvalRowResult`：均值、通过率、错误数、最低分行；按失败簇取样。
3. **只取 train 切片**的失败行组装归因 Prompt（含指标定义、阈值、代表性失败样本与 reason 截断），调用提案 LLM；失败则用规则归因。
4. 生成提案 JSON；`rsi_patch.validate` 做白名单/类型/长度/漂移/风险校验。
5. （P1）选取 1–3 条代表行做单行试跑，淘汰无效提案。
6. `rsi_patch.build_candidate_snapshot` 在基线快照上应用合法提案。
7. 创建影子 `EvalTask`（`result_save_mode="task_only"`、`scenario_snapshot=候选快照`、`rsi_loop_id/rsi_iteration_id`），`await run_evaluation(...)`。
8. `rsi_policy.judge` 计算全量、train、holdout 的目标增益、约束违例、失败迁移。
9. 决策：`awaiting_review` / `accepted` / `rejected` / `inconclusive`。
10. accepted 时：先写 `rsi_config_versions` 快照，再写回实体，更新 `best_iteration_id`；下一轮以 candidate 为基线。

### 3.4 任务调度与状态机

**调度方式**（与现有长任务一致）：

```python
# api/rsi.py
def _launch_rsi_loop(loop_id: int) -> None:
    def runner() -> None:
        asyncio.run(run_rsi_loop(loop_id, SessionLocal))
    threading.Thread(target=runner, name=f"rsi-loop-{loop_id}", daemon=True).start()
```

- `run_rsi_loop` 内**顺序**执行迭代（不并发写配置），每步 `db.commit()` 并刷新 `logs`。
- 候选评估在 SQLite 下串行；P1 若要并发，必须先切 PostgreSQL 或引入独立执行器，并解决写锁。
- 取消：前端 `POST /cancel` 置 `status="cancelled"`，并同步把当前候选 `EvalTask.status` 置为 `cancelled`；引擎在每个 LLM 调用/每轮开始时检查 loop 状态。
- 超时：`started_at + max_minutes` 超限即 `failed`，同步把当前候选 `EvalTask.status` 置为 `cancelled`，保留已完成迭代与日志。
- 恢复：列表/详情接口调用 `recover_stale_rsi_loop()`，把超过预算时长仍为 `running` 的 loop 标记为 `failed`，并同步关闭当前候选任务（对齐 `recover_stale_rag_dataset_job`）。
- 并发约束：同一 `scenario_id` 同时只允许一个 `running` loop（创建/启动时校验），避免两个循环互相覆盖配置。

**Loop 状态机**

```
draft ──start──► running ──┬──► awaiting_review ──approve──► running
                           ├──► completed（达到目标/收敛）
                           ├──► failed（异常/超时）
                           └──► cancelled
```

**Iteration 状态机**

```
pending → diagnosing → proposing → validating → evaluating → reviewing
        → accepted | rejected | inconclusive | failed
```

### 3.5 数据模型

新增文件：`backend/app/models/rsi.py`，并在 `backend/app/models/__init__.py` 注册（否则 `create_all` 不会建表）。

#### 3.5.1 `rsi_loops`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | |
| `name` | String(200) | 任务名 |
| `description` | Text | |
| `status` | String(50) | `draft/running/awaiting_review/completed/failed/cancelled` |
| `baseline_eval_id` | Integer FK `eval_tasks.id` | MVP 必填；从已完成的基线评测发起（P1 支持资源配置时先自动生成基线任务） |
| `dataset_id` | Integer FK | 回归数据集（与基线一致） |
| `scenario_id` | Integer FK | 回归场景（保持指标集稳定） |
| `llm_config_id` | Integer FK `llm_configs.id` | Judge 模型 |
| `proposer_llm_config_id` | Integer FK nullable | 提案模型；空则复用 Judge，建议不同模型 |
| `evaluation_mode` | String(50) | `offline/endpoint`，与基线一致 |
| `endpoint_target_id` | Integer FK nullable | |
| `target_config` | JSON | 端点配置快照（响应脱敏） |
| `response_mapping` | JSON | |
| `result_save_mode` | String(50) | 引擎强制 `task_only` |
| `objective_metric` | String(100) nullable | 主优化指标名；空则用 `reference_pass_rate` |
| `objective_target` | Float nullable | 目标值 |
| `objective_mode` | String(30) | `metric_mean` / `reference_pass_rate` |
| `reference_thresholds` | JSON | 创建 loop 时冻结的每指标参考阈值 |
| `holdout_config` | JSON | `{ratio, min_rows, min_rows_for_auto_accept}` |
| `acceptance_policy` | JSON | 见 3.10 |
| `budget` | JSON | 见 3.10 |
| `usage` | JSON | `llm_calls/prompt_tokens/completion_tokens/elapsed_ms/evaluations` |
| `current_iteration` | Integer | 已执行轮次 |
| `best_iteration_id` | Integer nullable | 当前最优迭代 |
| `final_eval_id` | Integer FK nullable | 结束时的代表评估 |
| `auto_apply_low_risk` | Boolean | 默认 false |
| `error_message` | Text | |
| `logs` | Text | 追加式日志，格式对齐 `EvalTask.logs` |
| `started_at` / `finished_at` / `created_at` / `updated_at` | DateTime | |

索引：`(status, created_at)`、`baseline_eval_id`、`scenario_id`。

#### 3.5.2 `rsi_iterations`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | |
| `loop_id` | Integer FK cascade | |
| `iteration_index` | Integer | 从 1 开始 |
| `status` | String(50) | 见状态机 |
| `baseline_eval_id` / `candidate_eval_id` | Integer FK nullable | 双评估 |
| `diagnosis` | JSON | `{summary, clusters[], sample_row_ids[], fallback}` |
| `metrics` | JSON | `{baseline, candidate, delta, train, holdout, decision_metrics}` |
| `proposal_count` | Integer | |
| `decision` | String(50) | `accepted/rejected/inconclusive/rolled_back` |
| `decision_reason` | Text | 必须可读 |
| `cost` | JSON | 本轮消耗 |
| `error_message` | Text | |
| `started_at` / `finished_at` / `created_at` | DateTime | |

唯一约束：`(loop_id, iteration_index)`。

#### 3.5.3 `rsi_proposals`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | |
| `loop_id` / `iteration_id` | Integer FK | |
| `target_type` | String(50) | `scenario_metric/metric_definition/scenario/dataset_row/endpoint_target` |
| `target_id` | Integer nullable | |
| `field` | String(100) | 如 `prompt_override`、`config.prompt` |
| `operation` | String(20) | `set/append/create` |
| `before_value` / `after_value` | JSON | diff 展示与漂移校验 |
| `rationale` | Text | 中文理由，必须引用证据 |
| `evidence` | JSON | `{metric, failed_row_ids, reason_snippets, cluster}` |
| `risk_level` | String(20) | `low/medium/high` |
| `requires_review` | Boolean | |
| `status` | String(30) | `proposed/validated/rejected/applied/failed/rolled_back` |
| `applied_version_id` | Integer FK nullable | |
| `decided_by` | String(50) nullable | `system/human:<name>` |
| `decided_at` | DateTime nullable | |
| `decision_source` | String(30) nullable | `auto/manual` |
| `created_at` / `applied_at` | DateTime | |

#### 3.5.4 `rsi_config_versions`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | |
| `loop_id` / `iteration_id` / `proposal_id` | Integer FK | |
| `scope` | String(50) | `scenario_metric/metric_definition/scenario/endpoint_target` |
| `scope_id` | Integer | 实体 id |
| `version` | Integer | 同一 scope 递增 |
| `snapshot` | JSON | 变更前完整实体快照；至少包含：scenario_metric → weight/pass_threshold/prompt_override；metric_definition → config；endpoint_target → request_body_template |
| `patch` | JSON | 实际应用的 Patch |
| `parent_version_id` | Integer FK nullable | 血缘父版本 |
| `actor` | String(50) | `system/human` |
| `created_at` / `rolled_back_at` | DateTime | |

索引/约束：唯一 `(scope, scope_id, version)`；索引 `(loop_id, iteration_id)`。

#### 3.5.5 现有表增量

`eval_tasks` 追加：

```python
rsi_loop_id = Column(Integer, ForeignKey("rsi_loops.id"), nullable=True)
rsi_iteration_id = Column(Integer, ForeignKey("rsi_iterations.id"), nullable=True)
```

`ensure_runtime_schema()` 中追加（模式与现有实现一致）：

```python
"rsi_loop_id": "ALTER TABLE eval_tasks ADD COLUMN rsi_loop_id INTEGER",
"rsi_iteration_id": "ALTER TABLE eval_tasks ADD COLUMN rsi_iteration_id INTEGER",
```

> 注意：`create_all` 只建新表，不会给旧表加列，因此旧库必须走上述补丁；新模型必须在 `models/__init__.py` 导入，否则 `create_all` 看不到。

#### 3.5.6 P1 可选分析表

MVP 不建，避免过早复杂化；P1 若需要跨 loop 分析失败模式，再新增：

- `rsi_signals`：`id/loop_id/iteration_id/source_task_id/row_result_id/metric_name/score/signal_type/reason/manual_tags/cluster_id/created_at`。
- `rsi_clusters`：`id/loop_id/iteration_id/cluster_key/failure_type/affected_metric/description/evidence/suggested_action/confidence/size/created_at`。

### 3.6 Patch DSL 与白名单

**提案输出示例**

```json
{
  "proposals": [
    {
      "target_type": "scenario_metric",
      "target_id": 12,
      "field": "prompt_override",
      "operation": "set",
      "before_value": "判断回答是否忠实于检索上下文……",
      "after_value": "判断回答是否忠实于检索上下文。若回答包含上下文中没有的数字、时间、主体或因果关系，必须扣分……",
      "rationale": "8 条失败样本的 reason 均指出回答出现上下文未支持的限定条件",
      "evidence": {
        "metric": "faithfulness",
        "failed_row_ids": [3, 7, 11, 15],
        "cluster": "unsupported_specifics"
      },
      "risk_level": "medium"
    }
  ]
}
```

**白名单（按阶段）**

| target_type | 允许字段 | 允许操作 | 阶段 | 默认风险 | 约束 |
|-------------|----------|----------|------|----------|------|
| `scenario_metric` | `prompt_override` | `set` | MVP | medium | 仅本场景生效；≤4000 字符；`diagnose_metric_prompt` 无错误；强制人工审批 |
| `scenario_metric` | `pass_threshold` | `set` | MVP | medium | 0–1，单轮变化 ≤0.15；验收用参考阈值/指标均值；强制人工审批 |
| `metric_definition` | `config.prompt`、`config.definition`、`config.description`、`config.allowed_values` | `set` | P1 | medium | 仅 `is_builtin=False`；影响所有引用场景 |
| `dataset_row` | 追加新行 / 新增字段 | `append/create` | P1 | medium | 只增不改不删；写入派生数据集；不得写入 holdout |
| `endpoint_target` | `request_body_template` | `set` | P2 | high | 仅请求模板；不得出现 `authorization/api_key/extra_headers`；强制审批 + 盲测门禁 |
| `scenario` | `description` | `set` | P2 | low | 可选，MVP/P1 不开放 |

**MVP 明确不允许**

- `weight`：当前 `weight` 未参与 `_compute_summary_scores`/`_determine_pass`，改权重不会产生可验证效果；P1 完成加权汇总后再开放。
- `metric_type`、`name`、`is_builtin`、`JUDGE_SYSTEM_PROMPT`、评分 JSON 契约。
- 删除类操作、任意 SQL、任意 URL、`authorization`/`api_key`/`extra_headers`。
- `before_value` 与当前值不一致（说明配置已漂移）→ 直接拒绝。
- Prompt 长度超过 4000 字符，或包含疑似凭据（`sk-`、`Bearer`）→ 拒绝。

**校验函数（建议签名）**

```python
# core/rsi_patch.py
def validate_patch(db, loop, proposal, snapshot) -> list[str]: ...
def build_candidate_snapshot(snapshot: dict, proposals: list[dict]) -> dict: ...
def snapshot_before_apply(db, proposal) -> dict: ...
def apply_patch(db, proposal) -> RsiConfigVersion: ...
def rollback_version(db, version_id: int) -> None: ...
```

**校验顺序**

1. Pydantic `RsiProposalPayload` 结构校验。
2. 白名单（`target_type/field/operation`）。
3. 漂移：`before_value` 必须同时等于基线快照值与当前实体值；任一不一致即拒绝（防止覆盖基线之后的人工修改）。
4. 类型与范围（阈值 0–1、权重 P1、`allowed_values` 非空）。
5. 长度与敏感串。
6. `diagnose_metric_prompt`：用 1 条代表行渲染提案 Prompt，若出现“引用字段不存在/类型与 Prompt 冲突”告警则降级为 `requires_review=True` 或拒绝。
7. 风险分级（低风险且 `auto_apply_low_risk` 才可自动采纳）。
8. 去重：对 `(target_type, target_id, field, after_value)` 做哈希，跨轮拒绝重复提案，避免死循环。

### 3.7 失败归因设计

**第一层：规则聚合（确定性，必做）**

- 只读取 train 切片的 `EvalRowResult`。
- 逐指标：`mean/min/max/pass_rate/error_count`（优先读 `summary_scores`，缺失时按行重算，复用 report 的 `_normalize_metric_summary` 思路）。
- 失败行：`is_pass=False` 或 `score < pass_threshold`，按分数升序取 Top-N。
- 错误行：`error != None`（接口失败、字段缺失、Judge 解析失败）单独成簇。
- 字段缺失：`score=None` 且 reason 含“缺少必需字段”→ 归类为 `missing_field`。
- 无 `pass_threshold` 的指标不参与“失败行”判定，只参与均值观察。

**第二层：LLM 聚类（可选失败降级）**

输出结构（强制 JSON）：

```json
{
  "clusters": [
    {
      "label": "回答出现上下文未支持的具体数字",
      "root_cause_type": "unsupported_specifics",
      "affected_metric": "faithfulness",
      "evidence_row_ids": [3, 7, 11],
      "suggested_lever": "scenario_prompt",
      "severity": "high"
    }
  ],
  "summary": "本轮主要问题集中在……"
}
```

`root_cause_type` 枚举：`prompt_ambiguity / missing_field / judge_misconfiguration / retrieval_gap / answer_incomplete / agent_tool_error / dataset_reference_noise / endpoint_failure / unsupported_specifics / unknown`。

`suggested_lever` 枚举：`scenario_prompt / metric_config / threshold / dataset / endpoint_template / none`。

**输入裁剪**：Top 20 失败行 × 每条 500 字符 reason/字段摘要，总负载控制在 ~8k tokens；按指标分层抽样。

**降级**：LLM 失败/JSON 不合法时，用规则簇（按 `affected_metric + root_cause_type` 分组）继续，并在 `diagnosis.summary` 标注 `fallback=true`。

### 3.8 提案生成与校验

- **Prompt 分层**：System 约束输出格式与安全边界；User 提供归因、当前配置、白名单、验收策略。
- **上下文**：只给必要字段（指标名/类型/阈值/Prompt/失败簇），不传 Authorization、API Key、完整数据集、holdout 行。
- **输出数量**：每轮 ≤3 条，按 `risk_level` 与证据强度排序。
- **证据强制**：每条提案必须包含 `failed_row_ids` 与 `reason_snippets`；没有证据的提案直接拒绝。
- **模型隔离**：优先使用 `proposer_llm_config_id`，与 Judge 模型不同；若相同，风险等级上调一级。
- **静态校验顺序**：见 3.6；校验失败只记录，不落配置。
- **去重与收敛**：同一 `(target, field, after_value)` 不重复提案；连续 2 轮无合法提案则 loop 结束。
- **失败处理**：提案 LLM 超时/JSON 非法 → 本轮标记 `rejected`，不写配置，不影响下一轮。

### 3.9 回归评估与影子快照

**基线快照来源**

- 必须使用 `loop.baseline_eval.scenario_snapshot`；若缺失，直接失败并提示重新基线，**不回退到当前 scenario 实时构建**，避免基线漂移。
- 创建 loop 时同时冻结 `reference_thresholds`（从基线快照的每个 `ScenarioMetric.pass_threshold` 读取；为空则用 0.7 作为参考值并在日志标注）。

**候选快照构建**

- 深拷贝基线快照后只修改白名单字段。
- 保持 `metrics[].metric_definition.name` 集合不变（MVP 硬约束，确保与基线可比）。
- 生成 `candidate_snapshot["_rsi"] = {"loop_id":..., "iteration":..., "proposal_ids":[...]}` 仅用于审计（`snapshot_to_scenario_metrics` 只读 `metrics`，未知根键会被忽略）。

**创建影子任务**

```python
task = EvalTask(
    name=f"[RSI] {loop.name} · iter {index}",
    dataset_id=loop.dataset_id,
    scenario_id=loop.scenario_id,
    llm_config_id=loop.llm_config_id,
    status="pending",
    scenario_snapshot=candidate_snapshot,
    evaluation_mode=loop.evaluation_mode,
    endpoint_target_id=loop.endpoint_target_id,
    target_config=loop.target_config,
    response_mapping=loop.response_mapping,
    result_save_mode="task_only",
    rsi_loop_id=loop.id,
    rsi_iteration_id=iteration.id,
)
```

随后 `await run_evaluation(task.id, SessionLocal)`。由于 `run_evaluation` 优先使用 `scenario_snapshot`，**原场景配置不会被读取或修改**。

**指标计算**

- 总体：pass_rate、fail_count、error_count、逐指标 mean/pass_rate。
- 目标指标：`objective_mode=metric_mean` 时取 `objective_metric` 的均值；`reference_pass_rate` 时用冻结参考阈值对 candidate 的原始 score 重算通过率。
- 迁移：`fixed / new_failures / still_failing / still_passing / new_errors`（语义对齐 `report.compare`，但由 RSI 自行计算）。
- **Holdout 划分**：稳定哈希 `bucket(md5(f"{loop.id}:{dataset_row_id}")) % 100 < holdout_ratio*100`；同一 loop 内稳定。
- **Holdout 隔离**：归因/提案只读 train；验收只读 holdout；候选任务本身仍在全量数据集上执行，但 `rsi_policy` 分别计算 train/holdout 切片。
- **小样本降级**：`rows < holdout.min_rows` 时禁用 holdout，`decision` 只能是 `inconclusive` 或“人工审批后的 accepted”；`holdout_rows < min_rows_for_auto_accept` 时禁止自动采纳。
- **逐指标 delta 与约束检查**：见 3.10。

**为什么不用 `/reports/{id}/compare`**

现接口要求同数据集、同场景、指标名集合一致；RSI 的候选配置可能改阈值/Prompt，且需要 holdout 子集、参考阈值与目标指标判定，直接复用会耦合展示逻辑。RSI 在 `rsi_policy.py` 内实现独立计算，展示层再复用报告组件。

### 3.10 验收策略、适应度、预算与收敛

**验收策略（`acceptance_policy`）**

```json
{
  "objective": {
    "metric": null,
    "direction": "maximize",
    "min_gain": 0.03,
    "mode": "reference_pass_rate"
  },
  "constraints": {
    "max_metric_drop": 0.02,
    "max_new_failures": 0,
    "max_error_rate_delta": 0.02,
    "protected_metrics": []
  },
  "sampling": {
    "holdout_ratio": 0.3,
    "min_rows": 10,
    "min_rows_for_auto_accept": 30
  },
  "review": {
    "auto_apply_low_risk": false,
    "require_human_for": ["prompt_override", "pass_threshold", "metric_config", "endpoint_template"]
  }
}
```

**两种目标口径（关键修正）**

| 模式 | 计算 | 适用 | 防刷机制 |
|------|------|------|----------|
| `metric_mean` | 取 `objective_metric` 在 holdout 上的平均分 | 有明确主指标（如 faithfulness） | 均值与 `pass_threshold` 无关 |
| `reference_pass_rate` | 用创建 loop 时冻结的 `reference_thresholds` 对 candidate 原始 score 重算通过率 | 没有主指标时的默认口径 | 不使用候选自己的阈值 |

> 禁止直接用候选 `pass_threshold` 计算 `pass_rate` 做验收目标。否则“把阈值从 0.8 降到 0.6”就能制造通过率提升，属于奖励黑客。

**判定规则**

| 条件 | 结论 |
|------|------|
| 目标增益 ≥ `min_gain` 且所有约束满足 且 holdout 已评估 且 人工审批通过（MVP 全部需要） | `accepted` |
| 增益 > 0 但 < `min_gain`，或样本不足无法判定，或 holdout 被禁用但未人工确认 | `inconclusive`（不写回，记录） |
| 增益 ≤ 0，或任一约束违例（关键指标下降、新增失败、错误率上升），或提案校验失败 | `rejected` |
| 本轮全部提案非法 / 沙盒失败 / LLM 输出不可解析 | `rejected`（不计入有效决策统计） |

**约束检查**

- 受保护指标：默认“除目标指标外的全部指标”；`metric_mean` 下降 > `max_metric_drop` 即拒绝。
- 错误率：`candidate_error_rate - baseline_error_rate > max_error_rate_delta` 即拒绝。
- 新增失败：holdout 上 `new_failures > max_new_failures` 即拒绝。
- 样本量：holdout 行数 < `min_rows_for_auto_accept` 时禁止自动采纳；MVP 默认人工审批，因此不阻塞闭环。

**适应度（P1，只用于候选排序）**

```text
fitness = 0.6 * normalize(objective_score) + 0.4 * normalize(mean(metric_means))
```

- `objective_score` 使用 `metric_mean` 或 `reference_pass_rate`，与阈值无关。
- `fitness` 仅用于同一轮多个候选的排序，不单独决定采纳；采纳仍由 3.10 的硬约束 + 人工门禁决定。
- 归一化以基线为 0、目标值为 1，超出目标值截断为 1。

**判据漂移守卫（P1，MVP 用人工审批替代）**

`prompt_override` 会改变 Judge 的评分标准，baseline 与 candidate 不是同一把尺子。P1 增加交叉校验：

1. 取 holdout 的 N 条样本（默认 10 条）。
2. 用 candidate Prompt 重打 baseline 回答；用 baseline Prompt 重打 candidate 回答。
3. 计算两组交叉分的绝对差；若平均差 > `max_judge_drift`（默认 0.15）或方向不一致，标记 `inconclusive` 并强制人工复核。
4. MVP 未实现交叉校验时，所有 `prompt_override` 提案必须人工审批，并抽检 5 条 reason 的一致性。

**预算（`budget`）**

```json
{
  "max_iterations": 3,
  "max_rows_per_iteration": 50,
  "max_llm_calls": 300,
  "max_minutes": 45,
  "max_proposals_per_iteration": 3,
  "max_consecutive_no_gain": 2
}
```

- 每轮开始前预估调用数：`sample_rows × llm_metric_count + 2`；累计超限即停止。
- `max_rows_per_iteration` 用于大表抽样：按失败行优先 + 稳定随机补齐；holdout 判定仍基于实际被评估的行，并在报告中标注采样。
- 成本估算：20 行 × 4 个 LLM 指标 = 80 次/轮；归因 + 提案 2 次；3 轮 ≈ 246 次，落在默认预算内。若 50 行 × 4 指标 = 200 次/轮，则 3 轮会超 300，需要把 `max_iterations` 降到 1–2 或启用 P1 两阶段评估。

**收敛与终止**

1. `objective_target` 达到。
2. 连续 `max_consecutive_no_gain` 轮增益 < `min_gain`。
3. 预算耗尽（轮次/调用/时长/行数）。
4. 无合法提案。
5. 人工取消。

### 3.11 版本化、写回、回滚与审计

**写回顺序（同一事务）**

```text
读取当前实体
  → 生成 before snapshot
  → 插入 rsi_config_versions
  → apply_patch 修改实体
  → 更新 proposal.status=applied / applied_version_id
  → commit
```

任一步失败则回滚事务，不产生“改了但没版本”的状态。

**回滚粒度**

- 单个 version：某次提案的变更。
- 整个 iteration：该轮全部提案，按 version 逆序恢复。

**回滚方式**

1. 按 `scope/scope_id` 读取 `snapshot`。
2. 把快照字段逐项写回实体。
3. 标记 `rolled_back_at`，提案状态改 `rolled_back`。
4. loop 记录 `decision_reason`，迭代状态改 `rolled_back`。
5. 回滚后建议重跑一次基线评测确认（P1 自动化，MVP 由人工触发）。

**审计信息**

- 谁：`actor=system` 或 `human:<name>`（当前无鉴权，先记录来源）。
- 何时、哪一轮、哪个提案、变更前后值、证据行、审批意见。
- 版本表只追加，不删除；数据集行只追加；评测任务不删除。
- P1 启动一致性检查：对比 `rsi_config_versions` 最新快照与实体当前值，发现不一致则告警（说明有人绕过 RSI 改了配置）。

### 3.12 API 设计（新增 `backend/app/api/rsi.py`，`prefix="/rsi"`）

| 方法 | 路径 | 作用 | 优先级 |
|------|------|------|--------|
| GET | `/api/rsi/loops` | 分页列表（状态/场景/关键词） | P0 |
| POST | `/api/rsi/loops` | 从已完成的基线评测创建 loop（MVP）；P1 支持资源配置 | P0 |
| GET | `/api/rsi/loops/{id}` | 详情（当前迭代、预算使用、摘要） | P0 |
| POST | `/api/rsi/loops/{id}/start` | 启动（线程） | P0 |
| POST | `/api/rsi/loops/{id}/cancel` | 取消（同步取消候选 EvalTask） | P0 |
| GET | `/api/rsi/loops/{id}/logs` | 增量日志（对齐评测日志接口） | P0 |
| GET | `/api/rsi/loops/{id}/iterations` | 迭代列表（不含大 JSON） | P0 |
| GET | `/api/rsi/iterations/{id}` | 迭代详情（归因、提案、双评估、delta、成本） | P0 |
| POST | `/api/rsi/iterations/{id}/approve` | 人工审批通过并采纳 | P0 |
| POST | `/api/rsi/iterations/{id}/reject` | 人工驳回（附理由） | P0 |
| POST | `/api/rsi/loops/{id}/rollback` | 回滚到指定 version / 整个 iteration | P0 |
| GET | `/api/rsi/configs/{scope}/{scope_id}/versions` | 版本列表 | P1 |
| POST | `/api/rsi/configs/versions/{id}/restore` | 版本恢复 | P1 |
| POST | `/api/rsi/proposals/{id}/preview` | 单行沙盒预览 | P1 |
| GET | `/api/rsi/loops/{id}/compare` | 基线与候选对比（RSI 自算） | P1 |

**创建请求示例**

```json
{
  "name": "RAG 忠实度自进化",
  "baseline_eval_id": 42,
  "llm_config_id": 1,
  "proposer_llm_config_id": 2,
  "objective_metric": "faithfulness",
  "objective_mode": "metric_mean",
  "objective_target": 0.85,
  "budget": {"max_iterations": 3, "max_rows_per_iteration": 20},
  "acceptance_policy": {
    "objective": {"min_gain": 0.03},
    "sampling": {"holdout_ratio": 0.3, "min_rows": 10}
  },
  "auto_apply_low_risk": false
}
```

**后端校验**

- MVP 必须提供 `baseline_eval_id`；基线任务必须 `completed`，且 `summary_scores` 非空。
- `dataset_id/scenario_id/evaluation_mode` 继承基线；`target_config/response_mapping` 继承基线 `EvalTask` 的字段，而不是当前 `EndpointTarget`，避免接口配置漂移。
- `objective_metric` 必须存在于基线快照的指标集中。
- 同一 `scenario_id` 无 `running/awaiting_review` loop，否则 409。
- `llm_config_id` 存在；`proposer_llm_config_id` 可空。
- `holdout_ratio` ∈ [0, 0.5]；`min_rows` ≥ 5；`max_iterations` ≤ 10。

**错误码约定**

| 码 | 场景 |
|----|------|
| 400 | 参数非法、基线未完成、目标指标不存在 |
| 404 | loop/iteration/version 不存在 |
| 409 | 同场景已有运行中的 loop；重复启动；已结束 loop 再启动 |
| 422 | 状态不允许（如未到 `awaiting_review` 就审批） |
| 500 | 内部异常（需返回可读 error_message） |

### 3.13 前端交互设计

**新增路由与菜单**

- `App.tsx`：新增分组“自进化” → 菜单“RSI 自进化”（`/rsi`）；详情 `/rsi/:id`。
- 也可暂挂在“结果分析”分组下，减少导航层级变化。

**页面**

1. `RsiLoopListPage.tsx`
   - 顶部：创建按钮；筛选（状态、场景、数据集）。
   - 表格列：名称、基线评测、场景、目标指标、当前轮次/最大轮次、最优增益、状态、预算使用、创建时间、操作。
   - 创建弹窗 `components/rsi/RsiCreateModal.tsx`：选择已完成评测 → 自动带出数据集/场景/Judge/模式；配置目标指标、目标值、预算、holdout、是否自动采纳低风险。
2. `RsiLoopDetailPage.tsx`
   - 顶部摘要：状态、目标、当前最优、预算进度、启动/取消/回滚。
   - `RsiIterationTimeline.tsx`：每轮卡片（状态、决策、目标增益、成本、耗时、进入详情）。
   - 迭代详情抽屉：`RsiDiagnosisPanel`（失败簇 + 证据行）、`RsiProposalDiff`（before/after diff + 风险标签 + 审批按钮）、双评估指标对比（复用报告表格样式）、`RsiTrendChart`（P1，objective/pass_rate 折线）。
   - `RsiApprovalDrawer.tsx`（P1）：二次确认、影响面提示（“该指标被 N 个场景引用”）、回滚提示。
3. `ReportDetailPage.tsx`（P1）
   - 在“基本信息”卡片旁增加“发起自进化”按钮，携带 `baseline_eval_id` 跳转 `/rsi?create=1&baseline_eval_id=...`。

**状态与轮询**

- 列表：`running/awaiting_review` 时 3s 轮询。
- 详情：`running` 时 2s 轮询详情 + 1s 拉日志（对齐 `EvaluationPage` 的 console 体验）。
- 错误：`failed` 展示 `error_message` 与最后 50 行日志。

**类型与 API 封装**

- `frontend/src/types/index.ts`：`RsiLoop`、`RsiIteration`、`RsiProposal`、`RsiConfigVersion`、`RsiMetricsDelta`、`RsiDiagnosis`。
- `frontend/src/services/api.ts`：新增 `// ===== RSI =====` 区块，风格与现有导出函数一致。

### 3.14 配置项与环境变量

`backend/app/core/config.py` 新增（带默认值，保持向后兼容）：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `RSI_ENABLED` | `true` | 关闭后路由返回 403/隐藏入口；生产建议先置 false，启用 RBAC 后再开 |
| `RSI_MAX_ITERATIONS` | `3` | |
| `RSI_MAX_ROWS_PER_ITERATION` | `50` | |
| `RSI_MAX_LLM_CALLS` | `300` | |
| `RSI_MAX_MINUTES` | `45` | |
| `RSI_MAX_PROPOSALS_PER_ITERATION` | `3` | |
| `RSI_HOLDOUT_RATIO` | `0.3` | |
| `RSI_HOLDOUT_MIN_ROWS` | `10` | 低于则禁用 holdout |
| `RSI_HOLDOUT_MIN_ROWS_AUTO` | `30` | 低于则禁止自动采纳 |
| `RSI_MIN_OBJECTIVE_GAIN` | `0.03` | |
| `RSI_MAX_METRIC_DROP` | `0.02` | |
| `RSI_MAX_ERROR_RATE_DELTA` | `0.02` | |
| `RSI_MAX_JUDGE_DRIFT` | `0.15` | P1 交叉校验阈值 |
| `RSI_AUTO_APPLY_LOW_RISK` | `false` | MVP 不支持自动采纳 |
| `RSI_PROPOSER_TEMPERATURE` | `0.2` | |

同步更新 `backend/.env.example` 与 `docs/usage-guide.md`。

### 3.15 三个关键防自欺机制

#### 3.15.1 阈值刷分

- 问题：`_determine_pass` 只看 `pass_threshold`，降低阈值会机械提高 `pass_rate`。
- 规则：验收目标使用 `metric_mean` 或 `reference_pass_rate`（冻结参考阈值）；候选自己的阈值只影响展示，不影响验收。
- 规则：`pass_threshold` 变更必须人工审批；MVP 不允许自动采纳。
- 规则：`weight` 未参与汇总，MVP 不允许 Patch；P1 先补加权汇总。

#### 3.15.2 判据漂移

- 问题：改 `prompt_override` 后，baseline 用旧判据、candidate 用新判据，均值不可直接比较。
- MVP：所有 `prompt_override` 强制人工审批；固定 Judge 模型；抽检 5 条 reason 一致性。
- P1：交叉打分（candidate Prompt 重打 baseline 回答，baseline Prompt 重打 candidate 回答），平均差 > `RSI_MAX_JUDGE_DRIFT` 则 `inconclusive`。
- 建议：`proposer_llm_config_id` 使用与 Judge 不同的模型；若相同，风险等级上调一级。

#### 3.15.3 Holdout 泄漏

- 问题：归因读取全量失败行时，holdout 的失败样本会进入提案上下文，holdout 不再干净。
- 规则：按 `md5(f"{loop.id}:{dataset_row_id}")` 稳定划分 train/holdout；归因/提案只读 train；holdout 不进入任何 Prompt。
- 规则：验收只读 holdout；候选任务在全量数据集上执行，但 `rsi_policy` 分别计算 train/holdout 切片。
- 规则：数据集 hard-case 只写 train/派生数据集，禁止写入 holdout。

---

## 4. 实施计划

### 4.1 任务拆解

> 工作量单位：人日；优先级见第 5 节；阶段对应 MVP / P1 / P2。

#### 后端

| ID | 任务 | 主要文件 | 工作量 | 依赖 | 阶段 |
|----|------|----------|--------|------|------|
| RSI-B1 | RSI ORM 模型并注册 | `models/rsi.py`、`models/__init__.py` | 0.8 | — | MVP |
| RSI-B2 | 运行时 Schema 补列 | `core/database.py` | 0.2 | B1 | MVP |
| RSI-B3 | Pydantic 请求/响应模型 | `schemas/rsi.py` | 0.6 | B1 | MVP |
| RSI-B4 | Patch 校验/应用/快照/diff/回滚 | `core/rsi_patch.py` | 1.5 | B1,B3 | MVP |
| RSI-B5 | 失败归因（规则 + LLM + 降级，train-only） | `core/rsi_diagnosis.py`、`prompt_manager.py` | 1.2 | B3 | MVP |
| RSI-B6 | 提案生成、证据强制、风险分级 | `core/rsi_proposer.py`、`prompt_manager.py` | 1.2 | B4,B5 | MVP |
| RSI-B7 | 候选场景快照构建 | `core/scenario_snapshot.py` | 0.4 | B4 | MVP |
| RSI-B8 | 影子回归、holdout 划分、delta | `core/rsi_regression.py` | 1.5 | B7 | MVP |
| RSI-B9 | 验收、预算、收敛、小样本降级 | `core/rsi_policy.py` | 1.2 | B8 | MVP |
| RSI-B10 | Loop 编排、状态机、日志、恢复、取消 | `core/rsi_engine.py` | 2.0 | B5–B9 | MVP |
| RSI-B11 | RSI 路由与注册 | `api/rsi.py`、`main.py` | 1.0 | B10 | MVP |
| RSI-B12 | 版本化与回滚接口 | `api/rsi.py`、`core/rsi_patch.py` | 0.8 | B4,B11 | MVP |
| RSI-B13 | 抽取单行调试 + 沙盒预筛 | `core/evaluation_debug.py`、`api/evaluation.py` | 1.0 | B6 | P1 |
| RSI-B14 | 数据集 hard-case 追加（派生数据集） | `core/rsi_dataset.py` | 1.5 | B8 | P1 |
| RSI-B15 | 非内置指标 config Patch | `core/rsi_patch.py`、`core/rsi_proposer.py` | 0.6 | B4 | P1 |
| RSI-B16 | 被测接口请求模板提案 | `core/rsi_patch.py`、`core/rsi_engine.py` | 1.2 | B4,B9 | P2 |
| RSI-B17 | 采纳后自动创建盲测 | `core/rsi_engine.py`、`api/blind_test.py` | 0.8 | B10 | P2 |
| RSI-B18 | 失败簇相似样本合成（复用 RAG 生成） | `core/rag_dataset_generator.py`、`core/rsi_dataset.py` | 1.5 | B14 | P2 |
| RSI-B19 | RSI 示例种子数据 | `seed.py` | 0.3 | B10 | P2 |
| RSI-B20 | 启动恢复与并发约束加固 | `core/rsi_engine.py`、`api/rsi.py` | 0.6 | B10 | P1 |
| RSI-B21 | fitness、显著性、受保护指标 | `core/rsi_policy.py` | 1.2 | B9 | P1 |
| RSI-B22 | 两阶段评估、Judge 缓存、分层抽样 | `core/rsi_regression.py`、`core/rsi_policy.py` | 1.2 | B8 | P1 |
| RSI-B23 | `rsi_signals`/`rsi_clusters` 分析表（可选） | `models/rsi.py`、`core/rsi_diagnosis.py` | 0.8 | B5 | P1 |
| RSI-B24 | 反奖励黑客：对抗集/跨场景校验 | `core/rsi_policy.py`、`core/rsi_regression.py` | 1.5 | B21 | P2 |
| RSI-B25 | 多目标/Pareto 选择 | `core/rsi_policy.py` | 1.5 | B21 | P2 |

#### 前端

| ID | 任务 | 主要文件 | 工作量 | 依赖 | 阶段 |
|----|------|----------|--------|------|------|
| RSI-F1 | 类型与 API 封装 | `types/index.ts`、`services/api.ts` | 0.4 | B3,B11 | MVP |
| RSI-F2 | 列表页 + 创建向导 | `pages/RsiLoopListPage.tsx`、`components/rsi/RsiCreateModal.tsx` | 1.5 | F1 | MVP |
| RSI-F3 | 详情页（时间线/归因/提案 diff/决策） | `pages/RsiLoopDetailPage.tsx`、`components/rsi/*` | 2.0 | F1,B12 | MVP |
| RSI-F4 | 路由与菜单 | `App.tsx` | 0.2 | F2,F3 | MVP |
| RSI-F5 | 趋势图与成本面板 | `components/rsi/RsiTrendChart.tsx` | 0.8 | F3 | P1 |
| RSI-F6 | 报告页“发起自进化”入口 | `pages/ReportDetailPage.tsx` | 0.4 | F2 | P1 |
| RSI-F7 | 审批抽屉与影响面提示 | `components/rsi/RsiApprovalDrawer.tsx` | 0.6 | F3 | P1 |
| RSI-F8 | 预算/验收策略编辑器 | `components/rsi/RsiPolicyForm.tsx` | 0.7 | F2 | P1 |
| RSI-F9 | endpoint 提案审批视图与盲测门禁入口 | `components/rsi/RsiProposalDiff.tsx`、`RsiApprovalDrawer.tsx` | 0.8 | F3 | P2 |

#### 测试与文档

| ID | 任务 | 主要文件 | 工作量 | 依赖 | 阶段 |
|----|------|----------|--------|------|------|
| RSI-T1 | Patch/Policy 单元测试 | `tests/test_rsi_patch.py` | 1.0 | B4,B9 | MVP |
| RSI-T2 | API 集成测试（创建/启动/取消/审批/404/409） | `tests/test_rsi_api.py` | 1.0 | B11 | MVP |
| RSI-T3 | 引擎状态机与失败恢复测试 | `tests/test_rsi_engine.py` | 1.0 | B10 | MVP |
| RSI-T4 | 归因/提案 JSON 容错测试 | `tests/test_rsi_diagnosis.py` | 0.6 | B5,B6 | P1 |
| RSI-T5 | 回滚与版本一致性测试 | `tests/test_rsi_rollback.py` | 0.5 | B12 | MVP |
| RSI-T6 | 现有回归（pytest + npm build） | `backend/tests/*`、`frontend` | 0.3 | 全部 | MVP/P1 |
| RSI-T7 | holdout/统计/阈值无关验收测试 | `tests/test_rsi_policy.py` | 0.4 | B9,B21 | P1 |
| RSI-T8 | 对抗集/多目标测试 | `tests/test_rsi_reward_hacking.py` | 0.4 | B24,B25 | P2 |
| RSI-D1 | 本文档 + 实现一致性维护 | `docs/RSIX.md` | 0.5 | — | MVP |
| RSI-D2 | 使用手册与 README 增补 | `docs/usage-guide.md`、`README.md` | 0.5 | MVP | P1 |
| RSI-D3 | AGENTS.md 常见任务补充 | `AGENTS.md` | 0.2 | — | P2 |
| RSI-M1 | 引入 Alembic 基线（可选） | `backend/alembic/` | 1.5 | — | P2 |

### 4.2 依赖关系

```text
B1 ─┬─ B2
    ├─ B3 ─┬─ B5 ─┐
    └─ B4 ─┤      ├─ B10 ─ B11 ─┬─ F1 ─┬─ F2 ─ F4
           ├─ B6 ─┘             │      └─ F3 ─ F4
           ├─ B7 ─ B8 ─ B9 ─────┘
           └─ B12

B13 依赖 B6；B14 依赖 B8；B15 依赖 B4；B20 依赖 B10；
B21 依赖 B9；B22 依赖 B8；B23 依赖 B5；B24/B25 依赖 B21。
T1/T3/T5 依赖 B4/B9/B10/B12；T2 依赖 B11；T7 依赖 B9/B21；
F* 依赖 B11 契约；F5–F8 依赖 F3；F9 依赖 F3。
```

关键路径：`B1 → B3 → B4 → B7 → B8 → B9 → B10 → B11 → F3`。

### 4.3 里程碑

#### M0：设计冻结（0.5–1 人日）

- 交付物：本文档、表结构、Patch DSL、API 契约、状态机、验收口径。
- 验收：评审通过；表/接口/字段命名与现有风格一致；无与现有模块冲突的假设；三类防自欺机制（阈值、判据漂移、holdout 泄漏）有明确规则。

#### MVP（P0，约 21 人日，含缓冲约 24 人日）

- 目标：单轮闭环可跑通，可审批、可回滚、可观测。
- 交付物：4 张核心表 + 2 个可空列；`rsi_patch/diagnosis/proposer/regression/policy/engine`；`/api/rsi/*`；列表/详情页；4 个 MVP 测试文件；本文档。
- 验收标准：
  1. 用种子 RAG 数据集（5 行）与已完成的“RAG 示例评测”创建 loop，跑 1 轮。
  2. 至少产出 1 条合法提案；不合法提案被拒绝且有原因。
  3. 完成影子回归，`rsi_iterations.metrics` 含 baseline/candidate/delta/train/holdout。
  4. 决策为 `accepted/rejected/inconclusive` 之一且 `decision_reason` 可读。
  5. `accepted` 后场景配置生效，`rsi_config_versions` 有 before 快照；回滚后恢复原值（自动化断言）。
  6. 取消 ≤1 次 LLM 调用内生效；超预算自动停止；同场景并发启动返回 409。
  7. 现有 5 个测试模块全绿；`npm run build` 通过。

#### P1：稳定性与效果增强（约 11 人日）

- 目标：让“变好”更可信、成本更低、可观测性更强。
- 交付物：holdout 统计与 fitness、判据交叉校验、沙盒试跑、两阶段评估/缓存、趋势图、报告页入口、数据集 hard-case、非内置指标 config Patch、`rsi_signals/rsi_clusters` 可选表、任务恢复加固、使用手册。
- 验收标准：
  1. 20+ 行数据集连续跑 3 轮，能因收敛/预算正确停止。
  2. holdout 指标下降超过阈值时拒绝采纳；小样本时正确降级为 `inconclusive`/人工审批。
  3. 沙盒试跑使无效提案的全量回归次数下降 ≥30%（按提案统计）。
  4. 判据交叉校验能识别“判据变宽松”导致的虚假提升。
  5. 前端可看到目标指标/通过率趋势与每轮成本；hard-case 写入派生数据集，原数据集 `row_count` 不变。

#### P2：能力完善（约 8–10 人日）

- 目标：扩展到接口配置与更强反自证能力。
- 交付物：endpoint 请求模板提案（人工审批）、盲测门禁、RAG 失败簇补样本、反奖励黑客对抗集、多目标/Pareto、示例种子、可选 Alembic 基线。
- 验收标准：
  1. endpoint 模板提案必须审批，diff 中不出现 Authorization/API Key。
  2. 采纳后可一键创建盲测并关联 loop。
  3. 失败簇补样本可回溯到源 chunk 与源行；不写入 holdout。
  4. 对抗集上无显著退化；多目标场景不被单一指标提升误导。
  5. 文档完整覆盖配置、边界与回滚操作。

### 4.4 建议实施顺序

| 阶段 | 周期 | 任务 | 出口条件 |
|------|------|------|----------|
| Sprint 0 | 1–2 天 | M0 评审 + B1/B2/B3 | 表结构/契约冻结，模型可建表 |
| Sprint 1 | 4–5 天 | B4/B5/B6/B7 | Patch 校验、归因、提案、候选快照可单测 |
| Sprint 2 | 5–6 天 | B8/B9/B10/B11/B12 | 单轮闭环 + API + 回滚可跑通 |
| Sprint 3 | 4–5 天 | F1–F4 + T1/T2/T3/T5/T6 | 前端可操作，MVP 验收通过 |
| Sprint 4 | 5–6 天 | B13/B20/B21/B22 + F5–F8 + T4/T7 + D2 | P1 验收通过 |
| Sprint 5 | 4–5 天 | B16–B19/B24/B25 + F9 + T8 + D3 + 可选 M1 | P2 验收通过 |

- 1 人全职：MVP 约 5 周，P1 约 2.5 周，P2 约 2 周。
- 2 人并行（后端 + 前端/测试）：MVP 约 12 个工作日；后端先交付 API 契约，前端可并行开发。

### 4.5 工作量汇总

| 阶段 | 后端 | 前端 | 测试/文档 | 合计（不含缓冲） | 含缓冲 |
|------|------|------|-----------|------------------|--------|
| MVP/P0 | 12.4 | 4.1 | 4.3 | **20.8** | **约 24**（15% 缓冲） |
| P1 | 6.9 | 2.5 | 1.5 | **10.9** | **约 11** |
| P2 | 6.8 | 0.8 | 0.6 | **8.2** | **约 8–10**（含可选 Alembic 1.5） |
| 合计 | 26.1 | 7.4 | 6.4 | **约 40** | **约 43–45** |

> 工时是规划参考，不是交付承诺。MVP 的“含缓冲约 24 人日”是建议排期口径，评审时可按团队熟悉度上下浮动 15%。

---

## 5. 优先级矩阵

### 5.1 功能优先级

| 优先级 | 功能点 | 排序依据 |
|--------|--------|----------|
| **P0** | Loop/Iteration/Proposal/ConfigVersion 数据模型与状态机 | 一切能力的基础；无版本与状态机无法安全落地 |
| **P0** | 失败归因（规则 + LLM + 降级，train-only） | RSI 的“智能”来源；规则层保证可用性 |
| **P0** | 白名单 Patch + 漂移校验 + 风险分级 | 安全底线，必须先于自动写回 |
| **P0** | 影子快照回归（复用 `run_evaluation`） | 唯一可信的验证手段；复用成本最低 |
| **P0** | 阈值无关验收 + 预算 + 收敛 + 小样本降级 | 防止刷分、无限循环与成本失控 |
| **P0** | 人工审批 + 版本快照 + 写回 + 回滚 | 业务可接受性的前提 |
| **P0** | 列表/详情最小前端 + 日志轮询 | 没有可视化闭环无法验收 |
| **P0** | Patch/API/Engine/回滚测试 | 保证不影响现有功能 |
| **P1** | holdout 统计、fitness、受保护指标 | 直接决定“是否真的变好”，避免自欺 |
| **P1** | 判据交叉校验 | 解决“改 Prompt 后两把尺子”问题 |
| **P1** | 沙盒单行试跑 | 降低全量回归成本，提升迭代速度 |
| **P1** | 两阶段评估/Judge 缓存/分层抽样 | 控制成本，提升吞吐 |
| **P1** | 报告页入口与趋势图 | 提升可用性，非闭环必需 |
| **P1** | 数据集 hard-case 追加 | 提升上限，但涉及数据污染风险 |
| **P1** | 非内置指标 config Patch | 扩大可优化面，但影响多个场景 |
| **P1** | `rsi_signals/rsi_clusters` 分析表 | 跨 loop 分析需要，MVP 用 JSON 足够 |
| **P2** | endpoint 模板提案 | 价值高但风险最高，需审批体系成熟 |
| **P2** | 盲测门禁 | 主观验证增强，非自动闭环必需 |
| **P2** | RAG 失败簇补样本 | 依赖生成质量与成本，收益不确定 |
| **P2** | 反奖励黑客对抗集/跨场景校验 | 防过拟合，需先有 P1 统计基础 |
| **P2** | 多目标/Pareto | 需要业务确定权衡口径 |
| **P2** | 示例种子、Alembic 基线 | 体验与工程化，非功能闭环 |

### 5.2 排序依据说明

1. **业务价值**：能直接减少“报告 → 改配置 → 重跑”人工步骤的功能优先；纯展示功能后置。
2. **实现成本**：复用 `run_evaluation`、`scenario_snapshot` 的功能优先；需要新造执行链路的后置。
3. **依赖关系**：Patch 校验、版本表、决策策略是写回的前置；写回又是前端审批的前置。
4. **风险**：越接近“自动改生产配置”的功能越后置；先建立审批、版本、回滚，再扩大可改范围。
5. **可回滚性**：没有快照与回滚的能力不允许进入 MVP。
6. **可验证性**：无法用现有指标/证据验证的改进不进入 MVP。

### 5.3 需求 → 方案 → 任务映射

| 需求 | 对应方案 | 对应任务 |
|------|----------|----------|
| R1 信号抽取 | 3.7 | B5 |
| R2 归因聚类 | 3.7 | B5 |
| R3 变异生成 | 3.6/3.8 | B6 |
| R4 候选评估 | 3.9 | B8 |
| R5 门禁校验 | 3.10 | B9/B21 |
| R6 版本化/回滚/审计 | 3.11 | B4/B12 |
| R7 Web 可视化 | 3.13 | F2/F3 |
| R8 成本与效率 | 3.10 | B9/B22 |
| R9 被测系统演化 | 3.6/3.9 | B16/B17 |
| R10 反自证守卫 | 3.15 | B21/B24 |

---

## 6. 风险与应对

### 6.1 风险矩阵

| 风险 | 概率 | 影响 | 等级 | 应对措施 | 观测信号 |
|------|------|------|------|----------|----------|
| 判据/数据集同源演化导致自证偏差 | 中 | 高 | 高 | train/holdout 隔离；受保护指标；人工审批；P2 对抗集/跨场景 | holdout 与 train delta 背离；连续多轮只对少数行有效 |
| 降低阈值刷 pass_rate | 高 | 高 | 高 | 验收用指标均值/冻结参考阈值；阈值变更人工审批；不允许自动采纳 | 阈值下降但指标均值不升；pass_rate 异常跳升 |
| 改判据后 baseline/candidate 不可比 | 高 | 高 | 高 | MVP 人工审批 + 固定 Judge + reason 抽检；P1 交叉打分 | 交叉分差大；新判据明显更宽松 |
| holdout 通过归因输入泄漏 | 中 | 高 | 中高 | 归因只读 train；holdout 不进入 Prompt；数据集补强不写 holdout | 提案证据中出现 holdout 行 id |
| LLM 成本超预期 | 中 | 中 | 中 | 四重预算；每轮预估；P1 两阶段/缓存；默认抽样 50 行 | `usage.llm_calls` 增长曲线、单轮耗时 |
| 配置被改坏/不可回滚 | 中 | 高 | 中高 | 先快照后写回；事务化；禁止删除；一键回滚；版本表只追加 | 写回失败率、回滚次数、实体与版本不一致告警 |
| SQLite 并发写锁 | 中 | 中 | 中 | loop 串行；候选评估串行；短事务；P2 切 PostgreSQL 后再并发 | `database is locked` 日志 |
| 进程重启导致任务悬挂 | 中 | 中 | 中 | `recover_stale_rsi_loop()` 按超时回收；日志保留 | 列表出现长时间 running |
| 提示注入（数据集内容进入提案 Prompt） | 中 | 高 | 中高 | 样本用分隔符包裹并声明“仅作证据”；截断/条数上限；白名单 Patch；高风险人工审批 | 提案出现与失败簇无关的指令性文本 |
| 敏感信息泄露 | 低 | 高 | 中 | 不向提案 LLM 传 Authorization/Key；响应统一脱敏；diff 过滤 | 日志/提案中出现 `Authorization`、`sk-` |
| 指标集变更导致 compare 失效 | 中 | 中 | 中 | MVP 禁止增删指标；RSI 自算 delta；P1 若支持增删，需扩展 compare 语义 | 迭代详情缺少 delta |
| 无鉴权导致误操作 | 中 | 中 | 中 | 默认人工审批；生产前置网关鉴权；记录 actor/source | 审批记录缺失 |
| LLM JSON 不稳定 | 中 | 低 | 低 | 严格 JSON + 提取首个对象；失败降级规则归因；提案失败本轮 rejected | `fallback=true` 比例 |
| 数据集被“注水”迎合指标 | 低 | 高 | 中 | 只增不改不删；派生数据集；独立校验集；不写 holdout | 新增样本与失败簇高度同质 |
| 用户误用自动采纳 | 低 | 中 | 低 | MVP 不支持自动采纳；P2 仅限非评判类且全审计 | 自动采纳记录与回滚率 |
| 与既有测试回归 | 低 | 中 | 低 | 新增表/路由不改既有语义；全量 pytest + npm build | CI 红灯 |

### 6.2 关键技术难点

| 编号 | 难点 | 说明 | 应对 |
|------|------|------|------|
| D1 | 自证偏差/奖励黑客 | 判据与数据集同源演化，可能“用改过的数据证明改过的判据” | train/holdout 隔离、受保护指标、人工门禁、P2 对抗集 |
| D2 | Judge 随机性 | LLM 评分非确定性，微小差异可能是噪声 | temperature 沿用 0.01；P1 重复采样/置信区间；reason 抽检 |
| D3 | 统计功效不足 | 小样本提升不可信 | `min_rows` 降级；`min_rows_for_auto_accept=30`；小样本只允许人工批准 |
| D4 | 成本爆炸 | 候选数 × 样本数 × 指标数次调用 | 预算上限、抽样、两阶段、缓存、提前剪枝 |
| D5 | 归因质量 | 聚类误判导致“改错对象” | 证据行强制；规则层兜底；人工确认归因（P1） |
| D6 | 事务与并发 | SQLite 单写锁，逐行 commit 与并发冲突 | loop/候选串行；短事务；P2 PostgreSQL |
| D7 | 历史复算一致性 | 采纳后历史任务不能被动改变 | 历史任务持有自带 `scenario_snapshot`，不回写 |
| D8 | 多目标冲突 | 提升 A 指标可能损害 B 指标 | 受保护指标；P2 Pareto；人工权衡 |
| D9 | 可解释/可回滚 | 演化必须可追溯、可撤销 | 版本表 + patch + parent 血缘 + 回滚指针 |
| D10 | 阈值刷分 | 降阈值机械提高 pass_rate | 阈值无关验收；参考阈值；人工审批 |
| D11 | 判据漂移 | 改 Prompt 后两套判据不可比 | 固定 Judge；MVP 人工；P1 交叉打分 |
| D12 | holdout 泄漏 | 归因读到 holdout 失败样本 | train-only 归因；holdout 不入 Prompt |

---

## 7. 验收标准

### 7.1 功能验收（MVP 必须全部满足）

- [ ] 可从“已完成评测”创建 loop，自动继承数据集、场景、Judge、评测模式与端点快照，并冻结参考阈值。
- [ ] 同场景并发启动被拒绝（409），不同场景可并行。
- [ ] 单轮执行产出：`diagnosis.clusters ≥ 1`（或明确 `no_failure`）、`proposals ≥ 1`（或无合法提案的明确原因）。
- [ ] 每条提案包含 `before/after/rationale/evidence/risk_level`，前端可读 diff。
- [ ] 所有提案经过白名单/漂移/长度/敏感串校验；非法提案被拒绝且记录原因。
- [ ] 影子回归任务与原场景解耦：执行前后 `scenario.metrics` 无变化。
- [ ] 决策结果有可读理由，并包含目标增益、约束检查、holdout 结果；目标口径与候选阈值无关。
- [ ] 归因/提案只读取 train 切片；holdout 不出现在提案证据中。
- [ ] `accepted` 写回前存在 `rsi_config_versions` 快照；回滚后实体字段逐项等于快照值。
- [ ] `prompt_override` 与 `pass_threshold` 提案必须人工审批；MVP 无自动采纳。
- [ ] 取消、超时、预算耗尽均能停在安全状态（无半写配置）；取消会同步取消候选 `EvalTask`。
- [ ] 日志可增量获取，包含每轮开始/归因/提案/校验/回归/决策。
- [ ] 相同场景只允许一个 `running` loop；重复启动返回 409。
- [ ] 旧库启动后自动补表补列；历史任务/报告不受影响。

### 7.2 非功能验收

- [ ] 默认预算下，单个 loop LLM 调用 ≤300；超限自动停止。
- [ ] 单轮提案生成（不含回归）P95 < 20s（以 Qwen Plus 实测为准）。
- [ ] 新增表数据量有界：每 loop ≤ `max_iterations × (1 + max_proposals_per_iteration)` 行级别。
- [ ] 所有 RSI 写操作在事务内；异常回滚后配置与版本表一致。
- [ ] 响应中不出现原始 `api_key`/`authorization`。
- [ ] SQLite 下串行执行，不出现 `database is locked`。
- [ ] `RSI_ENABLED=false` 时路由不可用，前端菜单隐藏或提示未启用。
- [ ] 现有接口 `GET /api/evaluations`、`/reports/*`、`/blind-tests/*` 响应结构不变。

### 7.3 回归与兼容性验收

- [ ] `cd backend && pytest`：现有 5 个测试模块 + 新增模块全部通过。
- [ ] `cd frontend && npm run build` 通过（`tsc -b` 严格类型检查）。
- [ ] 旧数据库（无 `rsi_*` 表、`eval_tasks` 无新列）启动后自动补表补列，历史任务/报告可正常打开。
- [ ] `SEED_ON_STARTUP=true` 时种子数据不受影响；重复启动不产生重复 RSI 数据（MVP 不写种子）。
- [ ] 历史 `EvalTask` 复算结果与 RSI 上线前一致（自带 `scenario_snapshot` 不被改写）。
- [ ] `/reports/{id}/compare` 的 422 约束与返回结构不变。

### 7.4 测试矩阵

| 类型 | 文件 | 覆盖点 | 阶段 |
|------|------|--------|------|
| 单元 | `tests/test_rsi_patch.py` | 白名单、漂移、阈值范围、敏感串、去重、回滚快照 | MVP |
| 单元 | `tests/test_rsi_policy.py` | 两种目标口径、受保护指标、小样本降级、收敛、错误率 | P1 |
| 单元 | `tests/test_rsi_diagnosis.py` | 规则簇、LLM 非法 JSON 降级、train-only、证据校验 | P1 |
| 集成 | `tests/test_rsi_api.py` | 创建/启动/取消/审批/404/409/422 | MVP |
| 集成 | `tests/test_rsi_engine.py` | 状态机、超时、恢复、取消传播 | MVP |
| 集成 | `tests/test_rsi_rollback.py` | 版本不可变、写回、回滚逐字段一致、血缘 | MVP |
| 集成 | `tests/test_rsi_reward_hacking.py` | 对抗集、跨场景、多目标不被单指标误导 | P2 |
| 回归 | 既有 5 模块 | `test_evaluation / test_dataset / test_blind_test / test_llm_config / test_rag_dataset_job` | MVP |
| 回归 | 历史复算 | 已有 `EvalTask` 结果不被 RSI 改写 | MVP |
| 回归 | 快照兼容 | 旧 `scenario_snapshot` 字段缺失时默认值可读 | MVP |
| 回归 | 前端构建 | `npm run build` 通过 | MVP |

**测试替身**：mock `OpenAIJudgeClient` 返回确定性 JSON，保证离线、可复现、零 API 成本；`run_evaluation` 在引擎测试中 mock 为快速返回。

### 7.5 文档验收

- [ ] `docs/RSIX.md`（本文）与实现一致，字段/接口/状态机无偏差。
- [ ] `docs/usage-guide.md` 增加“自进化”操作章节（创建 → 审批 → 回滚）。
- [ ] `README.md` 能力列表增加 RSI 一句话说明与文档链接。
- [ ] 文档明确能力边界：不改模型权重、不改外部系统内部 Prompt、内置指标只能通过场景覆盖。
- [ ] 文档明确“阈值无关验收”“判据漂移”“holdout 隔离”三条规则，避免使用者误用。

---

## 8. 表格总结

| 模块/功能点 | 改动位置 | 优先级 | 工作量 | 依赖 | 阶段 | 验收标准 |
|-------------|----------|--------|--------|------|------|----------|
| RSI 数据模型（4 表） | `backend/app/models/rsi.py`、`models/__init__.py` | P0 | 0.8 | — | MVP | `create_all` 建表成功；关系/级联正确 |
| 运行时补列 | `backend/app/core/database.py` | P0 | 0.2 | B1 | MVP | 旧库启动后 `eval_tasks` 含 `rsi_loop_id/rsi_iteration_id` |
| 请求/响应 Schema | `backend/app/schemas/rsi.py` | P0 | 0.6 | B1 | MVP | OpenAPI 文档可见；字段校验生效 |
| Patch 校验/应用/快照/回滚 | `backend/app/core/rsi_patch.py` | P0 | 1.5 | B1,B3 | MVP | 非法字段/漂移/超长/敏感串被拒；回滚恢复逐字段一致 |
| 候选快照构建 | `backend/app/core/scenario_snapshot.py` | P0 | 0.4 | B4 | MVP | 指标集不变；原快照不被修改（深拷贝） |
| 失败归因 | `backend/app/core/rsi_diagnosis.py`、`prompt_manager.py` | P0 | 1.2 | B3 | MVP | 规则簇可用；LLM 失败自动降级；只读 train |
| 提案生成 | `backend/app/core/rsi_proposer.py`、`prompt_manager.py` | P0 | 1.2 | B4,B5 | MVP | 输出合法 JSON；每条含证据与风险 |
| 影子回归 | `backend/app/core/rsi_regression.py` | P0 | 1.5 | B7 | MVP | 生成候选 `EvalTask` 并复用 `run_evaluation`；原场景无变更；holdout 隔离 |
| 验收/预算/收敛 | `backend/app/core/rsi_policy.py` | P0 | 1.2 | B8 | MVP | 三态决策正确；阈值无关；超预算停止；小样本降级 |
| Loop 编排 | `backend/app/core/rsi_engine.py` | P0 | 2.0 | B5–B9 | MVP | 状态机完整；取消/超时/恢复有效；同场景单 loop |
| RSI API | `backend/app/api/rsi.py`、`main.py` | P0 | 1.0 | B10 | MVP | 15 个端点契约符合 3.12；错误码规范 |
| 版本化与回滚 API | `backend/app/api/rsi.py`、`core/rsi_patch.py` | P0 | 0.8 | B4,B11 | MVP | 回滚后实体与快照一致 |
| 启动恢复与并发约束 | `backend/app/core/rsi_engine.py`、`api/rsi.py` | P1 | 0.6 | B10 | P1 | 超时/重启后 loop 不悬挂；同场景单 loop |
| 单行沙盒试跑 | `backend/app/core/evaluation_debug.py`、`api/evaluation.py` | P1 | 1.0 | B6 | P1 | 试跑不落任务；复用 Judge trace |
| 数据集 hard-case | `backend/app/core/rsi_dataset.py` | P1 | 1.5 | B8 | P1 | 只追加；原数据集不变；不写 holdout |
| 非内置指标 config Patch | `rsi_patch.py`、`rsi_proposer.py` | P1 | 0.6 | B4 | P1 | 内置指标写入被拒 |
| fitness/统计/受保护指标 | `backend/app/core/rsi_policy.py` | P1 | 1.2 | B9 | P1 | 置信区间/受保护指标；小样本正确 |
| 两阶段评估/缓存/分层 | `rsi_regression.py`、`rsi_policy.py` | P1 | 1.2 | B8 | P1 | 调用量下降；缓存命中可观测 |
| signals/clusters 分析表 | `models/rsi.py`、`rsi_diagnosis.py` | P1 | 0.8 | B5 | P1 | 可查询；不影响 MVP JSON |
| endpoint 模板提案 | `rsi_patch.py`、`rsi_engine.py` | P2 | 1.2 | B4,B9 | P2 | 强制审批；diff 无鉴权字段 |
| 盲测门禁 | `core/rsi_engine.py`、`api/blind_test.py` | P2 | 0.8 | B10 | P2 | 采纳后可创建并关联盲测 |
| RAG 失败簇补样本 | `rag_dataset_generator.py`、`rsi_dataset.py` | P2 | 1.5 | B14 | P2 | 可回溯源 chunk；不写 holdout |
| 反奖励黑客 | `rsi_policy.py`、`rsi_regression.py` | P2 | 1.5 | B21 | P2 | 对抗集无显著退化 |
| 多目标/Pareto | `backend/app/core/rsi_policy.py` | P2 | 1.5 | B21 | P2 | 不被单一指标提升误导 |
| RSI 示例种子 | `backend/app/seed.py` | P2 | 0.3 | B10 | P2 | 重复启动不重复插入 |
| 前端类型/API | `types/index.ts`、`services/api.ts` | P0 | 0.4 | B3,B11 | MVP | 类型与后端一致；build 通过 |
| 列表页/创建向导 | `pages/RsiLoopListPage.tsx`、`components/rsi/RsiCreateModal.tsx` | P0 | 1.5 | F1 | MVP | 可创建并跳转详情 |
| 详情页 | `pages/RsiLoopDetailPage.tsx`、`components/rsi/*` | P0 | 2.0 | F1,B12 | MVP | 时间线/归因/diff/决策/日志可见 |
| 路由与菜单 | `frontend/src/App.tsx` | P0 | 0.2 | F2,F3 | MVP | `/rsi`、`/rsi/:id` 可访问 |
| 趋势图/成本 | `components/rsi/RsiTrendChart.tsx` | P1 | 0.8 | F3 | P1 | 目标指标与 pass_rate 折线 |
| 报告页入口 | `pages/ReportDetailPage.tsx` | P1 | 0.4 | F2 | P1 | 一键带 `baseline_eval_id` 发起 |
| 审批抽屉 | `components/rsi/RsiApprovalDrawer.tsx` | P1 | 0.6 | F3 | P1 | 二次确认 + 影响面提示 |
| 策略编辑器 | `components/rsi/RsiPolicyForm.tsx` | P1 | 0.7 | F2 | P1 | 预算/阈值可配置并校验 |
| endpoint 审批/盲测入口 | `RsiProposalDiff.tsx`、`RsiApprovalDrawer.tsx` | P2 | 0.8 | F3 | P2 | 高风险提示 + 盲测入口 |
| Patch 校验单测 | `tests/test_rsi_patch.py` | P0 | 1.0 | B4 | MVP | 覆盖白名单/漂移/边界 |
| API 集成测试 | `tests/test_rsi_api.py` | P0 | 1.0 | B11 | MVP | 创建/启动/取消/审批/404/409 |
| 引擎测试 | `tests/test_rsi_engine.py` | P0 | 1.0 | B10 | MVP | mock 评测下状态流转正确 |
| 回滚一致性 | `tests/test_rsi_rollback.py` | P0 | 0.5 | B12 | MVP | 回滚后字段一致 |
| 现有回归 | `backend/tests`、`frontend` | P0 | 0.3 | 全部 | MVP | pytest + build 全绿 |
| 归因/提案容错 | `tests/test_rsi_diagnosis.py` | P1 | 0.6 | B5,B6 | P1 | 非法 JSON 降级 |
| holdout/统计测试 | `tests/test_rsi_policy.py` | P1 | 0.4 | B9,B21 | P1 | 阈值无关/小样本/置信区间 |
| 对抗集/多目标测试 | `tests/test_rsi_reward_hacking.py` | P2 | 0.4 | B24,B25 | P2 | 对抗集不退化 |
| 本文档 | `docs/RSIX.md` | P0 | 0.5 | — | MVP | 与实现一致 |
| 使用手册/README | `docs/usage-guide.md`、`README.md` | P1 | 0.5 | MVP | P1 | 有操作步骤与边界说明 |
| AGENTS.md 补充 | `AGENTS.md` | P2 | 0.2 | — | P2 | 常见任务可检索 |
| Alembic 基线 | `backend/alembic/` | P2 | 1.5 | — | P2 | 初始迁移可升级空库 |

---

## 9. 后续演进路线

| 阶段 | 方向 | 说明 | 前置条件 |
|------|------|------|----------|
| P2+ | **Meta-RSI** | 用历史提案成功率反向调整 `min_gain`、`holdout_ratio`、提案数量与温度，实现“改进改进器” | 至少 50 轮真实数据 |
| P2+ | **多目标优化** | 从单一目标扩展到 Pareto 前沿（质量/成本/延迟），结合 endpoint `latency_ms` 权衡 | P1 统计与受保护指标 |
| P3 | **在线影子流量** | 将候选配置投放到影子接口，基于真实流量对比，而非离线数据集 | 生产流量与灰度能力 |
| P3 | **经验库** | 跨 loop 沉淀“失败模式 → 有效 Patch”映射，提案时检索相似历史，降低 LLM 成本 | 足够的版本与提案数据 |
| P3 | **CI 回归门禁** | 提供 `POST /api/rsi/gate` 供 CI 调用：给定基线与候选配置，返回是否允许合并 | API 稳定、鉴权就绪 |
| P3 | **人工偏好融合** | 将盲测胜率作为验收约束之一（自动创建盲测 + 阈值） | P2 盲测门禁 |
| P3 | **Alembic + PostgreSQL** | 正式迁移体系与并发写能力，替换 `ensure_runtime_schema` 手工补列 | P2 可选 Alembic 完成 |
| P3 | **鉴权与审计** | 引入登录/RBAC，记录审批人与操作来源；版本表增加 actor 详情 | 平台鉴权体系 |
| P3 | **对抗集与跨场景** | 建立跨场景/对抗样本集，验证候选不是过拟合单场景 | P2 反奖励黑客 |

---

## 10. 附录

### 10.1 建议的新增文件清单

```text
backend/app/models/rsi.py
backend/app/schemas/rsi.py
backend/app/api/rsi.py
backend/app/core/rsi_engine.py
backend/app/core/rsi_diagnosis.py
backend/app/core/rsi_proposer.py
backend/app/core/rsi_patch.py
backend/app/core/rsi_policy.py
backend/app/core/rsi_regression.py
backend/app/core/rsi_dataset.py              # P1
backend/app/core/evaluation_debug.py          # P1：从 api/evaluation.py 抽取
frontend/src/pages/RsiLoopListPage.tsx
frontend/src/pages/RsiLoopDetailPage.tsx
frontend/src/components/rsi/RsiCreateModal.tsx
frontend/src/components/rsi/RsiIterationTimeline.tsx
frontend/src/components/rsi/RsiDiagnosisPanel.tsx
frontend/src/components/rsi/RsiProposalDiff.tsx
frontend/src/components/rsi/RsiApprovalDrawer.tsx
frontend/src/components/rsi/RsiTrendChart.tsx
frontend/src/components/rsi/RsiPolicyForm.tsx
backend/tests/test_rsi_patch.py
backend/tests/test_rsi_api.py
backend/tests/test_rsi_engine.py
backend/tests/test_rsi_diagnosis.py
backend/tests/test_rsi_rollback.py
backend/tests/test_rsi_policy.py
backend/tests/test_rsi_reward_hacking.py
```

### 10.2 需要修改的现有文件

| 文件 | 修改内容 |
|------|----------|
| `backend/app/models/__init__.py` | 导入并导出 RSI 模型 |
| `backend/app/core/database.py` | `eval_tasks` 补列 |
| `backend/app/core/scenario_snapshot.py` | 新增“按提案构建候选快照”函数（保持原函数签名不变） |
| `backend/app/core/prompt_manager.py` | 新增 RSI 归因/提案 System Prompt 与输出约束 |
| `backend/app/core/config.py`、`backend/.env.example` | RSI 配置项 |
| `backend/app/main.py` | 注册 `rsi_router` |
| `backend/app/api/evaluation.py` | P1：debug 逻辑抽取后改为调用 `core/evaluation_debug.py`（行为不变） |
| `frontend/src/App.tsx` | 菜单与路由 |
| `frontend/src/services/api.ts`、`frontend/src/types/index.ts` | RSI 封装与类型 |
| `frontend/src/pages/ReportDetailPage.tsx` | P1：发起入口 |
| `docs/usage-guide.md`、`README.md` | RSI 章节与能力说明 |
| `AGENTS.md` | P2：常见任务补充 |

### 10.3 关键决策记录（ADR 摘要）

| 决策 | 选择 | 理由 | 被否方案 |
|------|------|------|----------|
| 回归执行方式 | 复用 `run_evaluation` + 候选 `scenario_snapshot` | 零侵入、口径一致、成本最低 | 新建独立评分器（重复实现、口径漂移） |
| 配置生效方式 | 影子评测通过后写回实体 + 按实体版本快照 | 普通评测读得到、可回滚、可审计 | 只维护 `RSIVersion.is_active` 指针（评测引擎不读，回滚不生效） |
| 提案格式 | 结构化白名单 Patch | 可校验、可 diff、可回滚 | 自由文本建议（无法执行）/ 任意代码补丁（不可控） |
| 默认审批 | 人工审批；MVP 不支持自动采纳 | 当前无鉴权/RBAC，风险优先 | 全自动采纳（业务风险过高） |
| 目标口径 | `metric_mean` 或冻结参考阈值的 `reference_pass_rate` | 避免降阈值刷通过率 | 直接用候选 `pass_threshold` 计算 pass_rate |
| Holdout | 同数据集稳定哈希划分 + train-only 归因 | 低摩擦、防泄漏 | 要求用户额外准备 holdout 数据集（B 方案，MVP 不采用） |
| 任务调度 | 线程 + asyncio + 轮询；SQLite 串行 | 与现有评测/盲测/RAG 一致，无新增基础设施 | Celery/Redis；SQLite 上并发 3 |
| 权重 Patch | MVP 不开放；P1 先补加权汇总 | 当前 `weight` 不参与汇总与通过判定 | MVP 直接改 weight（无实际效果） |
| 工时 | MVP 21 人日，含缓冲约 24 | 覆盖 API/引擎/测试的真实复杂度 | 16 人日（过于乐观）/ 29 人日（偏高） |

### 10.4 待确认项（评审时对齐）

1. RSI 是否确为 Recursive Self-Improvement（而非其他含义）？
2. 自进化对象是否包含“被测系统提示词”？平台实际杠杆只有 `EndpointTarget.request_body_template`；若系统提示词不通过请求传入，无法优化。
3. Holdout 是否允许用户额外提供独立数据集？MVP 默认同数据集哈希划分，P1 可支持外部 holdout。
4. 是否接受“MVP 不支持自动采纳、P2 仅低风险非评判类自动采纳”？
5. 5 行种子数据是否作为 MVP 演示数据？若要求 ≥30 行，需要先补充种子或文档说明。
6. `rsi_signals/rsi_clusters` 是否在 P1 就落表，还是继续用 `rsi_iterations.diagnosis` JSON？
7. 是否在 P2 引入 Alembic 基线？当前 `ensure_runtime_schema` 足够，但长期建议迁移。

### 10.5 与 RSI.md / RSI1.md 的取舍说明

| 来源 | 采纳 | 修正/拒绝 |
|------|------|-----------|
| `docs/RSI.md` | 工程骨架、4 表模型、Patch DSL、写回/回滚、API/前端/任务/验收/总表/路线图 | 16 人日过于乐观；5.1 的“holdout 与统计门槛 P1”与 3.9/4.1 的 MVP holdout 冲突；`weight` 在 MVP 不应开放；基线快照缺失不应回退当前场景 |
| `RSI1.md` | R1–R10 需求、fitness/受保护指标、两阶段评估/缓存、signals/clusters 分析表（P1）、测试矩阵、风险矩阵、保守工时 | `is_active` 指针不写回实体，回滚对普通评测不生效；`N_min=30` 硬门禁与 5 行种子冲突；P0 缺 Patch 治理；`is_evolution=True` 不是候选任务唯一差异；并发 3 与 SQLite 冲突；`seed.py` 必须扩展的说法不成立；`target_prompt_evolve` 应按请求模板理解 |
| 共同修正 | 阈值无关验收、判据交叉校验、holdout 泄漏隔离、小样本降级、MVP 人工审批、SQLite 串行 | 两份原稿都未完整覆盖这三点，本文作为强制规则 |

### 10.6 术语表

| 术语 | 说明 |
|------|------|
| RSI | Recursive Self-Improvement，本项目指评测驱动的配置自进化 |
| Patch / Gene | 一次可回放的最小配置变更单元（Prompt/阈值/指标 config/数据集/请求模板） |
| Train | 用于归因与提案的样本切片，不参与验收 |
| Holdout | 固定验证切片，只用于验收，不进入归因/提案上下文 |
| `reference_pass_rate` | 用创建 loop 时冻结的参考阈值对候选原始分数重算的通过率 |
| Protected Metric | 受保护指标，不允许在候选版本中显著下降 |
| Guardrail | 采纳前的硬约束：目标增益、无回归、错误率、样本量、人工门禁 |
| Shadow Evaluation | 用候选快照创建影子 `EvalTask`，不修改原场景 |
| 漂移（Drift） | 提案的 `before_value` 与当前配置不一致，说明配置已被其他操作修改 |
| Reward Hacking | 通过降阈值、改宽松判据、污染数据等方式制造“指标提升” |
| 判据交叉校验 | 用 baseline/candidate 两套判据互相重打对方回答，检测判据宽松度变化 |

---

**结论**：RSIX 在本项目中最合理的落地形态是“**评测驱动的配置自进化**”，而不是模型训练或代码自改写。它以 `EvalTask` 快照、原生 Judge 引擎与逐条证据为基础，通过白名单 Patch、影子回归、阈值无关验收、holdout 隔离、人工审批与版本回滚，把“看报告改 Prompt”的经验动作变成可复现、可审计、可回滚的工程闭环。建议按 **MVP（单轮闭环）→ P1（统计/沙盒/趋势）→ P2（数据集/接口/反自证）** 推进，并在每一阶段保持对现有评估、盲测与报告功能的完全兼容。
