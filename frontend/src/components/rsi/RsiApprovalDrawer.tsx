import React, { useEffect, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Drawer,
  Input,
  Modal,
  Space,
  Switch,
  Tag,
  Typography,
  message,
} from 'antd';
import { CheckOutlined, CloseOutlined } from '@ant-design/icons';
import type { RsiIteration, RsiLoop } from '../../types';
import RsiProposalDiff from './RsiProposalDiff';
import RsiMetricsCompare from './RsiMetricsCompare';
import {
  decisionMeta,
  formatGain,
  iterationStatusMeta,
} from './rsiUtils';

const { Text, Paragraph } = Typography;

interface RsiApprovalDrawerProps {
  open: boolean;
  loop: RsiLoop | null;
  iteration: RsiIteration | null;
  submitting?: boolean;
  previewingId?: number | null;
  onClose: () => void;
  onApprove: (resume: boolean) => void;
  onReject: (reason: string, resume: boolean) => void;
  onPreview: (proposalId: number) => void;
}

const RsiApprovalDrawer: React.FC<RsiApprovalDrawerProps> = ({
  open,
  loop,
  iteration,
  submitting,
  previewingId,
  onClose,
  onApprove,
  onReject,
  onPreview,
}) => {
  const [resume, setResume] = useState(true);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState('');

  useEffect(() => {
    if (open) {
      setResume(true);
      setRejectReason('');
    }
  }, [open]);

  const metrics = iteration?.metrics;
  const judge = metrics?.decision_metrics;
  const decision = judge?.decision ? decisionMeta[judge.decision] : undefined;
  const status = iteration ? iterationStatusMeta[iteration.status] : undefined;
  const pending = Boolean(
    iteration
      && loop
      && iteration.status === 'reviewing'
      && loop.status === 'awaiting_review'
      && judge?.decision !== 'rejected',
  );

  const handleApprove = () => {
    if (!iteration) return;
    Modal.confirm({
      title: '确认采纳本轮提案并写回配置？',
      content: (
        <Space direction="vertical" size={6}>
          <Text>写回前会重新校验 before_value 漂移；任一配置已被人工改动则会中止写回。</Text>
          <Text>每个配置项会先保存版本快照，再写入新值。</Text>
          <Text type="secondary">采纳后{resume ? '继续下一轮迭代。' : '停止循环。'}</Text>
        </Space>
      ),
      okText: '确认写回',
      cancelText: '取消',
      onOk: () => onApprove(resume),
    });
  };

  const handleReject = () => {
    if (!rejectReason.trim()) {
      message.warning('请填写驳回理由');
      return;
    }
    onReject(rejectReason.trim(), resume);
    setRejectOpen(false);
  };

  return (
    <Drawer
      title={
        iteration ? (
          <Space wrap>
            <span>第 {iteration.iteration_index} 轮审批</span>
            {status && <Tag color={status.color}>{status.label}</Tag>}
            {decision && <Tag color={decision.color}>{decision.label}</Tag>}
          </Space>
        ) : (
          'RSI 迭代审批'
        )
      }
      width={980}
      open={open}
      onClose={onClose}
      destroyOnClose
      footer={
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <Space>
            <Text type="secondary">采纳 / 驳回后继续下一轮</Text>
            <Switch checked={resume} onChange={setResume} disabled={!pending} />
          </Space>
          <Space>
            <Button onClick={onClose}>关闭</Button>
            <Button
              danger
              icon={<CloseOutlined />}
              disabled={!pending}
              onClick={() => setRejectOpen(true)}
            >
              驳回
            </Button>
            <Button
              type="primary"
              icon={<CheckOutlined />}
              disabled={!pending}
              loading={submitting}
              onClick={handleApprove}
            >
              采纳并写回
            </Button>
          </Space>
        </Space>
      }
    >
      {!iteration ? (
        <Alert type="info" showIcon message="请选择一轮迭代查看详情" />
      ) : (
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <Alert
            type={judge?.decision === 'accepted' ? 'success' : judge?.decision === 'rejected' ? 'error' : 'warning'}
            showIcon
            message={`系统判定：${decision?.label || '未判定'}`}
            description={judge?.reason || iteration.decision_reason || '暂无判定理由'}
          />

          <Descriptions bordered size="small" column={3}>
            <Descriptions.Item label="目标增益">
              {formatGain(judge?.objective?.gain ?? iteration.objective_gain)}
            </Descriptions.Item>
            <Descriptions.Item label="目标口径">
              {loop?.objective_mode === 'metric_mean'
                ? `指标均值（${loop?.objective_metric || '-'}）`
                : '冻结参考阈值通过率'}
            </Descriptions.Item>
            <Descriptions.Item label="Fitness">
              {judge?.fitness !== undefined && judge?.fitness !== null
                ? judge.fitness.toFixed(3)
                : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="Holdout">
              {judge?.holdout?.enabled
                ? `${judge.holdout.rows ?? 0} 行（train ${judge.holdout.train_rows ?? 0} 行）`
                : '未启用或样本不足'}
            </Descriptions.Item>
            <Descriptions.Item label="自动采纳资格">
              {judge?.auto_accept_eligible ? <Tag color="green">满足</Tag> : <Tag>不满足</Tag>}
            </Descriptions.Item>
            <Descriptions.Item label="候选评测">
              {iteration.candidate_eval_id ? `#${iteration.candidate_eval_id}` : '-'}
            </Descriptions.Item>
          </Descriptions>

          {!!judge?.violations?.length && (
            <Alert
              type="error"
              showIcon
              message="验收约束未通过"
              description={judge.violations.join('；')}
            />
          )}

          <Card size="small" title="双评估指标对比（阈值无关口径）">
            <RsiMetricsCompare metrics={metrics} />
          </Card>

          {!!judge?.constraints?.length && (
            <Card size="small" title="约束检查">
              <Space direction="vertical" size={4}>
                {judge.constraints.map((check) => (
                  <Space key={check.name} size={8} wrap>
                    <Tag color={check.ok ? 'green' : 'red'}>{check.ok ? '通过' : '未通过'}</Tag>
                    <Text>{check.name}</Text>
                    <Text type="secondary">{check.detail}</Text>
                  </Space>
                ))}
              </Space>
            </Card>
          )}

          <Card size="small" title="提案 diff 与证据">
            <RsiProposalDiff
              proposals={iteration.proposals || []}
              onPreview={onPreview}
              previewingId={previewingId}
            />
          </Card>

          <Alert
            type="info"
            showIcon
            message="影响面与回滚"
            description="写回只修改白名单字段，并记录 rsi_config_versions 快照；如指标被多个场景引用，请确认变更对其它场景的影响。详情页支持按迭代一键回滚。"
          />
        </Space>
      )}

      <Modal
        title="驳回本轮提案"
        open={rejectOpen}
        okText="确认驳回"
        cancelText="取消"
        okButtonProps={{ danger: true }}
        onOk={handleReject}
        onCancel={() => setRejectOpen(false)}
      >
        <Paragraph type="secondary">
          驳回会保留候选评估与日志用于审计，不写回任何配置。{resume ? '驳回后继续下一轮。' : '驳回后停止循环。'}
        </Paragraph>
        <Input.TextArea
          rows={4}
          maxLength={2000}
          showCount
          placeholder="请填写驳回理由"
          value={rejectReason}
          onChange={(event: React.ChangeEvent<HTMLTextAreaElement>) =>
            setRejectReason(event.target.value)
          }
        />
      </Modal>
    </Drawer>
  );
};

export default RsiApprovalDrawer;
