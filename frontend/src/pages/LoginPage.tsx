import React, { useState } from 'react';
import { Card, Form, Input, Button, Typography, Space, Divider, message, Tabs } from 'antd';
import {
  ExperimentOutlined,
  UserOutlined,
  LockOutlined,
  ArrowLeftOutlined,
  ThunderboltOutlined,
  CheckCircleFilled,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';

const { Title, Text, Paragraph } = Typography;

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'quick' | 'account'>('quick');

  const handleQuickLogin = (role: string = 'admin') => {
    setLoading(true);
    message.loading({ content: '正在为您初始化工作台环境...', key: 'login' });
    setTimeout(() => {
      localStorage.setItem('eval_user', JSON.stringify({ role, name: role === 'admin' ? '系统管理员' : '算法评测工程师' }));
      message.success({ content: '登录成功！即将进入评测工作台', key: 'login' });
      navigate('/workbench');
    }, 600);
  };

  const handleAccountSubmit = (values: any) => {
    setLoading(true);
    message.loading({ content: '正在验证身份...', key: 'login' });
    setTimeout(() => {
      localStorage.setItem('eval_user', JSON.stringify({ name: values.username || '评测专家' }));
      message.success({ content: '登录成功！欢迎回来', key: 'login' });
      navigate('/workbench');
    }, 600);
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        background: '#090d16',
        color: '#fff',
        display: 'flex',
        flexDirection: 'column',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Glow background */}
      <div
        style={{
          position: 'absolute',
          top: '15%',
          left: '50%',
          transform: 'translateX(-50%)',
          width: '800px',
          height: '500px',
          background: 'radial-gradient(circle, rgba(59, 130, 246, 0.22) 0%, rgba(139, 92, 246, 0.1) 50%, transparent 70%)',
          pointerEvents: 'none',
        }}
      />

      {/* Top Header */}
      <header
        style={{
          padding: '24px 36px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          zIndex: 10,
        }}
      >
        <div
          style={{ display: 'flex', alignItems: 'center', gap: 12, cursor: 'pointer' }}
          onClick={() => navigate('/')}
          title="返回官网首页"
        >
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: 8,
              background: 'linear-gradient(135deg, #2563eb, #7c3aed)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff',
              fontSize: 18,
            }}
          >
            <ExperimentOutlined />
          </div>
          <Text strong style={{ fontSize: 17, color: '#fff', letterSpacing: '-0.02em' }}>
            EvalAgent · AI 评测平台
          </Text>
        </div>

        <Button
          type="text"
          icon={<ArrowLeftOutlined />}
          style={{ color: '#94a3b8' }}
          onClick={() => navigate('/')}
        >
          返回官网首页
        </Button>
      </header>

      {/* Main Login Card */}
      <main
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '20px 24px 60px',
          zIndex: 10,
        }}
      >
        <Card
          style={{
            width: '100%',
            maxWidth: 440,
            borderRadius: 18,
            background: 'rgba(15, 23, 42, 0.85)',
            borderColor: 'rgba(255, 255, 255, 0.1)',
            backdropFilter: 'blur(20px)',
            boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7)',
          }}
          bodyStyle={{ padding: '36px 32px' }}
        >
          <div style={{ textAlign: 'center', marginBottom: 28 }}>
            <div
              style={{
                width: 52,
                height: 52,
                margin: '0 auto 16px',
                borderRadius: 14,
                background: 'linear-gradient(135deg, rgba(37, 99, 235, 0.2), rgba(124, 58, 237, 0.2))',
                border: '1px solid rgba(59, 130, 246, 0.4)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#60a5fa',
                fontSize: 26,
              }}
            >
              <ExperimentOutlined />
            </div>
            <Title level={3} style={{ color: '#fff', margin: '0 0 8px' }}>
              登入评测中枢
            </Title>
            <Text style={{ color: '#94a3b8', fontSize: 13 }}>
              工业级 RAG / Agent / 多轮对话企业自托管评测工作台
            </Text>
          </div>

          <Tabs
            activeKey={activeTab}
            onChange={(key) => setActiveTab(key as any)}
            centered
            items={[
              { key: 'quick', label: '🚀 一键体验模式' },
              { key: 'account', label: '账号密码登入' },
            ]}
          />

          {activeTab === 'quick' ? (
            <div style={{ marginTop: 20 }}>
              <Paragraph style={{ color: '#cbd5e1', fontSize: 13, lineHeight: 1.6 }}>
                本平台开箱即用，已内置通义千问 Qwen Plus 种子配置与 RAG / Agent 示例评测任务，无需繁琐注册即可直接体验全流程：
              </Paragraph>

              <div
                style={{
                  background: 'rgba(30, 41, 59, 0.6)',
                  borderRadius: 12,
                  padding: '14px 16px',
                  marginBottom: 24,
                  border: '1px solid rgba(255, 255, 255, 0.06)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#93c5fd', marginBottom: 6 }}>
                  <CheckCircleFilled style={{ color: '#3b82f6' }} />
                  <span>免密直达 评测实验工作台</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#93c5fd', marginBottom: 6 }}>
                  <CheckCircleFilled style={{ color: '#3b82f6' }} />
                  <span>支持查看 历史评测报告与基线 Diff</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#93c5fd' }}>
                  <CheckCircleFilled style={{ color: '#3b82f6' }} />
                  <span>支持发起 RSI 递归自进化与双盲盲测</span>
                </div>
              </div>

              <Button
                type="primary"
                size="large"
                block
                icon={<ThunderboltOutlined />}
                loading={loading}
                onClick={() => handleQuickLogin('admin')}
                style={{
                  height: 48,
                  fontSize: 16,
                  fontWeight: 600,
                  borderRadius: 10,
                  background: 'linear-gradient(135deg, #2563eb, #7c3aed)',
                  border: 'none',
                  boxShadow: '0 4px 18px rgba(37, 99, 235, 0.45)',
                }}
              >
                一键直达工作台
              </Button>
            </div>
          ) : (
            <Form layout="vertical" onFinish={handleAccountSubmit} style={{ marginTop: 20 }}>
              <Form.Item
                name="username"
                rules={[{ required: true, message: '请输入用户名' }]}
                initialValue="admin"
              >
                <Input
                  prefix={<UserOutlined style={{ color: '#64748b' }} />}
                  placeholder="用户名 (默认 admin)"
                  size="large"
                  style={{
                    background: 'rgba(30, 41, 59, 0.6)',
                    borderColor: 'rgba(255, 255, 255, 0.12)',
                    color: '#fff',
                  }}
                />
              </Form.Item>

              <Form.Item
                name="password"
                rules={[{ required: true, message: '请输入密码' }]}
                initialValue="eval123456"
              >
                <Input.Password
                  prefix={<LockOutlined style={{ color: '#64748b' }} />}
                  placeholder="密码"
                  size="large"
                  style={{
                    background: 'rgba(30, 41, 59, 0.6)',
                    borderColor: 'rgba(255, 255, 255, 0.12)',
                    color: '#fff',
                  }}
                />
              </Form.Item>

              <Form.Item style={{ marginBottom: 0 }}>
                <Button
                  type="primary"
                  htmlType="submit"
                  size="large"
                  block
                  loading={loading}
                  style={{
                    height: 48,
                    fontSize: 16,
                    fontWeight: 600,
                    borderRadius: 10,
                    background: 'linear-gradient(135deg, #2563eb, #7c3aed)',
                    border: 'none',
                    boxShadow: '0 4px 18px rgba(37, 99, 235, 0.45)',
                  }}
                >
                  安全登入
                </Button>
              </Form.Item>
            </Form>
          )}

          <Divider style={{ borderColor: 'rgba(255, 255, 255, 0.08)', margin: '24px 0 16px' }} />

          <div style={{ textAlign: 'center' }}>
            <Text type="secondary" style={{ fontSize: 12, color: '#64748b' }}>
              自托管开源版 · Apache 2.0 协议 · 数据完全本地闭环
            </Text>
          </div>
        </Card>
      </main>
    </div>
  );
};

export default LoginPage;
