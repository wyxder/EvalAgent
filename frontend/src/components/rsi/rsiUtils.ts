export interface StatusMeta {
  color: string;
  label: string;
}

export const loopStatusMeta: Record<string, StatusMeta> = {
  draft: { color: 'default', label: '草稿' },
  running: { color: 'processing', label: '运行中' },
  awaiting_review: { color: 'gold', label: '待审批' },
  completed: { color: 'success', label: '已完成' },
  failed: { color: 'error', label: '失败' },
  cancelled: { color: 'default', label: '已取消' },
};

export const iterationStatusMeta: Record<string, StatusMeta> = {
  pending: { color: 'default', label: '排队中' },
  diagnosing: { color: 'processing', label: '失败归因' },
  proposing: { color: 'processing', label: '生成提案' },
  validating: { color: 'processing', label: 'Patch 校验' },
  evaluating: { color: 'processing', label: '影子回归' },
  reviewing: { color: 'gold', label: '待审批' },
  accepted: { color: 'success', label: '已采纳' },
  rejected: { color: 'error', label: '已驳回' },
  failed: { color: 'error', label: '失败' },
  rolled_back: { color: 'default', label: '已回滚' },
};

export const decisionMeta: Record<string, StatusMeta> = {
  accepted: { color: 'success', label: '建议采纳' },
  rejected: { color: 'error', label: '建议拒绝' },
  inconclusive: { color: 'warning', label: '证据不足' },
  rolled_back: { color: 'default', label: '已回滚' },
};

export const proposalStatusMeta: Record<string, StatusMeta> = {
  proposed: { color: 'default', label: '已生成' },
  validated: { color: 'processing', label: '校验通过' },
  rejected: { color: 'error', label: '已拒绝' },
  applied: { color: 'success', label: '已写回' },
  rolled_back: { color: 'default', label: '已回滚' },
};

export const riskMeta: Record<string, StatusMeta> = {
  low: { color: 'green', label: '低风险' },
  medium: { color: 'orange', label: '中风险' },
  high: { color: 'red', label: '高风险' },
};

export const severityMeta: Record<string, StatusMeta> = {
  low: { color: 'default', label: '低' },
  medium: { color: 'orange', label: '中' },
  high: { color: 'red', label: '高' },
};

export const formatPercent = (value?: number | null, digits = 1) =>
  value === null || value === undefined || Number.isNaN(value)
    ? '-'
    : `${(value * 100).toFixed(digits)}%`;

export const formatGain = (value?: number | null) =>
  value === null || value === undefined || Number.isNaN(value)
    ? '-'
    : `${value >= 0 ? '+' : ''}${(value * 100).toFixed(1)}%`;

export const formatTime = (value?: string | null) =>
  value ? new Date(value).toLocaleString('zh-CN') : '-';

export const formatDuration = (startedAt?: string | null, finishedAt?: string | null) => {
  if (!startedAt) return '-';
  const start = new Date(startedAt).getTime();
  const end = finishedAt ? new Date(finishedAt).getTime() : Date.now();
  if (Number.isNaN(start) || Number.isNaN(end) || end < start) return '-';
  const seconds = Math.round((end - start) / 1000);
  if (seconds < 60) return `${seconds} 秒`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes} 分 ${seconds % 60} 秒`;
};

export const formatValue = (value: unknown): string => {
  if (value === null || value === undefined) return '（空）';
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
};
