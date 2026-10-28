import React, { useState } from 'react';
import {
  Button,
  Carousel,
  Collapse,
  Drawer,
  Space,
  Tag,
  Typography,
} from 'antd';
import {
  ExperimentOutlined,
  ThunderboltOutlined,
  CheckCircleFilled,
  CloseCircleFilled,
  RobotOutlined,
  ApiOutlined,
  BarChartOutlined,
  DatabaseOutlined,
  SwapOutlined,
  SafetyCertificateOutlined,
  SlidersOutlined,
  TeamOutlined,
  StarFilled,
  RightOutlined,
  MenuOutlined,
  RocketOutlined,
  SyncOutlined,
  CodeOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import LandingRadarChart from '../components/landing/LandingRadarChart';
import '../styles/landing.css';

const { Title, Paragraph, Text } = Typography;

// Marquee items
const MARQUEE_ITEMS = [
  { icon: <RobotOutlined />, label: '通义千问 Qwen Plus' },
  { icon: <ThunderboltOutlined />, label: 'DeepSeek V3 / R1' },
  { icon: <ApiOutlined />, label: 'OpenAI GPT-4o' },
  { icon: <ExperimentOutlined />, label: 'Claude 3.5 Sonnet' },
  { icon: <CheckCircleFilled />, label: 'HitRate@K 零成本数学探针' },
  { icon: <SyncOutlined />, label: 'RSI 递归配置自进化闭环' },
  { icon: <DatabaseOutlined />, label: 'RAG 知识库无监督文档合成' },
  { icon: <SwapOutlined />, label: '双盲 A/B 人工偏好盲测' },
  { icon: <SafetyCertificateOutlined />, label: '场景快照冻结 · 零漂移保证' },
  { icon: <CodeOutlined />, label: 'vLLM / Ollama 私有化大模型接入' },
];

// Carousel showcases
const CAROUSEL_SLIDES = [
  {
    tag: 'RAG 检索增强评估',
    title: '从文档智能切片到生成忠实度全链路归因',
    desc: '覆盖 Context Recall / Precision / Relevancy 检索质量，与 Faithfulness / Answer Relevancy 生成质量。强制要求 Judge 模型输出具象评判依据（Reason），让每一分都掷地有据。',
    visualTitle: 'RAG 评测工作流看板',
    metrics: [
      { label: '忠实度 (Faithfulness)', val: '98.5%' },
      { label: '检索召回率 (Context Recall)', val: '96.2%' },
      { label: 'HitRate@5 命中率', val: '100%' },
    ],
  },
  {
    tag: 'AI Agent 工具链质检',
    title: '复杂任务目标完成度与工具调用死循环排查',
    desc: '深度解析 Agent 决策轨迹：评估 Tool 选取合理性、参数键值与动态变量准确性，同时计算步骤执行效率（Step Efficiency），自动报警工具死循环与参数幻觉。',
    visualTitle: 'Agent 执行链路与 Trace',
    metrics: [
      { label: '工具选取准确率', val: '97.8%' },
      { label: '参数键值匹配度', val: '99.1%' },
      { label: '步骤执行效率', val: '92.4%' },
    ],
  },
  {
    tag: 'RSI 评测驱动自进化',
    title: '业内首创「评估-归因-提案-回归-写回-回滚」闭环',
    desc: '以真实评测为基线，自动提取失败簇生成白名单 Patch。影子任务全自动验证，结合冻结参考阈值与 Holdout 样本严密隔离，经审批一键写回，支持秒级版本回滚。',
    visualTitle: '自进化循环状态机',
    metrics: [
      { label: '目标指标均值提升', val: '+12.6%' },
      { label: '影子回归耗时', val: '< 30s' },
      { label: '版本回滚一致性', val: '100%' },
    ],
  },
  {
    tag: '双盲 A/B 偏好测试',
    title: '随机混淆防偏置，让人工体感决策科学化',
    desc: '支持 LLM vs LLM、接口 vs 接口等多模式。自动抹除模型代号标签与乱序置乱，审校人员盲测投票，实时产出胜率分布（Win Rate）与 ELO 偏好雷达。',
    visualTitle: '双盲投票室与胜率大盘',
    metrics: [
      { label: '新版模型胜率', val: '64.2%' },
      { label: '平局率 (Tie)', val: '22.0%' },
      { label: '评估样本量', val: '120 条' },
    ],
  },
];

// Target Personas
const PERSONAS = [
  {
    avatar: '👨‍💻',
    title: '大模型应用研发工程师',
    tag: '快速联调 · 接口排障',
    pain: '痛点：被测接口黑盒调用，日志杂乱难排查，改了 Prompt 不知全局影响。',
    solution: '价值：RESTful 接口动态插值探针，实时抓取 HTTP 耗时与 Trace，单样本原地 Debug 秒级定位。',
  },
  {
    avatar: '🔬',
    title: 'RAG / 知识库算法专家',
    tag: '文档合成 · 召回率诊断',
    pain: '痛点：缺乏人工标注的真值（Ground Truth），优化检索参数全靠感觉盲猜。',
    solution: '价值：非结构化文档一键自动清洗切片并衍生高质 QA 问答集，HitRate@K 与纯度无消耗秒算。',
  },
  {
    avatar: '🤖',
    title: 'AI Agent 架构师',
    tag: '工具链质检 · 步骤防死循环',
    pain: '痛点：多步工具调用链路长，参数频繁报错，缺乏针对工具与参数的客观量化指标。',
    solution: '价值：原生支持 Tool Correctness 与 Argument Correctness，自动统计步数冗余度与参数幻觉。',
  },
  {
    avatar: '📊',
    title: '企业 AI 质检与产品负责人',
    tag: '质量门禁 · 科学决策',
    pain: '痛点：第三方评测库只给分数没有依据，无法向业务方解释，版本迭代容易出现退化。',
    solution: '价值：逐行强制输出具象 Judge 理由、多版本基线 Diff 对比，并提供双盲 A/B 人工偏好盲测门禁。',
  },
];

// Competitive Matrix
const MATRIX_ROWS = [
  { feature: '原生企业级 Web 可视化控制台', evalAgent: true, ragas: false, trulens: false, deepeval: false, promptfoo: true },
  { feature: '评测驱动的配置自进化闭环 (RSI)', evalAgent: true, ragas: false, trulens: false, deepeval: false, promptfoo: false },
  { feature: '在线 HTTP 接口探针与 Trace 抽取', evalAgent: true, ragas: false, trulens: true, deepeval: false, promptfoo: true },
  { feature: '场景快照冻结机制 (历史对比不失真)', evalAgent: true, ragas: false, trulens: false, deepeval: false, promptfoo: false },
  { feature: '强制输出样本级具象 Judge 理由 (Reason)', evalAgent: true, ragas: true, trulens: true, deepeval: true, promptfoo: false },
  { feature: 'RAG 知识库文档智能解析与合成数据流水线', evalAgent: true, ragas: true, trulens: false, deepeval: false, promptfoo: false },
  { feature: '双盲 A/B 人工偏好盲测室 (防主观偏置)', evalAgent: true, ragas: false, trulens: false, deepeval: false, promptfoo: false },
  { feature: '版本不可变快照与一键回滚 (Rollback)', evalAgent: true, ragas: false, trulens: false, deepeval: false, promptfoo: false },
  { feature: '纯自托管与私有化部署支持 (零数据外泄)', evalAgent: true, ragas: true, trulens: true, deepeval: true, promptfoo: true },
];

// Reviews
const REVIEWS = [
  {
    name: '李晨阳',
    role: 'AI 技术总监 · 某知名智能客服独角兽',
    avatar: '李',
    text: '以往上线新版 RAG 智能体，靠几个实习生盲测，上线后依然频频翻车。EvalAgent 的“具象理由”和“双盲盲测”让我们每次发版都能看到确凿的数据对比，发布信心翻倍！',
    stars: 5,
  },
  {
    name: '张浩博',
    role: '算法专家 · 金融科技实验室',
    avatar: '张',
    text: 'RSI 自进化功能简直是神来之笔！以前改完场景指标，根本不敢保证老用例不退化。现在系统自动生成候选 Patch，影子回归通过后才写回，还能一键回滚，工程化做得太扎实了。',
    stars: 5,
  },
  {
    name: 'Sarah Wang',
    role: '资深全栈工程师 · 跨境出海 AI 团队',
    avatar: 'S',
    text: '接入我们现有的 FastAPI 接口只花了几分钟，变量占位符配置非常自然。配合多轮对话的连贯性检测，直接帮我们把长程对话的丢记忆问题降低了 40% 以上。',
    stars: 5,
  },
];

// FAQs
const FAQ_ITEMS = [
  {
    key: '1',
    label: '如何开始使用 EvalAgent？',
    children: (
      <p style={{ color: '#94a3b8', lineHeight: 1.7, margin: 0 }}>
        平台开箱即用，已预置通义千问 Qwen Plus 种子配置和 3 个覆盖 RAG、Agent、多轮对话的标准数据集。只需点击右上角「立即体验」即可免密登录并直接进入工作台发起首个评测任务。
      </p>
    ),
  },
  {
    key: '2',
    label: '平台支持哪些评测大模型 (Judge Models)？',
    children: (
      <p style={{ color: '#94a3b8', lineHeight: 1.7, margin: 0 }}>
        默认推荐通义千问 Qwen Plus (性价比极高且中文逻辑强)。此外，平台底层采用原生 AsyncOpenAI 协议抽象层，支持无缝切换至 OpenAI GPT-4o、DeepSeek V3 / R1、Claude、智谱 GLM、以及本地 vLLM / Ollama 部署的模型。
      </p>
    ),
  },
  {
    key: '3',
    label: '什么是「评测驱动的配置自进化 (RSI)」？',
    children: (
      <p style={{ color: '#94a3b8', lineHeight: 1.7, margin: 0 }}>
        RSI (Recursive Self-Improvement) 是平台独创的递归优化引擎。它利用单次评测的失败行作为证据，自动归因聚类并由提案大模型生成合规的配置变更补丁（Patch）。通过影子评测任务在隔离环境中验证提升，经人工确认后安全写回，并保留版本快照以供任意时刻一键回滚。
      </p>
    ),
  },
  {
    key: '4',
    label: '企业私有化部署是否会产生数据外泄风险？',
    children: (
      <p style={{ color: '#94a3b8', lineHeight: 1.7, margin: 0 }}>
        绝不外泄。EvalAgent 采用纯自托管架构，所有评测样本、接口 Trace、指标配置均保存在您指定的本地 SQLite 或内网 PostgreSQL 数据库中。大模型调用也完全支持指向企业内部网关或私有化 Ollama/vLLM 实例。
      </p>
    ),
  },
];

export const LandingPage: React.FC = () => {
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const scrollTo = (id: string) => {
    setMobileMenuOpen(false);
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <div className="landing-wrapper">
      <div className="landing-bg-glow" />
      <div className="landing-grid-overlay" />

      {/* Navigation Bar */}
      <nav className="landing-nav">
        <div className="landing-nav-brand" onClick={() => navigate('/')}>
          <div className="landing-brand-logo">
            <ExperimentOutlined />
          </div>
          <span className="landing-brand-name">EvalAgent</span>
          <Tag color="cyan" style={{ borderRadius: 8, fontSize: 11, border: 'none' }}>
            AI 评测中枢
          </Tag>
        </div>

        <div className="landing-nav-links">
          <span className="landing-nav-link" onClick={() => scrollTo('features')}>
            特色功能
          </span>
          <span className="landing-nav-link" onClick={() => scrollTo('radar')}>
            能力雷达
          </span>
          <span className="landing-nav-link" onClick={() => scrollTo('personas')}>
            用户画像
          </span>
          <span className="landing-nav-link" onClick={() => scrollTo('matrix')}>
            竞品对比
          </span>
          <span className="landing-nav-link" onClick={() => scrollTo('pricing')}>
            会员计划
          </span>
          <span className="landing-nav-link" onClick={() => scrollTo('reviews')}>
            用户评价
          </span>
          <span className="landing-nav-link" onClick={() => scrollTo('faq')}>
            常见问题
          </span>
        </div>

        <div className="landing-nav-actions">
          <Button
            type="text"
            className="btn-ghost-glow"
            onClick={() => navigate('/login')}
            style={{ borderRadius: 8 }}
          >
            登入控制台
          </Button>
          <Button
            type="primary"
            className="btn-gradient-primary"
            icon={<RocketOutlined />}
            onClick={() => navigate('/login')}
            style={{ borderRadius: 8 }}
          >
            立即使用
          </Button>

          {/* Mobile hamburger icon */}
          <Button
            type="text"
            icon={<MenuOutlined style={{ color: '#fff', fontSize: 18 }} />}
            onClick={() => setMobileMenuOpen(true)}
            style={{ display: 'none' }}
            className="mobile-menu-trigger"
          />
        </div>
      </nav>

      {/* Mobile Drawer */}
      <Drawer
        title="EvalAgent 菜单"
        placement="right"
        onClose={() => setMobileMenuOpen(false)}
        open={mobileMenuOpen}
        styles={{
          body: { background: '#0f172a', color: '#fff', padding: '24px 16px' },
          header: { background: '#1e293b', borderBottom: '1px solid rgba(255,255,255,0.1)' },
        }}
      >
        <Space direction="vertical" size={20} style={{ width: '100%' }}>
          <Button type="text" block style={{ textAlign: 'left', color: '#cbd5e1' }} onClick={() => scrollTo('features')}>
            特色功能
          </Button>
          <Button type="text" block style={{ textAlign: 'left', color: '#cbd5e1' }} onClick={() => scrollTo('radar')}>
            能力雷达
          </Button>
          <Button type="text" block style={{ textAlign: 'left', color: '#cbd5e1' }} onClick={() => scrollTo('personas')}>
            用户画像
          </Button>
          <Button type="text" block style={{ textAlign: 'left', color: '#cbd5e1' }} onClick={() => scrollTo('matrix')}>
            竞品对比
          </Button>
          <Button type="text" block style={{ textAlign: 'left', color: '#cbd5e1' }} onClick={() => scrollTo('pricing')}>
            会员计划
          </Button>
          <Button type="text" block style={{ textAlign: 'left', color: '#cbd5e1' }} onClick={() => scrollTo('faq')}>
            常见问题
          </Button>
          <Button
            type="primary"
            block
            className="btn-gradient-primary"
            onClick={() => navigate('/login')}
            style={{ marginTop: 24, height: 44 }}
          >
            立即免费使用
          </Button>
        </Space>
      </Drawer>

      {/* Hero Section */}
      <section className="hero-section">
        <div className="hero-badge-pill">
          <ThunderboltOutlined style={{ color: '#38bdf8' }} />
          <span>业内首创 · 评测驱动的配置自进化 (RSI) 架构已发布</span>
          <RightOutlined style={{ fontSize: 10 }} />
        </div>

        <h1 className="hero-title">
          下一代企业级 <span className="hero-title-gradient">AI 应用评测中枢</span>
        </h1>

        <p className="hero-description">
          告别散落的脚本与黑盒黑分。面向 <strong>RAG 检索增强</strong>、<strong>AI Agent 智能体</strong> 与{' '}
          <strong>多轮对话</strong> 场景，提供样本合成、在线接口探针、原生裁判引擎、多版本对比与自进化闭环。
        </p>

        <div className="hero-buttons">
          <Button
            type="primary"
            size="large"
            className="btn-gradient-primary"
            icon={<ThunderboltOutlined />}
            onClick={() => navigate('/login')}
            style={{ height: 50, padding: '0 36px', fontSize: 16, borderRadius: 10 }}
          >
            立即免费体验
          </Button>
          <Button
            size="large"
            className="btn-ghost-glow"
            icon={<BarChartOutlined />}
            onClick={() => scrollTo('features')}
            style={{ height: 50, padding: '0 28px', fontSize: 16, borderRadius: 10 }}
          >
            探索特色功能
          </Button>
        </div>

        {/* Metrics Ribbon */}
        <div className="metrics-ribbon">
          <div className="metric-card-glass">
            <div className="metric-number">99.8%</div>
            <div className="metric-label">具象裁判理由覆盖率</div>
          </div>
          <div className="metric-card-glass">
            <div className="metric-number">6+ 维度</div>
            <div className="metric-label">RAG / Agent 核心指标矩阵</div>
          </div>
          <div className="metric-card-glass">
            <div className="metric-number">10x 提升</div>
            <div className="metric-label">失败归因与配置优化效率</div>
          </div>
          <div className="metric-card-glass">
            <div className="metric-number">100% 回滚</div>
            <div className="metric-label">版本不可变快照安全兜底</div>
          </div>
        </div>

        {/* Dashboard Preview Mockup */}
        <div className="preview-mockup-container">
          <div className="preview-mockup-inner">
            <div className="preview-mockup-bar">
              <span className="mockup-dot dot-red" />
              <span className="mockup-dot dot-yellow" />
              <span className="mockup-dot dot-green" />
              <span className="mockup-title">evalagent-workbench // live-evaluation-stream</span>
            </div>
            <div style={{ padding: '24px', background: '#0b1120' }}>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                  gap: 16,
                  marginBottom: 20,
                }}
              >
                <div style={{ background: '#1e293b', padding: '16px', borderRadius: 10 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>评测样本综合通过率</Text>
                  <div style={{ fontSize: 26, fontWeight: 700, color: '#10b981', marginTop: 4 }}>
                    94.2% <Tag color="success" style={{ marginLeft: 6 }}>+8.4%</Tag>
                  </div>
                </div>
                <div style={{ background: '#1e293b', padding: '16px', borderRadius: 10 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>忠实度 (Faithfulness)</Text>
                  <div style={{ fontSize: 26, fontWeight: 700, color: '#38bdf8', marginTop: 4 }}>
                    0.962 <span style={{ fontSize: 12, color: '#64748b' }}>/ 1.0</span>
                  </div>
                </div>
                <div style={{ background: '#1e293b', padding: '16px', borderRadius: 10 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>检索召回 (Context Recall)</Text>
                  <div style={{ fontSize: 26, fontWeight: 700, color: '#a855f7', marginTop: 4 }}>
                    0.920 <span style={{ fontSize: 12, color: '#64748b' }}>/ 1.0</span>
                  </div>
                </div>
                <div style={{ background: '#1e293b', padding: '16px', borderRadius: 10 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>在线接口 P95 物理耗时</Text>
                  <div style={{ fontSize: 26, fontWeight: 700, color: '#f59e0b', marginTop: 4 }}>
                    640ms <span style={{ fontSize: 12, color: '#64748b' }}>HTTP 200</span>
                  </div>
                </div>
              </div>

              {/* Sample Evidence Row */}
              <div
                style={{
                  background: 'rgba(30, 41, 59, 0.45)',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  borderRadius: 10,
                  padding: '16px',
                  fontFamily: 'monospace',
                  fontSize: 13,
                  lineHeight: 1.6,
                }}
              >
                <div style={{ color: '#38bdf8', marginBottom: 4 }}>
                  [Judge Reason - 逐句事实归因]:
                </div>
                <div style={{ color: '#cbd5e1' }}>
                  回答准确概述了退票手续费梯次规则，且每一项扣费比例均在 retrieved_contexts[0] 与 [2] 中获得明确事实支撑；未发现事实虚构或越界限定词。
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Infinite Marquee Ticker */}
      <div className="marquee-container">
        <div className="marquee-track">
          {[...MARQUEE_ITEMS, ...MARQUEE_ITEMS].map((item, idx) => (
            <div key={idx} className="marquee-item">
              <span className="marquee-badge">{item.icon}</span>
              <span>{item.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Feature Highlights Grid */}
      <section id="features" className="landing-section">
        <div className="section-header">
          <div className="section-tag">六大核心引擎</div>
          <h2 className="section-title">为 AI 落地打造的一体化工业级基础设施</h2>
          <p className="section-subtitle">
            从数据冷启动到线上发版把控，解决传统打分工具缺少依据、无法调优、对比失真的顽疾。
          </p>
        </div>

        <div className="features-grid">
          <div className="feature-card">
            <div className="feature-icon-box">
              <DatabaseOutlined />
            </div>
            <h3 className="feature-card-title">RAG 知识库合成数据衍生</h3>
            <p className="feature-card-desc">
              无标注文档秒变高质评测集。智能解析 PDF/Word/TXT，语义滑窗切片并利用 LLM 自动合成 QA 问答，双向验证自纠错过滤低质模糊样本。
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon-box">
              <ApiOutlined />
            </div>
            <h3 className="feature-card-title">被测接口在线实时探针</h3>
            <p className="feature-card-desc">
              不仅仅是离线打分。直接挂载外部开发中的 RESTful Chat / RAG 接口，动态入参插值注入，秒级捕获网络延迟与上下文 Trace。
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon-box">
              <ExperimentOutlined />
            </div>
            <h3 className="feature-card-title">原生 Judge 执行器与具体依据</h3>
            <p className="feature-card-desc">
              不强依赖第三方黑盒包。底层原生实现评分算法，每一项打分均强制要求大模型输出具象评判理由（Judge Reason），杜绝盲目给分。
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon-box">
              <SafetyCertificateOutlined />
            </div>
            <h3 className="feature-card-title">场景快照冻结机制</h3>
            <p className="feature-card-desc">
              评测触发瞬间自动固化场景挂载的所有指标、权重、及格阈值与 Prompt 覆盖，后续修改配置绝不影响历史任务，保障基线严格可比。
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon-box">
              <SyncOutlined />
            </div>
            <h3 className="feature-card-title">评测驱动配置自进化 (RSI)</h3>
            <p className="feature-card-desc">
              以历史失败评测为输入，规则与大模型自动归因聚类，产出合规 Patch 提案并在影子任务上验证验收，审批后一键生效，支持无损回滚。
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon-box">
              <SwapOutlined />
            </div>
            <h3 className="feature-card-title">双盲 A/B 人工偏好盲测</h3>
            <p className="feature-card-desc">
              抹除标识与乱序置乱，消除测试人员心理倾向。支持模型 vs 模型、接口 vs 接口主观盲测对决，产出可量化的 Win Rate 与上线决策雷达。
            </p>
          </div>
        </div>
      </section>

      {/* Interactive Carousel Showcase */}
      <section className="landing-section" style={{ paddingTop: 40, paddingBottom: 60 }}>
        <div className="carousel-card">
          <Carousel autoplay autoplaySpeed={5000} effect="fade">
            {CAROUSEL_SLIDES.map((slide, idx) => (
              <div key={idx}>
                <div className="carousel-slide-content">
                  <div className="carousel-slide-info">
                    <span className="carousel-slide-tag">{slide.tag}</span>
                    <h3 className="carousel-slide-title">{slide.title}</h3>
                    <p className="carousel-slide-desc">{slide.desc}</p>
                    <Space size={12}>
                      <Button
                        type="primary"
                        className="btn-gradient-primary"
                        icon={<RocketOutlined />}
                        onClick={() => navigate('/login')}
                        style={{ borderRadius: 8, height: 42 }}
                      >
                        立即上手体验
                      </Button>
                      <Button
                        className="btn-ghost-glow"
                        onClick={() => scrollTo('matrix')}
                        style={{ borderRadius: 8, height: 42 }}
                      >
                        查看对比
                      </Button>
                    </Space>
                  </div>

                  <div className="carousel-slide-visual">
                    <div style={{ width: '100%', maxWidth: 380 }}>
                      <div
                        style={{
                          fontSize: 13,
                          fontWeight: 600,
                          color: '#60a5fa',
                          marginBottom: 16,
                          display: 'flex',
                          alignItems: 'center',
                          gap: 6,
                        }}
                      >
                        <BarChartOutlined />
                        <span>{slide.visualTitle}</span>
                      </div>

                      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                        {slide.metrics.map((m, mIdx) => (
                          <div
                            key={mIdx}
                            style={{
                              background: '#1e293b',
                              padding: '14px 18px',
                              borderRadius: 10,
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              border: '1px solid rgba(255, 255, 255, 0.06)',
                            }}
                          >
                            <span style={{ color: '#cbd5e1', fontSize: 13 }}>{m.label}</span>
                            <span style={{ color: '#38bdf8', fontWeight: 700, fontSize: 16 }}>{m.val}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </Carousel>
        </div>
      </section>

      {/* Radar Chart Section */}
      <section id="radar" className="landing-section">
        <div className="section-header">
          <div className="section-tag">六维能力雷达</div>
          <h2 className="section-title">全方位碾压单一脚本评测库</h2>
          <p className="section-subtitle">
            对比传统开源脚本库，EvalAgent 在幻觉抑制、接口链路、动态记忆与自进化闭环上具备压倒性优势。
          </p>
        </div>

        <div className="radar-section-container">
          <LandingRadarChart />

          <div>
            <div style={{ marginBottom: 24 }}>
              <div style={{ color: '#38bdf8', fontSize: 13, fontWeight: 700, marginBottom: 8 }}>
                WHY EVALAGENT WINS
              </div>
              <h3 style={{ fontSize: 24, color: '#fff', margin: 0, fontWeight: 700 }}>
                从“离线静态打分”跃升至“工业级质量闭环”
              </h3>
            </div>

            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                <CheckCircleFilled style={{ color: '#38bdf8', fontSize: 18, marginTop: 3 }} />
                <div>
                  <Text strong style={{ color: '#fff', fontSize: 15 }}>确定性理由与打分透明</Text>
                  <Paragraph style={{ color: '#94a3b8', fontSize: 13, margin: 0 }}>
                    拒绝黑盒打分，所有指标均伴随逐句事实提取，精准定位到具体检索切片与字段错误。
                  </Paragraph>
                </div>
              </div>

              <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                <CheckCircleFilled style={{ color: '#38bdf8', fontSize: 18, marginTop: 3 }} />
                <div>
                  <Text strong style={{ color: '#fff', fontSize: 15 }}>被测服务直接联调</Text>
                  <Paragraph style={{ color: '#94a3b8', fontSize: 13, margin: 0 }}>
                    无需人工导出结果文件，挂载在线 HTTP 端点即可自动批量发起请求并提取 Trace。
                  </Paragraph>
                </div>
              </div>

              <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                <CheckCircleFilled style={{ color: '#38bdf8', fontSize: 18, marginTop: 3 }} />
                <div>
                  <Text strong style={{ color: '#fff', fontSize: 15 }}>独家 RSI 配置自进化机制</Text>
                  <Paragraph style={{ color: '#94a3b8', fontSize: 13, margin: 0 }}>
                    失败自动归因、影子回归验证、冻结参考阈值防刷分，并支持版本一键安全回滚。
                  </Paragraph>
                </div>
              </div>
            </Space>
          </div>
        </div>
      </section>

      {/* Target User Personas */}
      <section id="personas" className="landing-section">
        <div className="section-header">
          <div className="section-tag">用户画像与适配场景</div>
          <h2 className="section-title">专为大模型业务研发全流程角色量身定制</h2>
          <p className="section-subtitle">
            无论您是负责算法攻坚、应用工程交付，还是负责企业 AI 业务的质检上线决策。
          </p>
        </div>

        <div className="personas-grid">
          {PERSONAS.map((p, idx) => (
            <div key={idx} className="persona-card">
              <div className="persona-avatar">{p.avatar}</div>
              <div className="persona-title">{p.title}</div>
              <div className="persona-tag">{p.tag}</div>
              <div className="persona-pain-point">{p.pain}</div>
              <div className="persona-solution">{p.solution}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Competitive Matrix */}
      <section id="matrix" className="landing-section">
        <div className="section-header">
          <div className="section-tag">竞品横向对比</div>
          <h2 className="section-title">EvalAgent vs 业界常见评测框架</h2>
          <p className="section-subtitle">
            不仅是指标计算器，更是拥有数据准备、在线探针、双盲盲测与自进化闭环的完整平台。
          </p>
        </div>

        <div className="matrix-card">
          <table className="matrix-table">
            <thead>
              <tr>
                <th style={{ textAlign: 'left', width: '28%' }}>能力对比维度</th>
                <th className="highlight-col" style={{ width: '18%' }}>
                  EvalAgent (本项目)
                </th>
                <th style={{ width: '13%' }}>Ragas</th>
                <th style={{ width: '13%' }}>TruLens</th>
                <th style={{ width: '14%' }}>DeepEval</th>
                <th style={{ width: '14%' }}>Promptfoo</th>
              </tr>
            </thead>
            <tbody>
              {MATRIX_ROWS.map((row, idx) => (
                <tr key={idx}>
                  <td className="feature-title-col">{row.feature}</td>
                  <td className="highlight-col">
                    <CheckCircleFilled className="check-icon" />
                  </td>
                  <td>{row.ragas ? <CheckCircleFilled className="check-icon" /> : <CloseCircleFilled className="cross-icon" />}</td>
                  <td>{row.trulens ? <CheckCircleFilled className="check-icon" /> : <CloseCircleFilled className="cross-icon" />}</td>
                  <td>{row.deepeval ? <CheckCircleFilled className="check-icon" /> : <CloseCircleFilled className="cross-icon" />}</td>
                  <td>{row.promptfoo ? <CheckCircleFilled className="check-icon" /> : <CloseCircleFilled className="cross-icon" />}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Membership & Pricing Plans */}
      <section id="pricing" className="landing-section">
        <div className="section-header">
          <div className="section-tag">灵活计划方案</div>
          <h2 className="section-title">透明诚意，从个人开发者到企业级交付</h2>
          <p className="section-subtitle">
            完全开源免费自托管，同时提供面向团队协同与企业定制的高级支持方案。
          </p>
        </div>

        <div className="pricing-grid">
          {/* Free Tier */}
          <div className="pricing-card">
            <div className="pricing-plan-name">开源社区版</div>
            <div className="pricing-plan-desc">适合个人开发者、学术科研人员与离线快速验证</div>
            <div className="pricing-price-box">
              <span className="pricing-amount">¥0</span>
              <span className="pricing-period">/ 永久免费 · Apache 2.0</span>
            </div>

            <ul className="pricing-features-list">
              <li className="pricing-feature-item">
                <CheckCircleFilled style={{ color: '#10b981' }} />
                <span>完整开源 Web 可视化工作台</span>
              </li>
              <li className="pricing-feature-item">
                <CheckCircleFilled style={{ color: '#10b981' }} />
                <span>所有 RAG / Agent / 多轮原生指标</span>
              </li>
              <li className="pricing-feature-item">
                <CheckCircleFilled style={{ color: '#10b981' }} />
                <span>在线 HTTP 接口探针与 Trace 抓取</span>
              </li>
              <li className="pricing-feature-item">
                <CheckCircleFilled style={{ color: '#10b981' }} />
                <span>场景快照冻结机制</span>
              </li>
              <li className="pricing-feature-item">
                <CheckCircleFilled style={{ color: '#10b981' }} />
                <span>单机 SQLite 零外部依赖即启</span>
              </li>
            </ul>

            <Button
              className="btn-ghost-glow"
              size="large"
              block
              onClick={() => navigate('/login')}
              style={{ borderRadius: 8 }}
            >
              立即免费体验
            </Button>
          </div>

          {/* Pro Team */}
          <div className="pricing-card featured">
            <div className="pricing-badge-popular">🔥 团队研发推荐</div>
            <div className="pricing-plan-name">专业团队版</div>
            <div className="pricing-plan-desc">适合高频发版的大模型业务团队与算法工程组</div>
            <div className="pricing-price-box">
              <span className="pricing-amount">¥299</span>
              <span className="pricing-period">/ 团队月度起</span>
            </div>

            <ul className="pricing-features-list">
              <li className="pricing-feature-item">
                <CheckCircleFilled style={{ color: '#38bdf8' }} />
                <span><strong>包含社区版全部能力</strong></span>
              </li>
              <li className="pricing-feature-item">
                <CheckCircleFilled style={{ color: '#38bdf8' }} />
                <span>RSI 评测驱动自进化无限制迭代轮次</span>
              </li>
              <li className="pricing-feature-item">
                <CheckCircleFilled style={{ color: '#38bdf8' }} />
                <span>RAG 知识库批量无监督合成数据流水线</span>
              </li>
              <li className="pricing-feature-item">
                <CheckCircleFilled style={{ color: '#38bdf8' }} />
                <span>双盲 A/B 人工偏好盲测投票室</span>
              </li>
              <li className="pricing-feature-item">
                <CheckCircleFilled style={{ color: '#38bdf8' }} />
                <span>PostgreSQL 高并发集群生产配置支持</span>
              </li>
              <li className="pricing-feature-item">
                <CheckCircleFilled style={{ color: '#38bdf8' }} />
                <span>7x12h 官方专家技术答疑群</span>
              </li>
            </ul>

            <Button
              type="primary"
              className="btn-gradient-primary"
              size="large"
              block
              onClick={() => navigate('/login')}
              style={{ borderRadius: 8 }}
            >
              免费试用 14 天
            </Button>
          </div>

          {/* Enterprise */}
          <div className="pricing-card">
            <div className="pricing-plan-name">企业私有化版</div>
            <div className="pricing-plan-desc">适合金融、医疗、政企等对数据安全合规有极致要求的机构</div>
            <div className="pricing-price-box">
              <span className="pricing-amount">定制</span>
              <span className="pricing-period">/ 专家驻场与 SLA 保障</span>
            </div>

            <ul className="pricing-features-list">
              <li className="pricing-feature-item">
                <CheckCircleFilled style={{ color: '#10b981' }} />
                <span><strong>包含团队版全部高级功能</strong></span>
              </li>
              <li className="pricing-feature-item">
                <CheckCircleFilled style={{ color: '#10b981' }} />
                <span>企业完全纯内网离线物理隔离部署</span>
              </li>
              <li className="pricing-feature-item">
                <CheckCircleFilled style={{ color: '#10b981' }} />
                <span>多租户企业 RBAC 权限与审计合规日志</span>
              </li>
              <li className="pricing-feature-item">
                <CheckCircleFilled style={{ color: '#10b981' }} />
                <span>企业定制评测指标与业务判据开发</span>
              </li>
              <li className="pricing-feature-item">
                <CheckCircleFilled style={{ color: '#10b981' }} />
                <span>专属解决方案架构师与 SLA 保障</span>
              </li>
            </ul>

            <Button
              className="btn-ghost-glow"
              size="large"
              block
              onClick={() => navigate('/login')}
              style={{ borderRadius: 8 }}
            >
              联系专家方案顾问
            </Button>
          </div>
        </div>
      </section>

      {/* Customer Reviews */}
      <section id="reviews" className="landing-section">
        <div className="section-header">
          <div className="section-tag">真实用户口碑</div>
          <h2 className="section-title">来自一线 AI 工程师与算法团队的声音</h2>
          <p className="section-subtitle">
            听听正在使用 EvalAgent 把控大模型质量的技术 Leader 们怎么说。
          </p>
        </div>

        <div className="reviews-grid">
          {REVIEWS.map((rev, idx) => (
            <div key={idx} className="review-card">
              <div>
                <Space style={{ marginBottom: 12 }}>
                  {[...Array(rev.stars)].map((_, sIdx) => (
                    <StarFilled key={sIdx} style={{ color: '#f59e0b', fontSize: 15 }} />
                  ))}
                </Space>
                <div className="review-text">“{rev.text}”</div>
              </div>

              <div className="reviewer-profile">
                <div className="reviewer-avatar">{rev.avatar}</div>
                <div>
                  <div className="reviewer-name">{rev.name}</div>
                  <div className="reviewer-role">{rev.role}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* FAQ Accordion */}
      <section id="faq" className="landing-section" style={{ maxWidth: 880 }}>
        <div className="section-header">
          <div className="section-tag">常见解答</div>
          <h2 className="section-title">常见问题与解答</h2>
          <p className="section-subtitle">
            关于环境配置、模型支持及落地集成的疑问，我们为您梳理好了答案。
          </p>
        </div>

        <Collapse
          items={FAQ_ITEMS}
          bordered={false}
          style={{ background: 'transparent' }}
          className="landing-faq-collapse"
        />
      </section>

      {/* Pre-footer Call to Action */}
      <section className="landing-section" style={{ textAlign: 'center', paddingBottom: 100 }}>
        <div
          style={{
            padding: '60px 30px',
            borderRadius: 22,
            background: 'linear-gradient(135deg, rgba(37, 99, 235, 0.25), rgba(124, 58, 237, 0.2))',
            border: '1px solid rgba(59, 130, 246, 0.4)',
            boxShadow: '0 20px 60px rgba(0, 0, 0, 0.6)',
          }}
        >
          <h2 style={{ fontSize: 36, fontWeight: 800, color: '#fff', marginBottom: 16 }}>
            准备好将您的 AI 应用质量推向新高度了吗？
          </h2>
          <p style={{ color: '#cbd5e1', fontSize: 16, maxWidth: 640, margin: '0 auto 32px' }}>
            无需复杂搭建，3 分钟即可在本地跑通 RAG 与 Agent 的首轮客观评测。
          </p>
          <Button
            type="primary"
            size="large"
            className="btn-gradient-primary"
            icon={<ThunderboltOutlined />}
            onClick={() => navigate('/login')}
            style={{ height: 50, padding: '0 40px', fontSize: 17, borderRadius: 10 }}
          >
            立即免费开始使用
          </Button>
        </div>
      </section>

      {/* Footer */}
      <footer className="landing-footer">
        <div className="footer-inner">
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: 8,
                  background: 'linear-gradient(135deg, #2563eb, #7c3aed)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#fff',
                }}
              >
                <ExperimentOutlined />
              </div>
              <span style={{ fontSize: 18, fontWeight: 700, color: '#fff' }}>EvalAgent</span>
            </div>
            <p style={{ color: '#64748b', fontSize: 13, lineHeight: 1.6, maxWidth: 300 }}>
              面向 RAG、AI Agent 智能体与多轮对话场景的企业自托管 AI 应用评测与配置自进化中枢。
            </p>
          </div>

          <div>
            <div style={{ color: '#cbd5e1', fontWeight: 600, marginBottom: 14, fontSize: 14 }}>产品功能</div>
            <Space direction="vertical" size={8}>
              <span style={{ color: '#64748b', cursor: 'pointer', fontSize: 13 }} onClick={() => scrollTo('features')}>RAG 评测矩阵</span>
              <span style={{ color: '#64748b', cursor: 'pointer', fontSize: 13 }} onClick={() => scrollTo('features')}>Agent 工具链质检</span>
              <span style={{ color: '#64748b', cursor: 'pointer', fontSize: 13 }} onClick={() => scrollTo('features')}>RSI 配置自进化</span>
              <span style={{ color: '#64748b', cursor: 'pointer', fontSize: 13 }} onClick={() => scrollTo('features')}>双盲 A/B 盲测</span>
            </Space>
          </div>

          <div>
            <div style={{ color: '#cbd5e1', fontWeight: 600, marginBottom: 14, fontSize: 14 }}>开源生态</div>
            <Space direction="vertical" size={8}>
              <a href="https://github.com" target="_blank" rel="noreferrer" style={{ color: '#64748b', fontSize: 13 }}>GitHub 代码仓</a>
              <a href="/docs" style={{ color: '#64748b', fontSize: 13 }}>RESTful API 文档</a>
              <span style={{ color: '#64748b', cursor: 'pointer', fontSize: 13 }} onClick={() => scrollTo('matrix')}>竞品架构对比</span>
              <span style={{ color: '#64748b', cursor: 'pointer', fontSize: 13 }} onClick={() => scrollTo('pricing')}>商业化与支持</span>
            </Space>
          </div>

          <div>
            <div style={{ color: '#cbd5e1', fontWeight: 600, marginBottom: 14, fontSize: 14 }}>快速直达</div>
            <Space direction="vertical" size={8}>
              <span style={{ color: '#60a5fa', cursor: 'pointer', fontSize: 13 }} onClick={() => navigate('/login')}>一键体验登录</span>
              <span style={{ color: '#60a5fa', cursor: 'pointer', fontSize: 13 }} onClick={() => navigate('/workbench')}>评测实验工作台</span>
              <span style={{ color: '#60a5fa', cursor: 'pointer', fontSize: 13 }} onClick={() => navigate('/rsi')}>RSI 自进化管理</span>
            </Space>
          </div>
        </div>

        <div className="footer-bottom">
          <div>© 2026 EvalAgent Platform. Open-sourced under Apache-2.0 License.</div>
          <div>企业级自托管 · 零数据外泄 · 确定性理由评测</div>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;
