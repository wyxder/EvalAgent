import React from 'react';
import { Button, Space, Table, Tag, Typography } from 'antd';
import { ExperimentOutlined } from '@ant-design/icons';
import type { RsiProposal } from '../../types';
import { formatValue, proposalStatusMeta, riskMeta } from './rsiUtils';

const { Text, Paragraph } = Typography;

interface RsiProposalDiffProps {
  proposals: RsiProposal[];
  onPreview?: (proposalId: number) => void;
  previewingId?: number | null;
}

const valueBlock = (value: unknown, tone: 'before' | 'after') => (
  <pre
    style={{
      margin: 0,
      padding: 8,
      borderRadius: 6,
      fontSize: 12,
      lineHeight: 1.5,
      maxHeight: 160,
      overflow: 'auto',
      whiteSpace: 'pre-wrap',
      wordBreak: 'break-word',
      background: tone === 'before' ? '#fafafa' : '#f6ffed',
      border: `1px solid ${tone === 'before' ? '#f0f0f0' : '#d9f7be'}`,
    }}
  >
    {formatValue(value)}
  </pre>
);

const RsiProposalDiff: React.FC<RsiProposalDiffProps> = ({
  proposals,
  onPreview,
  previewingId,
}) => {
  const columns = [
    {
      title: '配置项',
      key: 'target',
      width: 230,
      render: (_: unknown, record: RsiProposal) => (
        <Space direction="vertical" size={2}>
          <Text strong>{record.field}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {record.target_type}
            {record.target_id ? ` #${record.target_id}` : ''} · {record.operation}
          </Text>
        </Space>
      ),
    },
    {
      title: '变更前',
      key: 'before',
      width: 300,
      render: (_: unknown, record: RsiProposal) => valueBlock(record.before_value, 'before'),
    },
    {
      title: '变更后',
      key: 'after',
      width: 300,
      render: (_: unknown, record: RsiProposal) => valueBlock(record.after_value, 'after'),
    },
    {
      title: '风险 / 状态',
      key: 'risk',
      width: 150,
      render: (_: unknown, record: RsiProposal) => {
        const risk = riskMeta[record.risk_level || 'medium'] || riskMeta.medium;
        const status = proposalStatusMeta[record.status] || {
          color: 'default',
          label: record.status,
        };
        return (
          <Space direction="vertical" size={4}>
            <Tag color={risk.color}>{risk.label}</Tag>
            <Tag color={status.color}>{status.label}</Tag>
            {record.requires_review && <Tag color="gold">需人工审批</Tag>}
          </Space>
        );
      },
    },
    ...(onPreview
      ? [
          {
            title: '操作',
            key: 'actions',
            width: 110,
            render: (_: unknown, record: RsiProposal) => (
              <Button
                size="small"
                type="link"
                icon={<ExperimentOutlined />}
                disabled={record.status !== 'validated'}
                loading={previewingId === record.id}
                onClick={() => onPreview(record.id)}
              >
                沙盒预览
              </Button>
            ),
          },
        ]
      : []),
  ];

  return (
    <Table
      rowKey="id"
      size="small"
      columns={columns}
      dataSource={proposals}
      pagination={false}
      scroll={{ x: 1000 }}
      locale={{ emptyText: '本轮没有通过校验的提案' }}
      expandable={{
        expandedRowRender: (record) => (
          <Space direction="vertical" size={6} style={{ padding: '4px 0' }}>
            <Text strong>变更理由</Text>
            <Paragraph style={{ margin: 0 }}>{record.rationale || '未提供理由'}</Paragraph>
            <Text strong>证据</Text>
            <pre
              style={{
                margin: 0,
                padding: 8,
                borderRadius: 6,
                background: '#fafafa',
                fontSize: 12,
                maxHeight: 160,
                overflow: 'auto',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              {formatValue(record.evidence)}
            </pre>
          </Space>
        ),
      }}
    />
  );
};

export default RsiProposalDiff;
