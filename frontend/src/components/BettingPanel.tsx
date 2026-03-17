'use client';

import { useState } from 'react';
import { OPTION_COLORS } from '@/lib/constants';
import type { Debate, Bet } from '@/lib/types';

interface Props {
  debate: Debate;
  onBet?: (option: string, amount: number) => void;
}

export default function BettingPanel({ debate, onBet }: Props) {
  const [selectedOption, setSelectedOption] = useState<number | null>(null);
  const [betAmount, setBetAmount] = useState(50);

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
  const potentialProfit = selectedStat ? Math.round(betAmount * (100 / selectedStat.price - 1)) : 0;

  return (
    <div className="bg-white rounded-xl border border-[#EBEBEB] overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[#F0F0F0] bg-[#FAFAFA]">
        <h3 className="text-sm font-semibold text-[#1A1A1A]">
          {isFinished ? '结算完成' : '观点交易台'}
        </h3>
        {!isFinished && (
          <p className="text-[11px] text-[#8590A6] mt-0.5">
            选中一个观点，用积分为你的判断买单
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
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm text-[#646464]">下注金额</span>
              <span className="text-lg font-bold text-[#1A1A1A]">{betAmount} 积分</span>
            </div>

            {/* Slider */}
            <input
              type="range"
              min={10}
              max={200}
              step={10}
              value={betAmount}
              onChange={(e) => setBetAmount(Number(e.target.value))}
              className="w-full h-2 bg-[#EBEBEB] rounded-full appearance-none cursor-pointer accent-[#0066FF]"
            />

            <div className="flex justify-between text-[10px] text-[#C8C8C8] mt-1">
              <span>10</span>
              <span>200</span>
            </div>

            {/* Payout preview */}
            <div className="mt-3 flex items-center justify-between text-sm">
              <span className="text-[#8590A6]">预计利润</span>
              <span className="text-[#00C853] font-bold text-lg">+{potentialProfit} 积分</span>
            </div>
          </div>

          {/* Confirm button */}
          <button
            onClick={() => onBet?.(debate.options[selectedOption], betAmount)}
            className="w-full py-3 bg-[#0066FF] text-white font-semibold rounded-xl hover:bg-[#0052CC] transition-all active:scale-[0.98]"
          >
            买入「{selectedStat?.name}」· {betAmount} 积分
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
