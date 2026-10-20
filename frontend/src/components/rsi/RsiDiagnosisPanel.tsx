import React from 'react';
import { Alert, Card, Empty, List, Space, Tag, Typography } from 'antd';
import type { RsiDiagnosis } from '../../types';
import { severityMeta } from './rsiUtils';

const { Text, Paragraph } = Typography;

interface RsiDiagnosisPanelProps {
  diagnosis?: RsiDiagnosis | null;
}

const RsiDiagnosisPanel: React.FC<RsiDiagnosisPanelProps> = ({ diagnosis }) => {
  if (!diagnosis) {
    return <Empty description="暂无归因结果" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  }
  const clusters = diagnosis.clusters || [];

  return (
    <Card
      size="small"
      title={
        <Space>
          <span>失败归因</span>
          <Tag color="blue">仅 train</Tag>
          {diagnosis.fallback ? <Tag color="orange">规则降级</Tag> : <Tag color="green">LLM 归因</Tag>}
        </Space>
      }
      extra={
        <Text type="secondary">
          train {diagnosis.train_rows ?? 0} 行 / 失败 {diagnosis.failed_rows ?? 0} 行
        </Text>
      }
    >
      {diagnosis.fallback && diagnosis.fallback_reason && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 12 }}
          message="已降级为规则归因"
          description={diagnosis.fallback_reason}
        />
      )}
      <Paragraph type="secondary" style={{ marginBottom: 12 }}>
        {diagnosis.summary || '暂无归因摘要'}
      </Paragraph>
      {clusters.length ? (
        <List
          size="small"
          dataSource={clusters}
          renderItem={(cluster) => {
            const severity = severityMeta[cluster.severity || 'medium'] || severityMeta.medium;
            return (
              <List.Item>
                <Space direction="vertical" size={2} style={{ width: '100%' }}>
                  <Space wrap size={6}>
                    <Text strong>{cluster.label || '未命名失败簇'}</Text>
                    <Tag>{cluster.root_cause_type || 'unknown'}</Tag>
                    {cluster.affected_metric && <Tag color="purple">{cluster.affected_metric}</Tag>}
                    <Tag color={severity.color}>严重度 {severity.label}</Tag>
                    <Tag color="default">{cluster.size ?? cluster.evidence_row_ids?.length ?? 0} 条证据</Tag>
                  </Space>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    建议杠杆：{cluster.suggested_lever || 'none'}
                  </Text>
                  {!!cluster.evidence_row_ids?.length && (
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      证据行：{cluster.evidence_row_ids.join(', ')}
                    </Text>
                  )}
                </Space>
              </List.Item>
            );
          }}
        />
      ) : (
        <Empty description="没有可归纳的失败簇" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      )}
    </Card>
  );
};

export default RsiDiagnosisPanel;
