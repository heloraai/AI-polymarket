'use client';

import Link from 'next/link';
import { getAgent, OPTION_COLORS } from '@/lib/constants';
import type { Debate } from '@/lib/types';

export default function DebateCard({ debate }: { debate: Debate }) {
  const isFinished = debate.status === 'finished';
  const hasBets = debate.bets.length > 0;
  const totalBet = debate.bets.reduce((sum, b) => sum + b.amount, 0);

  const backendPrices = debate.option_prices || {};
  const optionStats = debate.options.map((opt, i) => {
    const optBets = debate.bets.filter((b) => b.option === opt);
    const optTotal = optBets.reduce((sum, b) => sum + b.amount, 0);
    const optKey = `option_${i}`;
    const price = backendPrices[optKey]
      ?? (totalBet > 0 ? Math.round((optTotal / totalBet) * 100) : Math.round(100 / debate.options.length));
    const isWinner = debate.result === opt;
    return {
      name: opt,
      bets: optBets,
      total: optTotal,
      price,
      isWinner,
      isLoser: isFinished && !isWinner,
      color: isWinner ? '#00C853' : isFinished && !isWinner ? '#999' : OPTION_COLORS[i % OPTION_COLORS.length],
    };
  });

  return (
    <div className="block">
      <div className={`bg-white rounded-xl overflow-hidden border transition-all duration-300 ${
        isFinished ? 'border-[#E0E0E0]' : 'border-[#EBEBEB] hover:shadow-md hover:border-[#D0D0D0]'
      }`}>
        {/* Header */}
        <div className="p-4 md:p-5 pb-3">
          <div className="flex items-start gap-3">
            <div className="flex-1 min-w-0">
              <Link href={`/debate/${debate.id}`}>
                <h3 className="text-[16px] md:text-[17px] font-semibold text-[#1A1A1A] leading-relaxed hover:text-[#0066FF] transition-colors">
                  {debate.title}
                </h3>
              </Link>
              {debate.description && (
                <p className="text-[13px] text-[#8590A6] mt-0.5 truncate">{debate.description}</p>
              )}
            </div>

            {/* Status badge */}
            {isFinished ? (
              <span className="shrink-0 flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-full bg-[#E8F5E9] text-[#2E7D32]">
                ✓ 已结算
              </span>
            ) : debate.status === 'running' ? (
              <span className="shrink-0 flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-full bg-[#FFF3E0] text-[#E65100]">
                <span className="w-1.5 h-1.5 rounded-full bg-[#E65100] animate-pulse" />
                交易中
              </span>
            ) : (
              <span className="shrink-0 px-2.5 py-1 text-xs rounded-full bg-[#E8F0FE] text-[#0066FF]">
                可买入
              </span>
            )}
          </div>
        </div>

        {/* Polymarket-style option rows */}
        <div className="px-4 md:px-5 pb-4 space-y-1.5">
          {optionStats.map((opt, i) => (
            <div
              key={i}
              className={`relative rounded-lg overflow-hidden transition-all duration-300 ${
                opt.isWinner ? 'ring-1 ring-[#00C853]/40 bg-[#F1FFF6]'
                : opt.isLoser ? 'opacity-60 bg-[#FAFAFA]'
                : 'bg-[#F8F9FA]'
              }`}
            >
              {hasBets && (
                <div className="prob-bar absolute inset-0 rounded-lg" style={{
                  width: `${Math.max(opt.price, 3)}%`,
                  backgroundColor: opt.color,
                  opacity: opt.isWinner ? 0.12 : opt.isLoser ? 0.05 : 0.08,
                }} />
              )}

              <div className="relative px-3 md:px-4 py-2.5 md:py-3 flex items-center justify-between">
                <div className="flex items-center gap-2 min-w-0">
                  {opt.isWinner && <span className="shrink-0 w-5 h-5 rounded-full bg-[#00C853] text-white flex items-center justify-center text-[10px] font-bold">✓</span>}
                  {opt.isLoser && <span className="shrink-0 w-5 h-5 rounded-full bg-[#E0E0E0] text-[#999] flex items-center justify-center text-[10px]">✗</span>}
                  <span className={`text-[14px] md:text-[15px] font-medium truncate ${
                    opt.isWinner ? 'text-[#00C853]' : opt.isLoser ? 'text-[#999]' : 'text-[#1A1A1A]'
                  }`}>{opt.name}</span>
                </div>

                <div className="flex items-center gap-2 md:gap-3 shrink-0">
                  {/* Agent avatar stack */}
                  {opt.bets.length > 0 && (
                    <div className="hidden sm:flex items-center -space-x-1.5">
                      {opt.bets.slice(0, 3).map((bet) => {
                        const agent = getAgent(bet.agentName);
                        return (
                          <span key={bet.id} className="w-6 h-6 rounded-full flex items-center justify-center text-xs border-2 border-white shadow-sm" style={{ backgroundColor: agent.bg }}>
                            {agent.emoji}
                          </span>
                        );
                      })}
                    </div>
                  )}
                  <span className="text-lg md:text-xl font-bold tabular-nums" style={{ color: opt.color }}>{opt.price}分</span>
                </div>
              </div>
            </div>
          ))}

          {/* Footer stats */}
          {totalBet > 0 && (
            <div className="flex items-center justify-between pt-1 px-1">
              <span className="text-[11px] text-[#C8C8C8]">{debate.bets.length} 个 Agent · 总池 {totalBet.toLocaleString()} 分</span>
              {isFinished && debate.judgment?.mvp && (
                <span className="text-[11px] text-[#FF6D00] font-medium">MVP: {debate.judgment.mvp}</span>
              )}
            </div>
          )}
        </div>

        {/* Action bar */}
        <div className="px-4 md:px-5 py-2.5 border-t border-[#F0F0F0] bg-[#FAFAFA] flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs text-[#8590A6]">
            {debate.transcript.length > 0 && <span>{debate.transcript.length} 条发言</span>}
            {debate.transcript.length > 0 && hasBets && <span>·</span>}
            {hasBets && <span>{debate.bets.length} 笔下注</span>}
          </div>
          <div className="flex items-center gap-2">
            {debate.status === 'created' && (
              <button
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  fetch(`/api/debates/${debate.id}/run`, { method: 'POST' })
                    .then(() => window.location.reload())
                    .catch(() => alert('启动失败'));
                }}
                className="px-3 py-1.5 bg-[#0066FF] text-white text-xs font-medium rounded-full hover:bg-[#0052CC] transition-all active:scale-95"
              >
                ⚔️ 开始辩论
              </button>
            )}
            <Link href={`/debate/${debate.id}`} className="text-xs text-[#0066FF] font-medium hover:underline">
              查看详情 →
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
