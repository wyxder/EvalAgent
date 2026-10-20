import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Input,
  Modal,
  Progress,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import {
  EyeOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
  RobotOutlined,
} from '@ant-design/icons';
import { useNavigate, useSearchParams } from 'react-router-dom';
import type { EvalScenario, RsiLoop } from '../types';
import * as api from '../services/api';
import RsiCreateModal from '../components/rsi/RsiCreateModal';
import {
  formatGain,
  formatTime,
  loopStatusMeta,
} from '../components/rsi/rsiUtils';

const { Title, Text } = Typography;

const ACTIVE_STATUSES = ['running', 'awaiting_review'];

const RsiLoopListPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [loops, setLoops] = useState<RsiLoop[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [status, setStatus] = useState<string | undefined>();
  const [scenarioId, setScenarioId] = useState<number | undefined>();
  const [keyword, setKeyword] = useState('');
  const [loading, setLoading] = useState(false);
  const [scenarios, setScenarios] = useState<EvalScenario[]>([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [baselineEvalId, setBaselineEvalId] = useState<number | null>(null);

  const hasActive = useMemo(
    () => loops.some((item) => ACTIVE_STATUSES.includes(item.status)),
    [loops],
  );

  const fetchLoops = useCallback(
    async (nextPage = page, nextPageSize = pageSize) => {
      setLoading(true);
      try {
        const data = await api.listRsiLoops({
          page: nextPage,
          page_size: nextPageSize,
          status,
          scenario_id: scenarioId,
          keyword: keyword || undefined,
        });
        setLoops(data.items || []);
        setTotal(data.total || 0);
        setPage(data.page || nextPage);
        setPageSize(data.page_size || nextPageSize);
      } catch (error: any) {
        const detail = error?.response?.data?.detail;
        message.error(typeof detail === 'string' ? detail : '加载 RSI 循环失败');
      } finally {
        setLoading(false);
      }
    },
    [page, pageSize, status, scenarioId, keyword],
  );

  useEffect(() => {
    api.listScenarios().then((data) => setScenarios(data as EvalScenario[])).catch(() => undefined);
  }, []);

  useEffect(() => {
    fetchLoops(1, pageSize);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, scenarioId]);

  useEffect(() => {
    if (!hasActive) return;
    const timer = window.setInterval(() => {
      fetchLoops(page, pageSize);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [hasActive, fetchLoops, page, pageSize]);

  useEffect(() => {
    if (searchParams.get('create') !== '1') return;
    const raw = Number(searchParams.get('baseline_eval_id'));
    setBaselineEvalId(Number.isFinite(raw) && raw > 0 ? raw : null);
    setCreateOpen(true);
    const next = new URLSearchParams(searchParams);
    next.delete('create');
    next.delete('baseline_eval_id');
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);

  const handleStart = (loop: RsiLoop) => {
    Modal.confirm({
      title: `启动 RSI 循环「${loop.name}」？`,
      content: '启动后引擎会串行执行 归因 → 提案 → 影子回归 → 验收判定；默认在写回前等待人工审批。',
      okText: '启动',
      cancelText: '取消',
      onOk: async () => {
        try {
          await api.startRsiLoop(loop.id);
          message.success('循环已启动');
          fetchLoops(page, pageSize);
        } catch (error: any) {
          const detail = error?.response?.data?.detail;
          message.error(typeof detail === 'string' ? detail : '启动失败');
        }
      },
    });
  };

  const columns = [
    {
      title: '循环',
      key: 'name',
      width: 260,
      render: (_: unknown, record: RsiLoop) => (
        <Space direction="vertical" size={0}>
          <Space size={6}>
            <Text strong>{record.name}</Text>
            <Tag color={loopStatusMeta[record.status]?.color || 'default'}>
              {loopStatusMeta[record.status]?.label || record.status}
            </Tag>
          </Space>
          <Text type="secondary" style={{ fontSize: 12 }}>
            #{record.id} · 基线评测 #{record.baseline_eval_id}
          </Text>
        </Space>
      ),
    },
    {
      title: '数据集 / 场景',
      key: 'scope',
      width: 220,
      render: (_: unknown, record: RsiLoop) => (
        <Space direction="vertical" size={0}>
          <Text>{record.dataset_name || `数据集 #${record.dataset_id}`}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {record.scenario_name || `场景 #${record.scenario_id}`}
          </Text>
        </Space>
      ),
    },
    {
      title: '目标',
      key: 'objective',
      width: 210,
      render: (_: unknown, record: RsiLoop) => (
        <Space direction="vertical" size={0}>
          <Text>
            {record.objective_mode === 'metric_mean'
              ? `均值 · ${record.objective_metric || '-'}`
              : '冻结阈值通过率'}
          </Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {record.objective_target !== null && record.objective_target !== undefined
              ? `目标值 ${(record.objective_target * 100).toFixed(1)}%`
              : '未设置目标值'}
          </Text>
        </Space>
      ),
    },
    {
      title: '轮次 / 预算',
      key: 'budget',
      width: 220,
      render: (_: unknown, record: RsiLoop) => {
        const maxIterations = record.budget?.max_iterations || 3;
        const maxCalls = record.budget?.max_llm_calls || 300;
        const usedCalls = record.usage?.llm_calls || 0;
        return (
          <Space direction="vertical" size={2} style={{ width: '100%' }}>
            <Text>
              第 {record.current_iteration || 0} / {maxIterations} 轮
            </Text>
            <Progress
              percent={Math.min(100, Math.round((usedCalls / Math.max(maxCalls, 1)) * 100))}
              size="small"
              format={() => `${usedCalls}/${maxCalls} 调用`}
            />
          </Space>
        );
      },
    },
    {
      title: '最优增益',
      key: 'gain',
      width: 110,
      render: (_: unknown, record: RsiLoop) => {
        const gain = record.best_gain ?? record.best_iteration?.objective_gain;
        return (
          <Text type={typeof gain === 'number' && gain < 0 ? 'danger' : 'success'}>
            {formatGain(gain)}
          </Text>
        );
      },
    },
    {
      title: '最近决策',
      key: 'decision',
      width: 180,
      render: (_: unknown, record: RsiLoop) => (
        <Space direction="vertical" size={0}>
          <Text>{record.latest_iteration?.decision || '-'}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {record.latest_iteration?.decision_reason?.slice(0, 40) || '-'}
          </Text>
        </Space>
      ),
    },
    {
      title: '创建时间',
      key: 'created_at',
      width: 170,
      render: (_: unknown, record: RsiLoop) => formatTime(record.created_at),
    },
    {
      title: '操作',
      key: 'actions',
      width: 170,
      render: (_: unknown, record: RsiLoop) => (
        <Space size={4}>
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => navigate(`/rsi/${record.id}`)}
          >
            详情
          </Button>
          {record.status === 'draft' && (
            <Button
              type="link"
              size="small"
              icon={<PlayCircleOutlined />}
              onClick={() => handleStart(record)}
            >
              启动
            </Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 16 }}>
        <div>
          <Title level={4} style={{ marginBottom: 4 }}>
            RSI 自进化
          </Title>
          <Text type="secondary">
            以已完成评测为基线，自动完成失败归因、白名单提案、影子回归与人工审批写回。
          </Text>
        </div>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => fetchLoops(page, pageSize)}>
            刷新
          </Button>
          <Button
            type="primary"
            icon={<RobotOutlined />}
            onClick={() => {
              setBaselineEvalId(null);
              setCreateOpen(true);
            }}
          >
            创建循环
          </Button>
        </Space>
      </Space>

      <Card style={{ marginBottom: 16 }}>
        <Space wrap>
          <Input.Search
            placeholder="搜索循环名称"
            allowClear
            style={{ width: 240 }}
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            onSearch={() => fetchLoops(1, pageSize)}
          />
          <Select
            allowClear
            placeholder="状态"
            style={{ width: 170 }}
            value={status}
            onChange={(value) => setStatus(value)}
            options={Object.entries(loopStatusMeta).map(([value, meta]) => ({
              value,
              label: meta.label,
            }))}
          />
          <Select
            allowClear
            showSearch
            optionFilterProp="label"
            placeholder="场景"
            style={{ width: 220 }}
            value={scenarioId}
            onChange={(value) => setScenarioId(value)}
            options={scenarios.map((item) => ({ value: item.id, label: item.name }))}
          />
        </Space>
      </Card>

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="安全约束"
        description="Patch 白名单 + before_value 漂移校验；默认人工审批；写回前先保存版本快照；同场景只允许一个 running / awaiting_review 循环；预算耗尽会自动停止；归因与提案只读 train 切片。"
      />

      <Card>
        <Table
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={loops}
          scroll={{ x: 1500 }}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            showTotal: (count) => `共 ${count} 个循环`,
            onChange: (nextPage, nextPageSize) => fetchLoops(nextPage, nextPageSize),
          }}
          locale={{ emptyText: '暂无 RSI 循环，可从已完成评测创建' }}
        />
      </Card>

      <RsiCreateModal
        open={createOpen}
        baselineEvalId={baselineEvalId}
        onClose={() => setCreateOpen(false)}
        onCreated={(loop) => {
          setCreateOpen(false);
          navigate(`/rsi/${loop.id}`);
        }}
      />
    </div>
  );
};

export default RsiLoopListPage;
