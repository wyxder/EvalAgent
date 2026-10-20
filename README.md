# AI Evaluation Platform (AI 评测平台)

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white)](https://www.python.org/) [![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/) [![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-D71F00?logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org/) [![React](https://img.shields.io/badge/React-18.3-61DAFB?logo=react&logoColor=black)](https://react.dev/) [![TypeScript](https://img.shields.io/badge/TypeScript-5.5-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/) [![Ant%20Design](https://img.shields.io/badge/Ant%20Design-5.20-0170FE?logo=antdesign&logoColor=white)](https://ant.design/) [![Vite](https://img.shields.io/badge/Vite-5.4-646CFF?logo=vite&logoColor=white)](https://vitejs.dev/) [![OpenAI%20API](https://img.shields.io/badge/Judge-OpenAI%20Compatible-412991?logo=openai&logoColor=white)](https://openai.com/) [![Qwen](https://img.shields.io/badge/Default%20LLM-Qwen%20Plus-6236FF)](https://help.aliyun.com/zh/dashscope/) [![License](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)

---

## 📋 项目简介

**AI Evaluation Platform** 是一套专为 **RAG 检索增强生成**、**AI Agent 智能体**、**多轮智能对话** 等复杂业务场景打造的**现代化、企业级自托管 AI 应用评测与运营中枢**。

传统的大模型评测往往停留在散落的 Jupyter Notebook 脚本、单一的指标计算库（如 Ragas、TruLens）或离线的静态打分阶段，缺乏统一的数据管理、场景快照、在线接口探测、深度归因与人工审校协同。本项目旨在打破评测与业务工程之间的断层，提供涵盖 **数据集生命周期管理**、**RAG 知识库合成数据自动衍生**、**评测场景与指标快照**、**在线 HTTP 接口实时评测**、**原生 LLM-as-a-Judge 引擎**、**多版本报告对比**、**人工审计复核** 及 **双盲 A/B 人工偏好盲测** 的全链路工业化工作台。

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            AI Evaluation Platform                           │
├─────────────────┬───────────────────┬───────────────────┬───────────────────┤
│  1. 数据中枢     │  2. 场景与指标     │  3. 任务与执行    │  4. 报告与协同    │
│  • 单轮/多轮样本 │  • RAG 核心指标   │  • 原生 Judge LLM │  • 样本级得分理由 │
│  • RAG 文档合成  │  • Agent 工具链   │  • 实时接口探针   │  • 基线版本 Diff  │
│  • CSV/JSON 导入 │  • 对话连贯/记忆  │  • 任务快照冻结   │  • 人工复核标记   │
│  • 上下文/Trace  │  • 自定义 Prompt  │  • 异步调度流式   │  • 双盲 A/B 投票  │
└─────────────────┴───────────────────┴───────────────────┴───────────────────┘
```

### ✨ 核心业务价值

1. **工程化闭环，告别单点脚本**：将测试数据导入、场景指标制定、被测服务联调、批量运行、失败归因与人工复核完整串接在统一直观的 Web UI 中。
2. **原生执行引擎与确定性理由**：不强依赖黑盒三方评测框架，底层原生实现评分算法与结构化 Prompt 解析；每一项打分均强制要求 Judge 模型输出 **具象评判理由（Judge Reason）**，杜绝无据评分。
3. **支持离线与在线双模评测**：既支持直接对已知输出结果做批量离线质检，又支持直接挂载开发中的 RESTful Chat / RAG / Agent 接口进行实时在线评测，自动捕获请求 Trace 与网络耗时。
4. **科学严谨的场景快照机制**：评测任务触发瞬间自动固化当前场景所挂载的指标、权重、阈值与 Prompt 覆盖配置，避免后续指标修改导致历史任务对比失真。
5. **AI 自动打分与人工评测双轮驱动**：结合自动化 LLM-as-a-Judge 与交互式人工复审机制，更提供防偏置的人工双盲 A/B 测试系统，保障上线决策可靠。
6. **评测驱动的配置自进化（RSI）**：以已完成评测为基线，自动完成失败归因、白名单补丁提案、影子回归与阈值无关验收，经人工审批后写回场景配置，并支持版本快照与一键回滚（详见 [usage-guide 第八章](docs/usage-guide.md) 与 [RSIX.md](docs/RSIX.md)）。

---

## 🛠️ 技术栈

本项目采用高内聚、低耦合的前后端分离与微内核架构，分为 **前端交互层**、**后端核心服务** 以及 **AI 服务与评测引擎**。

### 1. 前端技术栈 (Frontend)

| 组件 / 依赖库 | 版本 | 职责定位 / 作用说明 |
| :--- | :--- | :--- |
| **React** | `^18.3.0` | 核心 UI 视图渲染引擎，全面采用函数式组件与 Hooks 响应式开发 |
| **TypeScript** | `^5.5.0` | 前端强类型约束系统，保障接口出入参、实体对象的一致性与健壮性 |
| **Ant Design (antd)** | `^5.20.0` | 企业级 UI 组件库，提供高级表单、表格分页、弹窗、抽屉与状态反馈组件 |
| **@ant-design/charts** | `^2.1.0` | 复杂图表与数据可视化套件，用于报告得分分布、多指标雷达图与趋势呈现 |
| **@ant-design/icons** | `^5.4.0` | 官方高质感语义化图标集，提升界面视觉一致性 |
| **Vite** | `^5.4.0` | 下一代现代化前端构建工具，极速 HMR 热重载与高效生产打包优化 |
| **React Router DOM** | `^6.26.0` | 前端单页应用声明式路由管理，实现工作台与多模块无刷新流畅切换 |
| **Axios** | `^1.7.0` | 前后端 HTTP 交互客户端，封装统一拦截器、请求超时期与异常统一分发 |
| **Day.js** | `^1.11.0` | 轻量级高性能时间日期格式化与解析工具 |

### 2. 后端技术栈 (Backend)

| 组件 / 依赖库 | 版本 | 职责定位 / 作用说明 |
| :--- | :--- | :--- |
| **Python** | `3.9+` (推荐 `3.11+`) | 后端主体开发语言，深度采用强类型 Type Annotations 与异步语法糖 |
| **FastAPI** | `>=0.104.0` | 高性能现代 Web 框架，基于 ASGI 标准，自动生成 OpenAPI 交互文档与校验 |
| **Uvicorn** | `>=0.24.0` | 极速轻量级 ASGI 服务器，承载 HTTP 与 WebSocket 异步长连接请求 |
| **SQLAlchemy** | `>=2.0.0` | 现代化 Python ORM，统一管理关系型数据库映射，支持 SQLite 与 PostgreSQL |
| **Psycopg 3 (psycopg[binary])** | `>=3.1.0` | 高性能 PostgreSQL 数据库异步驱动，支撑生产环境高并发存取 |
| **Pydantic & Pydantic-Settings**| `>=2.0.0` | 数据模式验证与环境变量配置加载引擎，提供严格的入参过滤与类型强转 |
| **Aiofiles & Python-Multipart** | 最新稳定版 | 异步文件 I/O 读写与多格式 Multipart 表单、文档流上传支持 |
| **PyPDF / PyMuPDF (fitz)** | `>=1.26.0` | 深度 PDF 文本与版面解析，用于 RAG 知识库合成数据的文本提取 |
| **python-docx** | `>=1.1.0` | 结构化解析 Word (`.docx`) 文档，提取多级段落与表格文字 |
| **HTTPX** | `>=0.25.0` | 异步 HTTP 客户端，用于在线调用被测服务 Endpoint 与第三方 API |
| **Pytest & Pytest-Asyncio** | `>=7.0.0` | 自动化单元测试与异步 API 路由回归套件 |

### 3. AI 服务与评测引擎 (AI Services & Evaluation Engine)

| 模块 / 服务协议 | 支撑模型 / 驱动组件 | 职责定位 / 评测能力 |
| :--- | :--- | :--- |
| **OpenAI 兼容协议客户端** | `openai>=1.0.0 (AsyncOpenAI)` | 统一与 Judge 模型交互的标准抽象层，解耦具体大模型厂商 |
| **默认 Judge 模型** | **通义千问 Qwen-Plus** (DashScope) | 具备卓越的中文语义理解、逻辑推理与严苛的判卷准度，提供稳定高质打分 |
| **多模型扩展兼容** | GPT-4o、DeepSeek、GLM、vLLM、Ollama | 任何提供兼容 `/v1/chat/completions` 的公有云或私有化大模型均可秒级接入 |
| **Native RAG 指标集** | 原生执行器 + 结构化 Critic Prompt | 覆盖检索质量（Context Recall / Precision / Relevancy）与生成质量（Faithfulness 等） |
| **Native Agent 指标集** | 规则比对 + 语义推导复合引擎 | 评估任务完成度 (Task Completion)、工具与参数正确性、执行步骤效率 (Step Efficiency) |
| **Native 多轮对话指标集** | 历史上下文滑窗审查引擎 | 评估话题一致性 (Topic Adherence)、知识继承与上下文记忆 (Knowledge Retention) |
| **确定性检索评测器** | 纯数学统计（HitRate@K, MRR） | 基于已知文档 ID 序列做秒级零消耗计算，评估向量检索召回与重排质量 |
| **合成数据生成器** | LLM 问答衍生 + 反向验证自纠错 | 从无标注 PDF/Word 自动清洗、切片并生成高质量带有 Ground Truth 的评测集 |

---

## 📁 目录结构

系统代码组织遵循模块化、高可维护性与领域驱动的设计思想，核心目录结构如下：

```text
ai-eval-platform/
├── backend/                               # 后端服务源码根目录
│   ├── .env.example                       # 环境变量示例配置文件
│   ├── requirements.txt                   # 后端 Python 依赖清单
│   ├── run.py                             # 后端开发环境快捷启动脚本 (Uvicorn 包装器)
│   ├── app/                               # FastAPI 应用核心目录
│   │   ├── main.py                        # 应用入口点：生命周期挂载、中间件、路由总装
│   │   ├── seed.py                        # 系统初始化种子数据（内置指标、场景与示例数据）
│   │   ├── api/                           # 业务 RESTful API 路由模块
│   │   │   ├── blind_test.py              # 人工盲测任务创建、投票与胜率统计接口
│   │   │   ├── dataset.py                 # 数据集增删改查、数据行维护、CSV/JSON 导入导出
│   │   │   ├── endpoint_target.py         # 被测 HTTP 接口配置靶场与测试接口
│   │   │   ├── evaluation.py              # 评测任务创建、调试单测、日志与任务取消
│   │   │   ├── llm_config.py              # Judge 模型配置、可用性连通性测试接口
│   │   │   ├── metric.py                  # 评测指标定义、自定义 Prompt 指标管理
│   │   │   ├── rag_dataset_job.py         # 文档切片与 RAG 合成数据集异步生成任务
│   │   │   ├── report.py                  # 评测报告详情、样本明细、人工复核与报告版本比对
│   │   │   ├── rsi.py                     # RSI 自进化循环、审批、回滚、预览与版本接口
│   │   │   └── scenario.py                # 评测场景模板管理与指标权重配置
│   │   ├── core/                          # 核心执行引擎与基础设施
│   │   │   ├── config.py                  # 全局 Settings 配置类（基于 Pydantic-Settings）
│   │   │   ├── database.py                # 数据库连接池、Base 基类与运行时 Schema 校验
│   │   │   ├── evaluation_debug.py        # 单行沙盒调试抽取（支持场景快照覆盖）
│   │   │   ├── evaluation_engine.py       # 原生评测引擎：指标打分、OpenAI Client、理由提取
│   │   │   ├── endpoint_eval.py           # 在线接口调用探针、动态参数插值与 Trace 抽取
│   │   │   ├── prompt_manager.py          # 评测 System Prompt、评分指令与模板渲染器
│   │   │   ├── rag_dataset_generator.py   # RAG 知识库文档智能解析、分块与问答合成器
│   │   │   ├── blind_test_engine.py       # 双盲 A/B 测试异步分发与偏好聚合引擎
│   │   │   ├── rsi_dataset.py             # RSI 失败样本派生 hard-case 数据集（只追加）
│   │   │   ├── rsi_diagnosis.py           # 失败归因：分簇、证据抽取与规则降级
│   │   │   ├── rsi_engine.py              # RSI 循环编排：预算、迭代状态机、审批与回滚
│   │   │   ├── rsi_patch.py               # Patch 白名单校验、漂移检查、写回与版本恢复
│   │   │   ├── rsi_policy.py              # 验收策略、holdout 切分、指标汇总与判定
│   │   │   ├── rsi_proposer.py            # 提案生成与静态校验
│   │   │   ├── rsi_regression.py          # 影子回归任务创建与执行
│   │   │   └── scenario_snapshot.py       # 场景快照固化与历史不可变版本归档
│   │   ├── models/                        # SQLAlchemy ORM 实体数据模型定义
│   │   │   ├── dataset.py                 # 数据集 (Dataset) 与数据行 (DatasetRow)
│   │   │   ├── endpoint_target.py         # 被测接口配置 (EndpointTarget)
│   │   │   ├── evaluation.py              # 评测任务、单行得分记录、人工盲测实体
│   │   │   ├── llm_config.py              # LLM Judge 配置实体
│   │   │   ├── metric_definition.py       # 指标元数据定义 (MetricDefinition)
│   │   │   ├── rag_dataset_job.py         # RAG 合成任务、文档、切片与合成样本模型
│   │   │   ├── rsi.py                     # RSI 循环、迭代、提案与配置版本模型
│   │   │   └── scenario.py                # 场景模板 (EvalScenario) 与场景指标绑定
│   │   └── schemas/                       # Pydantic 请求与响应验证模型
│   │       ├── dataset.py                 # 数据集 DTO
│   │       ├── endpoint_target.py         # 接口目标 DTO
│   │       ├── evaluation.py              # 任务创建、调试响应 DTO
│   │       ├── llm_config.py              # 模型配置 DTO
│   │       ├── metric_definition.py       # 指标定义 DTO
│   │       ├── rag_dataset_job.py         # 合成任务 DTO
│   │       ├── rsi.py                     # RSI 循环、提案、迭代与版本 DTO
│   │       ├── scenario.py                # 场景配置 DTO
│   └── tests/                             # 后端自动化测试套件 (全量 101 个用例全部通过)
│       ├── conftest.py                    # SQLite 测试夹具与依赖覆盖
│       ├── test_evaluation.py             # 核心评测、指标加权与场景快照测试
│       ├── test_dataset.py                # 数据集与样本行 CRUD 测试
│       ├── test_blind_test.py             # 双盲测试与投票聚合测试
│       ├── test_rag_dataset_job.py        # RAG 文档切片与问答生成测试
│       ├── test_rsi_patch.py              # RSI 白名单校验与漂移防护测试
│       ├── test_rsi_diagnosis.py          # 失败聚类与降级测试
│       ├── test_rsi_policy.py             # 验收策略、Holdout 切分与门禁测试
│       ├── test_rsi_engine.py             # RSI 状态机、预算与超时恢复测试
│       ├── test_rsi_api.py                # RSI RESTful API 路由与契约测试
│       └── test_rsi_rollback.py           # 版本不可变、回滚一致性与血缘测试
│   ├── index.html                         # 前端单页应用 HTML 模板入口
│   ├── package.json                       # 前端项目依赖与脚本定义
│   ├── tsconfig.json                      # TypeScript 编译配置文件
│   ├── vite.config.ts                     # Vite 构建配置（含 /api 本地代理）
│   └── src/                               # 核心源码
│       ├── main.tsx                       # React 应用挂载根入口
│       ├── App.tsx                        # 全局路由、侧边栏菜单与统一 Layout 骨架
│       ├── styles.css                     # 全局设计规范、主题微调与样式定制
│       ├── services/                      # API 网络通信层
│       │   └── api.ts                     # 统一导出对后端 RESTful API 的调用函数
│       ├── pages/                         # 业务视图页面组件
│       │   ├── ExperimentWorkbenchPage.tsx# 🌟 评测实验工作台（全流程向导）
│       │   ├── LLMConfigPage.tsx          # Judge 大模型配置与连通测试
│       │   ├── DatasetListPage.tsx        # 数据集列表、新建与导入导出
│       │   ├── DatasetDetailPage.tsx      # 数据集行级数据在线浏览、增删改
│       │   ├── RagDatasetBuilderPage.tsx  # RAG 知识库合成数据自动化生成器
│       │   ├── ScenarioListPage.tsx       # 场景模板管理、指标与阈值调配
│       │   ├── MetricListPage.tsx         # 指标库总览与自定义 Prompt 指标配置
│       │   ├── EndpointTargetPage.tsx     # 被测在线接口注册与联调验证
│       │   ├── EvaluationPage.tsx         # 评测任务实时监控、流式日志与进度
│       │   ├── ReportListPage.tsx         # 评测报告列表总览
│       │   ├── ReportDetailPage.tsx       # 报告深度详情、雷达图、人工复核与基线对比
│       │   ├── RsiLoopListPage.tsx        # RSI 自进化循环列表、创建与预算概况
│       │   ├── RsiLoopDetailPage.tsx      # RSI 循环详情、归因/提案审批、回滚与日志
│       │   └── BlindTestPage.tsx          # 人工双盲偏好评测与 A/B 投票室
│       ├── components/                    # 通用业务组件
│       │   ├── ConversationViewer.tsx     # 多轮对话沉浸式展示组件
│       │   ├── DataImportModal.tsx        # CSV / JSON 数据导入弹窗
│       │   ├── MetricConfigPanel.tsx      # 指标权重滑块与阈值配置面板
│       │   ├── MetricHelpDrawer.tsx       # 指标科学原理与计算公式帮助抽屉
│       │   └── rsi/                       # RSI 创建、审批、Diff、趋势与归因组件
│       └── types/                         # TypeScript 全局接口与数据契约定义
├── docs/                                  # 核心系统设计与使用指南文档
│   ├── usage-guide.md                     # 平台深度使用指南（含 RSI 第八章）
│   ├── evaluation-guide.md                # 评测指标原理与实践指南
│   ├── database-and-storage.md            # 存储架构选型与 PostgreSQL 迁移指南
│   ├── comparison.md                      # 与行业评测框架对比深度分析
│   └── open-source-readiness.md           # 开源就绪度与发布检查清单
├── AGENTS.md                              # 平台智能体开发与编码规范
├── README.md                              # 英文主页文档
├── README.zh-CN.md                        # 中文主页文档
└── LICENSE                                # 开源许可证 (Apache License 2.0)
```

---

## ⚡ 核心功能模块和工作流程

系统以“**评测闭环与质量运营**”为核心，构建了从数据衍生、场景固化、接口探针、原生裁判到人工审校的七大关键模块。

```mermaid
flowchart TD
    subgraph DataPrep["1. 数据与样本准备"]
        D1[外部 CSV/JSON 导入] --> DS[统一数据集仓库]
        D2[知识库文档 PDF/DOCX] --> RAG_GEN[RAG 合成数据引擎] --> DS
    end

    subgraph Config["2. 评测配置与编排"]
        DS --> WB[评测实验工作台]
        SCN[场景模板与指标库] --> WB
        LLM_J[LLM Judge 模型] --> WB
        TARGET[被测在线 HTTP 接口] -.->|可选在线挂载| WB
    end

    subgraph Exec["3. 任务固化与原生评测引擎"]
        WB -->|生成不可变快照| SNAP[场景配置快照]
        SNAP --> TASK[异步评测执行器]
        TARGET -->|实时网络调用| PROBE[接口探针 & Trace 提取]
        PROBE --> TASK
        TASK --> NATIVE_ENG[原生 Judge 引擎]
        NATIVE_ENG -->|JSON Mode / Prompt 判定| LLM_CALL[OpenAI 兼容 Judge LLM]
        LLM_CALL -->|输出具体评分与依据| NATIVE_ENG
    end

    subgraph ReportReview["4. 报告分析与决策闭环"]
        NATIVE_ENG --> RPT[深度评测报告]
        RPT --> RPT_DIFF[多版本基线 Diff 对比]
        RPT --> HUMAN_AUDIT[人工审校与复核修正]
        RPT_DIFF --> DECISION[上线发布决策]
        HUMAN_AUDIT --> DECISION
    end

    subgraph BlindTestModule["5. 人工盲测 A/B 评优"]
        DS --> BT_TASK[盲测任务分发]
        BT_TASK -->|打乱顺序隐藏标识| BT_ROOM[双盲投票室]
        BT_ROOM --> ELO[胜率统计与人工偏好分析]
        ELO --> DECISION
    end

    style WB fill:#e6f7ff,stroke:#1890ff,stroke-width:2px
    style NATIVE_ENG fill:#f6ffed,stroke:#52c41a,stroke-width:2px
    style DECISION fill:#fff7e6,stroke:#fa8c16,stroke-width:2px
```

---

### 1. 评测实验工作台 (Experiment Workbench)

工作台是系统最核心的日常作业空间，提供引导式向导，5 分钟内即可完成单次实验的设计与分发：
- **第一步：数据集绑定** —— 选择单轮问答、多轮对话样本或带有检索 Context 的预置数据集。
- **第二步：场景选择与微调** —— 挂载 RAG、Agent、客服对话等场景模板，针对本次实验临时调整指标激活状态、及格阈值、权重或直接覆写特定 Prompt。
- **第三步：Judge 模型挑选** —— 选择用于打分的后台大模型（如通义千问 Qwen Plus），支持临时调节 Temperature 等超参数。
- **第四步：被测目标配置（可选）** —— 选择离线模式（评估样本中已记录的 `response`），或挂载在线 HTTP 接口对实时输出进行现场评测。
- **第五步：单样本实时联调 (Debug)** —— 在提交完整任务前，选取任意一条样本进行原地单测执行，直接预览接口调用 Trace、Judge 提示词以及打分输出，排查入参映射错误。

---

### 2. 评测场景与指标体系 (Evaluation Scenarios & Metrics)

平台构建了多维度、成体系的原生指标池，分为四大核心门类：

```
                              ┌── 忠实度 (Faithfulness) ────────── 评估是否由 Context 支撑，杜绝幻觉
                              ├── 上下文召回率 (Context Recall) ── 是否完整召回 Ground Truth 事实
               ┌── RAG 评测 ──┼── 上下文精确度 (Context Precision) 检索到的切片信息纯度与相关性
               │              ├── 上下文相关性 (Contextual Relevancy) 检索切片与问题的契合度
               │              ├── 回答相关性 (Answer Relevancy) ─── 回答是否紧扣提问核心
               │              └── 检索排序 (HitRate@K / MRR) ────── 纯 ID 精准数学评测
               │
               │              ┌── 任务完成度 (Task Completion) ──── 目标是否达成
               ├── Agent 评测 ┼── 工具正确性 (Tool Correctness) ─── 选取的 Tool 是否合理
原生指标体系 ──┤              ├── 参数正确性 (Argument Correctness) 填写的入参键值是否准确
               │              └── 步骤效率 (Step Efficiency) ────── 是否存在工具死循环与冗余调用
               │
               │              ┌── 话题遵守度 (Topic Adherence) ──── 是否出现跑题或被引导偏离
               ├── 多轮对话 ──┼── 轮次相关性 (Turn Relevancy) ───── 单轮互动上下文衔接度
               │              ├── 对话完成度 (Conversation Completeness) 复杂业务全流程是否闭环
               │              └── 上下文记忆 (Knowledge Retention) 跨轮次记忆保留度
               │
               └── 通用安全 ──── 连贯性 (Coherence) / 有害性过滤 (Harmfulness)
```

- **内置 LLM 指标 (`NativeBuiltinLLMMetric`)**：通过专门调优的 System Prompt + JSON Schema，引导模型输出 0~1 的实数评分，并结构化吐出 `reason`。
- **自定义 Prompt 指标 (`NativePromptMetric`)**：支持用户直接编写判定规则与评分区间（如 0/1 二值打分、1~5 分、Aspect Critic 审查模式），并支持在 Prompt 中引用 `{{user_input}}`、`{{response}}`、`{{retrieved_contexts}}` 等动态占位符。
- **确定性检索评测器**：针对带有预埋标注 `ground_truth_context_ids` 的样本，直接由后端内存算法秒级计算 **HitRate@K**（召回命中率）与 **MRR**（平均倒数排名），零 LLM 调用成本。

---

### 3. 被测接口在线实时探针 (Endpoint Target & Trace Extraction)

平台不仅是一个离线评测器，更是 AI 应用的在线集成测试靶场：
- **RESTful 请求模板化**：支持自定义 HTTP 请求方法（POST/GET）、请求头（Headers，支持 Bearer Token / API-Key 安全脱敏保存）以及 JSON Body 模板。
- **动态占位符插值**：Body 模板支持注入数据集行字段，如 `{"query": "{{user_input}}", "history": {{messages}}}`。
- **结果反向抽取 (Field Mapping)**：
  - `response_path`：通过点号语法（如 `data.choices.0.message.content`）提取生成的文本回答。
  - `context_path`：提取在线检索出来的文档切片列表。
  - `tool_calls_path`：提取 Agent 触发调用的工具名及参数。
  - `latency` & `status_code`：完整记录每次在线调用的物理耗时与 HTTP 状态码，形成可供追溯的 Endpoint Trace。

---

### 4. RAG 知识库合成数据生成器 (RAG Dataset Builder Pipeline)

针对缺乏真实标注样本的冷启动痛点，平台内置工业级文档自动衍生合成数据流水线：

```
[原始企业文档 (PDF / Word / TXT)]
           │
           ▼
[版面解析 & 智能文本清洗] (去除页眉页脚、版次修订记录、回执表格等干扰信息)
           │
           ▼
[语义滑窗切片 (Semantic Chunking)] (保持段落完整性与重叠区)
           │
           ▼
[LLM 提问衍生 (Question Generation)] (生成多角度业务提问)
           │
           ▼
[LLM 答案合成 (Ground Truth Answer)] (基于切片精确生成标准答案)
           │
           ▼
[双向验证自纠错 (QA Validation Filter)] (淘汰低质模糊样本)
           │
           ▼
[输出高质量评测数据集] (自动打上 chunk_id 与 ground_truth_context 标签)
```

- **多格式支持**：基于 `PyMuPDF` 和 `python-docx`，深层提取非结构化文件。
- **启发式降噪过滤**：自动识别并剔除如“第 X 页 / 共 Y 页”、“文件编号”、“批准人”、“签名回执”等表格噪声。
- **自适应并发与断点重试**：控制并发调用（默认并发限流），遇到网络波动支持单个失败样本一键重试（Retry Failed）。

---

### 5. 原生 LLM-as-a-Judge 评测执行流

评测执行过程采用基于异步协程池的任务架构：
1. **快照冻结**：任务分发前，调用 `build_scenario_snapshot` 将该场景当前的指标列表、提示词覆盖、权重快照序列化进 `eval_tasks.scenario_snapshot` 字段中。
2. **在线调用（如有）**：若绑定了被测 Endpoint，先异步并发调度接口探针获取动态响应与 Trace。
3. **并发评分**：`OpenAIJudgeClient` 发起评测调用，优先使用 `response_format={"type": "json_object"}` 强制模型输出 JSON 字典；若模型网关不支持，则自动降级使用纯文本重试并配合正则做健壮 JSON 提取。
4. **统一分值归一化**：支持对打分结果根据场景指标权重自动加权聚合，生成单样本综合分与任务整体及格率（Pass Rate）。

---

### 6. 评测报告、版本对比与人工复核 (Report, Diff & Review)

- **全局概览与雷达图**：展示任务通过率、各指标平均分、耗时分布与整体得分雷达图。
- **逐条明细审计**：表格分页展开，点击任意一行可展开查看原始提问、参考答案、接口 Trace、各项指标得分以及 **Judge 模型给出的具象打分依据（Reason）**。
- **人工复核机制 (Human Review)**：自动化评分不是绝对真理。系统支持审校人员介入，将样本状态更新为 `approved`（认可）或 `flagged`（存疑），可覆写人工真实分数、打上业务标签并补充人工复核备注。
- **多版本基线比对 (Report Compare)**：选择任意历史评测任务作为 Baseline，系统自动计算各项指标得分的升降 Delta、通过率变化趋势，精准定位 Prompt 优化或模型版本变更后的退化用例（Regression Cases）。

---

### 7. 双盲 A/B 人工偏好盲测 (Blind Test System)

消除人工主观偏置的 A/B 评测系统：
- **三种对比模式**：支持 `LLM vs LLM`（两个大模型直接比拼）、`Endpoint vs Endpoint`（两套业务接口比拼）、`LLM vs Endpoint`（新算法接口与 Baseline 模型比拼）。
- **盲测乱序混淆**：后台请求两套来源后，前端展示时随机置乱 A/B 序号并抹去模型/接口名称标签，防止测试人员带心理倾向打分。
- **偏好裁决与胜率统计**：审校人员选择“模型 A 更好”、“模型 B 更好”、“平局（皆可）”或“两者皆差（皆不可）”，系统实时计算各方胜率（Win Rate）、平局率及偏好分布图表。

---

### 8. 评测驱动的配置自进化 (RSI - Recursive Self-Improvement)

平台实现业界领先的 **“评测驱动的配置自进化” (RSI)** 闭环。以一次已完成的真实评测为基线，自动化执行失败归因、白名单补丁提案、影子回归与验收判定，并在人工审批后写回场景配置与留存版本快照，支持一键回滚。

```text
┌──────────────────────────────────────────────────────────────────────────┐
│                         RSI 循环 (Recursive Evolution)                   │
│                                                                          │
│  ① 基线评测 ──► ② 失败归因 ──► ③ 优化提案 ──► ④ 白名单/漂移静态校验      │
│      ▲              │              │                   │                 │
│      │         (只读 train)         │                   ▼                 │
│      │              │              │            ⑤ 沙盒单行预览 (P1)      │
│      │              │              │                   │                 │
│      │              │              │                   ▼                 │
│      │              │              └────────► ⑥ 影子回归评估 (全量/Holdout)│
│      │              │                                       │            │
│      │              │                                       ▼            │
│      │              │                          ⑦ 冻结参考阈值验收判定    │
│      │              │                                       │            │
│      │              │                          ┌────────────┴─────────┐  │
│      │              │                          ▼                      ▼  │
│      │              │                    人工审批 / 确认采纳       驳回/终止轮次│
│      │              │                          │                         │
│      │              └──────────────────► ⑧ 版本快照 + 写回 + 一键回滚     │
│      │                                         │                         │
│      └────────────── 下一轮以 candidate 为基线 ◄─────────────────────────┘
└──────────────────────────────────────────────────────────────────────────┘
```

- **三大防自欺安全红线**：
  1. **阈值无关验收**：验收目标采用创建循环时冻结的 `reference_thresholds` 计算样本通过率或目标指标均值，杜绝“通过降低 `pass_threshold` 虚假抬高通过率”。
  2. **Holdout 严格隔离**：采用样本稳定哈希切分，失败归因与提案 Prompt **只读取 Train 切片**，Holdout 数据绝不进入提示词上下文，防止测试集泄漏。
  3. **漂移检测与先快照后落库**：提案校验时强制比对 `before_value` 是否与当前数据库实体一致；写回前先在 `rsi_config_versions` 创建不可变快照，支持任意历史版本一键回滚。
- **P1 级效率与诊断增强**：
  - **沙盒单行试跑 (`/preview`)**：复用底层评测调试引擎，一键预览单条样本在应用候选补丁后的出分与 Reason，降低全量回归试错成本。
  - **Hard-case 派生数据集 (`/hard-cases`)**：自动将当轮未通过用例提炼为派生数据集（只追加、不改原表、自动剔除 holdout），形成困难样本库持续复测。
  - **指标演化折线图**：多轮次各维度增益、通过率演化趋势及 LLM 消耗量可视化大盘。

---

## ⚙️ 部署指南

### 1. 环境准备

- **操作系统**：Linux / macOS / Windows 10+
- **Python 运行时**：Python 3.9+（强烈推荐使用 Python 3.11 或 3.12 获得最佳异步性能）
- **Node.js 运行时**：Node.js 18.0+ 及配套 npm / pnpm / yarn
- **大模型 API Key**：阿里云 DashScope（默认通义千问）、OpenAI 或任意兼容接口的密钥

---

### 2. 环境变量配置

进入 `backend/` 目录，由示例配置复制生成 `.env`：

```bash
cd backend
cp .env.example .env
```

核心配置项说明及推荐生产配置：

| 环境变量名 | 类型 | 默认值 | 作用说明与配置建议 |
| :--- | :--- | :--- | :--- |
| `LLM_API_KEY` | String | *(空)* | **必需**。Judge 模型的 API Key（如 DashScope 的 `sk-xxx`） |
| `LLM_MODEL` | String | `qwen-plus` | Judge 模型代号，推荐 `qwen-plus` 或 `gpt-4o` |
| `LLM_ENDPOINT` | String | `https://dashscope.aliyuncs.com/compatible-mode/v1` | OpenAI 兼容模式的 API 基础端点 |
| `DATABASE_URL` | String | `sqlite:///./eval_platform.db` | 数据库连接串。单机开发用 SQLite，生产环境推荐 PostgreSQL |
| `UPLOAD_DIR` | String | `./uploads` | RAG 任务上传文件的本地落盘保存路径 |
| `CORS_ORIGINS` | JSON Array | `["http://localhost:5173"]` | 允许跨域的前端 Origin 域名列表 |
| `SEED_ON_STARTUP` | Boolean | `true` | 是否在后端初次启动时自动写入预设指标、场景与示例数据集 |
| `RUN_EVAL_ON_CREATE`| Boolean | `true` | 创建评测任务后是否立即后台异步开始评测 |
| `LLM_TEMPERATURE` | Float | `0.01` | Judge 评测时的采样温度（建议极低值以保证打分确定性） |
| `LLM_MAX_TOKENS` | Integer | `1024` | Judge 评分输出的最大 Token 数量 |
| `RSI_ENABLED` | Boolean | `true` | RSI 自进化模块总开关，关闭后 `/api/rsi/*` 返回 403 并隐藏前端菜单 |
| `RSI_MAX_ITERATIONS` | Integer | `3` | 单个自进化循环的最大迭代轮次数上限 |
| `RSI_MAX_ROWS_PER_ITERATION`| Integer | `50` | 每轮迭代用于归因裁剪与预算估算的最大样本行数 |
| `RSI_MAX_LLM_CALLS` | Integer | `300` | 单个自进化循环消耗的 LLM 调用次数安全预算熔断阈值 |
| `RSI_MAX_MINUTES` | Integer | `45` | 单个自进化循环的最大运行时长超时阈值（超期自动标记 failed） |
| `RSI_MAX_PROPOSALS_PER_ITERATION` | Integer | `3` | 每轮迭代生成的最大候选 Patch 提案数 |
| `RSI_HOLDOUT_RATIO` | Float | `0.3` | Holdout 验证集哈希抽样比例（0~0.5） |
| `RSI_MIN_OBJECTIVE_GAIN` | Float | `0.03` | 验收建议通过所需的最小目标指标增益幅度 |
| `RSI_MAX_METRIC_DROP` | Float | `0.02` | 受保护指标允许的最大允许降幅门禁（防退化） |
| `RSI_AUTO_APPLY_LOW_RISK`| Boolean | `false` | 是否允许低风险且满足严格 Holdout 样本量的补丁自动写回采纳 |
| `RSI_PROPOSER_TEMPERATURE` | Float | `0.2` | 提案生成大模型的采样温度（兼顾稳定性与探索性） |

---

### 3. 后端服务启动

#### 方式 A：标准 Python venv 环境

```bash
# 1. 进入后端目录
cd backend

# 2. 创建并激活虚拟环境
python3 -m venv venv
# Linux / macOS:
source venv/bin/activate
# Windows PowerShell:
# .\venv\Scripts\Activate.ps1

# 3. 安装核心依赖
pip install --upgrade pip
pip install -r requirements.txt

# 4. 启动后端应用
python3 run.py
```

#### 方式 B：使用现代化包管理器 `uv`（极速推荐）

```bash
cd backend
uv venv
uv pip install -r requirements.txt
uv run python run.py
```

服务启动成功后，控制台将输出服务地址，访问交互式 API 文档：
- **Swagger UI**：`http://localhost:8000/docs`
- **ReDoc**：`http://localhost:8000/redoc`

---

### 4. 前端应用启动

打开新的终端窗口，进入 `frontend/` 目录：

```bash
# 1. 进入前端目录
cd frontend

# 2. 安装前端依赖
npm install

# 3. 启动 Vite 开发调试服务器
npm run dev
```

启动完成后，使用浏览器访问前端控制台：
- **Web UI 访问入口**：`http://localhost:5173`

---

### 5. 生产环境部署建议

#### 切换至 PostgreSQL 数据库
在并发评测与大规模数据集场景下，SQLite 可能会出现锁库等待。修改 `backend/.env`：

```bash
DATABASE_URL=postgresql+psycopg://eval_user:StrongPassword123@127.0.0.1:5432/ai_eval_platform
```

> **提示**：系统启动时，SQLAlchemy 会自动检测目标数据库并创建对应表结构与索引，无需手动执行复杂 SQL 脚本。

#### 前端静态编译与 Nginx 反向代理

```bash
# 前端编译生成生产静态资源
cd frontend
npm run build
# 产物输出至 frontend/dist
```

推荐的 Nginx 代理配置示例：

```nginx
server {
    listen 80;
    server_name eval.yourdomain.com;

    # 前端静态页面托管
    location / {
        root /path/to/EvalAgent/frontend/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # 后端 RESTful API 转发
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 300s;
    }

    # 上传静态资源托管
    location /uploads/ {
        alias /path/to/EvalAgent/backend/uploads/;
        expires 7d;
    }
}
```

---

## 📦 API 接口

平台提供丰富、规范的 RESTful API。所有业务接口统一挂载在 `/api` 路径下，敏感凭据（如 API-Key / Authorization Header）在查询与列表接口中均经过自动掩码（Masking）脱敏处理。

### 1. 系统与 LLM 配置管理 (`/api/llm-configs`)

| 请求方式 | 接口端点 | 描述说明 | 核心入参 / 请求体 | 核心响应说明 |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/health` | 节点健康检查探针 | 无 | 返回 `{"status": "ok"}` |
| `GET` | `/api/llm-configs` | 获取所有已注册的 Judge 模型配置 | 无 | 返回模型配置列表（密钥字段已脱敏） |
| `POST` | `/api/llm-configs` | 注册新的 Judge 模型配置 | `name`, `model_name`, `api_base_url`, `api_key`, `temperature` | 返回创建后的配置详情及唯一 ID |
| `GET` | `/api/llm-configs/{id}` | 查询单个模型配置详情 | 路径参数: `id` | 返回单条配置详情 |
| `PUT` | `/api/llm-configs/{id}` | 更新指定模型配置 | 路径参数: `id`, 更新键值对 | 返回更新后的模型实体 |
| `DELETE` | `/api/llm-configs/{id}` | 删除指定模型配置 | 路径参数: `id` | 状态码 `204 No Content` |
| `POST` | `/api/llm-configs/{id}/test` | 测试已保存模型的真实网络连通性 | 路径参数: `id` | 返回可用性、响应耗时及测试回包 |
| `POST` | `/api/llm-configs/test-draft` | 草稿模式测试（保存前验真） | 表单录入的模型参数体 | 返回连接测试是否成功与错误诊断 |

---

### 2. 数据集与样本管理 (`/api/datasets`)

| 请求方式 | 接口端点 | 描述说明 | 核心入参 / 请求体 | 核心响应说明 |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/datasets` | 获取数据集列表 | 支持关键词搜索与筛选 | 返回数据集概要与包含样本数统计 |
| `POST` | `/api/datasets` | 创建空数据集仓库 | `name`, `description` | 返回创建的数据集元数据 |
| `GET` | `/api/datasets/{id}` | 获取数据集详情元数据 | 路径参数: `id` | 数据集名称、描述、总行数与创建时间 |
| `PUT` | `/api/datasets/{id}` | 更新数据集名称与描述 | 路径参数: `id`, 更新体 | 返回更新后的元数据 |
| `DELETE` | `/api/datasets/{id}` | 级联删除数据集及所有数据行 | 路径参数: `id` | 状态码 `204 No Content` |
| `GET` | `/api/datasets/{id}/rows` | 分页拉取数据集行列表 | Query: `page`, `page_size`, `query` | 返回样本列表、总数 `total` 与当前分页 |
| `POST` | `/api/datasets/{id}/rows` | 向数据集手工插入单条样本 | `user_input`, `response`, `ground_truth`, `retrieved_contexts`, `tool_calls` | 返回新建的样本行实体与自增 ID |
| `DELETE` | `/api/datasets/{id}/rows/{row_id}` | 删除单条样本数据 | 路径参数: `id`, `row_id` | 状态码 `204 No Content` |
| `POST` | `/api/datasets/{id}/import` | 批量上传导入数据集文件 | `multipart/form-data`: `file` (CSV / JSON) | 返回导入成功行数与异常跳过行数 |
| `GET` | `/api/datasets/{id}/export` | 导出数据集为本地文件 | Query: `format=csv` 或 `format=json` | 返回文件二进制流（带附件下载 Header） |

---

### 3. RAG 知识库合成数据任务 (`/api/rag-dataset-jobs`)

| 请求方式 | 接口端点 | 描述说明 | 核心入参 / 请求体 | 核心响应说明 |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/rag-dataset-jobs` | 获取合成任务列表 | 支持分页与状态过滤 | 任务名称、关联模型、阶段状态与进度 |
| `POST` | `/api/rag-dataset-jobs` | 创建新的 RAG 合成任务 | `title`, `llm_config_id`, `target_dataset_id`, `chunk_size` | 返回新建任务实例 |
| `GET` | `/api/rag-dataset-jobs/{id}` | 获取合成任务进度与详情 | 路径参数: `id` | 任务解析状态、完成百分比与样本计数 |
| `POST` | `/api/rag-dataset-jobs/{id}/documents` | 上传源文档 (PDF/DOCX/TXT) | `multipart/form-data`: `files` | 返回上传成功文档列表与初始大小 |
| `GET` | `/api/rag-dataset-jobs/{id}/documents` | 查看任务关联的源文档清单 | 路径参数: `id` | 文档名称、文件格式与解析状态 |
| `GET` | `/api/rag-dataset-jobs/{id}/chunks` | 查看文档清洗切片分块详情 | Query: `document_id` (可选) | 返回切片后的文本内容、字符数与片段元数据 |
| `GET` | `/api/rag-dataset-jobs/{id}/samples` | 分页查看已合成的 QA 问答样本 | Query: `page`, `page_size`, `status` | 生成的提问、标准答案与源切片引用 |
| `POST` | `/api/rag-dataset-jobs/{id}/start` | 启动后台合成生成任务 | 路径参数: `id` | 触发后台 Worker，返回初始运行状态 |
| `POST` | `/api/rag-dataset-jobs/{id}/retry-failed` | 对失败生成的切片重试合成 | 路径参数: `id` | 触发增量补偿生成任务 |

---

### 4. 评测指标与场景管理 (`/api/metrics` & `/api/scenarios`)

| 请求方式 | 接口端点 | 描述说明 | 核心入参 / 请求体 | 核心响应说明 |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/metrics` | 获取所有评测指标（内置+自定义） | Query: `page`, `page_size`, `category` | 返回指标元数据、评测方式及必填字段列表 |
| `POST` | `/api/metrics` | 注册自定义 Prompt 评测指标 | `name`, `display_name`, `metric_type`, `config` | 返回新建的自定义指标实体 |
| `PUT` | `/api/metrics/{id}` | 更新自定义指标规则与 Prompt | 路径参数: `id`, 更新体 | 返回更新后的指标信息 |
| `DELETE` | `/api/metrics/{id}` | 删除自定义指标（内置不可删） | 路径参数: `id` | 状态码 `204 No Content` |
| `GET` | `/api/scenarios/presets` | 获取系统内置标准场景模板 | 无 | 返回 RAG、Agent、多轮对话等标准场景 |
| `GET` | `/api/scenarios` | 获取所有已配置场景模板 | 无 | 返回场景列表及各自关联的指标集合 |
| `POST` | `/api/scenarios` | 新建场景并绑定指标权重 | `name`, `description`, `metrics: [{metric_id, weight, pass_threshold}]` | 返回场景详情与完整指标配置 |
| `GET` | `/api/scenarios/{id}` | 查询单个场景详情 | 路径参数: `id` | 场景元数据及其挂载的指标矩阵 |
| `PUT` | `/api/scenarios/{id}` | 更新场景指标绑定与阈值设置 | 路径参数: `id`, 场景配置体 | 返回更新后的场景对象 |
| `DELETE` | `/api/scenarios/{id}` | 删除场景模板配置 | 路径参数: `id` | 状态码 `204 No Content` |

---

### 5. 被测接口配置 (`/api/endpoint-targets`)

| 请求方式 | 接口端点 | 描述说明 | 核心入参 / 请求体 | 核心响应说明 |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/endpoint-targets` | 获取已注册的被测服务接口列表 | 无 | 返回被测目标列表（含鉴权脱敏） |
| `POST` | `/api/endpoint-targets` | 注册新的被测服务 HTTP 接口 | `name`, `endpoint_url`, `method`, `headers`, `body_template`, `field_mapping` | 返回创建后的目标服务实体 |
| `PUT` | `/api/endpoint-targets/{id}` | 更新被测服务配置 | 路径参数: `id`, 更新体 | 返回更新后的接口靶场实体 |
| `DELETE` | `/api/endpoint-targets/{id}` | 删除被测服务配置 | 路径参数: `id` | 状态码 `204 No Content` |
| `POST` | `/api/endpoint-targets/{id}/test` | 在线联调靶场服务与字段提取规则 | 路径参数: `id`, `mock_input` (测试输入数据) | 返回接口原生回包、提取字段与网络延时 |

---

### 6. 评测执行与调试 (`/api/evaluations`)

| 请求方式 | 接口端点 | 描述说明 | 核心入参 / 请求体 | 核心响应说明 |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/evaluations` | 获取评测任务运行列表 | 支持状态与场景筛选 | 任务状态、总样本数、已完成数与耗时 |
| `POST` | `/api/evaluations` | 创建并立即触发批量评测任务 | `name`, `dataset_id`, `scenario_id`, `llm_config_id`, `endpoint_target_id` (可选) | 冻结场景快照，返回异步任务实体与 Task ID |
| `POST` | `/api/evaluations/debug` | 🌟 单样本原地调试验证 (Debug) | `sample_data`, `scenario_id`, `llm_config_id`, `endpoint_config` | 原地执行打分，返回各项得分、Judge 理由与 Trace |
| `POST` | `/api/evaluations/test-endpoint` | 评测向导内的接口连通与参数提取测试 | 动态 endpoint 配置与待测行数据 | 返回提取出来的 response/contexts 及调用耗时 |
| `GET` | `/api/evaluations/{id}` | 查询评测任务实时运行状态 | 路径参数: `id` | 任务当前进度百分比、状态 (`running`/`completed`) |
| `GET` | `/api/evaluations/{id}/logs` | 查看评测任务后台执行日志流 | 路径参数: `id` | 返回带时间戳的运行日志字符串文本 |
| `POST` | `/api/evaluations/{id}/cancel` | 中止正在运行中的评测任务 | 路径参数: `id` | 状态置为 `cancelled`，返回最终任务实体 |

---

### 7. 评测报告、复核与比对 (`/api/reports`)

| 请求方式 | 接口端点 | 描述说明 | 核心入参 / 请求体 | 核心响应说明 |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/reports` | 获取评测历史报告列表 | Query: 分页与任务状态 | 报告列表、及格率、综合得分摘要 |
| `GET` | `/api/reports/{eval_id}/summary` | 获取单次评测深度统计摘要 | 路径参数: `eval_id` | 综合得分、及格率、各维度指标均分与分布统计 |
| `GET` | `/api/reports/{eval_id}/rows` | 分页拉取单次评测的明细打分行 | Query: `page`, `page_size`, `status` (`pass`/`fail`) | 样本提问、各指标详细得分、通过标记与审校状态 |
| `GET` | `/api/reports/{eval_id}/rows/{row_id}` | 获取单行样本的详细打分报告 | 路径参数: `eval_id`, `row_id` | 样本输入输出、**各项指标具象 Judge 理由**与 Trace |
| `PATCH`| `/api/reports/{eval_id}/rows/{row_id}/review` | 人工介入审校复核单行结果 | `review_status` (`approved`/`flagged`), `human_score`, `review_notes` | 返回复核更新后的样本打分实体 |
| `GET` | `/api/reports/{eval_id}/compare` | 报告多版本基线比对 (Diff) | 路径参数: `eval_id`, Query: `baseline_eval_id` | 指标均分 Delta、及格率对比、退化与提升样本清单 |

---

### 8. 双盲 A/B 人工偏好盲测 (`/api/blind-tests`)

| 请求方式 | 接口端点 | 描述说明 | 核心入参 / 请求体 | 核心响应说明 |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/blind-tests` | 获取人工盲测任务列表 | 支持分页与状态过滤 | 盲测任务列表、参与对比来源及投票完成度 |
| `POST` | `/api/blind-tests` | 创建并触发盲测任务 | `title`, `dataset_id`, `target_a`, `target_b` | 异步调度 Target A 与 B 生成对比响应 |
| `POST` | `/api/blind-tests/test-target` | 盲测前单方目标输出连通测试 | 目标配置 (LLM 或 Endpoint) 及测试输入 | 返回单方目标的回包内容与耗时 |
| `GET` | `/api/blind-tests/{id}` | 查询盲测任务总体进度 | 路径参数: `id` | 总轮次、已投票轮次、状态 |
| `GET` | `/api/blind-tests/{id}/summary` | 查看双盲胜率与偏好统计结果 | 路径参数: `id` | A 胜率、B 胜率、平局率、胜负场次聚合 |
| `GET` | `/api/blind-tests/{id}/rows` | 分页拉取双盲对比条目（已脱敏与随机置乱） | Query: `page`, `page_size`, `status` | 用户提问、随机映射后的输出 A 与输出 B |
| `POST` | `/api/blind-tests/{id}/rows/{row_id}/vote` | 提交测试人员的偏好投票 | `winner` (`target_a`/`target_b`/`tie`/`both_bad`), `comment` | 记录投票结果，更新任务胜率统计 |
| `POST` | `/api/blind-tests/{id}/cancel` | 终止盲测任务 | 路径参数: `id` | 状态更新为 `cancelled` |

---

### 9. RSI 自进化与配置版本管理 (`/api/rsi`)

| 请求方式 | 接口端点 | 描述说明 | 核心入参 / 请求体 | 核心响应说明 |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/rsi/loops` | 获取自进化循环任务列表 | Query: `status`, `scenario_id`, `keyword` | 返回循环概要、当前轮次、最优增益与状态 |
| `POST` | `/api/rsi/loops` | 发起创建新的自进化循环 | `baseline_eval_id`, `objective_metric`, `budget`, `holdout` | 继承基线配置并冻结参考阈值，返回新建 loop |
| `GET` | `/api/rsi/loops/{id}` | 查询单个循环详情与预算使用 | 路径参数: `id` | 详细配置、各轮次简报、最佳迭代与消耗统计 |
| `POST` | `/api/rsi/loops/{id}/start` | 启动后台循环调度执行器 | 路径参数: `id` | 校验单场景独占锁后异步触发后台 Worker |
| `POST` | `/api/rsi/loops/{id}/cancel` | 取消自进化循环任务 | 路径参数: `id` | 同步取消底层候选评测任务并更新状态 |
| `GET` | `/api/rsi/loops/{id}/logs` | 增量拉取自进化实时控制台日志 | Query: `offset` (字符偏移量) | 返回最新日志文本与当前最新 offset |
| `GET` | `/api/rsi/loops/{id}/iterations` | 查询该循环的所有迭代轮次列表 | 路径参数: `id` | 轮次索引、验收判定、目标增益与决策原因 |
| `GET` | `/api/rsi/iterations/{id}` | 获取单轮迭代明细与双评估对比 | 路径参数: `id` | 归因失败簇、结构化提案列表与全量/Holdout Delta |
| `POST` | `/api/rsi/iterations/{id}/approve` | 人工审批采纳本轮提案并写回配置 | `resume` (审批后是否立即自动继续下一轮) | 校验漂移后生成不可变版本快照并写回实体 |
| `POST` | `/api/rsi/iterations/{id}/reject` | 驳回本轮所有提案 | `reason` (驳回说明) | 提案标记 rejected 并累加连续无增益轮次 |
| `POST` | `/api/rsi/loops/{id}/rollback` | 一键回滚场景配置 | `version_id` 或 `iteration_id` | 还原实体至指定快照字段，追加生成新版本 |
| `POST` | `/api/rsi/proposals/{id}/preview` | 单样本沙盒原地调试预览打分 | `row_id` (可选指定数据行，默认首条失败行) | 原地运行调试评测，返回打分、Judge 理由与 Trace |
| `POST` | `/api/rsi/loops/{id}/hard-cases` | 将本轮失败样本沉淀为派生数据集 | `name` (新数据集名，可选) | 自动排除 holdout，创建标记 _rsi_origin 的新数据集 |
| `GET` | `/api/rsi/configs/{scope}/{scope_id}/versions` | 查询指定配置实体的版本变迁历史 | 路径参数: `scope`, `scope_id` | 返回各版本快照、变更 Patch、操作者与时间 |
| `POST` | `/api/rsi/configs/versions/{id}/restore` | 将实体回退至任意历史版本 | 路径参数: `id` | 将指定版本快照写回实体，生成新版本保持血缘 |

---

## 💡 总结与展望

### 1. 架构优势与设计亮点

- **自包含与低摩擦**：开箱即用，无需预先搭建复杂的分布式消息队列或外置向量数据库，纯 Python + SQLite 即可在笔记本上跑通完整评测流水线；平滑扩展支持 PostgreSQL。
- **透明可信的评测逻辑**：拒绝“只有分数、没有依据”的黑盒打分，所有 LLM Judge 指标均强制输出结构化论据，便于工程师快速反思 Prompt、调优 Badcase。
- **版本化快照设计**：通过 `ScenarioSnapshot` 机制，彻底避免因“事后调整指标权重或提示词”导致历史任务报告前后口径不一致的问题，保证评测严谨度。
- **主观与客观双重校准**：既支持自动化的大规模指标打分，又配备了人工介入审校系统与双盲 A/B 投票机制，使模型评测结果真正能够指引业务上线决策。

---

### 2. 演进路线图 (Roadmap)

平台正处于快速迭代中，后续版本规划如下：

```
2026 Q1: v0.2.0                2026 Q2: v0.3.0                2026 Q3: v0.4.0                2026 Q4+: v0.5.0+
┌──────────────────┐           ┌──────────────────┐           ┌──────────────────┐           ┌──────────────────┐
│  容器与 CI/CD    │   ───►    │  存储与高可用    │   ───►    │  安全与企业协同  │   ───►    │  生态与高级智能体 │
├──────────────────┤           ├──────────────────┤           ├──────────────────┤           ├──────────────────┤
│• Docker Compose  │           │• Alembic 数据迁移│           │• RBAC 权限与多租户│          │• Python SDK / CLI│
│• GitHub Actions  │           │• Postgres 高级索引│          │• 登录认证 (OAuth) │          │• 多模态 (图文) 评测│
│• 自动化回归测试  │           │• 异步 Celery/Redis│          │• 审计日志与密文存储│         │• 开源 Benchmark 集│
└──────────────────┘           └──────────────────┘           └──────────────────┘           └──────────────────┘
```

- **v0.2**：补充官方 `Dockerfile` 与 `docker-compose.yml`，一键拉起后端、前端与 PostgreSQL 环境；完善 CI/CD 自动化检测。
- **v0.3**：正式引入 Alembic 进行数据库版本化迁移，针对上万条长评测数据优化查询索引，支持分布式 Worker 调度。
- **v0.4**：引入企业级用户权限体系（RBAC）、团队多租户隔离、审计追踪日志，敏感 API-Key 采用对称密钥信封加密落盘。
- **v0.5+**：发布统一评测客户端 Python SDK 与 CLI 工具，方便直接嵌入 CI 流程中执行上线前门禁卡点；扩展支持多模态（Vision LLM）多轮评测。

---

## 🤝 贡献与交流

欢迎任何形式的贡献与交流，无论是提出新的评测指标想法、提交 Bug 报告、优化前端组件，还是补充更多场景模板！

- **提交 Issue**：在 GitHub 仓库提出功能建议或缺陷反馈。
- **提交 PR**：请遵循规范的分支开发流程，确保前后端静态检查与测试通过。
- **技术规范**：开发指南请详见 [AGENTS.md](AGENTS.md) 与 [CONTRIBUTING.md](CONTRIBUTING.md)。
- **安全报告**：若发现潜在安全隐患，请参阅 [SECURITY.md](SECURITY.md) 进行负责任的漏洞披露。

---

## 📄 开源许可证

本项目基于 [Apache License 2.0](LICENSE) 协议开源。可免费用于个人学习、学术研究与企业商业项目。
