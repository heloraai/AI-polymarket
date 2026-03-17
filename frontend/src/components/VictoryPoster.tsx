'use client';

import { useRef, useState } from 'react';
import { getAgent } from '@/lib/constants';
import type { Debate } from '@/lib/types';

interface Props {
  debate: Debate;
  onClose: () => void;
}

export default function VictoryPoster({ debate, onClose }: Props) {
  const posterRef = useRef<HTMLDivElement>(null);
  const [copied, setCopied] = useState(false);

  if (!debate.judgment) return null;

  const winner = debate.result;
  const mvp = debate.judgment.mvp;
  const totalPool = debate.judgment.total_pool || 0;
  const payouts = debate.judgment.payouts || {};

  // Sort agents by profit
  const sortedAgents = Object.entries(payouts)
    .map(([name, p]) => ({ name, ...p }))
    .sort((a, b) => b.profit - a.profit);

  const handleShare = async () => {
    // Try to use native share if available
    if (navigator.share) {
      try {
        await navigator.share({
          title: `观点交易所 · ${debate.title}`,
          text: `「${winner}」观点胜出！MVP: ${mvp}。总池 ${totalPool} 积分。来观点交易所，为你的观点下注！`,
          url: window.location.href,
        });
      } catch {
        // User cancelled or not supported
      }
    } else {
      // Fallback: copy link
      await navigator.clipboard.writeText(
        `【观点交易所】${debate.title}\n🏆 胜出观点：${winner}\n⭐ MVP：${mvp}\n💰 总池：${totalPool} 积分\n\n🌊 获胜论点已出圈到知乎！\n\n来观点交易所，为你的观点下注 👉 ${window.location.href}`
      );
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="fixed inset-0 z-[200] bg-black/60 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="relative max-w-sm w-full"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Poster card */}
        <div
          ref={posterRef}
          className="bg-gradient-to-br from-[#1A1A2E] via-[#16213E] to-[#0F3460] rounded-2xl overflow-hidden shadow-2xl"
        >
          {/* Header */}
          <div className="px-6 pt-6 pb-4">
            <div className="flex items-center gap-2 mb-1">
              <img src="/liu-kanshan.png" alt="刘看山" className="w-6 h-6 rounded-full" />
              <span className="text-white/60 text-xs font-medium tracking-wider uppercase">观点交易所 · 结算报告</span>
            </div>
            <h2 className="text-white text-lg font-bold leading-snug mt-2">
              {debate.title.length > 40 ? debate.title.slice(0, 40) + '...' : debate.title}
            </h2>
          </div>

          {/* Winner banner */}
          <div className="mx-6 mb-4 bg-gradient-to-r from-[#00C853]/20 to-[#00C853]/5 border border-[#00C853]/30 rounded-xl px-4 py-3">
            <div className="text-[#00C853] text-xs font-medium mb-1">🏆 胜出观点</div>
            <div className="text-white text-xl font-bold">{winner}</div>
          </div>

          {/* Settlement table */}
          <div className="mx-6 mb-4">
            <div className="text-white/40 text-[10px] font-medium uppercase tracking-wider mb-2">结算明细</div>
            <div className="space-y-1.5">
              {sortedAgents.map((agent, i) => {
                const agentInfo = getAgent(agent.name);
                const isWin = agent.result === 'win';
                return (
                  <div key={agent.name} className="flex items-center justify-between py-1.5 px-3 rounded-lg bg-white/5">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-white/30 w-4">{i + 1}</span>
                      <span className="text-base">{agentInfo.emoji}</span>
                      <span className="text-white text-sm">{agent.name}</span>
                      {agent.name === mvp && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#FF6D00]/20 text-[#FF6D00]">MVP</span>
                      )}
                    </div>
                    <span className={`text-sm font-bold tabular-nums ${isWin ? 'text-[#00C853]' : 'text-[#FF1744]'}`}>
                      {isWin ? '+' : ''}{agent.profit}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Stats row */}
          <div className="mx-6 mb-4 flex items-center justify-between">
            <div className="text-center">
              <div className="text-white text-lg font-bold">{totalPool}</div>
              <div className="text-white/40 text-[10px]">总池积分</div>
            </div>
            <div className="text-center">
              <div className="text-white text-lg font-bold">{debate.bets.length}</div>
              <div className="text-white/40 text-[10px]">参与交易员</div>
            </div>
            <div className="text-center">
              <div className="text-white text-lg font-bold">{debate.transcript.length}</div>
              <div className="text-white/40 text-[10px]">辩论发言</div>
            </div>
          </div>

          {/* 观点出圈 status */}
          <div className="mx-6 mb-4 bg-gradient-to-r from-[#0066FF]/10 to-[#0066FF]/5 border border-[#0066FF]/20 rounded-xl px-4 py-3">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-base">🌊</span>
              <span className="text-white/90 text-sm font-medium">观点已出圈</span>
            </div>
            <p className="text-white/60 text-xs leading-relaxed">
              获胜论点已自动发布到知乎圈子，真实用户正在看到你的观点
            </p>
          </div>

          {/* Footer */}
          <div className="bg-white/5 px-6 py-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <img src="/liu-kanshan.png" alt="" className="w-4 h-4 rounded-full" />
              <span className="text-white/40 text-[10px]">观点交易所 — 观点有价，下注见真章</span>
            </div>
            <span className="text-white/20 text-[10px]">知乎 × SecondMe</span>
          </div>
        </div>

        {/* Action buttons */}
        <div className="mt-4 flex gap-3">
          <button
            onClick={handleShare}
            className="flex-1 py-3 bg-[#07C160] text-white font-semibold rounded-xl hover:bg-[#06AD56] transition-all active:scale-[0.98] flex items-center justify-center gap-2"
          >
            {copied ? '✓ 已复制' : '分享到微信'}
          </button>
          <button
            onClick={onClose}
            className="px-6 py-3 bg-white/10 text-white rounded-xl hover:bg-white/20 transition-all"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  );
}
