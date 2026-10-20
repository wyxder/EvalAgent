import React, { useState } from 'react';
import { Tag } from 'antd';

interface RadarAxis {
  label: string;
  evalAgent: number;
  traditional: number;
  desc: string;
}

const RADAR_DATA: RadarAxis[] = [
  { label: '幻觉与忠实度', evalAgent: 96, traditional: 55, desc: '原生执行器 + 逐句事实归因，杜绝无据给分' },
  { label: '检索召回与重排', evalAgent: 95, traditional: 60, desc: '包含 HitRate@K/MRR 数学探针与上下文纯度' },
  { label: 'Agent工具参数校验', evalAgent: 98, traditional: 45, desc: '参数键值深层比对与死循环步骤效率检测' },
  { label: '多轮记忆连贯性', evalAgent: 92, traditional: 35, desc: '跨轮次滑窗知识继承与话题偏离防范' },
  { label: 'RSI配置自进化闭环', evalAgent: 97, traditional: 15, desc: '归因-提案-影子回归-冻结阈值验收-版本回滚' },
  { label: '双盲人工偏好对齐', evalAgent: 94, traditional: 30, desc: '随机混淆防偏置 A/B 投票与胜率雷达' },
];

export const LandingRadarChart: React.FC = () => {
  const [activeLayer, setActiveLayer] = useState<'both' | 'evalAgent' | 'traditional'>('both');
  const [hoveredAxis, setHoveredAxis] = useState<number | null>(null);

  const size = 360;
  const center = size / 2;
  const radius = center - 52;
  const totalAxes = RADAR_DATA.length;
  const angleStep = (Math.PI * 2) / totalAxes;

  // Calculate polygon points for a set of values
  const getPoints = (key: 'evalAgent' | 'traditional') => {
    return RADAR_DATA.map((item, i) => {
      const value = item[key] / 100;
      const angle = i * angleStep - Math.PI / 2;
      const x = center + radius * value * Math.cos(angle);
      const y = center + radius * value * Math.sin(angle);
      return `${x},${y}`;
    }).join(' ');
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <div style={{ marginBottom: 16, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <Tag
          color={activeLayer === 'both' ? 'processing' : 'default'}
          style={{ cursor: 'pointer', padding: '4px 12px', fontSize: 13, borderRadius: 12 }}
          onClick={() => setActiveLayer('both')}
        >
          全维对比
        </Tag>
        <Tag
          color={activeLayer === 'evalAgent' ? 'blue' : 'default'}
          style={{ cursor: 'pointer', padding: '4px 12px', fontSize: 13, borderRadius: 12 }}
          onClick={() => setActiveLayer('evalAgent')}
        >
          EvalAgent (95.3分)
        </Tag>
        <Tag
          color={activeLayer === 'traditional' ? 'warning' : 'default'}
          style={{ cursor: 'pointer', padding: '4px 12px', fontSize: 13, borderRadius: 12 }}
          onClick={() => setActiveLayer('traditional')}
        >
          传统开源库 (39.2分)
        </Tag>
      </div>

      <div style={{ position: 'relative', width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          <defs>
            <linearGradient id="evalAgentGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.45" />
              <stop offset="100%" stopColor="#818cf8" stopOpacity="0.2" />
            </linearGradient>
            <linearGradient id="traditionalGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#ef4444" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#f59e0b" stopOpacity="0.1" />
            </linearGradient>
          </defs>

          {/* Concentric Web Polygons */}
          {[0.2, 0.4, 0.6, 0.8, 1.0].map((level, lvlIdx) => {
            const levelPoints = Array.from({ length: totalAxes }).map((_, i) => {
              const angle = i * angleStep - Math.PI / 2;
              const x = center + radius * level * Math.cos(angle);
              const y = center + radius * level * Math.sin(angle);
              return `${x},${y}`;
            }).join(' ');

            return (
              <polygon
                key={lvlIdx}
                points={levelPoints}
                fill="none"
                stroke="rgba(255, 255, 255, 0.08)"
                strokeWidth={lvlIdx === 4 ? 1.5 : 1}
                strokeDasharray={lvlIdx < 4 ? '3 3' : undefined}
              />
            );
          })}

          {/* Radial Spokes */}
          {RADAR_DATA.map((_, i) => {
            const angle = i * angleStep - Math.PI / 2;
            const x = center + radius * Math.cos(angle);
            const y = center + radius * Math.sin(angle);
            return (
              <line
                key={i}
                x1={center}
                y1={center}
                x2={x}
                y2={y}
                stroke="rgba(255, 255, 255, 0.12)"
                strokeWidth={1}
              />
            );
          })}

          {/* Traditional Layer */}
          {(activeLayer === 'both' || activeLayer === 'traditional') && (
            <polygon
              points={getPoints('traditional')}
              fill="url(#traditionalGrad)"
              stroke="#f87171"
              strokeWidth={2}
              strokeDasharray="4 4"
            />
          )}

          {/* EvalAgent Layer */}
          {(activeLayer === 'both' || activeLayer === 'evalAgent') && (
            <polygon
              points={getPoints('evalAgent')}
              fill="url(#evalAgentGrad)"
              stroke="#38bdf8"
              strokeWidth={2.5}
            />
          )}

          {/* Vertex Points & Labels */}
          {RADAR_DATA.map((item, i) => {
            const angle = i * angleStep - Math.PI / 2;
            // Coordinates for evalAgent point
            const ax = center + radius * (item.evalAgent / 100) * Math.cos(angle);
            const ay = center + radius * (item.evalAgent / 100) * Math.sin(angle);

            // Coordinates for outer label
            const lx = center + (radius + 28) * Math.cos(angle);
            const ly = center + (radius + 24) * Math.sin(angle);

            const isHovered = hoveredAxis === i;

            return (
              <g
                key={i}
                onMouseEnter={() => setHoveredAxis(i)}
                onMouseLeave={() => setHoveredAxis(null)}
                style={{ cursor: 'pointer' }}
              >
                {/* Vertex dot */}
                {(activeLayer === 'both' || activeLayer === 'evalAgent') && (
                  <circle
                    cx={ax}
                    cy={ay}
                    r={isHovered ? 6 : 4}
                    fill="#38bdf8"
                    stroke="#ffffff"
                    strokeWidth={1.5}
                  />
                )}
                <text
                  x={lx}
                  y={ly}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fontSize={isHovered ? 12 : 11}
                  fontWeight={isHovered ? 700 : 500}
                  fill={isHovered ? '#38bdf8' : '#cbd5e1'}
                >
                  {item.label}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {/* Interactive Tooltip Card */}
      <div
        style={{
          marginTop: 12,
          padding: '12px 16px',
          borderRadius: 10,
          background: 'rgba(255, 255, 255, 0.05)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          fontSize: 13,
          color: '#cbd5e1',
          maxWidth: 380,
          textAlign: 'center',
          minHeight: 48,
        }}
      >
        {hoveredAxis !== null ? (
          <div>
            <strong style={{ color: '#38bdf8' }}>{RADAR_DATA[hoveredAxis].label}</strong>:
            <span style={{ marginLeft: 6 }}>{RADAR_DATA[hoveredAxis].desc}</span>
            <div style={{ marginTop: 4, fontSize: 12, color: '#94a3b8' }}>
              EvalAgent: <span style={{ color: '#38bdf8', fontWeight: 600 }}>{RADAR_DATA[hoveredAxis].evalAgent}%</span>
              {' vs '}
              开源库: <span style={{ color: '#f87171' }}>{RADAR_DATA[hoveredAxis].traditional}%</span>
            </div>
          </div>
        ) : (
          <span style={{ color: '#94a3b8' }}>💡 悬停各雷达顶点，查看具体能力维度释义与打分对比</span>
        )}
      </div>
    </div>
  );
};

export default LandingRadarChart;
