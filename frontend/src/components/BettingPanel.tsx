'use client';

import { useState } from 'react';
import { OPTION_COLORS } from '@/lib/constants';
import type { Debate, Bet } from '@/lib/types';

interface Props {
  debate: Debate;
  wallet?: { balance: number; user_id: string } | null;
  onBuyShares?: (optionKey: string, quantity: number) => Promise<void>;
}

export default function BettingPanel({ debate, wallet, onBuyShares }: Props) {
  const [selectedOption, setSelectedOption] = useState<number | null>(null);
  const [buying, setBuying] = useState(false);
  const quantity = 1;

  const isFinished = debate.status === 'finished';
  const totalBet = debate.bets.reduce((sum, b) => sum + b.amount, 0);

  const optionStats = debate.options.map((opt, i) => {
    const optBets = debate.bets.filter((b) => b.option === opt);
    const optTotal = optBets.reduce((sum, b) => sum + b.amount, 0);
    const optKey = `option_${i}`;
    const backendPrices = debate.option_prices || {};
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
      color: isWinner ? '#00C853' : OPTION_COLORS[i % OPTION_COLORS.length],
    };
  });

  const selectedStat = selectedOption !== null ? optionStats[selectedOption] : null;

  return (
    <div className="bg-white rounded-xl border border-[#EBEBEB] overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[#F0F0F0] bg-[#FAFAFA]">
        <h3 className="text-sm font-semibold text-[#1A1A1A]">
          {isFinished ? '结算完成' : '买入观点 · 派出分身'}
        </h3>
        {!isFinished && (
          <p className="text-[11px] text-[#8590A6] mt-0.5">
            选中观点 → 买入 → 你的 AI 分身自动参战
          </p>
        )}
      </div>

      {/* Options */}
      <div className="p-4 space-y-2">
        {optionStats.map((opt, i) => (
          <button
            key={i}
            onClick={() => !isFinished && setSelectedOption(selectedOption === i ? null : i)}
            disabled={isFinished}
            className={`w-full relative rounded-xl overflow-hidden transition-all duration-300 text-left ${
              isFinished
                ? opt.isWinner
                  ? 'ring-2 ring-[#00C853] bg-[#F1FFF6]'
                  : 'opacity-50 bg-[#FAFAFA]'
                : selectedOption === i
                  ? 'ring-2 ring-[#0066FF] bg-[#E8F0FE] shadow-md'
                  : 'bg-[#F8F9FA] hover:bg-[#F0F2F5] hover:shadow-sm cursor-pointer'
            }`}
          >
            {/* Price bar background */}
            <div
              className="prob-bar absolute inset-0"
              style={{
                width: `${Math.max(opt.price, 5)}%`,
                backgroundColor: opt.color,
                opacity: selectedOption === i ? 0.15 : 0.08,
              }}
            />

            <div className="relative px-4 py-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                {opt.isWinner && (
                  <span className="w-6 h-6 rounded-full bg-[#00C853] text-white flex items-center justify-center text-xs font-bold">✓</span>
                )}
                {opt.isLoser && (
                  <span className="w-6 h-6 rounded-full bg-[#E0E0E0] text-[#999] flex items-center justify-center text-xs">✗</span>
                )}
                <span className={`text-[16px] font-semibold ${
                  opt.isWinner ? 'text-[#00C853]' : opt.isLoser ? 'text-[#999]' : 'text-[#1A1A1A]'
                }`}>
                  {opt.name}
                </span>
              </div>

              <div className="text-right">
                <span className="text-2xl font-bold tabular-nums" style={{ color: opt.color }}>
                  {opt.price}分
                </span>
                {!isFinished && (
                  <span className="block text-[10px] text-[#8590A6]">
                    赢得 {100 - opt.price} 积分利润
                  </span>
                )}
              </div>
            </div>
          </button>
        ))}
      </div>

      {/* Bet form - shown when option selected */}
      {selectedOption !== null && !isFinished && (
        <div className="px-4 pb-4 space-y-3 animate-slide-down">
          <div className="bg-[#F8F9FA] rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-[#646464]">买入价</span>
              <span className="text-lg font-bold text-[#1A1A1A]">{selectedStat?.price} 积分</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-[#8590A6]">预计利润</span>
              <span className="text-[#00C853] font-bold text-lg">+{100 - (selectedStat?.price || 0)} 积分</span>
            </div>
            {wallet && (
              <div className="mt-2 pt-2 border-t border-[#EBEBEB] flex items-center justify-between text-xs text-[#8590A6]">
                <span>可用余额</span>
                <span className="tabular-nums">{wallet.balance} 积分</span>
              </div>
            )}
          </div>

          <button
            onClick={async () => {
              if (!onBuyShares || !selectedStat) return;
              setBuying(true);
              try {
                const optionKey = `option_${selectedOption}`;
                await onBuyShares(optionKey, 1);
              } catch (err: unknown) {
                alert(err instanceof Error ? err.message : '买入失败');
              } finally {
                setBuying(false);
              }
            }}
            disabled={buying || !!(wallet && wallet.balance < (selectedStat?.price || 0))}
            className="w-full py-3 bg-[#0066FF] text-white font-semibold rounded-xl hover:bg-[#0052CC] disabled:opacity-50 disabled:cursor-not-allowed transition-all active:scale-[0.98]"
          >
            {buying ? '买入中...' : wallet && wallet.balance < (selectedStat?.price || 0) ? '余额不足' : `参战 · 买入「${selectedStat?.name}」`}
          </button>
        </div>
      )}

      {/* Pool stats */}
      {totalBet > 0 && (
        <div className="px-4 py-3 border-t border-[#F0F0F0] bg-[#FAFAFA] flex items-center justify-between text-xs text-[#8590A6]">
          <span>{debate.bets.length} 个 Agent · 总池 {totalBet.toLocaleString()} 分</span>
          {isFinished && debate.judgment?.mvp && (
            <span className="text-[#FF6D00] font-medium">MVP: {debate.judgment.mvp}</span>
          )}
        </div>
      )}
    </div>
  );
}
