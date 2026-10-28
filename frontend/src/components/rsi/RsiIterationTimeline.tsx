import React from 'react';
import { Card, Empty, Space, Tag, Timeline, Typography } from 'antd';
import type { RsiIterationBrief } from '../../types';
import {
  decisionMeta,
  formatDuration,
  formatGain,
  formatTime,
  iterationStatusMeta,
} from './rsiUtils';

const { Text } = Typography;

interface RsiIterationTimelineProps {
  iterations: RsiIterationBrief[];
  selectedId?: number | null;
  onSelect: (iterationId: number) => void;
}

const RsiIterationTimeline: React.FC<RsiIterationTimelineProps> = ({
  iterations,
  selectedId,
  onSelect,
}) => {
  if (!iterations.length) {
    return <Empty description="循环尚未产生迭代记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  }

  return (
    <Timeline
      items={iterations.map((item) => {
        const status = iterationStatusMeta[item.status] || {
          color: 'default',
          label: item.status,
        };
        const decision = item.decision ? decisionMeta[item.decision] : undefined;
        const selected = selectedId === item.id;
        return {
          color: status.color === 'processing' ? 'blue' : status.color,
          children: (
            <Card
              size="small"
              hoverable
              onClick={() => onSelect(item.id)}
              style={{
                borderColor: selected ? '#1677ff' : undefined,
                boxShadow: selected ? '0 0 0 2px rgba(22, 119, 255, 0.12)' : undefined,
              }}
            >
              <Space direction="vertical" size={4} style={{ width: '100%' }}>
                <Space wrap size={6}>
                  <Text strong>第 {item.iteration_index} 轮</Text>
                  <Tag color={status.color}>{status.label}</Tag>
                  {decision && <Tag color={decision.color}>{decision.label}</Tag>}
                  {item.objective_gain !== null && item.objective_gain !== undefined && (
                    <Text type={item.objective_gain >= 0 ? 'success' : 'danger'}>
                      目标增益 {formatGain(item.objective_gain)}
                    </Text>
                  )}
                </Space>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {item.decision_reason || item.error_message || '等待执行'}
                </Text>
                <Space wrap size={12}>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    开始 {formatTime(item.started_at)}
                  </Text>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    耗时 {formatDuration(item.started_at, item.finished_at)}
                  </Text>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    LLM 调用 {item.cost?.llm_calls ?? 0} 次
                  </Text>
                  {item.candidate_eval_id && (
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      候选评测 #{item.candidate_eval_id}
                    </Text>
                  )}
                </Space>
              </Space>
            </Card>
          ),
        };
      })}
    />
  );
};

export default RsiIterationTimeline;
