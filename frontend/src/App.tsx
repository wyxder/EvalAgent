import React, { useState } from 'react';
import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';
import { Button, Layout, Menu, Space, Typography, Tooltip } from 'antd';
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

import ExperimentWorkbenchPage from './pages/ExperimentWorkbenchPage';
import LLMConfigPage from './pages/LLMConfigPage';
import DatasetListPage from './pages/DatasetListPage';
import DatasetDetailPage from './pages/DatasetDetailPage';
import RagDatasetBuilderPage from './pages/RagDatasetBuilderPage';
import ScenarioListPage from './pages/ScenarioListPage';
import MetricListPage from './pages/MetricListPage';
import EndpointTargetPage from './pages/EndpointTargetPage';
import EvaluationPage from './pages/EvaluationPage';
import ReportListPage from './pages/ReportListPage';
import ReportDetailPage from './pages/ReportDetailPage';
import BlindTestPage from './pages/BlindTestPage';
import RsiLoopListPage from './pages/RsiLoopListPage';
import RsiLoopDetailPage from './pages/RsiLoopDetailPage';
import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';

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

  if (isLanding) {
    return <LandingPage />;
  }

  if (isLogin) {
    return <LoginPage />;
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
          </Content>
        </Layout>
      </Layout>
    </Layout>
  );
};

export default App;
