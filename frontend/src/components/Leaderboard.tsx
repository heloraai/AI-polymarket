'use client';

import { useEffect, useState } from 'react';
import { AGENT_COLORS, DEFAULT_ROSTER } from '@/lib/constants';

interface AgentStats {
  name: string;
  emoji: string;
  description: string;
  total_profit: number;
  wins: number;
  losses: number;
  total_bets: number;
  total_wagered: number;
  win_rate: number;
}

export default function Leaderboard() {
  const [agents, setAgents] = useState<AgentStats[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    fetch('/api/leaderboard')
      .then((r) => r.json())
      .then((d) => {
        setAgents(d.leaderboard || []);
        setLoaded(true);
      })
      .catch(() => setLoaded(true));
  }, []);

  const hasData = agents.length > 0;

  return (
    <div className="bg-white rounded-lg border border-[#EBEBEB] p-4">
      <h3 className="text-sm font-semibold text-[#1A1A1A] mb-3">
        {hasData ? '积分排行榜' : '常驻选手'}
      </h3>

      {!loaded ? (
        <div className="text-xs text-[#C8C8C8] py-4 text-center">加载中...</div>
      ) : hasData ? (
        /* Leaderboard with stats */
        <div className="space-y-1">
          {agents.map((agent, i) => {
            const color = AGENT_COLORS[agent.name] || '#666';
            const isPositive = agent.total_profit > 0;
            const isNegative = agent.total_profit < 0;
            return (
              <div
                key={agent.name}
                className={`flex items-center gap-2.5 p-2 rounded-md transition-colors ${
                  i === 0 ? 'bg-[#FFF8E1]' : 'hover:bg-[#FAFAFA]'
                }`}
              >
                {/* Rank */}
                <span className={`w-5 h-5 flex items-center justify-center rounded text-xs font-bold ${
                  i === 0 ? 'bg-[#FFD600] text-white' :
                  i === 1 ? 'bg-[#BDBDBD] text-white' :
                  i === 2 ? 'bg-[#A1887F] text-white' :
                  'bg-transparent text-[#C8C8C8]'
                }`}>
                  {i + 1}
                </span>

                {/* Avatar */}
                <span className="text-lg">{agent.emoji}</span>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1">
                    <span className="text-sm font-medium" style={{ color }}>
                      {agent.name.replace(/^[^\u4e00-\u9fff]+/, '')}
                    </span>
                    <span className="text-[10px] text-[#C8C8C8]">
                      {agent.wins}胜{agent.losses}负
                    </span>
                  </div>
                  {/* Win rate bar */}
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <div className="flex-1 h-1 bg-[#F0F0F0] rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${agent.win_rate}%`,
                          backgroundColor: color,
                          opacity: 0.6,
                        }}
                      />
                    </div>
                    <span className="text-[10px] text-[#8590A6]">{agent.win_rate}%</span>
                  </div>
                </div>

                {/* Profit */}
                <span className={`text-sm font-bold tabular-nums ${
                  isPositive ? 'text-[#00C853]' :
                  isNegative ? 'text-[#FF1744]' :
                  'text-[#8590A6]'
                }`}>
                  {isPositive ? '+' : ''}{agent.total_profit}
                </span>
              </div>
            );
          })}
        </div>
      ) : (
        /* Default roster - no data yet */
        <div className="space-y-2.5">
          {DEFAULT_ROSTER.map((a) => (
            <div key={a.name} className="flex items-center gap-2">
              <span className="text-lg">{a.emoji}</span>
              <div>
                <span className="text-sm font-medium" style={{ color: a.color }}>{a.name}</span>
                <p className="text-xs text-[#8590A6]">{a.desc}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Judge - always shown */}
      <div className="mt-3 pt-3 border-t border-[#EBEBEB]">
        <div className="flex items-center gap-2">
          <img src="/liu-kanshan.png" alt="刘看山" className="w-8 h-8 rounded-full" />
          <div>
            <span className="text-sm font-medium text-[#37474F]">刘看山</span>
            <span className="ml-1 text-xs bg-[#37474F] text-white px-1 py-0.5 rounded">裁判</span>
            <p className="text-xs text-[#8590A6]">公正裁决，一锤定音</p>
          </div>
        </div>
      </div>
    </div>
  );
}
