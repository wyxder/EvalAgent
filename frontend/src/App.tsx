import React, { Suspense, useState } from 'react';
import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';
import { Button, Layout, Menu, Space, Spin, Typography, Tooltip } from 'antd';
import {
  SettingOutlined,
  DatabaseOutlined,
  AppstoreOutlined,
  PlayCircleOutlined,
  BarChartOutlined,
  SwapOutlined,
  SlidersOutlined,
  ApiOutlined,
  ExperimentOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  RobotOutlined,
  GlobalOutlined,
  LogoutOutlined,
} from '@ant-design/icons';

import ErrorBoundary from './components/ErrorBoundary';

// 路由级懒加载：首屏只加载当前页面，降低初始包体
const ExperimentWorkbenchPage = React.lazy(() => import('./pages/ExperimentWorkbenchPage'));
const LLMConfigPage = React.lazy(() => import('./pages/LLMConfigPage'));
const DatasetListPage = React.lazy(() => import('./pages/DatasetListPage'));
const DatasetDetailPage = React.lazy(() => import('./pages/DatasetDetailPage'));
const RagDatasetBuilderPage = React.lazy(() => import('./pages/RagDatasetBuilderPage'));
const ScenarioListPage = React.lazy(() => import('./pages/ScenarioListPage'));
const MetricListPage = React.lazy(() => import('./pages/MetricListPage'));
const EndpointTargetPage = React.lazy(() => import('./pages/EndpointTargetPage'));
const EvaluationPage = React.lazy(() => import('./pages/EvaluationPage'));
const ReportListPage = React.lazy(() => import('./pages/ReportListPage'));
const ReportDetailPage = React.lazy(() => import('./pages/ReportDetailPage'));
const BlindTestPage = React.lazy(() => import('./pages/BlindTestPage'));
const RsiLoopListPage = React.lazy(() => import('./pages/RsiLoopListPage'));
const RsiLoopDetailPage = React.lazy(() => import('./pages/RsiLoopDetailPage'));
const LandingPage = React.lazy(() => import('./pages/LandingPage'));
const LoginPage = React.lazy(() => import('./pages/LoginPage'));

const { Header, Sider, Content } = Layout;
const { Title } = Typography;

const menuItems = [
  {
    key: 'workflow',
    type: 'group' as const,
    label: '实验流程',
    children: [
      { key: '/workbench', icon: <ExperimentOutlined />, label: '评测实验工作台' },
    ],
  },
  {
    key: 'resources',
    type: 'group' as const,
    label: '资源管理',
    children: [
      { key: '/datasets', icon: <DatabaseOutlined />, label: '数据管理' },
      { key: '/metrics', icon: <SlidersOutlined />, label: '指标管理' },
      { key: '/endpoint-targets', icon: <ApiOutlined />, label: '被测接口' },
      { key: '/scenarios', icon: <AppstoreOutlined />, label: '场景管理' },
      { key: '/llm-configs', icon: <SettingOutlined />, label: 'LLM配置' },
    ],
  },
  {
    key: 'evolution',
    type: 'group' as const,
    label: '自进化',
    children: [
      { key: '/rsi', icon: <RobotOutlined />, label: 'RSI 自进化' },
    ],
  },
  {
    key: 'results',
    type: 'group' as const,
    label: '结果分析',
    children: [
      { key: '/evaluations', icon: <PlayCircleOutlined />, label: '评测执行' },
      { key: '/reports', icon: <BarChartOutlined />, label: '评测报告' },
      { key: '/blind-tests', icon: <SwapOutlined />, label: '人工盲测' },
    ],
  },
];

const App: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  // If user is accessing the landing page or login page directly, render them standalone
  const isLanding = location.pathname === '/' || location.pathname === '/landing';
  const isLogin = location.pathname === '/login';

  const pageFallback = (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, padding: '96px 0' }}>
      <Spin size="large" />
      <span style={{ color: '#64748b' }}>页面加载中...</span>
    </div>
  );

  if (isLanding) {
    return (
      <ErrorBoundary title="官网页面加载异常">
        <Suspense fallback={pageFallback}>
          <LandingPage />
        </Suspense>
      </ErrorBoundary>
    );
  }

  if (isLogin) {
    return (
      <ErrorBoundary title="登录页面加载异常">
        <Suspense fallback={pageFallback}>
          <LoginPage />
        </Suspense>
      </ErrorBoundary>
    );
  }

  const selectedKey = '/' + location.pathname.split('/')[1];

  return (
    <Layout className="app-shell">
      <Header className="app-header" style={{ justifyContent: 'space-between' }}>
        <Tooltip title="点击返回官网宣传页" placement="bottomLeft">
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              cursor: 'pointer',
              userSelect: 'none',
            }}
            onClick={() => navigate('/')}
          >
            <div className="brand-mark">
              <ExperimentOutlined />
            </div>
            <div>
              <Title level={4} className="brand-title">
                AI 评测平台
              </Title>
              <div className="brand-subtitle">RAG / Agent / 多轮对话评测中枢</div>
            </div>
          </div>
        </Tooltip>

        <Space size={12}>
          <Button
            icon={<GlobalOutlined />}
            size="small"
            onClick={() => navigate('/')}
            style={{ borderRadius: 6 }}
          >
            官网宣传页
          </Button>
          <Button
            type="text"
            size="small"
            icon={<LogoutOutlined />}
            onClick={() => navigate('/login')}
            style={{ color: '#64748b' }}
          >
            切换身份
          </Button>
        </Space>
      </Header>
      <Layout className="app-body">
        <Sider
          collapsible
          collapsed={collapsed}
          onCollapse={setCollapsed}
          theme="dark"
          width={232}
          collapsedWidth={80}
          className="app-sider"
          trigger={null}
        >
          <div className="sider-toolbar">
            {!collapsed && <span>导航</span>}
            <Button
              type="text"
              size="small"
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setCollapsed(!collapsed)}
              className="sider-collapse-button"
            />
          </div>
          <Menu
            mode="inline"
            theme="dark"
            selectedKeys={[selectedKey]}
            className="app-menu"
            items={menuItems}
            onClick={({ key }) => navigate(key)}
          />
        </Sider>
        <Layout className="workspace-layout">
          <Content className="workspace-content">
            <ErrorBoundary title="当前页面渲染异常">
              <Suspense fallback={pageFallback}>
                <Routes>
                  <Route path="/workbench" element={<ExperimentWorkbenchPage />} />
                  <Route path="/llm-configs" element={<LLMConfigPage />} />
                  <Route path="/datasets" element={<DatasetListPage />} />
                  <Route path="/datasets/rag-builder" element={<RagDatasetBuilderPage />} />
                  <Route path="/datasets/:id" element={<DatasetDetailPage />} />
                  <Route path="/metrics" element={<MetricListPage />} />
                  <Route path="/endpoint-targets" element={<EndpointTargetPage />} />
                  <Route path="/scenarios" element={<ScenarioListPage />} />
                  <Route path="/evaluations" element={<EvaluationPage />} />
                  <Route path="/blind-tests" element={<BlindTestPage />} />
                  <Route path="/rsi" element={<RsiLoopListPage />} />
                  <Route path="/rsi/:id" element={<RsiLoopDetailPage />} />
                  <Route path="/reports" element={<ReportListPage />} />
                  <Route path="/reports/:id" element={<ReportDetailPage />} />
                  <Route path="*" element={<Navigate to="/workbench" replace />} />
                </Routes>
              </Suspense>
            </ErrorBoundary>
          </Content>
        </Layout>
      </Layout>
    </Layout>
  );
};

export default App;
