import React from 'react';
import { Card, Empty, Space, Typography } from 'antd';
import type { RsiIterationBrief } from '../../types';
import { formatGain, formatPercent } from './rsiUtils';

const { Text } = Typography;

interface RsiTrendChartProps {
  iterations: RsiIterationBrief[];
}

const WIDTH = 660;
const HEIGHT = 220;
const PADDING = { left: 48, right: 18, top: 18, bottom: 30 };

const RsiTrendChart: React.FC<RsiTrendChartProps> = ({ iterations }) => {
  const points = iterations
    .filter((item) => item.status !== 'pending')
    .map((item) => ({
      label: `第 ${item.iteration_index} 轮`,
      gain: typeof item.objective_gain === 'number' ? item.objective_gain : null,
      passRate: typeof item.holdout_pass_rate === 'number' ? item.holdout_pass_rate : null,
    }));

  const gains = points
    .map((item) => item.gain)
    .filter((value): value is number => value !== null);
  const passRates = points
    .map((item) => item.passRate)
    .filter((value): value is number => value !== null);

  if (!gains.length && !passRates.length) {
    return (
      <Card size="small" title="趋势（P1）">
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="完成至少一轮影子回归后展示目标增益与 holdout 通过率趋势"
        />
      </Card>
    );
  }

  const plotWidth = WIDTH - PADDING.left - PADDING.right;
  const plotHeight = HEIGHT - PADDING.top - PADDING.bottom;
  const minGain = Math.min(0, ...gains);
  const maxGain = Math.max(0, ...gains);
  const gainSpan = maxGain - minGain || 1;

  const x = (index: number) =>
    PADDING.left + (points.length <= 1 ? plotWidth / 2 : (index / (points.length - 1)) * plotWidth);
  const yGain = (value: number) =>
    PADDING.top + plotHeight - ((value - minGain) / gainSpan) * plotHeight;
  const yPass = (value: number) => PADDING.top + plotHeight - value * plotHeight;

  const line = (values: (number | null)[], mapY: (value: number) => number) =>
    values
      .map((value, index) => (value === null ? null : `${x(index)},${mapY(value)}`))
      .filter((item): item is string => Boolean(item))
      .join(' ');

  const gainLine = line(points.map((item) => item.gain), yGain);
  const passLine = line(points.map((item) => item.passRate), yPass);
  const latestGain = gains.length ? gains[gains.length - 1] : null;
  const latestPass = passRates.length ? passRates[passRates.length - 1] : null;

  return (
    <Card
      size="small"
      title="趋势（P1）"
      extra={
        <Space size={16}>
          <Text style={{ color: '#fa8c16' }}>目标增益 {formatGain(latestGain)}</Text>
          <Text style={{ color: '#1677ff' }}>Holdout 通过率 {formatPercent(latestPass)}</Text>
        </Space>
      }
    >
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        style={{ width: '100%', height: 'auto', display: 'block' }}
        role="img"
        aria-label="RSI 迭代趋势图"
      >
        {[0, 0.25, 0.5, 0.75, 1].map((tick) => (
          <g key={tick}>
            <line
              x1={PADDING.left}
              x2={WIDTH - PADDING.right}
              y1={PADDING.top + plotHeight * tick}
              y2={PADDING.top + plotHeight * tick}
              stroke="#f0f0f0"
              strokeWidth={1}
            />
            <text
              x={PADDING.left - 8}
              y={PADDING.top + plotHeight * tick + 4}
              textAnchor="end"
              fontSize={11}
              fill="#8c8c8c"
            >
              {formatPercent(1 - tick, 0)}
            </text>
          </g>
        ))}

        {maxGain > 0 && (
          <line
            x1={PADDING.left}
            x2={WIDTH - PADDING.right}
            y1={yGain(0)}
            y2={yGain(0)}
            stroke="#d9d9d9"
            strokeDasharray="4 4"
          />
        )}

        {passLine && (
          <polyline points={passLine} fill="none" stroke="#1677ff" strokeWidth={2} />
        )}
        {gainLine && (
          <polyline points={gainLine} fill="none" stroke="#fa8c16" strokeWidth={2} />
        )}

        {points.map((item, index) => (
          <g key={item.label}>
            <line
              x1={x(index)}
              x2={x(index)}
              y1={PADDING.top + plotHeight}
              y2={PADDING.top + plotHeight + 4}
              stroke="#d9d9d9"
            />
            <text
              x={x(index)}
              y={HEIGHT - 8}
              textAnchor="middle"
              fontSize={11}
              fill="#8c8c8c"
            >
              {item.label}
            </text>
            {item.passRate !== null && (
              <circle cx={x(index)} cy={yPass(item.passRate)} r={3.5} fill="#1677ff">
                <title>{`${item.label} holdout 通过率 ${formatPercent(item.passRate)}`}</title>
              </circle>
            )}
            {item.gain !== null && (
              <circle cx={x(index)} cy={yGain(item.gain)} r={3.5} fill="#fa8c16">
                <title>{`${item.label} 目标增益 ${formatGain(item.gain)}`}</title>
              </circle>
            )}
            {item.gain !== null && (
              <text
                x={x(index)}
                y={yGain(item.gain) - 8}
                textAnchor="middle"
                fontSize={11}
                fill="#fa8c16"
              >
                {formatGain(item.gain)}
              </text>
            )}
          </g>
        ))}
      </svg>
    </Card>
  );
};

export default RsiTrendChart;
