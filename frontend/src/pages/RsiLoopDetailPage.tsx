import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Empty,
  InputNumber,
  Modal,
  Progress,
  Row,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
  message,
} from 'antd';
import {
  ArrowLeftOutlined,
  ExperimentOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  RollbackOutlined,
  StopOutlined,
} from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import type {
  RsiConfigVersion,
  RsiIteration,
  RsiIterationBrief,
  RsiLoop,
} from '../types';
import * as api from '../services/api';
import RsiApprovalDrawer from '../components/rsi/RsiApprovalDrawer';
import RsiDiagnosisPanel from '../components/rsi/RsiDiagnosisPanel';
import RsiIterationTimeline from '../components/rsi/RsiIterationTimeline';
import RsiMetricsCompare from '../components/rsi/RsiMetricsCompare';
import RsiProposalDiff from '../components/rsi/RsiProposalDiff';
import RsiTrendChart from '../components/rsi/RsiTrendChart';
import {
  decisionMeta,
  formatGain,
  formatPercent,
  formatTime,
  iterationStatusMeta,
  loopStatusMeta,
} from '../components/rsi/rsiUtils';

const { Title, Text } = Typography;
const ACTIVE_STATUSES = ['running', 'awaiting_review'];

const RsiLoopDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const loopId = Number(id);
  const navigate = useNavigate();

  const [loop, setLoop] = useState<RsiLoop | null>(null);
  const [iterations, setIterations] = useState<RsiIterationBrief[]>([]);
  const [selectedIterationId, setSelectedIterationId] = useState<number | null>(null);
  const [iterationDetail, setIterationDetail] = useState<RsiIteration | null>(null);
  const [logs, setLogs] = useState('');
  const [versions, setVersions] = useState<RsiConfigVersion[]>([]);
  const [activeTab, setActiveTab] = useState('timeline');
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [previewingId, setPreviewingId] = useState<number | null>(null);
  const [approvalOpen, setApprovalOpen] = useState(false);
  const [rollbackOpen, setRollbackOpen] = useState(false);
  const [rollbackIterationId, setRollbackIterationId] = useState<number | null>(null);

  const loadLoop = useCallback(
    async (silent = false) => {
      if (!Number.isFinite(loopId)) return;
      if (!silent) setLoading(true);
      try {
        const [loopData, iterationData] = await Promise.all([
          api.getRsiLoop(loopId),
          api.listRsiIterations(loopId),
        ]);
        setLoop(loopData as RsiLoop);
        const items = (iterationData.items || []) as RsiIterationBrief[];
        setIterations(items);
        setSelectedIterationId((current) => {
          if (current && items.some((item) => item.id === current)) return current;
          return items.length ? items[items.length - 1].id : null;
        });
      } catch (error: any) {
        const detail = error?.response?.data?.detail;
        message.error(typeof detail === 'string' ? detail : '加载 RSI 循环失败');
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [loopId],
  );

  const loadIteration = useCallback(async (iterationId: number) => {
    try {
      const data = (await api.getRsiIteration(iterationId)) as RsiIteration;
      setIterationDetail(data);
    } catch {
      setIterationDetail(null);
    }
  }, []);

  const loadLogs = useCallback(async () => {
    if (!Number.isFinite(loopId)) return;
    try {
      const data = await api.getRsiLoopLogs(loopId);
      setLogs(data.logs || '');
    } catch {
      // keep the previous log content on transient failures
    }
  }, [loopId]);

  const loadVersions = useCallback(async () => {
    if (!Number.isFinite(loopId)) return;
    try {
      const data = await api.listRsiLoopVersions(loopId);
      setVersions((data.items || []) as RsiConfigVersion[]);
    } catch {
      setVersions([]);
    }
  }, [loopId]);

  useEffect(() => {
    loadLoop();
    loadLogs();
  }, [loadLoop, loadLogs]);

  useEffect(() => {
    if (selectedIterationId) {
      loadIteration(selectedIterationId);
    } else {
      setIterationDetail(null);
    }
  }, [selectedIterationId, loadIteration]);

  useEffect(() => {
    if (!loop || !ACTIVE_STATUSES.includes(loop.status)) return;
    const interval = loop.status === 'running' ? 2000 : 3000;
    const timer = window.setInterval(() => {
      loadLoop(true);
      if (selectedIterationId) {
        loadIteration(selectedIterationId);
      }
    }, interval);
    return () => window.clearInterval(timer);
  }, [loop, selectedIterationId, loadLoop, loadIteration]);

  useEffect(() => {
    if (loop?.status !== 'running') return;
    const timer = window.setInterval(loadLogs, 1000);
    return () => window.clearInterval(timer);
  }, [loop?.status, loadLogs]);

  useEffect(() => {
    if (activeTab === 'versions') {
      loadVersions();
    }
  }, [activeTab, loadVersions, loop?.status]);

  const acceptedIterations = useMemo(
    () => iterations.filter((item) => item.status === 'accepted'),
    [iterations],
  );

  const handleStart = () => {
    if (!loop) return;
    Modal.confirm({
      title: '启动 RSI 循环？',
      content: '引擎将串行执行归因 → 提案 → 影子回归 → 验收判定；默认在写回前等待人工审批。',
      okText: '启动',
      onOk: async () => {
        try {
          await api.startRsiLoop(loop.id);
          message.success('循环已启动');
          loadLoop(true);
          loadLogs();
        } catch (error: any) {
          message.error(error?.response?.data?.detail || '启动失败');
        }
      },
    });
  };

  const handleCancel = () => {
    if (!loop) return;
    Modal.confirm({
      title: '取消当前循环？',
      content: '取消会终止当前候选评估，已写入的配置不会自动回滚；如需恢复请使用回滚。',
      okText: '取消循环',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await api.cancelRsiLoop(loop.id);
          message.success('循环已取消');
          loadLoop(true);
        } catch (error: any) {
          message.error(error?.response?.data?.detail || '取消失败');
        }
      },
    });
  };

  const handleRollback = async () => {
    if (!loop || !rollbackIterationId) return;
    try {
      const result = await api.rollbackRsiLoop(loop.id, {
        iteration_id: rollbackIterationId,
        actor: 'human',
      });
      message.success(result.message || '回滚完成');
      setRollbackOpen(false);
      loadLoop(true);
      loadVersions();
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '回滚失败');
    }
  };

  const handleRestoreVersion = (version: RsiConfigVersion) => {
    Modal.confirm({
      title: `恢复配置版本 v${version.version}？`,
      content: '恢复会追加一条新版本记录，不会删除审计历史。',
      okText: '恢复',
      onOk: async () => {
        try {
          await api.restoreRsiVersion(version.id, 'human');
          message.success('配置已恢复');
          loadVersions();
          loadLoop(true);
        } catch (error: any) {
          message.error(error?.response?.data?.detail || '恢复失败');
        }
      },
    });
  };

  const handleHardCases = () => {
    if (!loop) return;
    Modal.confirm({
      title: '从最近一轮失败样本派生 hard-case 数据集？',
      content: '只写入 train 失败行，holdout 行会被跳过；原数据集不会被修改。',
      okText: '创建数据集',
      onOk: async () => {
        try {
          const result = await api.createRsiHardCases(loop.id, {});
          Modal.success({
            title: '已创建 hard-case 数据集',
            content: `${result.dataset_name}（#${result.dataset_id}），新增 ${result.created_rows} 行，跳过 holdout ${result.skipped_row_ids?.length || 0} 行。`,
            okText: '查看数据集',
            onOk: () => navigate(`/datasets/${result.dataset_id}`),
          });
        } catch (error: any) {
          message.error(error?.response?.data?.detail || '创建 hard-case 数据集失败');
        }
      },
    });
  };

  const handlePreview = async (proposalId: number) => {
    setPreviewingId(proposalId);
    try {
      const result = await api.previewRsiProposal(proposalId, {});
      Modal.info({
        title: '沙盒预览结果',
        width: 760,
        content: (
          <Space direction="vertical" size={8} style={{ width: '100%' }}>
            <Alert
              type={result.success ? 'success' : 'error'}
              showIcon
              message={result.message || (result.success ? '预览成功' : '预览失败')}
            />
            <Text>
              样本 #{result.row_id ?? '-'} · {result.is_pass ? '通过' : '未通过'}
            </Text>
            <pre
              style={{
                margin: 0,
                padding: 12,
                borderRadius: 6,
                background: '#fafafa',
                fontSize: 12,
                maxHeight: 320,
                overflow: 'auto',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              {JSON.stringify(result.metric_scores || {}, null, 2)}
            </pre>
            {!!result.warnings?.length && (
              <Alert type="warning" showIcon message={result.warnings.join('；')} />
            )}
            {!!result.errors?.length && (
              <Alert type="error" showIcon message={result.errors.join('；')} />
            )}
          </Space>
        ),
      });
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '沙盒预览失败');
    } finally {
      setPreviewingId(null);
    }
  };

  const handleApprove = async (resume: boolean) => {
    if (!iterationDetail) return;
    setSubmitting(true);
    try {
      await api.approveRsiIteration(iterationDetail.id, { actor: 'human', resume });
      message.success(resume ? '已采纳并继续迭代' : '已采纳并停止循环');
      setApprovalOpen(false);
      await loadLoop(true);
      await loadIteration(iterationDetail.id);
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '审批失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleReject = async (reason: string, resume: boolean) => {
    if (!iterationDetail) return;
    setSubmitting(true);
    try {
      await api.rejectRsiIteration(iterationDetail.id, {
        reason,
        actor: 'human',
        resume,
      });
      message.success(resume ? '已驳回并继续下一轮' : '已驳回并停止循环');
      setApprovalOpen(false);
      await loadLoop(true);
      await loadIteration(iterationDetail.id);
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '驳回失败');
    } finally {
      setSubmitting(false);
    }
  };

  if (!Number.isFinite(loopId)) {
    return <Alert type="error" showIcon message="无效的 RSI 循环 ID" />;
  }

  const status = loop ? loopStatusMeta[loop.status] : undefined;
  const budget = loop?.budget || {};
  const usage = loop?.usage || {};
  const maxCalls = budget.max_llm_calls || 300;
  const maxIterations = budget.max_iterations || 3;
  const judge = iterationDetail?.metrics?.decision_metrics;
  const decision = judge?.decision ? decisionMeta[judge.decision] : undefined;
  const iterationStatus = iterationDetail
    ? iterationStatusMeta[iterationDetail.status]
    : undefined;

  const tabItems = [
    {
      key: 'timeline',
      label: '迭代时间线',
      children: (
        <Row gutter={16}>
          <Col xs={24} lg={9}>
            <Card size="small" title="迭代时间线" loading={loading}>
              <RsiIterationTimeline
                iterations={iterations}
                selectedId={selectedIterationId}
                onSelect={setSelectedIterationId}
              />
            </Card>
          </Col>
          <Col xs={24} lg={15}>
            {iterationDetail ? (
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                <Card
                  size="small"
                  title={`第 ${iterationDetail.iteration_index} 轮详情`}
                  extra={
                    iterationDetail.status === 'reviewing' && loop?.status === 'awaiting_review' ? (
                      <Button type="primary" onClick={() => setApprovalOpen(true)}>
                        进入审批
                      </Button>
                    ) : undefined
                  }
                >
                  <Space wrap size={[8, 8]} style={{ marginBottom: 12 }}>
                    {iterationStatus && <Tag color={iterationStatus.color}>{iterationStatus.label}</Tag>}
                    {decision && <Tag color={decision.color}>{decision.label}</Tag>}
                    <Tag color="default">目标增益 {formatGain(iterationDetail.objective_gain)}</Tag>
                    <Tag color="blue">Holdout 通过率 {formatPercent(iterationDetail.holdout_pass_rate)}</Tag>
                    {iterationDetail.candidate_eval_id && (
                      <Tag color="purple">候选评测 #{iterationDetail.candidate_eval_id}</Tag>
                    )}
                  </Space>
                  <Descriptions size="small" column={2}>
                    <Descriptions.Item label="开始时间">
                      {formatTime(iterationDetail.started_at)}
                    </Descriptions.Item>
                    <Descriptions.Item label="结束时间">
                      {formatTime(iterationDetail.finished_at)}
                    </Descriptions.Item>
                    <Descriptions.Item label="LLM 调用">
                      {iterationDetail.cost?.llm_calls ?? 0} 次
                    </Descriptions.Item>
                    <Descriptions.Item label="Fitness">
                      {typeof judge?.fitness === 'number' ? judge.fitness.toFixed(3) : '-'}
                    </Descriptions.Item>
                  </Descriptions>
                  {(judge?.reason || iterationDetail.decision_reason) && (
                    <Alert
                      style={{ marginTop: 12 }}
                      type={judge?.decision === 'accepted' ? 'success' : judge?.decision === 'rejected' ? 'error' : 'warning'}
                      showIcon
                      message={judge?.reason || iterationDetail.decision_reason}
                    />
                  )}
                  {iterationDetail.error_message && (
                    <Alert
                      style={{ marginTop: 12 }}
                      type="error"
                      showIcon
                      message="迭代执行异常"
                      description={iterationDetail.error_message}
                    />
                  )}
                </Card>

                <RsiDiagnosisPanel diagnosis={iterationDetail.diagnosis} />

                <Card size="small" title="双评估指标对比（阈值无关口径）">
                  <RsiMetricsCompare metrics={iterationDetail.metrics} />
                </Card>

                <Card size="small" title="提案 diff 与证据">
                  <RsiProposalDiff
                    proposals={iterationDetail.proposals || []}
                    onPreview={handlePreview}
                    previewingId={previewingId}
                  />
                </Card>

                <RsiTrendChart iterations={iterations} />
              </Space>
            ) : (
              <Card size="small" loading={loading}>
                <Empty description="暂无迭代详情" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              </Card>
            )}
          </Col>
        </Row>
      ),
    },
    {
      key: 'logs',
      label: '运行日志',
      children: (
        <Card size="small" title="运行日志" extra={<Button size="small" onClick={loadLogs}>刷新日志</Button>}>
          <pre
            style={{
              margin: 0,
              minHeight: 320,
              maxHeight: 560,
              overflow: 'auto',
              padding: 12,
              background: '#0b1020',
              color: '#d6e4ff',
              borderRadius: 8,
              fontSize: 12,
              lineHeight: 1.6,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}
          >
            {logs || '暂无日志'}
          </pre>
        </Card>
      ),
    },
    {
      key: 'versions',
      label: `版本记录${versions.length ? `（${versions.length}）` : ''}`,
      children: (
        <Card size="small" title="配置版本（写回前快照）">
          <Table
            rowKey="id"
            size="small"
            dataSource={versions}
            pagination={false}
            locale={{ emptyText: '尚未写回任何配置' }}
            columns={[
              { title: '版本', key: 'version', width: 90, render: (_: unknown, record: RsiConfigVersion) => `v${record.version}` },
              { title: 'Scope', key: 'scope', width: 160, render: (_: unknown, record: RsiConfigVersion) => `${record.scope} #${record.scope_id}` },
              { title: '轮次', key: 'iteration', width: 90, render: (_: unknown, record: RsiConfigVersion) => record.iteration_id ? `#${record.iteration_id}` : '-' },
              { title: '操作人', dataIndex: 'actor', key: 'actor', width: 100 },
              { title: '创建时间', key: 'created_at', width: 180, render: (_: unknown, record: RsiConfigVersion) => formatTime(record.created_at) },
              {
                title: '状态',
                key: 'rolled',
                width: 110,
                render: (_: unknown, record: RsiConfigVersion) =>
                  record.rolled_back_at ? <Tag>已回滚</Tag> : <Tag color="green">生效快照</Tag>,
              },
              {
                title: '操作',
                key: 'actions',
                width: 110,
                render: (_: unknown, record: RsiConfigVersion) => (
                  <Button type="link" size="small" onClick={() => handleRestoreVersion(record)}>
                    恢复此版本
                  </Button>
                ),
              },
            ]}
          />
        </Card>
      ),
    },
  ];

  return (
    <div>
      <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 16 }} align="start">
        <Space align="start">
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/rsi')} />
          <div>
            <Space wrap size={8}>
              <Title level={4} style={{ margin: 0 }}>
                {loop?.name || `RSI 循环 #${loopId}`}
              </Title>
              {status && <Tag color={status.color}>{status.label}</Tag>}
            </Space>
            <Text type="secondary">
              #{loopId} · 基线评测 #{loop?.baseline_eval_id ?? '-'} · {loop?.dataset_name || `数据集 #${loop?.dataset_id ?? '-'}`}
            </Text>
          </div>
        </Space>
        <Space wrap>
          <Button icon={<ReloadOutlined />} onClick={() => { loadLoop(); loadLogs(); }}>
            刷新
          </Button>
          {loop?.status === 'draft' && (
            <Button type="primary" icon={<PlayCircleOutlined />} onClick={handleStart}>
              启动
            </Button>
          )}
          {loop && ACTIVE_STATUSES.includes(loop.status) && (
            <Button danger icon={<StopOutlined />} onClick={handleCancel}>
              取消
            </Button>
          )}
          {!!acceptedIterations.length && loop?.status !== 'running' && (
            <Button
              icon={<RollbackOutlined />}
              onClick={() => {
                setRollbackIterationId(acceptedIterations[acceptedIterations.length - 1].id);
                setRollbackOpen(true);
              }}
            >
              回滚
            </Button>
          )}
          <Button
            icon={<ExperimentOutlined />}
            disabled={!loop?.latest_iteration?.candidate_eval_id}
            onClick={handleHardCases}
          >
            沉淀 hard-case
          </Button>
        </Space>
      </Space>

      {loop?.error_message && (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          message="循环执行异常"
          description={loop.error_message}
        />
      )}

      <Card style={{ marginBottom: 16 }} loading={!loop && loading}>
        {loop && (
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <Descriptions size="small" column={4}>
              <Descriptions.Item label="目标口径">
                {loop.objective_mode === 'metric_mean'
                  ? `指标均值 · ${loop.objective_metric || '-'}`
                  : '冻结参考阈值通过率'}
              </Descriptions.Item>
              <Descriptions.Item label="目标值">
                {loop.objective_target !== null && loop.objective_target !== undefined
                  ? formatPercent(loop.objective_target)
                  : '未设置'}
              </Descriptions.Item>
              <Descriptions.Item label="最优增益">
                {formatGain(loop.best_gain ?? loop.best_iteration?.objective_gain)}
              </Descriptions.Item>
              <Descriptions.Item label="当前轮次">
                {loop.current_iteration || 0} / {maxIterations}
              </Descriptions.Item>
              <Descriptions.Item label="Judge">
                {loop.llm_model_name || `#${loop.llm_config_id}`}
              </Descriptions.Item>
              <Descriptions.Item label="提案模型">
                {loop.proposer_model_name || '同 Judge'}
              </Descriptions.Item>
              <Descriptions.Item label="创建时间">
                {formatTime(loop.created_at)}
              </Descriptions.Item>
              <Descriptions.Item label="自动采纳">
                {loop.auto_apply_low_risk ? <Tag color="orange">已开启</Tag> : <Tag>关闭</Tag>}
              </Descriptions.Item>
            </Descriptions>
            <Progress
              percent={Math.min(100, Math.round(((usage.llm_calls || 0) / Math.max(maxCalls, 1)) * 100))}
              status={loop.status === 'failed' ? 'exception' : loop.status === 'completed' ? 'success' : 'active'}
              format={() => `LLM 调用 ${usage.llm_calls || 0} / ${maxCalls}`}
            />
            <Text type="secondary" style={{ fontSize: 12 }}>
              Holdout：{loop.holdout_config?.holdout_ratio !== undefined
                ? `${Math.round((loop.holdout_config.holdout_ratio || 0) * 100)}%，最少 ${loop.holdout_config.min_rows ?? 10} 行`
                : '默认 30%'} · 评估次数 {usage.evaluations || 0}
            </Text>
          </Space>
        )}
      </Card>

      <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />

      <RsiApprovalDrawer
        open={approvalOpen}
        loop={loop}
        iteration={iterationDetail}
        submitting={submitting}
        previewingId={previewingId}
        onClose={() => setApprovalOpen(false)}
        onApprove={handleApprove}
        onReject={handleReject}
        onPreview={handlePreview}
      />

      <Modal
        title="回滚已采纳的迭代"
        open={rollbackOpen}
        okText="确认回滚"
        okButtonProps={{ danger: true }}
        onOk={handleRollback}
        onCancel={() => setRollbackOpen(false)}
      >
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <Alert
            type="warning"
            showIcon
            message="回滚只恢复该迭代写回的配置，并追加新的版本快照"
            description="正在运行的循环不能被回滚；回滚后循环的 best_iteration 与 baseline 会同步修正。"
          />
          <Select
            style={{ width: '100%' }}
            value={rollbackIterationId ?? undefined}
            onChange={setRollbackIterationId}
            options={acceptedIterations.map((item) => ({
              value: item.id,
              label: `第 ${item.iteration_index} 轮 · 目标增益 ${formatGain(item.objective_gain)}`,
            }))}
          />
          <Text type="secondary">
            如需按单个配置版本恢复，请在“版本记录”标签页操作。
          </Text>
        </Space>
      </Modal>
    </div>
  );
};

export default RsiLoopDetailPage;
