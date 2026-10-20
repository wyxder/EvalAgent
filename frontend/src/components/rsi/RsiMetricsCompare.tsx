import React from 'react';
import { Table } from 'antd';
import type { RsiMetricsDelta } from '../../types';
import { formatGain, formatPercent } from './rsiUtils';

interface RsiMetricsCompareProps {
  metrics?: RsiMetricsDelta | null;
  size?: 'small' | 'middle';
}

const RsiMetricsCompare: React.FC<RsiMetricsCompareProps> = ({ metrics, size = 'small' }) => {
  const rows = [
    { key: 'full', label: '全量数据集', data: metrics },
    { key: 'train', label: 'Train 切片', data: metrics?.train },
    { key: 'holdout', label: 'Holdout 切片', data: metrics?.holdout },
  ].map((item) => ({
    key: item.key,
    label: item.label,
    baselineRate: item.data?.baseline?.pass_rate,
    candidateRate: item.data?.candidate?.pass_rate,
    baselineError: item.data?.baseline?.error_rate,
    candidateError: item.data?.candidate?.error_rate,
    baselineTotal: item.data?.baseline?.total,
    candidateTotal: item.data?.candidate?.total,
  }));

  return (
    <Table
      rowKey="key"
      size={size}
      pagination={false}
      dataSource={rows}
      columns={[
        { title: '切片', dataIndex: 'label', key: 'label', width: 130 },
        {
          title: '样本数（基线 / 候选）',
          key: 'total',
          width: 170,
          render: (_: unknown, row: any) => `${row.baselineTotal ?? '-'} / ${row.candidateTotal ?? '-'}`,
        },
        {
          title: '通过率（基线）',
          key: 'baseRate',
          render: (_: unknown, row: any) => formatPercent(row.baselineRate),
        },
        {
          title: '通过率（候选）',
          key: 'candRate',
          render: (_: unknown, row: any) => formatPercent(row.candidateRate),
        },
        {
          title: '通过率变化',
          key: 'rateDelta',
          render: (_: unknown, row: any) =>
            typeof row.baselineRate === 'number' && typeof row.candidateRate === 'number'
              ? formatGain(row.candidateRate - row.baselineRate)
              : '-',
        },
        {
          title: '错误率（基线 → 候选）',
          key: 'error',
          render: (_: unknown, row: any) =>
            `${formatPercent(row.baselineError)} → ${formatPercent(row.candidateError)}`,
        },
      ]}
    />
  );
};

export default RsiMetricsCompare;
