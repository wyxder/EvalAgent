# AI 评测平台操作手册

> 本手册以实际操作为导向，按照"启动 → 验证 → 评测"的顺序编写，可直接对照操作。

---

## 与 Ragas / DeepEval 的关系

本项目当前不依赖 Ragas 或 DeepEval：后端依赖中没有安装它们，代码里也没有 import 或调用它们的服务。平台只是参考并对齐业界通用评测概念，例如 Ragas 常见的 RAG 指标、DeepEval 的 Agentic / RAG / Multi-Turn 指标分类。

实际评分由平台原生实现：LLM 类指标通过你配置的 OpenAI-compatible 评判模型和本项目自己的 Judge Prompt 输出分数与理由；HitRate@K、MRR、工具正确性、参数正确性、步骤效率等确定性指标由后端代码直接计算。

---

## 零、启动与验证

### 0.1 启动后端

```bash
cd ai-eval-platform/backend
source venv/bin/activate
python3 run.py
```

**验证后端**：打开 http://localhost:8000/docs ，看到 Swagger API 文档页面。

### 0.2 启动前端

```bash
cd ai-eval-platform/frontend
npm run dev
```

**验证前端**：打开 http://localhost:5175 ，看到左侧有 6 个导航菜单的评测平台界面。

### 0.3 验证预置数据

按顺序点击以下页面确认预置数据正常加载：

| 页面 | 应该看到 |
|------|---------|
| LLM 配置 | 一条 "Qwen Plus (通义千问)" 配置 |
| 数据管理 | 3 个示例数据集（见下表） |
| 场景管理 | 3 个预置模板卡片（RAG / Agent / 多轮对话） |
| 人工盲测 | 可创建人工盲测任务的工作台 |
| 评测报告 | 一条已完成的 "RAG 示例评测" |

**3 个示例数据集**：

| 数据集 | 类型 | 条数 | 覆盖字段 | 对应场景 |
|--------|------|------|---------|---------|
| RAG 示例数据集 | single_turn | 5 | user_input, response, retrieved_contexts(text_list), reference, retrieved_context_ids, reference_context_ids | RAG 评测模板 |
| Agent 工具调用示例数据集 | multi_turn | 3 | user_input(conversation), reference, reference_tool_calls(tool_call_list), reference_topics, reference_role, retrieved_contexts | Agent 评测模板 |
| 多轮对话示例数据集 | multi_turn | 3+ | user_input(conversation), reference, reference_topics, reference_role, retrieved_contexts | 多轮对话评测模板 |

点进每个数据集的详情页查看数据内容，可以直观理解每种字段类型的实际数据格式。

### 0.4 测试 LLM 连通性

1. 进入「LLM 配置」页面
2. 找到 "Qwen Plus (通义千问)" 这行
3. 点击「测试连接」按钮
4. 等待 2-5 秒，应该看到绿色提示 "连接测试成功 (xxxms)"

也可以直接点击「新增 LLM」或「编辑」弹窗里的 **测试当前配置** 按钮。这个按钮会使用当前表单里的草稿配置直接发请求，不需要先保存，适合在录入新的 Base URL / API Key / 模型名时先确认能否打通。

**如果失败**：编辑 `backend/.env`，检查 `LLM_API_KEY` 是否正确，重启后端。

---

## 一、人工盲测（A/B 主观对比）

人工盲测适合回答这类问题：

- 两个模型谁回答更好？
- 新版 chat 接口和老版本相比，体感是否真的提升？
- 自动评分差不多时，人看起来到底哪个更可靠？

### 1.1 它和普通离线评测的关系

推荐把人工盲测当成自动评测的补充，而不是替代：

1. 先用普通离线评测筛出关键数据集、失败样本和高风险样本
2. 再用人工盲测比较两个应答端
3. 最后结合自动分数、人工胜率和人工复核意见做上线判断

也就是说：

- **自动评测** 更擅长规模化、稳定复跑、看趋势
- **人工盲测** 更擅长比较主观体感、业务可接受度和回答质量细节

### 1.2 盲测支持什么对象

当前人工盲测统一比较的是“应答端”，不是只比较模型。

支持：

- `LLM 配置 vs LLM 配置`
- `Chat 接口 vs Chat 接口`
- `LLM 配置 vs Chat 接口`

因此它既能做模型对比，也能做新旧 chat 接口的 A/B 测试。

### 1.3 创建人工盲测任务

1. 点击左侧「人工盲测」
2. 点击「创建盲测任务」
3. 选择：
   - 数据集
   - 对比对象 A
   - 对比对象 B
4. 可选填写抽样条数
5. 点击创建

**要求**：

- 数据集必须包含 `user_input`
- 单轮和多轮都可以，只要 `user_input` 能作为问题/对话输入给应答端

### 1.4 Chat 接口盲测的默认配置

如果对比对象选择 `Chat 接口`，表单会默认预填和 RAG 数据集生成器一致的接口参数：

- URL：`https://example.com/chat/completions`
- 返回方式：`SSE`
- 请求体模板：

```json
{
  "question": "{{question}}",
  "kb_codes": [],
  "payload": {
    "files": []
  }
}
```

- 附加 Headers：

```json
{
  "origin": "https://example.com",
  "X-App-Id": "xxx",
  "referer": "https://example.com/"
}
```

Authorization 会预填当前默认值，但仍可手动修改。

### 1.5 创建前先测接口

人工盲测的 Chat 接口卡片里自带 **接口连通性测试** 区块：

1. 填好接口地址、Authorization、附加 Headers、请求体模板
2. 输入一条测试问题
3. 点击 **测试接口**

成功后会弹出回答预览。建议在创建盲测任务前先测一次，避免任务创建后才发现接口打不通。

### 1.6 盲测执行与并发

盲测任务创建后会后台生成 A/B 两边的回答。

当前默认行为：

- 样本级并发：`3`
- 每条样本的 A / B 会同时请求

因此峰值会同时发出多条请求，不是串行一个一个等。

### 1.7 如何做人工判断

进入任务详情后，每条样本可以投：

- `左侧更好`
- `右侧更好`
- `都好`
- `都不好`

评判弹窗里的按钮已做成居中且间距更大，降低误点风险。

### 1.8 去盲结果是什么意思

盲测时你看到的是 **左侧 / 右侧**，但每条样本的左右展示顺序会随机交换。

所以：

- `左侧更好` / `右侧更好` 只是当时的展示位置
- `A 胜` / `B 胜` 才是去盲后还原出来的真实归属

现在页面里已经补了两层解释：

1. 汇总区会说明：`A/B 胜出是去盲后的真实结果`
2. 逐条明细会直接显示：`本条左侧=A，右侧=B` 或 `本条左侧=B，右侧=A`

这样你不用自己再心算左右和 A/B 的关系。

### 1.9 盲测结果怎么看

盲测任务详情会展示：

- 总样本数
- A 胜
- B 胜
- 都好
- 都不好
- 待投票

逐条明细里会展示：

- 问题
- 回答是否已生成
- 人工判断
- 去盲结果

这套结果最适合用于：

- 新旧版本接口对比
- 多模型主观对比
- 在自动评分接近时做最终决策

---

## 二、使用预置数据快速体验评测

最快了解平台的方式：用预置的示例数据跑一次完整评测。

### 步骤 1：创建评测任务

1. 点击左侧「评测执行」
2. 在顶部表单中填写：
   - **任务名称**：`我的第一次评测`
   - **选择数据集**：下拉选 `RAG 示例数据集`
   - **选择场景**：下拉选 `RAG 评测模板`
   - **选择 LLM**：下拉选 `Qwen Plus (通义千问)`
3. 点击「开始评测」

### 步骤 2：等待执行

- 页面下方的任务列表会出现你的任务
- 状态从 `pending` → `running`（显示进度条）→ `completed`
- 5 条数据大约需要 30 秒 ~ 2 分钟（取决于 LLM 响应速度）
- 页面每 3 秒自动刷新进度

### 步骤 3：查看报告

评测完成后：
1. 在任务列表中点击「查看报告」
2. 或点击左侧「评测报告」，选择刚完成的评测

**报告总览 Tab**：
- 4 个统计卡片：通过率、总条数、通过数、不通过数
- 各指标得分表：Faithfulness / Context Recall / Context Precision / Answer Relevancy / Factual Correctness / Answer Completeness 的均值、最小、最大、通过率
- 基本信息：任务名称、数据集、场景、LLM

**逐条明细 Tab**：
- 每行数据的各指标得分和通过/失败状态
- 点击行展开抽屉，查看：
  - 原始数据（user_input、response、reference 等）
  - 每个指标的具体分数和评分理由

---

## 三、创建自己的 RAG 评测

### 2.1 准备数据文件

创建一个 CSV 文件 `my_rag_test.csv`：

```csv
user_input,response,retrieved_contexts,reference,retrieved_context_ids,reference_context_ids
什么是机器学习？,机器学习是让计算机从数据中自动学习的技术,"[""机器学习是AI的子领域"", ""通过算法从数据中学习模式""]",机器学习是人工智能的分支使计算机能从数据中学习,"[""ml-doc-001"", ""ml-doc-002""]","[""ml-doc-001""]"
什么是深度学习？,深度学习使用多层神经网络处理复杂数据,"[""深度学习基于多层神经网络"", ""属于机器学习的子集""]",深度学习是机器学习的子集通过多层神经网络提取特征,"[""dl-doc-001"", ""ml-doc-003""]","[""dl-doc-001""]"
```

**字段说明**：
- `user_input`：用户问题
- `response`：**你的系统生成的回答**（评测对象）
- `retrieved_contexts`：检索到的上下文（JSON 数组格式）
- `reference`：标准参考答案
- `retrieved_context_ids`：检索到的文档/分片 ID，顺序与 `retrieved_contexts` 一致，用于 HitRate@K、MRR 等检索单测指标
- `reference_context_ids`：人工标注的标准文档/分片 ID，用于判断检索是否命中正确资料

> CSV 中的 `retrieved_contexts`、`retrieved_context_ids`、`reference_context_ids` 字段需要用 JSON 数组格式：`"[""文本1"", ""文本2""]"`。
> 如果暂时没有文档 ID，也可以先不填 ID 字段；默认 RAG 问答模板不会强制启用 ID 指标。

### 2.2 创建数据集并导入

1. 点击「数据管理」→「新建数据集」
2. 填写：
   - 名称：`我的 RAG 测试集`
   - 样本类型：选 `single_turn`
   - 字段自动预填（user_input、response、retrieved_contexts、reference），直接确认
3. 点击进入数据集详情页
4. 点击「导入数据」→ 上传 `my_rag_test.csv` → 确认
5. 确认导入后看到数据行出现在表格中

### 2.3 执行评测

1. 点击「评测执行」
2. 选择数据集：`我的 RAG 测试集`
3. 选择场景：`RAG 评测模板`
4. 选择 LLM：`Qwen Plus (通义千问)`
5. 点击「开始评测」

### 2.4 查看结果

评测完成后查看报告，重点关注：
- **Faithfulness 低分的行**：说明回答中有不在检索上下文中的信息（幻觉）
- **Context Recall 低分的行**：说明检索的内容没有覆盖参考答案的要点
- **Context Precision 低分的行**：说明检索结果混入了较多无关内容
- **Contextual Relevancy 低分的行**：说明检索上下文整体和用户问题不够相关，适合在启用扩展检索质量指标时查看
- **Answer Relevancy 低分的行**：说明回答没有紧扣用户问题
- **Answer Completeness 低分的行**：说明回答事实可能没错，但遗漏了参考答案中的关键要点
- **reason 字段**：LLM 给出的评分依据，帮你定位具体问题

---

## 四、创建 Agent 评测

Agent 评测评估任务完成度、工具正确性、参数正确性、步骤效率和目标准确度。它和“多轮对话评测”的区别是：Agent 场景关注行动链路是否正确，包括是否调用了正确工具、参数是否正确、工具返回后是否完成用户目标；多轮对话场景关注对话体验是否稳定，包括是否跑题、是否记住上下文、是否遵守角色边界。

| 场景 | 关注点 | 典型字段 | 典型指标 |
|------|--------|----------|----------|
| Agent 评测 | 工具调用和任务闭环 | `reference_tool_calls`, `reference` | Task Completion, Tool Correctness, Argument Correctness, Step Efficiency, Goal Accuracy |
| 多轮对话评测 | 话题范围、上下文记忆和角色一致性 | `reference_topics`, `reference`, `reference_role`, 可选 `retrieved_contexts` | Topic Adherence, Turn Relevancy, Conversation Completeness, Knowledge Retention, Role Adherence |

如果一个样本既是多轮，又包含工具调用和明确任务目标，优先按 Agent 评测处理；如果只是普通 human/ai 多轮聊天，没有工具执行链，就按多轮对话评测处理。

### 3.1 准备数据文件

创建 `my_agent_test.json`：

```json
[
  {
    "user_input": [
      {"type": "human", "content": "帮我查一下订单 ORD-001 的状态"},
      {"type": "ai", "content": "", "tool_calls": [{"name": "query_order", "args": {"order_id": "ORD-001"}}]},
      {"type": "tool", "content": "{\"status\": \"shipped\", \"tracking\": \"SF001\"}"},
      {"type": "ai", "content": "您的订单 ORD-001 已发货，快递单号 SF001。"}
    ],
    "reference": "成功查询到订单状态并告知用户",
    "reference_tool_calls": [
      {"name": "query_order", "args": {"order_id": "ORD-001"}}
    ],
    "reference_role": "客服 Agent：只能基于工具返回结果答复订单状态，不编造物流信息。",
    "retrieved_contexts": ["订单查询工具返回订单状态和快递单号后，Agent 应把状态和快递单号告知用户。"]
  },
  {
    "user_input": [
      {"type": "human", "content": "帮我取消订单 ORD-002"},
      {"type": "ai", "content": "好的，我帮您取消订单。", "tool_calls": [{"name": "cancel_order", "args": {"order_id": "ORD-002"}}]},
      {"type": "tool", "content": "{\"success\": true}"},
      {"type": "ai", "content": "订单 ORD-002 已成功取消。"}
    ],
    "reference": "成功取消指定订单",
    "reference_tool_calls": [
      {"name": "cancel_order", "args": {"order_id": "ORD-002"}}
    ],
    "reference_role": "客服 Agent：按工具返回结果确认取消状态，不越权承诺退款到账时间。",
    "retrieved_contexts": ["取消订单工具返回 success=true 后，Agent 才能告知订单已取消。"]
  }
]
```

**关键格式**：
- `user_input`：消息数组，type 为 `human` / `ai` / `tool`
- `ai` 消息的 `tool_calls`：Agent 实际调用的工具
- `reference_tool_calls`：期望 Agent 应该调用的工具
- `reference_role`：可选，Agent 应遵守的角色和职责边界
- `retrieved_contexts`：可选，任务相关的业务/工具背景资料，用于多轮可信度类指标

### 3.2 创建数据集

1. 「数据管理」→「新建数据集」
2. 名称：`Agent 工具调用测试集`
3. 样本类型：`multi_turn`
4. 确认预填字段（user_input、reference、reference_tool_calls）
5. 进入详情页 → 「导入数据」→ 上传 JSON 文件

### 3.3 执行评测

- 场景选 `Agent 评测模板`（含 Task Completion + Tool Correctness + Argument Correctness + Step Efficiency + Goal Accuracy）
- 执行后查看报告
- **Task Completion**：平台原生 Judge 判断 Agent 是否完成任务闭环
- **Tool Correctness**：后端确定性比较实际工具调用和期望工具调用，工具名和参数都匹配才算命中
- **Argument Correctness**：后端确定性比较同名工具的参数匹配度
- **Step Efficiency**：后端确定性比较实际工具步骤数和期望步骤数，识别多调、漏调、重复调用
- **Goal Accuracy**：平台原生 Judge 判断最终结果是否准确达成 `reference` 描述的目标

### 3.4 创建多轮对话评测

多轮对话评测不要求工具调用，重点看对话是否围绕业务话题、是否满足用户需求、是否记住上下文、是否遵守角色边界。

核心字段：

- `user_input`：human/ai 交替的完整对话
- `reference_topics`：允许讨论的话题范围，例如 `["订单查询", "退货退款", "物流追踪"]`
- `reference`：用于描述期望对话结果，Conversation Completeness 指标需要
- `reference_role`：AI 应遵守的角色、职责边界和语气要求，Role Adherence 指标需要
- `retrieved_contexts`：可选，多轮回复可依据的业务资料，Turn Faithfulness 指标需要

执行时选择 `多轮对话评测模板`：

- **Topic Adherence**：平台原生 Judge 判断对话是否围绕 `reference_topics`
- **Turn Relevancy**：平台原生 Judge 逐轮判断 AI 回复是否回应当前用户问题
- **Conversation Completeness**：平台原生 Judge 判断整段对话是否完成 `reference` 描述的用户需求
- **Knowledge Retention**：平台原生 Judge 判断 AI 是否记住前面已给出的事实、偏好、订单号、时间等信息
- **Role Adherence**：平台原生 Judge 判断 AI 是否遵守 `reference_role`
- **Turn Faithfulness**：可选扩展，平台原生 Judge 判断多轮回复是否基于 `retrieved_contexts` 或给定资料

---

## 五、创建自定义指标

### 4.1 通过 API 创建（推荐）

创建一个"礼貌性"评测指标：

```bash
curl -X POST http://localhost:8000/api/metrics \
  -H "Content-Type: application/json" \
  -d '{
    "name": "politeness",
    "display_name": "礼貌性",
    "metric_type": "aspect_critic",
    "config": {
      "definition": "Does the response maintain a polite and respectful tone? Return 1 if polite, 0 if not."
    },
    "category": "custom"
  }'
```

创建后在「场景管理」的「新建场景」中即可选择这个指标。

### 4.2 指标类型说明

| 类型 | metric_type | 说明 | 输出 |
|------|------------|------|------|
| 维度评判 | `aspect_critic` | LLM 按自定义标准做二值判断 | 0 或 1 |
| 离散评分 | `discrete` | LLM 从预定义选项中选择 | "pass"/"fail" 等 |
| 数值评分 | `numeric` | LLM 给出数值评分 | 0.0 ~ 1.0 |

### 4.3 内置指标一览

| 指标 | 适用场景 | 需要的数据字段 |
|------|---------|---------------|
| Faithfulness | RAG | user_input, response, retrieved_contexts |
| Context Recall | RAG | user_input, retrieved_contexts, reference |
| Context Precision | RAG | user_input, retrieved_contexts, reference |
| Contextual Relevancy | RAG 扩展 | user_input, retrieved_contexts |
| Factual Correctness | RAG | response, reference |
| Answer Relevancy | RAG | user_input, response |
| Answer Completeness | RAG | user_input, response, reference |
| HitRate@K (Hit Rate at K) | RAG 检索单测 | retrieved_context_ids, reference_context_ids |
| MRR (Mean Reciprocal Rank) | RAG 检索单测 | retrieved_context_ids, reference_context_ids |
| Task Completion | Agent | user_input (conversation), reference |
| Tool Correctness | Agent | user_input (conversation), reference_tool_calls |
| Argument Correctness | Agent | user_input (conversation), reference_tool_calls |
| Step Efficiency | Agent | user_input (conversation), reference_tool_calls |
| Goal Accuracy | Agent | user_input (conversation), reference |
| Topic Adherence | 多轮对话 | user_input (conversation), reference_topics |
| Turn Relevancy | 多轮对话 | user_input (conversation) |
| Conversation Completeness | 多轮对话 | user_input (conversation), reference |
| Knowledge Retention | 多轮对话 | user_input (conversation) |
| Role Adherence | 多轮对话 | user_input (conversation), reference_role |
| Turn Faithfulness | 多轮对话扩展 | user_input (conversation), retrieved_contexts |
| Harmfulness | 通用 | response |
| Coherence | 通用 | response |

---

## 六、LLM 配置管理

### 5.1 添加新的 LLM

1. 「LLM 配置」→「新增 LLM」
2. 填写字段：

| 字段 | 示例值 | 说明 |
|------|--------|------|
| 名称 | `GPT-4o` | 显示名称（需唯一） |
| API 地址 | `https://api.openai.com/v1` | OpenAI 兼容端点 |
| API Key | `sk-xxx` | 认证密钥 |
| 模型名称 | `gpt-4o` | 模型 ID |
| 温度 | `0.01` | 评测建议低值 |
| 最大 Token | `1024` | 单次回复上限 |

3. 保存后点击「测试连接」确认可用

### 5.2 支持的 LLM 端点

任何 OpenAI 兼容的 API 端点都可以使用：

| 服务商 | API 端点 |
|--------|---------|
| OpenAI | `https://api.openai.com/v1` |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| DeepSeek | `https://api.deepseek.com/v1` |
| Ollama 本地 | `http://localhost:11434/v1` |
| OpenRouter | `https://openrouter.ai/api/v1` |

---

## 七、评测报告解读

### 6.1 指标分数含义

| 分数范围 | 含义 |
|----------|------|
| 0.9 ~ 1.0 | 优秀 |
| 0.7 ~ 0.9 | 良好 |
| 0.5 ~ 0.7 | 有改进空间 |
| < 0.5 | 需要重点关注 |

### 6.2 逐条明细的 reason 字段

这是 LLM 对该条数据给出的评分依据。例如：

> Faithfulness = 0.67，reason: "回答中'多线程无法真正利用多核CPU'的表述在上下文中仅有间接支持"

这告诉你具体哪个陈述有问题，可以针对性地改进检索策略或 prompt。

### 6.3 按状态筛选

在报告明细 Tab 的下拉筛选中选择：
- **全部**：查看所有行
- **通过**：只看通过的行
- **不通过**：重点分析失败原因
- **错误**：查看评测过程中出错的行

---

## 八、RSI 自进化闭环

RSI（Recursive Self-Improvement）把「评测 → 归因 → 提案 → 影子回归 → 审批 → 写回 → 回滚」串成一个可审计的闭环：系统只提出白名单内的配置补丁（场景指标 Prompt、通过阈值、指标定义等），每轮先在影子任务中回归验证，再由人决定是否写回。入口在左侧菜单「RSI 自进化」，或直接访问 `/api/rsi/*`。

> 设计细节与字段级约定见 [`docs/RSIX.md`](../RSIX.md)。

### 8.1 前置条件

1. 已有一条**已完成**的评测任务作为基线（`baseline_eval_id`），且该任务带有 `scenario_snapshot`。
2. 至少一个可用 LLM 配置（默认沿用基线任务的 Judge 配置）；提案模型可单独指定，不指定则与 Judge 相同。
3. `backend/.env` 中 `RSI_ENABLED=true`；设为 `false` 时所有 `/api/rsi/*` 返回 403，前端入口也会隐藏。

### 8.2 创建循环

在「RSI 自进化」页点击「新建循环」，选择基线评测任务并填写：

| 字段 | 说明 |
|------|------|
| `name` | 循环名称 |
| `baseline_eval_id` | 基线评测任务，决定数据集、场景与冻结的指标快照 |
| `objective_metric` / `objective_mode` | 目标指标与口径：`reference_pass_rate`（按冻结阈值算通过率）或 `metric_mean`（该指标平均分） |
| `objective_target` | 可选，目标值，仅用于展示 |
| `budget` | 迭代数、LLM 调用数、分钟数、每轮提案数、最大行数、连续无增益次数上限 |
| `acceptance_policy` | 目标增益、受保护指标、最大降幅、holdout 比例、人工审批要求 |
| `auto_apply_low_risk` | 默认 `false`；即使打开，也只对低风险且满足自动采纳门槛的补丁生效 |

同一场景同时只允许一个 `running` / `awaiting_review` 的循环，冲突返回 409。

### 8.3 一轮循环做了什么

1. **基线取数**：按冻结阈值统计基线通过率与指标均值，并用稳定哈希切出 train / holdout。
2. **失败归因**：只读 train 行，按指标与根因分簇；LLM 不可用时降级为规则归因（`fallback=true`）。
3. **提案生成**：提案模型输出补丁列表，必须带证据与理由，最多 `max_proposals_per_iteration` 条。
4. **校验**：白名单、目标存在性、`before_value` 漂移、长度/敏感串、同值、跨轮去重依次校验，不通过直接标记 `rejected`。
5. **影子回归**：把候选快照写入新的 `EvalTask`（`result_save_mode=task_only`）并复用 `run_evaluation` 执行，不改动原场景、不改动评分逻辑。
6. **验收判定**：用**创建循环时冻结的阈值**计算 train/holdout 增益，检查受保护指标降幅、错误率与新增失败数，给出 `accepted / rejected / inconclusive` 建议。
7. **写回或待审**：命中自动采纳条件才直接写回；否则循环进入 `awaiting_review`，等待人工审批。

循环状态：`pending` → `running` → `awaiting_review` → `running` → `completed`，异常为 `failed`；达到预算上限会以 `failed` 停止并写入 `error_message`。

### 8.4 审批、拒绝与回滚

- **审批**：在详情页逐条查看补丁 Diff（`before_value` → `value`）、归因证据与回归指标，确认后点击「通过」。写回前会再执行一次 `before_value` 漂移校验，配置已被他人改动时返回 422 并保留现场。
- **拒绝**：填写原因后提案全部标记 `rejected`，本轮计入连续无增益，可选择是否继续下一轮。
- **回滚**：详情页「回滚」支持按版本或按迭代回滚；回滚是**追加一条新版本**恢复旧值，不会删除历史。
- **版本**：`GET /api/rsi/loops/{id}/versions` 查看循环相关版本，`/api/rsi/configs/{scope}/{scope_id}/versions` 查看某个实体的全部版本，`POST /api/rsi/configs/versions/{id}/restore` 恢复任意版本。

### 8.5 安全与脱敏约定

- 只接受白名单字段：`scenario_metric.prompt_override / pass_threshold`、`metric_definition.config.*`、`endpoint_target.request_body_template`、`scenario.description`；`weight` 暂不允许修改。
- 所有写回先落 `rsi_config_versions` 快照，再写实体；补丁值禁止包含 `authorization`、`api_key`、`sk-`、`Bearer` 等敏感串。
- 接口响应中的 endpoint 配置经 `redact_sensitive_mapping` 脱敏（`authorization` 置空并返回 `authorization_masked`）。
- 验收、行迁移与约束全部使用冻结的 `reference_thresholds`，候选自身改阈值不会污染判定；归因与提案只读 train，holdout 只在判定阶段使用。

### 8.6 沙盒预览与 hard-case 数据集

- **沙盒预览**：`POST /api/rsi/proposals/{id}/preview` 用候选快照对单条数据跑一次调试评测（复用 `/api/evaluations/debug` 的抽取逻辑），用于人工判断提案是否值得回归。
- **hard-case 数据集**：`POST /api/rsi/loops/{id}/hard-cases` 把最近一轮的失败行派生为**只追加**的新数据集，行内写入 `_rsi_origin` 溯源信息，并自动排除 holdout 行。

### 8.7 主要接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/api/rsi/loops` | 列表 / 创建循环 |
| GET | `/api/rsi/loops/{id}` | 循环详情（含预算用量、holdout 配置） |
| POST | `/api/rsi/loops/{id}/start` | 启动（后台线程执行） |
| POST | `/api/rsi/loops/{id}/cancel` | 取消并终止候选任务 |
| GET | `/api/rsi/loops/{id}/logs?offset=` | 增量日志 |
| GET | `/api/rsi/loops/{id}/iterations` | 迭代列表 |
| GET | `/api/rsi/iterations/{id}` | 迭代详情（指标、判定、提案） |
| POST | `/api/rsi/iterations/{id}/approve` | 审批写回 |
| POST | `/api/rsi/iterations/{id}/reject` | 拒绝本轮 |
| POST | `/api/rsi/loops/{id}/rollback` | 按版本 / 迭代回滚 |
| GET | `/api/rsi/loops/{id}/compare` | 基线与候选指标对比 |
| POST | `/api/rsi/loops/{id}/hard-cases` | 派生 hard-case 数据集 |
| POST | `/api/rsi/proposals/{id}/preview` | 单行沙盒预览 |

### 8.8 当前限制

- 影子回归目前按数据集全量执行，`max_rows_per_iteration` 只用于预算估算与归因样本裁剪。
- 自动采纳要求低风险补丁、holdout 样本量达到 `min_rows_for_auto_accept` 且增益达 `min_gain`；默认仍走人工审批。
- `weight` 不在白名单内（现有引擎的汇总不使用权重，改它不会产生可验证收益）。

---

## 九、常见问题

### Q: 评测一直在 running 状态不结束？

检查后端日志（终端输出），可能原因：
- LLM API 响应慢或超时 → 检查网络和 API Key
- 数据格式有误 → 检查数据集字段是否匹配场景要求

### Q: 报告中所有指标都是 None？

说明评测引擎在调用指标时出错。检查：
- 数据集字段名是否正确（如 `retrieved_contexts` 而非 `contexts`）
- LLM 配置是否有效（先测试连通性）

### Q: CSV 导入后 retrieved_contexts 字段显示为字符串？

CSV 中的 JSON 数组需要双引号转义：`"[""文本1"", ""文本2""]"`。推荐使用 JSON 格式导入复杂数据。

### Q: 如何更换 API Key？

1. 编辑 `backend/.env` 中的 `LLM_API_KEY`
2. 重启后端
3. 或者在界面的「LLM 配置」中编辑，填入新的 API Key 保存

### Q: RSI 页面提示 403 或菜单不显示？

后端 `RSI_ENABLED` 为 `false`。改为 `true` 后重启后端；前端通过 `GET /api/rsi/loops` 探测开关状态。

### Q: RSI 创建循环提示 409？

同一场景已有 `running` 或 `awaiting_review` 的循环。先审批/拒绝上一轮，或取消旧循环再创建。
